"""Configuration models and loading."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SortdConfig(BaseModel):
    """Validated application configuration."""

    model_config = ConfigDict(extra="ignore")

    target: Path = Path.home() / "Downloads"
    stability_seconds: float = Field(default=1.5, ge=0)
    output_image_format: str = "jpg"
    archive_originals: bool = True
    classifier: str = "heuristic"
    confidence_threshold: float = Field(default=0.75, ge=0, le=1)
    ollama_url: str = "http://localhost:11434/api/generate"
    ollama_model: str = "qwen2.5:3b"
    gemini_model: str = "gemini-2.0-flash"
    folders: dict[str, str] = Field(
        default_factory=lambda: {
            "applications": "Applications",
            "archives": "Archives",
            "documents": "Documents",
            "images": "Images",
            "audio": "Audio",
            "video": "Video",
            "code": "Code",
            "duplicates": "Duplicates",
            "review": "Needs_Review",
            "other": "Other",
        }
    )
    rules: list[dict[str, str]] = Field(default_factory=list)


def default_config_path() -> Path:
    """Return the per-user config path."""
    return Path.home() / ".config" / "sortd" / "config.yaml"


def load_config(path: Path | None = None) -> SortdConfig:
    """Load YAML config, falling back to defaults when no file exists."""
    config_path = path or default_config_path()
    if not config_path.exists():
        return SortdConfig()
    raw: Any = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Configuration at {config_path} must be a YAML mapping")
    if "target" in raw:
        raw["target"] = Path(raw["target"]).expanduser()
    return SortdConfig.model_validate(raw)


def write_default_config(path: Path | None = None) -> Path:
    """Write a commented starter config without overwriting an existing file."""
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(
            "# sortd settings\ntarget: ~/Downloads\nstability_seconds: 1.5\n"
            "output_image_format: jpg\narchive_originals: true\nclassifier: heuristic\n"
            "confidence_threshold: 0.75\nfolders:\n  applications: Applications\n"
            "  archives: Archives\n  documents: Documents\n  images: Images\n"
            "  audio: Audio\n  video: Video\n  code: Code\n  duplicates: Duplicates\n"
            "  review: Needs_Review\n  other: Other\nrules: []\n",
            encoding="utf-8",
        )
    return target
