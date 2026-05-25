"""Tests for deterministic PDF content hashing (M2 audit fingerprint)."""

from __future__ import annotations

from ocean_read.domain.validation.pdf_hash import compute_pdf_hash


def test_compute_pdf_hash_same_bytes_same_digest() -> None:
    """Same PDF bytes always yield the same sha256-prefixed digest."""

    data = b"%PDF-1.4 minimal"
    a = compute_pdf_hash(data)
    b = compute_pdf_hash(data)
    assert a == b
    assert a.startswith("sha256:")
    assert len(a) == 7 + 64


def test_compute_pdf_hash_different_bytes_different_digest() -> None:
    """Different bytes produce different digests."""

    assert compute_pdf_hash(b"a") != compute_pdf_hash(b"b")
