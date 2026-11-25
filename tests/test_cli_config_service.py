from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from sortd.cli import app
from sortd.config import load_config, write_default_config
from sortd.service import install, service_file, uninstall

runner = CliRunner()


def test_help_and_version() -> None:
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert "sortd" in runner.invoke(app, ["--version"]).output


def test_init_config(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    written = write_default_config(target)
    assert written == target
    assert load_config(target).confidence_threshold == 0.75
    target.write_text("target: /tmp/example\nclassifier: heuristic\n", encoding="utf-8")
    assert str(load_config(target).target) == "/tmp/example"


def test_once_cli_dry_run(tmp_path: Path) -> None:
    (tmp_path / "a.zip").write_bytes(b"archive")
    result = runner.invoke(app, ["once", "--target", str(tmp_path), "--dry-run"])
    assert result.exit_code == 0
    assert "1 file(s) processed" in result.output
    assert (tmp_path / "a.zip").exists()


def test_demo_cli_cleans_up() -> None:
    result = runner.invoke(app, ["demo"])
    assert result.exit_code == 0
    assert "Before" in result.output and "After" in result.output
    sandbox = result.output.split("Before")[-1].splitlines()[0].strip()
    assert not Path(sandbox).exists()


def test_unknown_classifier_rejected(tmp_path: Path) -> None:
    config = tmp_path / "bad.yaml"
    config.write_text("classifier: unknown\n", encoding="utf-8")
    result = runner.invoke(app, ["once", "--config", str(config)])
    assert result.exit_code != 0


def test_service_path_by_platform() -> None:
    with patch("sortd.service.platform.system", return_value="Linux"):
        assert service_file().name == "sortd.service"
    with patch("sortd.service.platform.system", return_value="Darwin"):
        assert service_file().name == "com.sortd.agent.plist"


def test_service_install_uninstall_linux(tmp_path: Path) -> None:
    with (
        patch("sortd.service.platform.system", return_value="Linux"),
        patch("sortd.service.Path.home", return_value=tmp_path),
        patch("sortd.service.subprocess.run"),
    ):
        path = install()
        assert path.exists() and "systemd" in str(path)
        assert uninstall() == path
        assert not path.exists()


def test_service_install_macos(tmp_path: Path) -> None:
    with (
        patch("sortd.service.platform.system", return_value="Darwin"),
        patch("sortd.service.Path.home", return_value=tmp_path),
        patch("sortd.service.subprocess.run"),
    ):
        path = install()
        assert "launchd" in path.read_text(
            encoding="utf-8"
        ) or "ProgramArguments" in path.read_text(encoding="utf-8")
        uninstall()
