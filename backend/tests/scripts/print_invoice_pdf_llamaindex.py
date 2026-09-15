"""
Print LlamaIndex PDF loader output for the Cursor invoice fixture.

Compare built-in readers (``PDFReader``, ``PyMuPDFReader``, ``SimpleDirectoryReader``).

From ``backend/``::

    uv pip install -e ".[llamaindex]"
    python -m tests.scripts.print_invoice_pdf_llamaindex
    python -m tests.scripts.print_invoice_pdf_llamaindex --reader pymupdf
    python -m tests.scripts.print_invoice_pdf_llamaindex --format json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Literal

_DEFAULT_PDF = (
    Path(__file__).resolve().parents[1] / "fixtures" / "invoice" / "inv_cursor_formatted.pdf"
)

ReaderName = Literal["auto", "pdf", "pymupdf", "llamaparse"]
FormatName = Literal["text", "json"]


def _require_llamaindex() -> None:
    try:
        import llama_index.core  # noqa: F401
        import llama_index.readers.file  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "LlamaIndex is not installed. From backend/: uv pip install -e \".[llamaindex]\""
        ) from exc


def load_documents(pdf_path: Path, reader: ReaderName) -> list[Any]:
    """Load *pdf_path* with the selected LlamaIndex reader."""

    _require_llamaindex()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    resolved = pdf_path.resolve()

    if reader == "auto":
        from llama_index.core import SimpleDirectoryReader

        return SimpleDirectoryReader(input_files=[str(resolved)]).load_data()

    if reader == "pdf":
        from llama_index.readers.file import PDFReader

        return PDFReader().load_data(resolved)

    if reader == "pymupdf":
        from llama_index.readers.file import PyMuPDFReader

        return PyMuPDFReader().load_data(resolved)

    if reader == "llamaparse":
        api_key = os.environ.get("LLAMA_CLOUD_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError(
                "LlamaParse requires LLAMA_CLOUD_API_KEY. "
                "Use --reader pdf|pymupdf|auto for local parsing."
            )
        try:
            from llama_parse import LlamaParse
        except ImportError as exc:
            raise RuntimeError(
                "llama-parse is not installed. Run: uv pip install llama-parse"
            ) from exc
        parser = LlamaParse(api_key=api_key, result_type="markdown")
        return parser.load_data(str(resolved))

    raise ValueError(f"Unsupported reader: {reader}")


def _document_to_dict(document: Any) -> dict[str, object]:
    return {
        "id": getattr(document, "id_", None),
        "metadata": dict(document.metadata or {}),
        "text": document.text,
    }


def format_documents(documents: list[Any], fmt: FormatName) -> str:
    """Serialize LlamaIndex ``Document`` list for terminal output."""

    if fmt == "json":
        payload = {
            "document_count": len(documents),
            "documents": [_document_to_dict(doc) for doc in documents],
        }
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    lines: list[str] = [f"documents={len(documents)}", ""]
    for index, doc in enumerate(documents):
        lines.append(f"--- document {index} ---")
        if doc.metadata:
            lines.append(f"metadata: {json.dumps(doc.metadata, ensure_ascii=False)}")
        lines.append(doc.text or "")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def dump_pdf_llamaindex(pdf_path: Path, *, reader: ReaderName, fmt: FormatName) -> str:
    """Load *pdf_path* via LlamaIndex and return formatted output."""

    documents = load_documents(pdf_path, reader)
    body = format_documents(documents, fmt)
    header = (
        f"pdf: {pdf_path.resolve()}\n"
        f"engine: llamaindex\n"
        f"reader: {reader}\n"
        f"format: {fmt}\n"
        f"{'=' * 60}\n"
    )
    return header + body


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse args, print LlamaIndex loader output to stdout."""

    parser = argparse.ArgumentParser(
        description="Dump LlamaIndex PDF loader output (default: invoice fixture).",
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=_DEFAULT_PDF,
        help=f"PDF file (default: {_DEFAULT_PDF.name} fixture)",
    )
    parser.add_argument(
        "--reader",
        choices=("auto", "pdf", "pymupdf", "llamaparse"),
        default="pymupdf",
        help=(
            "Loader: auto=SimpleDirectoryReader, pdf=PDFReader (pypdf), "
            "pymupdf=PyMuPDFReader, llamaparse=cloud API (needs LLAMA_CLOUD_API_KEY)"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output representation (default: text)",
    )
    args = parser.parse_args(argv)
    try:
        out = dump_pdf_llamaindex(args.pdf, reader=args.reader, fmt=args.format)
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
