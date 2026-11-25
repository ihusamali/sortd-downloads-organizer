# sortd — Local-First Downloads Folder Organizer

![CI](https://github.com/ihusamali/sortd-downloads-organizer/actions/workflows/ci.yml/badge.svg) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Style](https://img.shields.io/badge/code%20style-Ruff-D7FF64)

**A local-first Downloads folder organizer CLI for macOS and Linux that sorts files by type, routes PDFs by meaning, detects duplicates, and lets you undo every move.**

<!-- Add demo.gif here -->

## What it does

`sortd` is a Python Downloads folder organizer for people who want local processing and reversible file moves. It combines extension and filename rules with optional PDF text classification (offline heuristic, local Ollama, or Gemini), HEIC/WEBP conversion, SHA-256 duplicate routing, dry-run previews, and undo history. It works as a one-shot CLI; a background watcher is available but optional.

## Why sortd?

| | Manual sorting | Cloud organizer tools | sortd |
|---|---|---|---|
| Where files are processed | You | Often remote | Locally by default |
| Organization | Manual | Service-specific | Rules in milliseconds; optional AI classification |
| Undo | Manual | Varies | JSONL move history |
| Cost | Free | Often subscription | Free and open source |

## Architecture

- **Tier 1:** Watchdog completion debounce, image conversion, SHA-256 duplicate detection, and extension/regex routing.
- **Tier 2:** PDF text extraction and interchangeable Ollama, Gemini, or offline heuristic classifiers. Low confidence goes to `Needs_Review/`.
- **Safety:** `--dry-run` previews moves, and successful moves are recorded for `sortd undo`. Optional staging holds recent files in `Latest` until they are 24 hours old.

## 60-second quickstart

```bash
uv tool install git+https://github.com/ihusamali/sortd-downloads-organizer.git
# or: pipx install git+https://github.com/ihusamali/sortd-downloads-organizer.git
sortd demo
sortd once --dry-run
```

The GitHub install works as soon as this repository is public. After the first PyPI release, install by package name with `uv tool install sortd-downloads-organizer` or `pipx install sortd-downloads-organizer`. The installed command is `sortd`.

To contribute from a checkout: `git clone https://github.com/ihusamali/sortd-downloads-organizer.git && cd sortd-downloads-organizer && python -m pip install -e '.[dev]'`.

## Commands

| Command | Purpose |
|---|---|
| `sortd init` | Create `~/.config/sortd/config.yaml` without overwriting it |
| `sortd once [--dry-run] [--target PATH] [--config PATH]` | Scan a folder once |
| `sortd watch [--dry-run] [--target PATH]` | Watch a folder for completed downloads |
| `sortd undo [--last N] [--dry-run]` | Reverse recent moves from `~/.local/share/sortd/history.jsonl` |
| `sortd demo` | Run a temporary sandbox demo and remove it afterward |
| `sortd service install\|uninstall` | Register or remove a macOS launchd or Linux systemd user service |

`sortd --help` lists all options. `sortd once --target ~/Downloads --dry-run` is a safe first scan.

## Configuration

The full template lives in [`config.example.yaml`](config.example.yaml). For example:

```yaml
target: ~/Downloads
classifier: heuristic # ollama, gemini, or heuristic
confidence_threshold: 0.75
output_image_format: jpg
archive_originals: true
staging_enabled: true
staging_hours: 24
latest_folder: Latest
folders:
  documents: Documents
rules:
  - pattern: "tax|invoice|receipt"
    folder: Finance
  - pattern: "Readability|SS26|Lecture"
    folder: Education
```

When staging is enabled, `sortd once` moves files downloaded less than 24 hours ago into `Latest`. Run it again after they age past the delay to classify them. It also processes eligible files already in `Latest`. Creating a folder by hand does not register a rule; configure `folders` to rename a built-in destination or add a `rules` entry to route matching filenames to a custom folder. Rules match filenames and take precedence over classifier output. Existing category folders are left alone; `once` scans files at the Downloads root and the staging folder only.

Ollama uses `ollama_url` and `ollama_model` (`qwen2.5:3b` by default). Gemini reads `GOOGLE_API_KEY`. The heuristic backend needs no API key or network connection.

Custom destinations can be set with `folders`; filename patterns in `rules` can route files to folders such as `Finance` or `Education`. sortd does not infer rules from folders that happen to exist in Downloads.

## Package and repository

The repository is `ihusamali/sortd-downloads-organizer`; the installable Python distribution is `sortd-downloads-organizer`, while the shell command is `sortd`. PyPI already has an unrelated project named `sortd`, so the longer distribution name avoids an install collision.

## Development

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy src/
pytest -v --cov=sortd
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance.

