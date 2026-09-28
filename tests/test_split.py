import pytest

from shortify.video.split import CoverageReport, compute_parts


def test_even_split_exact_multiples():
    parts = compute_parts(120.0, 30.0)
    assert [p.duration for p in parts] == [30.0, 30.0, 30.0, 30.0]
    assert parts[0].start == 0.0
    assert parts[-1].end == 120.0


def test_uneven_split_last_part_shorter():
    parts = compute_parts(100.0, 45.0)
    # 0-45, 45-90, 90-100
    assert len(parts) == 3
    assert parts[-1].start == 90.0
    assert parts[-1].end == 100.0
    assert parts[-1].duration == pytest.approx(10.0)


def test_no_gaps_or_overlaps_for_arbitrary_durations():
    for total, part_len in [(3600.0, 45.0), (61.3, 12.0), (7.0, 60.0), (0.5, 1.0)]:
        parts = compute_parts(total, part_len)
        prev_end = 0.0
        for p in parts:
            assert p.start == pytest.approx(prev_end)
            assert p.end <= total + 1e-6
            prev_end = p.end
        if parts:
            assert prev_end == pytest.approx(total)


def test_tiny_remainder_merged_into_previous_part():
    # 100s / 33s => 33,33,33,1 -- the trailing 1s should be merged in.
    parts = compute_parts(100.0, 33.0, min_last_part=2.0)
    assert parts[-1].duration > 2.0
    # Still covers the whole timeline with no gaps.
    assert parts[-1].end == pytest.approx(100.0)


def test_trim_start_and_end_reduce_usable_timeline():
    parts = compute_parts(100.0, 30.0, trim_start=10.0, trim_end=10.0)
    assert parts[0].start == pytest.approx(10.0)
    assert parts[-1].end == pytest.approx(90.0)


def test_zero_duration_source_returns_no_parts():
    assert compute_parts(0.0, 30.0) == []


def test_invalid_part_duration_raises():
    with pytest.raises(ValueError):
        compute_parts(100.0, 0.0)


def test_coverage_report_perfect_coverage():
    parts = compute_parts(90.0, 30.0)
    report = CoverageReport(90.0, parts)
    d = report.to_dict()
    assert d["coverage_percentage"] == 100.0
    assert d["gap_count"] == 0
    assert d["overlap_count"] == 0
    assert d["discarded_duration"] == 0.0


def test_coverage_report_detects_gap():
    parts = compute_parts(90.0, 30.0)
    # Introduce an artificial gap by dropping the middle part.
    parts_with_gap = [parts[0], parts[2]]
    report = CoverageReport(90.0, parts_with_gap)
    assert report.gap_count == 1


def test_coverage_report_detects_overlap():
    parts = compute_parts(90.0, 30.0)
    parts[1].start = parts[0].end - 5.0  # force overlap
    report = CoverageReport(90.0, parts)
    assert report.overlap_count == 1
