"""Document text extraction helpers."""

from pathlib import Path

import pymupdf


def extract_pdf_text(path: Path, limit: int = 1000) -> str:
    """Extract up to ``limit`` characters from the first PDF page."""
    with pymupdf.open(path) as document:  # type: ignore[no-untyped-call]
        if not document.page_count:
            return ""
        return str(document[0].get_text())[:limit]
