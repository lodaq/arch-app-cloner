"""Utility functions for Arch App Cloner."""

import os
import re
import signal
from pathlib import Path
from typing import Optional, Tuple


def get_base_data_dir() -> Path:
    """Return base data directory for app cloner."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    return base / "arch-app-cloner"


def get_clones_dir() -> Path:
    """Return directory where all clone data and configurations reside."""
    clones_dir = get_base_data_dir() / "clones"
    clones_dir.mkdir(parents=True, exist_ok=True)
    return clones_dir


def get_desktop_dir() -> Path:
    """Return user's desktop application directory for .desktop launchers."""
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    d = base / "applications"
    d.mkdir(parents=True, exist_ok=True)
    return d


def slugify(text: str) -> str:
    """Convert a string into a clean lowercase identifier for folder and file names."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "clone"


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_directory_size(path: Path) -> Tuple[int, str]:
    """Calculate the total size of a directory in bytes and human-readable format."""
    total_bytes = 0
    if not path.exists():
        return 0, "0 B"
    if path.is_file():
        total_bytes = path.stat().st_size
    else:
        for entry in path.rglob("*"):
            if entry.is_file() and not entry.is_symlink():
                try:
                    total_bytes += entry.stat().st_size
                except (OSError, PermissionError):
                    pass
    return total_bytes, format_bytes(total_bytes)


def clean_desktop_exec(exec_cmd: str) -> str:
    """Remove standard Freedesktop .desktop field codes like %u, %U, %f, %F, etc."""
    cleaned = re.sub(r"%[a-zA-Z]", "", exec_cmd)
    return " ".join(cleaned.split())


def is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is still alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    # Extra check on Linux /proc
    proc_stat = Path(f"/proc/{pid}/status")
    if proc_stat.exists():
        try:
            with open(proc_stat, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("State:"):
                        state = line.split()[1]
                        return state not in ("Z", "X")  # zombie / dead
        except (OSError, PermissionError):
            pass
    return True


def read_pid_file(pid_path: Path) -> Optional[int]:
    """Read PID from file and return it if process is alive, else clean up and return None."""
    if not pid_path.exists():
        return None
    try:
        with open(pid_path, "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
        if is_pid_alive(pid):
            return pid
        else:
            pid_path.unlink(missing_ok=True)
            return None
    except Exception:
        pid_path.unlink(missing_ok=True)
        return None


def write_pid_file(pid_path: Path, pid: int) -> None:
    """Write PID to tracking file."""
    with open(pid_path, "w", encoding="utf-8") as f:
        f.write(str(pid))


def clear_pid_file(pid_path: Path) -> None:
    """Remove PID tracking file."""
    try:
        pid_path.unlink(missing_ok=True)
    except Exception:
        pass


def kill_process(pid: int, timeout_sec: float = 3.0) -> bool:
    """Gracefully terminate a process (SIGTERM) and kill (SIGKILL) if unresponsive."""
    import time
    if not is_pid_alive(pid):
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return True

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.1)

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
    return not is_pid_alive(pid)
