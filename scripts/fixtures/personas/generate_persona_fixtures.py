#!/usr/bin/env python3
"""
Generate persona fixture metadata and copy wine PDFs into scripts/fixtures/personas/.

Maria uses the wine corpus in-place; James gets JSON sidecars pointing at demo paths.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WINE = ROOT / "backend" / "tests" / "fixtures" / "wine"
OUT = ROOT / "scripts" / "fixtures" / "personas"


def _write_sidecar(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def maria_fixtures() -> None:
    """Maria — supplier CoA (wine corpus)."""
    maria_dir = OUT / "maria_lab"
    maria_dir.mkdir(parents=True, exist_ok=True)
    entries = [
        ("coa_pass_clean.pdf", "clean/row_000_clean.pdf", "PASS", "Routine supplier CoA — approve"),
        ("coa_pass_noisy.pdf", "noisy/row_001_noisy.pdf", "PASS", "Scanned/noisy supplier PDF"),
        ("coa_fail_alcohol_high.pdf", "fail_schema/syn_fs_alcohol_high.pdf", "FAIL", "Alcohol above spec — hold batch"),
        ("coa_fail_missing_ph.pdf", "fail_missing/syn_fm_no_ph.pdf", "FAIL", "Incomplete CoA — reject supplier"),
        ("coa_ambiguous_ph.pdf", "ambiguous/syn_amb_ph_dup.pdf", "AMBIGUOUS", "Conflicting pH — human review"),
    ]
    for dest_name, src_rel, outcome, note in entries:
        src = WINE / src_rel
        if not src.is_file():
            raise FileNotFoundError(src)
        shutil.copy2(src, maria_dir / dest_name)
        _write_sidecar(
            maria_dir / f"{dest_name}.json",
            {
                "persona": "maria",
                "schema_key": "supplier_coa",
                "schema_version": "1.0",
                "source": str(src_rel),
                "expected_outcome": outcome,
                "audit_note": note,
            },
        )
    print(f"Maria: {len(entries)} PDFs → {maria_dir}")


def james_fixtures() -> None:
    """James — metadata only (PDFs created separately or reused)."""
    james_dir = OUT / "james_industrial"
    james_dir.mkdir(parents=True, exist_ok=True)
    specs = [
        {
            "file": "delivery_note_pass.pdf",
            "schema_key": "delivery_note",
            "expected_outcome": "PASS",
            "audit_note": "Inbound shipment OK",
        },
        {
            "file": "invoice_pass.pdf",
            "schema_key": "invoice",
            "expected_outcome": "PASS",
            "audit_note": "Supplier invoice within policy",
        },
    ]
    for spec in specs:
        _write_sidecar(james_dir / f"{spec['file']}.json", {"persona": "james", **spec})
    print(f"James: {len(specs)} sidecars → {james_dir}")


def main() -> None:
    maria_fixtures()
    james_fixtures()


if __name__ == "__main__":
    main()
