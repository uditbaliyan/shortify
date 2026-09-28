"""Deterministic caching for expensive per-source analysis.

Cache key = hash(source fingerprint + relevant config fields). A second
run with the same source and same relevant settings reuses cached
results instead of re-probing/re-detecting silence, etc.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def fingerprint_file(path: Path, *, chunk_size: int = 1 << 20) -> str:
    """A fast-ish fingerprint of a (potentially large) media file.

    Hashing the whole file is the most correct approach but can be slow
    for very large videos, so this hashes file size + mtime + the first
    and last chunk of bytes, which is enough to detect the vast majority
    of real-world changes while staying fast.
    """
    path = Path(path)
    stat = path.stat()
    h = hashlib.sha256()
    h.update(str(stat.st_size).encode())
    h.update(str(int(stat.st_mtime)).encode())
    with path.open("rb") as f:
        h.update(f.read(chunk_size))
        if stat.st_size > chunk_size:
            f.seek(max(0, stat.st_size - chunk_size))
            h.update(f.read(chunk_size))
    return h.hexdigest()[:16]


def cache_key(source_fingerprint: str, config_fields: dict[str, Any]) -> str:
    payload = json.dumps(
        {"source": source_fingerprint, "config": config_fields}, sort_keys=True
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class Cache:
    """Simple JSON-file cache keyed by a deterministic fingerprint."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str, key: str) -> Path:
        return self.cache_dir / f"{name}.{key}.json"

    def get(self, name: str, key: str) -> Any | None:
        path = self._path(name, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, name: str, key: str, value: Any) -> None:
        path = self._path(name, key)
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
