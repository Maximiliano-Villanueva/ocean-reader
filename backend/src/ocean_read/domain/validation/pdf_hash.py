"""SHA-256 fingerprint for uploaded PDF bytes (M2 audit / deduplication key)."""

from __future__ import annotations

import hashlib


def compute_pdf_hash(data: bytes) -> str:
    """Return ``sha256:{hexdigest}`` for the raw PDF bytes."""

    digest = hashlib.sha256(data).hexdigest()
    return f"sha256:{digest}"
