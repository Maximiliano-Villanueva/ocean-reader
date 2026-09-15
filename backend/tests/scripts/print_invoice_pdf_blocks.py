"""
Print PyMuPDF layout blocks for the Cursor invoice fixture (same path as validation).

Run from ``backend/`` (editable install or ``PYTHONPATH=src``)::

    python -m tests.scripts.print_invoice_pdf_blocks
    python -m tests.scripts.print_invoice_pdf_blocks --pdf path/to/file.pdf
    python -m tests.scripts.print_invoice_pdf_blocks --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ocean_read.domain.validation.pdf_blocks import TextBlock, parse_pdf_blocks

_DEFAULT_PDF = (
    Path(__file__).resolve().parents[1] / "fixtures" / "invoice" / "inv_cursor_formatted.pdf"
)


def _block_to_dict(block: TextBlock) -> dict[str, object]:
    return {
        "id": block.id,
        "page": block.page,
        "bbox": list(block.bbox),
        "section_label": block.section_label,
        "font_size_max": block.font_size_max,
        "text": block.text,
    }


def format_blocks_text(blocks: list[TextBlock]) -> str:
    """Human-readable dump for terminal inspection."""

    lines: list[str] = [f"blocks={len(blocks)}", ""]
    for block in blocks:
        lines.append(f"--- {block.id} page={block.page} ---")
        lines.append(f"bbox: {block.bbox}")
        if block.section_label:
            lines.append(f"section: {block.section_label}")
        if block.font_size_max is not None:
            lines.append(f"font_size_max: {block.font_size_max}")
        lines.append(block.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def dump_pdf_blocks(pdf_path: Path, *, as_json: bool) -> str:
    """Load *pdf_path* and return formatted block output."""

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    data = pdf_path.read_bytes()
    blocks = parse_pdf_blocks(data)
    if as_json:
        payload = {"pdf": str(pdf_path.resolve()), "block_count": len(blocks), "blocks": [_block_to_dict(b) for b in blocks]}
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    header = f"pdf: {pdf_path.resolve()}\n"
    return header + format_blocks_text(blocks)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse args, print blocks to stdout."""

    parser = argparse.ArgumentParser(
        description="Dump validation pipeline PDF blocks (parse_pdf_blocks) to stdout.",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=_DEFAULT_PDF,
        help=f"PDF file (default: {_DEFAULT_PDF.name} fixture)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text",
    )
    args = parser.parse_args(argv)
    try:
        print(dump_pdf_blocks(args.pdf, as_json=args.json), end="")
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
