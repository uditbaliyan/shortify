from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Word:
    text: str
    start: float
    end: float
    probability: float | None = None


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    words: list[Word]
