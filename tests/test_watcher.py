from pathlib import Path
from unittest.mock import Mock

from watchdog.events import FileCreatedEvent

from sortd.watcher import SortHandler, is_eligible, wait_until_stable


def test_partial_filtering(tmp_path: Path) -> None:
    partial = tmp_path / "download.crdownload"
    partial.write_text("x")
    complete = tmp_path / "ready.pdf"
    complete.write_text("x")
    assert not is_eligible(partial)
    assert is_eligible(complete)


def test_stability(tmp_path: Path) -> None:
    file = tmp_path / "ready.txt"
    file.write_text("ready")
    assert wait_until_stable(file, seconds=0.01, timeout=0.3, poll_interval=0.01)


def test_wait_stability_missing_and_zero_timeout(tmp_path: Path) -> None:
    assert not wait_until_stable(tmp_path / "gone", seconds=0, timeout=0.01)
    file = tmp_path / "quick"
    file.write_text("a")
    assert not wait_until_stable(file, seconds=10, timeout=0.01, poll_interval=0.005)


def test_handler_filters_and_processes_stable_file(tmp_path: Path) -> None:
    source = tmp_path / "file.txt"
    source.write_text("data")
    engine = Mock()
    handler = SortHandler(engine, stability_seconds=0)
    handler.on_created(FileCreatedEvent(str(tmp_path / "broken.part")))
    handler.on_created(FileCreatedEvent(str(source)))
    engine.process.assert_called_once_with(source)
