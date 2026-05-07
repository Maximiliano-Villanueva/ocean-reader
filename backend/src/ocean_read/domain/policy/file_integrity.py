"""Hash helpers for ingestion / deduplication (pure I/O in application layer)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_hex_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """SHA-256 hexdigest of file contents (streaming)."""

    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
