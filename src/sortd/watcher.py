"""Watchdog integration with stable-file debounce."""

import time
from pathlib import Path
from threading import Event

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .engine import IGNORED_NAMES, IGNORED_SUFFIXES, SortEngine


def is_eligible(path: Path) -> bool:
    """Return whether a path is a candidate completed download."""
    return (
        path.is_file()
        and path.name.lower() not in IGNORED_NAMES
        and path.suffix.lower() not in IGNORED_SUFFIXES
    )


def wait_until_stable(
    path: Path, seconds: float = 1.5, timeout: float = 120.0, poll_interval: float = 0.2
) -> bool:
    """Wait for two equal file sizes separated by seconds; return false on timeout/removal."""
    started = time.monotonic()
    previous: int | None = None
    stable_since: float | None = None
    while time.monotonic() - started < timeout:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        now = time.monotonic()
        if size == previous:
            stable_since = stable_since or now
            if now - stable_since >= seconds:
                return True
        else:
            previous, stable_since = size, now
        time.sleep(poll_interval)
    return False


class SortHandler(FileSystemEventHandler):
    """Synchronous event handler; processing is isolated per file."""

    def __init__(self, engine: SortEngine, stability_seconds: float) -> None:
        self.engine, self.stability_seconds = engine, stability_seconds

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._process(Path(str(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._process(Path(str(event.dest_path)))

    def _process(self, path: Path) -> None:
        if is_eligible(path) and wait_until_stable(path, self.stability_seconds):
            try:
                self.engine.process(path)
            except (OSError, ValueError):
                return


def watch(
    engine: SortEngine, root: Path, stability_seconds: float, stop: Event | None = None
) -> None:
    """Run observer until interrupted or stop event is set."""
    root.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(SortHandler(engine, stability_seconds), str(root), recursive=False)
    observer.start()
    last_staging_sweep = time.monotonic()
    try:
        while stop is None or not stop.wait(0.5):
            if stop is None:
                time.sleep(0.5)
            if engine.config.staging_enabled and time.monotonic() - last_staging_sweep >= 60:
                try:
                    engine.process_staged()
                except OSError:
                    pass
                last_staging_sweep = time.monotonic()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
