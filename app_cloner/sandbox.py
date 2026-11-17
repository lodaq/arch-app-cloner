"""Bubblewrap sandbox builder and runner for isolated application instances."""

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app_cloner.utils import write_pid_file


def build_bwrap_command(
    clone_home_dir: Path,
    exec_cmd: str,
    extra_args: Optional[List[str]] = None,
    share_downloads: bool = False,
    share_documents: bool = False,
    share_pictures: bool = False,
    custom_mounts: Optional[List[Tuple[str, str]]] = None,
    custom_env: Optional[Dict[str, str]] = None,
    offline_mode: bool = False,
) -> List[str]:
    """Construct bubblewrap command array for launching the isolated app instance."""
    user = os.environ.get("USER", "user")
    home = Path.home()
    xdg_rt = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    wl_disp = os.environ.get("WAYLAND_DISPLAY", "wayland-1")
    disp = os.environ.get("DISPLAY", ":0")

    # Ensure required clone directories exist
    clone_home_dir = Path(clone_home_dir)
    clone_home_dir.mkdir(parents=True, exist_ok=True)
    (clone_home_dir / ".config").mkdir(exist_ok=True)
    (clone_home_dir / ".local" / "share").mkdir(parents=True, exist_ok=True)
    (clone_home_dir / ".cache").mkdir(exist_ok=True)

    cmd = [
        "bwrap",
        # Read-only system mounts
        "--ro-bind", "/", "/",
        # Device & process trees
        "--dev", "/dev",
        "--proc", "/proc",
        # GPU / DRI acceleration
        "--ro-bind-try", "/dev/dri", "/dev/dri",
        "--ro-bind-try", "/sys", "/sys",
        # Isolated /tmp with proper 1777 sticky permissions and X11 socket support
        "--perms", "01777",
        "--tmpfs", "/tmp",
        "--ro-bind-try", "/tmp/.X11-unix", "/tmp/.X11-unix",
        # Isolated home directory
        "--bind", str(clone_home_dir), str(home),
    ]

    # Preserved user directories (read-only) for binaries, fonts, and icons
    for user_ro_path in [
        home / ".local" / "bin",
        home / ".cargo" / "bin",
        home / ".bun" / "bin",
        home / ".local" / "share" / "fonts",
        home / ".fonts",
        home / ".config" / "fontconfig",
        home / ".local" / "share" / "icons",
        home / ".icons",
    ]:
        if user_ro_path.exists():
            cmd.extend(["--ro-bind-try", str(user_ro_path), str(user_ro_path)])

    # Shared user directories if requested
    if share_downloads:
        host_dl = home / "Downloads"
        if host_dl.exists():
            (clone_home_dir / "Downloads").mkdir(exist_ok=True)
            cmd.extend(["--bind", str(host_dl), str(home / "Downloads")])

    if share_documents:
        host_docs = home / "Documents"
        if host_docs.exists():
            (clone_home_dir / "Documents").mkdir(exist_ok=True)
            cmd.extend(["--bind", str(host_docs), str(home / "Documents")])

    if share_pictures:
        host_pics = home / "Pictures"
        if host_pics.exists():
            (clone_home_dir / "Pictures").mkdir(exist_ok=True)
            cmd.extend(["--bind", str(host_pics), str(home / "Pictures")])

    if custom_mounts:
        for host_path, sandbox_path in custom_mounts:
            if Path(host_path).exists():
                cmd.extend(["--bind", host_path, sandbox_path])

    # Isolated XDG_RUNTIME_DIR: clean tmpfs with strict 0700 permissions with only Wayland and Audio bound
    cmd.extend([
        "--perms", "0700",
        "--tmpfs", xdg_rt,
        "--ro-bind-try", f"{xdg_rt}/{wl_disp}", f"{xdg_rt}/{wl_disp}",
        "--ro-bind-try", f"{xdg_rt}/pipewire-0", f"{xdg_rt}/pipewire-0",
        "--ro-bind-try", f"{xdg_rt}/pulse", f"{xdg_rt}/pulse",
    ])

    # Isolation namespaces
    cmd.append("--unshare-ipc")
    cmd.append("--unshare-pid")
    if offline_mode:
        cmd.append("--unshare-net")

    # Set up clean environment variables
    env_vars = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(home),
        "USER": user,
        "LOGNAME": user,
        "TMPDIR": "/tmp",
        "XDG_RUNTIME_DIR": xdg_rt,
        "WAYLAND_DISPLAY": wl_disp,
        "DISPLAY": disp,
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
        "XDG_DATA_DIRS": os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share"),
        "PULSE_SERVER": f"unix:{xdg_rt}/pulse/native",
    }
    if custom_env:
        env_vars.update(custom_env)

    for k, v in env_vars.items():
        cmd.extend(["--setenv", k, v])

    # Launch inside private D-Bus session
    cmd.extend(["dbus-run-session", "--"])

    # Parse and append application command
    app_cmd_parts = shlex.split(exec_cmd)
    if extra_args:
        app_cmd_parts.extend(extra_args)

    cmd.extend(app_cmd_parts)
    return cmd


def launch_in_sandbox(
    clone_dir: Path,
    exec_cmd: str,
    extra_args: Optional[List[str]] = None,
    share_downloads: bool = False,
    share_documents: bool = False,
    share_pictures: bool = False,
    custom_mounts: Optional[List[Tuple[str, str]]] = None,
    custom_env: Optional[Dict[str, str]] = None,
    offline_mode: bool = False,
    detach: bool = True,
) -> subprocess.Popen:
    """Launch the cloned application inside the bubblewrap sandbox."""
    clone_dir = Path(clone_dir)
    clone_home = clone_dir / "data" / "home"
    pid_file = clone_dir / "run.pid"
    log_file = clone_dir / "launch.log"

    cmd = build_bwrap_command(
        clone_home_dir=clone_home,
        exec_cmd=exec_cmd,
        extra_args=extra_args,
        share_downloads=share_downloads,
        share_documents=share_documents,
        share_pictures=share_pictures,
        custom_mounts=custom_mounts,
        custom_env=custom_env,
        offline_mode=offline_mode,
    )

    if detach:
        log_f = open(log_file, "a", encoding="utf-8")
        log_f.write(f"\n--- Launching clone at {clone_dir.name} ---\nCommand: {' '.join(cmd)}\n")
        log_f.flush()

        process = subprocess.Popen(
            cmd,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

        # Brief pause to verify the process didn't instantly crash or fail to execute
        import time
        time.sleep(0.3)
        exit_code = process.poll()
        if exit_code is not None:
            log_f.close()
            error_hint = ""
            if log_file.exists():
                try:
                    lines = [ln.strip() for ln in log_file.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
                    if lines:
                        error_hint = f":\n{lines[-1]}"
                except Exception:
                    pass
            raise RuntimeError(f"Application exited immediately (exit code {exit_code}){error_hint}")

        write_pid_file(pid_file, process.pid)
        return process
    else:
        process = subprocess.Popen(cmd)
        write_pid_file(pid_file, process.pid)
        return process
