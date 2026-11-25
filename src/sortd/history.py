"""Append-only move history and safe undo operations."""

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def history_path() -> Path:
    """Return the history log path."""
    return Path.home() / ".local" / "share" / "sortd" / "history.jsonl"


def append_event(event: dict[str, Any], path: Path | None = None) -> None:
    """Append one durable event to the JSONL log."""
    target = path or history_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(UTC).isoformat(), **event}
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_events(path: Path | None = None) -> list[dict[str, Any]]:
    """Read valid records, ignoring a truncated final line."""
    target = path or history_path()
    if not target.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict) and item.get("action") == "move":
                events.append(item)
        except json.JSONDecodeError:
            continue
    return events


def undo(last: int = 1, path: Path | None = None, dry_run: bool = False) -> list[str]:
    """Reverse up to ``last`` latest moves, preserving conflicts safely."""
    if last < 1:
        raise ValueError("last must be at least 1")
    target = path or history_path()
    events = read_events(target)
    selected = events[-last:]
    reverted: list[str] = []
    for event in reversed(selected):
        src, dst = Path(str(event["src"])), Path(str(event["dst"]))
        if not dst.exists():
            continue
        if src.exists():
            raise FileExistsError(f"Cannot undo because original path is occupied: {src}")
        reverted.append(f"{dst} -> {src}")
        if not dry_run:
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))
    return reverted


def atomic_move(src: Path, dst: Path) -> None:
    """Move within or across filesystems via a same-directory temporary file."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.stat().st_dev == dst.parent.stat().st_dev:
        os.replace(src, dst)
        return
    fd, temp_name = tempfile.mkstemp(prefix=f".{dst.name}.", dir=dst.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copy2(src, temp)
        os.replace(temp, dst)
        src.unlink()
    finally:
        temp.unlink(missing_ok=True)
