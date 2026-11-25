from pathlib import Path

import fitz

from sortd.extractors import extract_pdf_text


def test_extract_first_page(tmp_path: Path) -> None:
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Sample report text")
    doc.save(path)
    doc.close()
    assert "Sample report text" in extract_pdf_text(path)
