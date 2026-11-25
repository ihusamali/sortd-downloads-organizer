"""User-level background service registration."""

import platform
import shutil
import subprocess
from pathlib import Path


def service_file() -> Path:
    """Return the platform service definition path."""
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "LaunchAgents" / "com.sortd.agent.plist"
    if platform.system() == "Linux":
        return Path.home() / ".config" / "systemd" / "user" / "sortd.service"
    raise RuntimeError("Background service installation supports macOS and Linux")


def install() -> Path:
    """Install and enable the user service."""
    executable = shutil.which("sortd") or "sortd"
    path = service_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Darwin":
        path.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>com.sortd.agent</string>
<key>ProgramArguments</key><array><string>{executable}</string><string>watch</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/></dict></plist>""",
            encoding="utf-8",
        )
        subprocess.run(["launchctl", "load", str(path)], check=False)
    else:
        path.write_text(
            f"[Unit]\nDescription=sortd downloads organizer\n"
            f"[Service]\nExecStart={executable} watch\nRestart=on-failure\n"
            "[Install]\nWantedBy=default.target\n",
            encoding="utf-8",
        )
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        subprocess.run(["systemctl", "--user", "enable", "--now", "sortd.service"], check=False)
    return path


def uninstall() -> Path:
    """Disable and remove the user service definition."""
    path = service_file()
    if platform.system() == "Darwin":
        subprocess.run(["launchctl", "unload", str(path)], check=False)
    else:
        subprocess.run(["systemctl", "--user", "disable", "--now", "sortd.service"], check=False)
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    path.unlink(missing_ok=True)
    return path
