from pathlib import Path

import pymupdf
from PIL import Image

from sortd.classifier import Classification
from sortd.config import SortdConfig
from sortd.engine import SortEngine
from sortd.history import undo


class FakeClassifier:
    def classify(self, text: str, filename: str) -> Classification:
        return Classification(
            category="Finance", suggested_filename="2026-01-01_Invoice.pdf", confidence=0.9
        )


def test_sort_and_undo(tmp_path: Path) -> None:
    source = tmp_path / "invoice.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "invoice sample")
    document.save(source)
    document.close()
    log = tmp_path / "history.jsonl"
    config = SortdConfig(target=tmp_path)
    engine = SortEngine(config, history_file=log, classifier=FakeClassifier())
    engine.process(source)
    output = tmp_path / "Finance" / "2026-01-01_Invoice.pdf"
    assert output.exists()
    assert undo(1, log) == [f"{output} -> {source}"]
    assert source.exists()


def test_dry_run_leaves_source(tmp_path: Path) -> None:
    source = tmp_path / "archive.zip"
    source.write_bytes(b"zip")
    engine = SortEngine(SortdConfig(target=tmp_path), dry_run=True)
    assert engine.process(source) == tmp_path / "Archives" / "archive.zip"
    assert source.exists()


def test_partial_download_ignored(tmp_path: Path) -> None:
    source = tmp_path / "x.pdf.part"
    source.write_bytes(b"x")
    assert SortEngine(SortdConfig(target=tmp_path)).process(source) is None


def test_low_confidence_routes_to_review(tmp_path: Path) -> None:
    source = tmp_path / "unknown.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "unclassified")
    document.save(source)
    document.close()
    classifier = FakeClassifier()
    classifier.classify = lambda text, filename: Classification(
        category="Finance", suggested_filename="anything.pdf", confidence=0.2
    )
    output = SortEngine(
        SortdConfig(target=tmp_path), classifier=classifier, history_file=tmp_path / "h.jsonl"
    ).process(source)
    assert output == tmp_path / "Needs_Review" / "unknown.pdf"


def test_duplicate_routes_to_duplicates(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("same content")
    second.write_text("same content")
    engine = SortEngine(SortdConfig(target=tmp_path), history_file=tmp_path / "h.jsonl")
    engine.process(first)
    output = engine.process(second)
    assert output == tmp_path / "Duplicates" / "second.txt"


def test_undo_conflict_is_safe(tmp_path: Path) -> None:
    source = tmp_path / "original.txt"
    dest = tmp_path / "moved.txt"
    source.write_text("original")
    dest.write_text("moved")
    log = tmp_path / "history.jsonl"
    from sortd.history import append_event

    append_event({"action": "move", "src": str(source), "dst": str(dest)}, log)
    try:
        undo(1, log)
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected an occupied-source conflict")
    assert dest.exists()


def test_rule_routing_and_collision_rename(tmp_path: Path) -> None:
    source = tmp_path / "tax-notes.txt"
    source.write_text("tax records")
    config = SortdConfig(target=tmp_path, rules=[{"pattern": "tax", "folder": "Finance"}])
    engine = SortEngine(config, history_file=tmp_path / "h.jsonl")
    assert engine.process(source) == tmp_path / "Finance" / "tax-notes.txt"
    another = tmp_path / "tax-notes.txt"
    another.write_text("different records")
    assert engine.process(another) == tmp_path / "Finance" / "tax-notes (1).txt"


def test_webp_conversion_in_engine_and_dry_run(tmp_path: Path) -> None:
    source = tmp_path / "photo.webp"
    Image.new("RGB", (3, 3), "blue").save(source, "WEBP")
    config = SortdConfig(target=tmp_path, archive_originals=False)
    engine = SortEngine(config, history_file=tmp_path / "h.jsonl")
    destination = engine.process(source)
    assert destination == tmp_path / "Images" / "photo.jpg"
    assert destination and destination.exists()
    preview = tmp_path / "preview.webp"
    Image.new("RGB", (3, 3), "red").save(preview, "WEBP")
    dry = SortEngine(config, dry_run=True)
    assert dry.process(preview) == tmp_path / "Images" / "preview.jpg"
    assert preview.exists()


def test_missing_target_is_empty(tmp_path: Path) -> None:
    assert SortEngine(SortdConfig(target=tmp_path / "missing")).scan() == []
