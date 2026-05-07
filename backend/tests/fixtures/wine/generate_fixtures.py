#!/usr/bin/env python3
"""Build M1 wine validation corpus: ``clean/``, ``noisy/``, ``corpus_index.json``, per-row JSON.

Run manually after changing cases or schema::

    python backend/tests/fixtures/wine/generate_fixtures.py

Requires PyMuPDF and the UCI ``winequality-red.csv`` at ``<repo>/data/winequality-red.csv``.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _here() -> Path:
    return Path(__file__).resolve().parent


def _read_red_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader)


def _lab_report_text(*, ph: float, alcohol: float, quality: int, omit_quality: bool, noise_extra: str = "") -> str:
    lines = [
        "Wine QA Report (UCI red wine)",
        "SECTION HEADER",
        f"pH: {ph}",
        f"Alcohol: {alcohol}%",
    ]
    if not omit_quality:
        lines.append(f"Quality: {quality}")
    body = "\n".join(lines)
    if noise_extra:
        return body + "\n" + noise_extra
    return body


def _noise_lines() -> str:
    # Unrelated numeric lines — must not become ph/alcohol/quality candidates via regex.
    return "\n".join(
        [
            "Noise line A: batch temperature 22.7 C",
            "Noise line B: tank pressure 1.03 bar",
            "Noise line C: serial 884422",
        ]
    )


def _build_pdf(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72.0
    for line in text.splitlines():
        page.insert_text((72.0, y), line)
        y += 18.0
    out = doc.tobytes()
    doc.close()
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None, help="Override winequality-red.csv path")
    args = parser.parse_args()

    root = _repo_root()
    csv_path = args.csv or (root / "data" / "winequality-red.csv")
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = _read_red_rows(csv_path)
    if len(rows) < 10:
        raise SystemExit("CSV has too few rows")

    base = _here()
    clean_dir = base / "clean"
    noisy_dir = base / "noisy"
    clean_dir.mkdir(parents=True, exist_ok=True)
    noisy_dir.mkdir(parents=True, exist_ok=True)

    specs: list[dict[str, object]] = []

    def add_case(
        idx: int,
        *,
        csv_i: int,
        status: str,
        errors: list[dict[str, str]],
        ph: float,
        alcohol: float,
        quality: int | None,
        omit_quality: bool,
        noise: bool = True,
    ) -> None:
        tag = f"{idx:03d}"
        truth: dict[str, float | int] = {"ph": ph, "alcohol": alcohol}
        if not omit_quality and quality is not None:
            truth["quality"] = quality
        text_clean = _lab_report_text(ph=ph, alcohol=alcohol, quality=int(quality or 0), omit_quality=omit_quality)
        text_noisy = _lab_report_text(
            ph=ph,
            alcohol=alcohol,
            quality=int(quality or 0),
            omit_quality=omit_quality,
            noise_extra=_noise_lines(),
        )
        (clean_dir / f"row_{tag}_clean.pdf").write_bytes(_build_pdf(text_clean))
        (clean_dir / f"row_{tag}_clean.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        if noise:
            (noisy_dir / f"row_{tag}_noisy.pdf").write_bytes(_build_pdf(text_noisy))
            (noisy_dir / f"row_{tag}_noisy.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        specs.append(
            {
                "id": f"row_{tag}",
                "csv_row_index": csv_i,
                "clean_pdf": f"clean/row_{tag}_clean.pdf",
                "clean_truth": f"clean/row_{tag}_clean.json",
                "noisy_pdf": f"noisy/row_{tag}_noisy.pdf" if noise else None,
                "noisy_truth": f"noisy/row_{tag}_noisy.json" if noise else None,
                "expected_status": status,
                "expected_errors": errors,
            }
        )

    # PASS rows 000–004
    for i in range(5):
        r = rows[i]
        add_case(
            i,
            csv_i=i,
            status="PASS",
            errors=[],
            ph=float(r["pH"]),
            alcohol=float(r["alcohol"]),
            quality=int(float(r["quality"])),
            omit_quality=False,
        )

    # FAIL alcohol 005–007 (out of [8,15] per schema)
    for j, alc in enumerate([18.0, 17.2, 22.5]):
        idx = 5 + j
        r = rows[idx]
        add_case(
            idx,
            csv_i=idx,
            status="FAIL",
            errors=[{"field": "alcohol", "rule": "range_validation"}],
            ph=float(r["pH"]),
            alcohol=alc,
            quality=int(float(r["quality"])),
            omit_quality=False,
        )

    # FAIL missing quality 008
    r = rows[8]
    add_case(
        8,
        csv_i=8,
        status="FAIL",
        errors=[{"field": "quality", "rule": "required"}],
        ph=float(r["pH"]),
        alcohol=float(r["alcohol"]),
        quality=None,
        omit_quality=True,
    )

    # Boundary PASS: ph at upper inclusive max (4.5), mid alcohol/quality
    add_case(
        9,
        csv_i=9,
        status="PASS",
        errors=[],
        ph=4.5,
        alcohol=12.0,
        quality=7,
        omit_quality=False,
    )

    manifest = {"schema": "schema.json", "rows": specs}
    (base / "corpus_index.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote corpus under {base}")
    print(f"Rows: {len(specs)}")


if __name__ == "__main__":
    main()
