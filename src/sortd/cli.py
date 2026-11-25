"""Command-line interface."""

import shutil
import tempfile
from pathlib import Path

import pymupdf
import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import SortdConfig, load_config, write_default_config
from .engine import SortEngine
from .history import history_path, undo
from .service import install as install_service
from .service import uninstall as uninstall_service
from .watcher import watch as run_watch

app = typer.Typer(
    help="Semantic & Rule-Based Downloads Organizer",
    no_args_is_help=True,
    invoke_without_command=True,
)
service_app = typer.Typer(help="Manage the background service")
app.add_typer(service_app, name="service")
console = Console()


def _table(rows: list[tuple[str, str]]) -> None:
    table = Table(title="sortd organization plan")
    table.add_column("File", style="cyan")
    table.add_column("Destination", style="green")
    for source, destination in rows:
        table.add_row(source, destination)
    console.print(table)
    console.print(f"[bold]{len(rows)}[/bold] file(s) processed")


@app.callback()
def main(version: bool = typer.Option(False, "--version", help="Show version and exit")) -> None:
    """Organize downloads safely on your machine."""
    if version:
        console.print(f"sortd {__version__}")
        raise typer.Exit()


@app.command()
def init() -> None:
    """Create the default user config."""
    console.print(f"Configuration ready: {write_default_config()}")


@app.command()
def once(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without changing files"),
    target: Path | None = typer.Option(None, "--target", help="Folder to scan"),
    config: Path | None = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Organize files already in the target directory."""
    settings = load_config(config)
    if target:
        settings.target = target.expanduser()
    _table(SortEngine(settings, dry_run=dry_run).scan())


@app.command()
def watch(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview file destinations"),
    target: Path | None = typer.Option(None, "--target", help="Folder to monitor"),
    config: Path | None = typer.Option(None, "--config", help="Config file path"),
) -> None:
    """Monitor a directory and organize completed downloads."""
    settings = load_config(config)
    if target:
        settings.target = target.expanduser()
    console.print(f"Watching [cyan]{settings.target}[/cyan] (Ctrl-C to stop)")
    run_watch(SortEngine(settings, dry_run=dry_run), settings.target, settings.stability_seconds)


@app.command("undo")
def undo_command(
    last: int = typer.Option(1, "--last", min=1),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview rollback"),
) -> None:
    """Undo the most recent file moves."""
    try:
        results = undo(last, history_path(), dry_run)
    except (FileExistsError, ValueError) as exc:
        console.print(f"[red]Undo failed:[/red] {exc}")
        raise typer.Exit(1) from exc
    for row in results:
        console.print(row)
    console.print(f"Reverted {len(results)} move(s)" + (" (dry run)" if dry_run else ""))


@app.command()
def demo() -> None:
    """Run a safe self-contained demo with realistic sample files."""
    sandbox = Path(tempfile.mkdtemp(prefix="sortd-demo-"))
    try:
        documents = {
            "document (1).pdf": "Invoice sample",
            "Train_Ticket_Sample.pdf": "Train ticket sample",
            "Lecture_04_AI.pdf": "Lecture 04 artificial intelligence",
        }
        for name, content in documents.items():
            document = pymupdf.open()  # type: ignore[no-untyped-call]
            document.new_page().insert_text((72, 72), content)
            document.save(sandbox / name)  # type: ignore[no-untyped-call]
            document.close()  # type: ignore[no-untyped-call]
        (sandbox / "installer.dmg").write_bytes(b"demo installer")
        (sandbox / "IMG_4821.HEIC").write_bytes(b"demo image placeholder")
        console.print(f"[bold]Before[/bold]  {sandbox}")
        for item in sorted(sandbox.iterdir()):
            console.print(f"  {item.name}")
        # The placeholder is not a decodable image; omit it from processing.
        (sandbox / "IMG_4821.HEIC").unlink()
        config = SortdConfig(target=sandbox, classifier="heuristic", staging_enabled=False)
        rows = SortEngine(config, history_file=sandbox / "history.jsonl").scan()
        _table(rows)
        console.print("[bold]After[/bold]")
        for item in sorted(sandbox.rglob("*")):
            if item.is_file() and item.name != "history.jsonl":
                console.print(f"  {item.relative_to(sandbox)}")
        console.print("Demo sandbox is temporary and will now be removed.")
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


@service_app.command("install")
def service_install() -> None:
    """Register sortd watch as a user service."""
    console.print(f"Installed service: {install_service()}")


@service_app.command("uninstall")
def service_uninstall() -> None:
    """Unregister the sortd user service."""
    console.print(f"Removed service: {uninstall_service()}")


if __name__ == "__main__":
    app()
