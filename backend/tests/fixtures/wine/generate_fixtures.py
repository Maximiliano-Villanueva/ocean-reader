#!/usr/bin/env python3
"""Build wine validation corpus: ``clean/``, ``noisy/``, ``fail_schema/``, ``fail_missing/``,
``ambiguous/``, ``corpus_index.json``, and per-row JSON truth files.

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
    """Legacy single-page builder — prefer :func:`_build_rich_pdf_from_lines`."""

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


def _build_rich_pdf_from_lines(lines: list[str], *, noise_extra: str = "") -> bytes:
    """Map legacy line lists to multi-page rich PDFs (lab section preserved)."""

    from rich_pdf_builder import LabValues, build_rich_wine_pdf

    import re

    lab = LabValues()
    extra: list[str] = []
    for line in lines:
        t = line.strip()
        if not t or t.startswith("Wine QA Report"):
            continue
        if t.startswith("SECTION"):
            continue
        m = re.match(r"(?i)p[hH]\s*:\s*([\d.]+)", t)
        if m:
            if lab.ph is not None:
                extra.append(t)
            else:
                lab = LabValues(ph=float(m.group(1)), alcohol=lab.alcohol, quality=lab.quality, omit_quality=lab.omit_quality)
            continue
        m = re.match(r"(?i)alcohol\s*:\s*([\d.]+)", t)
        if m:
            if lab.alcohol is not None:
                extra.append(t)
            else:
                lab = LabValues(ph=lab.ph, alcohol=float(m.group(1)), quality=lab.quality, omit_quality=lab.omit_quality)
            continue
        m = re.match(r"(?i)quality\s*:\s*([\d.]+)", t)
        if m:
            if lab.quality is not None:
                extra.append(t)
            else:
                lab = LabValues(ph=lab.ph, alcohol=lab.alcohol, quality=int(float(m.group(1))), omit_quality=False)
            continue
        if re.search(r"(?i)measured\s+p[hH]|p[hH]\s+level|ph\s+value", t):
            extra.append(t)
            continue
        if "alcohol" in t.lower() and "duplicate" in t.lower():
            extra.append(t)
            continue
        extra.append(t)
    return build_rich_wine_pdf(lab=lab, extra_lab_lines=extra, noise_extra=noise_extra)


def _append_synthetic_corpus(base: Path, specs: list[dict[str, object]]) -> None:
    """Add hand-crafted PDFs not tied to CSV rows: schema violations, missing fields, ambiguity.

    Layout under ``fixtures/wine/``:

    - ``fail_schema/`` — all three fields present in text but at least one violates range.
    - ``fail_missing/`` — document omits one or more required labels so validation fails ``required``.
    - ``ambiguous/`` — conflicting duplicate readings for the same logical field → ``AMBIGUOUS``.
    """

    fail_schema = base / "fail_schema"
    fail_missing = base / "fail_missing"
    ambiguous_dir = base / "ambiguous"
    for d in (fail_schema, fail_missing, ambiguous_dir):
        d.mkdir(parents=True, exist_ok=True)

    def write_case(
        rel_pdf: str,
        lines: list[str],
        *,
        truth: dict[str, float | int],
        row: dict[str, object],
    ) -> None:
        pdf_path = base / rel_pdf
        pdf_path.write_bytes(_build_rich_pdf_from_lines(lines))
        truth_path = base / str(row["clean_truth"])
        truth_path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        specs.append(row)

    header = "Wine QA Report (synthetic)"

    # --- 5× FAIL by schema (values extracted, violate range) ---
    fs: list[tuple[str, list[str], dict[str, float | int], str, list[dict[str, str]]]] = [
        (
            "syn_fs_alcohol_high.pdf",
            [header, "pH: 3.5", "Alcohol: 18%", "Quality: 7"],
            {"ph": 3.5, "alcohol": 18.0, "quality": 7},
            "FAIL",
            [{"field": "alcohol", "rule": "range_validation"}],
        ),
        (
            "syn_fs_ph_high.pdf",
            [header, "pH: 5.0", "Alcohol: 12%", "Quality: 7"],
            {"ph": 5.0, "alcohol": 12.0, "quality": 7},
            "FAIL",
            [{"field": "ph", "rule": "range_validation"}],
        ),
        (
            "syn_fs_quality_high.pdf",
            [header, "pH: 3.4", "Alcohol: 12%", "Quality: 11"],
            {"ph": 3.4, "alcohol": 12.0, "quality": 11},
            "FAIL",
            [{"field": "quality", "rule": "range_validation"}],
        ),
        (
            "syn_fs_alcohol_low.pdf",
            [header, "pH: 3.4", "Alcohol: 7.0%", "Quality: 7"],
            {"ph": 3.4, "alcohol": 7.0, "quality": 7},
            "FAIL",
            [{"field": "alcohol", "rule": "range_validation"}],
        ),
        (
            "syn_fs_ph_low.pdf",
            [header, "pH: 2.4", "Alcohol: 12%", "Quality: 7"],
            {"ph": 2.4, "alcohol": 12.0, "quality": 7},
            "FAIL",
            [{"field": "ph", "rule": "range_validation"}],
        ),
    ]
    for fname, lines, truth, st, errs in fs:
        rid = fname.replace(".pdf", "")
        rel = f"fail_schema/{fname}"
        write_case(
            rel,
            lines,
            truth=truth,
            row={
                "id": rid,
                "csv_row_index": -1,
                "clean_pdf": rel,
                "clean_truth": rel.replace(".pdf", ".json"),
                "noisy_pdf": None,
                "noisy_truth": None,
                "expected_status": st,
                "expected_errors": errs,
            },
        )

    # --- 5× FAIL by missing data in PDF (required fields) ---
    fm: list[tuple[str, list[str], dict[str, float | int], list[dict[str, str]]]] = [
        (
            "syn_fm_no_quality.pdf",
            [header, "pH: 3.5", "Alcohol: 12%"],
            {"ph": 3.5, "alcohol": 12.0},
            [{"field": "quality", "rule": "required"}],
        ),
        (
            "syn_fm_no_ph.pdf",
            [header, "Alcohol: 12%", "Quality: 7"],
            {"alcohol": 12.0, "quality": 7},
            [{"field": "ph", "rule": "required"}],
        ),
        (
            "syn_fm_no_alcohol.pdf",
            [header, "pH: 3.5", "Quality: 7"],
            {"ph": 3.5, "quality": 7},
            [{"field": "alcohol", "rule": "required"}],
        ),
        (
            "syn_fm_only_quality.pdf",
            [header, "Quality: 7"],
            {"quality": 7},
            [
                {"field": "ph", "rule": "required"},
                {"field": "alcohol", "rule": "required"},
            ],
        ),
        (
            "syn_fm_header_only.pdf",
            [header],
            {},
            [
                {"field": "ph", "rule": "required"},
                {"field": "alcohol", "rule": "required"},
                {"field": "quality", "rule": "required"},
            ],
        ),
    ]
    for fname, lines, truth, errs in fm:
        rid = fname.replace(".pdf", "")
        rel = f"fail_missing/{fname}"
        write_case(
            rel,
            lines,
            truth=truth,
            row={
                "id": rid,
                "csv_row_index": -1,
                "clean_pdf": rel,
                "clean_truth": rel.replace(".pdf", ".json"),
                "noisy_pdf": None,
                "noisy_truth": None,
                "expected_status": "FAIL",
                "expected_errors": errs,
            },
        )

    # --- 5× AMBIGUOUS (conflicting extractions for same field) ---
    amb: list[tuple[str, list[str], dict[str, float | int], list[str]]] = [
        (
            "syn_amb_ph_dup.pdf",
            [header, "pH: 3.1", "pH: 4.2", "Alcohol: 12%", "Quality: 7"],
            {"ph": 3.1, "alcohol": 12.0, "quality": 7},
            ["ph"],
        ),
        (
            "syn_amb_alcohol_dup.pdf",
            [header, "pH: 3.5", "Alcohol: 11%", "Alcohol: 13%", "Quality: 7"],
            {"ph": 3.5, "alcohol": 11.0, "quality": 7},
            ["alcohol"],
        ),
        (
            "syn_amb_quality_dup.pdf",
            [header, "pH: 3.5", "Alcohol: 12%", "Quality: 6", "Quality: 8"],
            {"ph": 3.5, "alcohol": 12.0, "quality": 6},
            ["quality"],
        ),
        (
            "syn_amb_ph_triple.pdf",
            [header, "Measured pH: 3.0", "pH level: 3.9", "ph value: 4.1", "Alcohol: 12%", "Quality: 7"],
            {"ph": 3.0, "alcohol": 12.0, "quality": 7},
            ["ph"],
        ),
        (
            "syn_amb_alcohol_regex_vs_layout.pdf",
            [
                header,
                "pH: 3.5",
                "Alcohol: 10%",
                "Also note alcohol measured at 14 on duplicate tank sample",
                "Quality: 7",
            ],
            {"ph": 3.5, "alcohol": 10.0, "quality": 7},
            ["alcohol"],
        ),
    ]
    for fname, lines, truth, amb_fields in amb:
        rid = fname.replace(".pdf", "")
        rel = f"ambiguous/{fname}"
        write_case(
            rel,
            lines,
            truth=truth,
            row={
                "id": rid,
                "csv_row_index": -1,
                "clean_pdf": rel,
                "clean_truth": rel.replace(".pdf", ".json"),
                "noisy_pdf": None,
                "noisy_truth": None,
                "expected_status": "AMBIGUOUS",
                "expected_errors": [],
                "expected_ambiguous_fields": amb_fields,
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None, help="Override winequality-red.csv path")
    parser.add_argument(
        "--m3-only",
        action="store_true",
        help="Only write M3 cross-field corpus (no CSV / M1 corpus_index refresh)",
    )
    args = parser.parse_args()

    base = _here()
    if args.m3_only:
        write_m3_cross_field_corpus(base)
        return

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
        from rich_pdf_builder import LabValues, build_rich_wine_pdf

        lab = LabValues(
            ph=ph,
            alcohol=alcohol,
            quality=int(quality or 0) if quality is not None else None,
            omit_quality=omit_quality,
        )
        (clean_dir / f"row_{tag}_clean.pdf").write_bytes(build_rich_wine_pdf(lab=lab))
        (clean_dir / f"row_{tag}_clean.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        if noise:
            (noisy_dir / f"row_{tag}_noisy.pdf").write_bytes(
                build_rich_wine_pdf(lab=lab, noise_extra=_noise_lines())
            )
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

    _append_synthetic_corpus(base, specs)

    manifest = {"schema": "schema.json", "rows": specs}
    (base / "corpus_index.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    write_m3_cross_field_corpus(base)

    print(f"Wrote corpus under {base}")
    print(f"Rows: {len(specs)}")


def write_m3_cross_field_corpus(base: Path) -> None:
    """Hand-crafted PDFs for ``schema_m3_wine_cross_field.json`` (no CSV required).

    Writes ``m3_cross_field/*.pdf`` + ``m3_corpus_index.json`` for :mod:`test_pipeline_m3_corpus`.
    """

    m3_dir = base / "m3_cross_field"
    m3_dir.mkdir(parents=True, exist_ok=True)
    header = "Wine QA Report (synthetic)"
    rows: list[dict[str, object]] = []

    def add(
        stem: str,
        lines: list[str],
        truth: dict[str, float | int],
        *,
        status: str,
        errors: list[dict[str, str]],
    ) -> None:
        rel = f"m3_cross_field/{stem}.pdf"
        (base / rel).write_bytes(_build_rich_pdf_from_lines(lines))
        (base / f"m3_cross_field/{stem}.json").write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8")
        rows.append(
            {
                "id": stem,
                "csv_row_index": -1,
                "clean_pdf": rel,
                "clean_truth": f"m3_cross_field/{stem}.json",
                "noisy_pdf": None,
                "noisy_truth": None,
                "expected_status": status,
                "expected_errors": errors,
            }
        )

    add(
        "syn_m3_cf_pass",
        [header, "pH: 3.5", "Alcohol: 11%", "Quality: 6"],
        {"ph": 3.5, "alcohol": 11.0, "quality": 6},
        status="PASS",
        errors=[],
    )
    add(
        "syn_m3_cf_fail_high_alcohol",
        [header, "pH: 3.5", "Alcohol: 13%", "Quality: 4"],
        {"ph": 3.5, "alcohol": 13.0, "quality": 4},
        status="FAIL",
        errors=[{"field": "alcohol", "rule": "high_alcohol_quality"}],
    )

    manifest = {"schema": "schema_m3_wine_cross_field.json", "rows": rows}
    (base / "m3_corpus_index.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"M3 cross-field corpus: {len(rows)} rows under {m3_dir}")


if __name__ == "__main__":
    main()
