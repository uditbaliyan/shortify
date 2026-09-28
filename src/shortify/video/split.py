"""Compute sequential part boundaries that cover the entire source timeline.

This module is deliberately pure/side-effect-free (no ffmpeg, no I/O) so
splitting logic can be unit tested in isolation.
"""

from __future__ import annotations

from shortify.models.part import Part


def compute_parts(
    total_duration: float,
    part_duration: float,
    *,
    trim_start: float = 0.0,
    trim_end: float = 0.0,
    min_last_part: float = 1.5,
) -> list[Part]:
    """Split ``[trim_start, total_duration - trim_end]`` into sequential parts.

    The entire usable timeline is always covered: there are no gaps and no
    overlaps between consecutive parts, and the final part naturally
    absorbs whatever time remains (it will be shorter than
    ``part_duration`` unless the source divides evenly).

    Args:
        total_duration: Duration of the source media, in seconds.
        part_duration: Target duration of each part, in seconds.
        trim_start: Seconds to skip from the beginning before splitting.
        trim_end: Seconds to skip from the end before splitting.
        min_last_part: If the trailing remainder would be shorter than
            this many seconds, it is merged into the previous part
            instead of becoming its own tiny clip.

    Returns:
        A list of :class:`Part` objects with ``start``/``end`` set,
        ordered and contiguous.
    """
    if part_duration <= 0:
        raise ValueError("part_duration must be > 0")
    if total_duration < 0:
        raise ValueError("total_duration must be >= 0")

    usable_start = max(0.0, trim_start)
    usable_end = max(usable_start, total_duration - max(0.0, trim_end))
    usable_total = usable_end - usable_start

    if usable_total <= 0:
        return []

    parts: list[Part] = []
    cursor = usable_start
    index = 0
    while cursor < usable_end - 1e-9:
        end = min(cursor + part_duration, usable_end)
        remainder = usable_end - end
        # Merge a too-small trailing remainder into this part rather than
        # emitting a near-empty final clip.
        if 0 < remainder < min_last_part:
            end = usable_end
        parts.append(Part(index=index, start=round(cursor, 3), end=round(end, 3)))
        cursor = end
        index += 1

    return parts


class CoverageReport:
    """Coverage statistics comparing generated parts to the source timeline."""

    def __init__(
        self,
        source_duration: float,
        parts: list[Part],
        *,
        trim_start: float = 0.0,
        trim_end: float = 0.0,
    ) -> None:
        self.source_duration = source_duration
        self.parts = sorted(parts, key=lambda p: p.start)
        self.trim_start = trim_start
        self.trim_end = trim_end

    @property
    def covered_duration(self) -> float:
        return round(sum(p.duration for p in self.parts), 3)

    @property
    def discarded_duration(self) -> float:
        return round(
            max(0.0, self.source_duration - self.covered_duration), 3
        )

    @property
    def coverage_percentage(self) -> float:
        if self.source_duration <= 0:
            return 0.0
        return round(100.0 * self.covered_duration / self.source_duration, 2)

    @property
    def gap_count(self) -> int:
        gaps = 0
        prev_end = self.trim_start
        for p in self.parts:
            if p.start - prev_end > 1e-6:
                gaps += 1
            prev_end = p.end
        return gaps

    @property
    def overlap_count(self) -> int:
        overlaps = 0
        prev_end = None
        for p in self.parts:
            if prev_end is not None and p.start < prev_end - 1e-6:
                overlaps += 1
            prev_end = p.end
        return overlaps

    def to_dict(self) -> dict:
        return {
            "source_duration": self.source_duration,
            "covered_duration": self.covered_duration,
            "discarded_duration": self.discarded_duration,
            "coverage_percentage": self.coverage_percentage,
            "gap_count": self.gap_count,
            "overlap_count": self.overlap_count,
            "part_count": len(self.parts),
        }

    def summary(self) -> str:
        from shortify.utils.timefmt import format_timestamp as _fmt

        d = self.to_dict()
        return (
            f"Source duration:    {_fmt(d['source_duration'])}\n"
            f"Generated coverage: {_fmt(d['covered_duration'])}\n"
            f"Discarded:          {_fmt(d['discarded_duration'])}\n"
            f"Coverage:           {d['coverage_percentage']:.2f}%\n"
            f"Gaps:               {d['gap_count']}\n"
            f"Overlaps:           {d['overlap_count']}"
        )
