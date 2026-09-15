"""
Print Docling conversion output for the Cursor invoice fixture.

Requires the ``docling`` extra (heavy; pulls PyTorch). From ``backend/``::

    uv pip install -e ".[docling]"
    python -m tests.scripts.print_invoice_pdf_docling
    python -m tests.scripts.print_invoice_pdf_docling --format json
    python -m tests.scripts.print_invoice_pdf_docling --ocr
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal

_DEFAULT_PDF = (
    Path(__file__).resolve().parents[1] / "fixtures" / "invoice" / "inv_cursor_formatted.pdf"
)

FormatName = Literal["markdown", "text", "json", "doctags", "element-tree"]


def _build_converter(*, do_ocr: bool) -> Any:
    """Lazy-import Docling and return a ``DocumentConverter``."""

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as exc:
        raise RuntimeError(
            "docling is not installed. From backend/: uv pip install -e \".[docling]\""
        ) from exc

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = do_ocr
    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def convert_pdf(pdf_path: Path, *, do_ocr: bool) -> Any:
    """Run Docling on *pdf_path* and return the ``document`` object."""

    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    converter = _build_converter(do_ocr=do_ocr)
    result = converter.convert(str(pdf_path.resolve()))
    return result.document


def format_docling_output(document: Any, fmt: FormatName) -> str:
    """Serialize a Docling document to the requested representation."""

    if fmt == "markdown":
        return document.export_to_markdown()
    if fmt == "text":
        return document.export_to_text()
    if fmt == "json":
        return json.dumps(document.export_to_dict(), indent=2, ensure_ascii=False) + "\n"
    if fmt == "doctags":
        return document.export_to_doctags()
    if fmt == "element-tree":
        return document.export_to_element_tree()
    raise ValueError(f"Unsupported format: {fmt}")


def dump_pdf_docling(pdf_path: Path, *, fmt: FormatName, do_ocr: bool) -> str:
    """Convert *pdf_path* with Docling and return formatted output."""

    document = convert_pdf(pdf_path, do_ocr=do_ocr)
    body = format_docling_output(document, fmt)
    header = (
        f"pdf: {pdf_path.resolve()}\n"
        f"engine: docling\n"
        f"format: {fmt}\n"
        f"do_ocr: {do_ocr}\n"
        f"{'=' * 60}\n"
    )
    return header + body


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse args, print Docling output to stdout."""

    parser = argparse.ArgumentParser(
        description="Dump Docling conversion for a PDF (default: invoice fixture).",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=_DEFAULT_PDF,
        help=f"PDF file (default: {_DEFAULT_PDF.name} fixture)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "text", "json", "doctags", "element-tree"),
        default="markdown",
        help="Output representation (default: markdown)",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Enable OCR (slower; default off for text-native PDFs)",
    )
    args = parser.parse_args(argv)
    try:
        out = dump_pdf_docling(args.pdf, fmt=args.format, do_ocr=args.ocr)
        if not out.endswith("\n"):
            out += "\n"
        print(out, end="")
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
