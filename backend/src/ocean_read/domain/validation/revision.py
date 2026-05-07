"""Revision labels for immutable schema versions — suggest next label without user inventing versions."""

from __future__ import annotations

from typing import Sequence


def suggest_next_version_label(existing_labels: Sequence[str]) -> str:
    """Return the next revision string for a schema key.

    - If no versions exist → ``1.0``.
    - If existing labels match ``major.minor`` (digits) → bump **minor** on the lexicographically greatest pair.
    - Otherwise → ``rev-{n}`` where *n* increases with how many labels we saw.
    """

    labels = [x.strip() for x in existing_labels if x and x.strip()]
    if not labels:
        return "1.0"

    pairs: list[tuple[int, int]] = []
    for L in labels:
        parts = L.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            pairs.append((int(parts[0]), int(parts[1])))

    if pairs:
        major, minor = max(pairs, key=lambda t: (t[0], t[1]))
        return f"{major}.{minor + 1}"

    return f"rev-{len(labels) + 1}"
