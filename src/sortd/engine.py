"""Deterministic and semantic file organization pipeline."""

import re
import time
from pathlib import Path

from .classifier import BaseClassifier, make_classifier
from .config import SortdConfig
from .converters import convert_image, sha256_file
from .extractors import extract_pdf_text
from .history import append_event, atomic_move

IGNORED_SUFFIXES = {".crdownload", ".part", ".download", ".tmp"}
IGNORED_NAMES = {".ds_store", ".localized"}
ROUTES = {
    "applications": {".dmg", ".pkg", ".exe", ".msi", ".deb", ".rpm", ".appimage"},
    "archives": {".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".heic", ".webp"},
    "audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "video": {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    "code": {
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".json",
        ".yaml",
        ".yml",
        ".md",
        ".sh",
        ".tex",
        ".cls",
    },
    "documents": {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".rtf",
        ".csv",
        ".ics",
    },
}


class SortEngine:
    """Organize files according to config, preserving a reversible move log."""

    def __init__(
        self,
        config: SortdConfig,
        *,
        dry_run: bool = False,
        history_file: Path | None = None,
        classifier: BaseClassifier | None = None,
    ) -> None:
        self.config, self.dry_run, self.history_file = config, dry_run, history_file
        self.classifier = classifier or make_classifier(
            config.classifier, config.ollama_url, config.ollama_model, config.gemini_model
        )
        self.seen: dict[str, Path] = {}

    def scan(self, root: Path | None = None) -> list[tuple[str, str]]:
        """Process files directly inside root and return (name, destination) rows."""
        folder = root or self.config.target
        if not folder.exists():
            return []
        files = sorted((p for p in folder.iterdir() if p.is_file()), key=lambda p: p.name.lower())
        results: list[tuple[str, str]] = []
        for path in files:
            destination = self.process(path)
            if destination:
                results.append((path.name, str(destination)))
        for path, destination in self.process_staged():
            results.append((path.name, str(destination)))
        return results

    def process(self, path: Path) -> Path | None:
        """Process one completed file; return destination, or None if ignored."""
        if (
            not path.is_file()
            or path.name.lower() in IGNORED_NAMES
            or path.suffix.lower() in IGNORED_SUFFIXES
        ):
            return None
        if self.config.staging_enabled:
            target = self.config.target.expanduser().resolve()
            latest = (target / self.config.latest_folder).resolve()
            age_seconds = max(0.0, time.time() - path.stat().st_mtime)
            delay_seconds = self.config.staging_hours * 3600
            if path.parent.resolve() == latest:
                if age_seconds < delay_seconds:
                    return None
            elif path.parent.resolve() == target and age_seconds < delay_seconds:
                return self._move(
                    path,
                    self._destination(self.config.latest_folder, path.name),
                )
        if path.parent.name in set(self.config.folders.values()):
            return None
        digest = sha256_file(path)
        if digest in self.seen:
            return self._move(
                path,
                self._destination(self.config.folders.get("duplicates", "Duplicates"), path.name),
            )
        self.seen[digest] = path

        suffix = path.suffix.lower()
        if suffix in {".heic", ".webp"}:
            if self.dry_run:
                converted_name = path.with_suffix(
                    ".jpg" if self.config.output_image_format.lower() in {"jpg", "jpeg"} else ".png"
                ).name
                return self._destination(
                    self.config.folders.get("images", "Images"), converted_name
                )
            converted = convert_image(path, self.config.output_image_format)
            if not self.dry_run and self.config.archive_originals:
                archive = self._destination("Originals", path.name)
                self._move(path, archive)
            elif not self.dry_run:
                path.unlink(missing_ok=True)
            return self._move(
                converted,
                self._destination(self.config.folders.get("images", "Images"), converted.name),
            )

        semantic = None
        if suffix == ".pdf":
            try:
                semantic = self.classifier.classify(extract_pdf_text(path), path.name)
            except Exception:
                semantic = None
        if semantic:
            if semantic.confidence < self.config.confidence_threshold:
                category = self.config.folders.get("review", "Needs_Review")
                name = path.name
            else:
                category = re.sub(r"[^A-Za-z0-9 _-]", "", semantic.category).strip() or "Documents"
                name = Path(semantic.suggested_filename).name
        else:
            route = next((key for key, suffixes in ROUTES.items() if suffix in suffixes), "other")
            category = self.config.folders.get(route, route.title())
            name = path.name
        for rule in self.config.rules:
            pattern = rule.get("pattern", "")
            if pattern and re.search(pattern, path.name, re.IGNORECASE):
                category = rule.get("folder", category)
                break
        return self._move(path, self._destination(category, name))

    def process_staged(self) -> list[tuple[Path, Path]]:
        """Categorize staged files that have aged past the configured delay."""
        if not self.config.staging_enabled:
            return []
        latest = self.config.target / self.config.latest_folder
        if not latest.is_dir():
            return []
        results: list[tuple[Path, Path]] = []
        for path in sorted(latest.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            destination = self.process(path)
            if destination:
                results.append((path, destination))
        return results

    def _destination(self, category: str, name: str) -> Path:
        parent = self.config.target
        candidate = parent / category / name
        index = 1
        while candidate.exists():
            candidate = candidate.with_name(f"{Path(name).stem} ({index}){Path(name).suffix}")
            index += 1
        if candidate.exists():
            candidate = candidate.with_name(f"{candidate.stem} ({index}){candidate.suffix}")
        return candidate

    def _move(self, src: Path, dst: Path) -> Path:
        if not self.dry_run:
            atomic_move(src, dst)
            append_event({"action": "move", "src": str(src), "dst": str(dst)}, self.history_file)
        return dst
