"""Clone lifecycle manager for Arch App Cloner."""

import json
import os
import shlex
import shutil
import subprocess
import tarfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app_cloner.apps import AppInfo, find_app, scan_installed_apps
from app_cloner.badge import create_badged_icon
from app_cloner.sandbox import launch_in_sandbox
from app_cloner.utils import (
    clear_pid_file,
    get_clones_dir,
    get_desktop_dir,
    get_directory_size,
    is_pid_alive,
    kill_process,
    read_pid_file,
    slugify,
)


@dataclass
class CloneConfig:
    """Configuration and metadata for an isolated app clone."""
    id: str
    app_name: str
    desktop_id: str
    exec_cmd: str
    clone_name: str
    badge_color: str = "#3b82f6"
    badge_text: str = ""
    icon_path: str = ""
    share_downloads: bool = False
    share_documents: bool = False
    share_pictures: bool = False
    offline_mode: bool = False
    custom_env: Dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    last_launched: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloneConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class CloneManager:
    """Manages creation, lifecycle, isolation, and desktop integration of app clones."""

    def __init__(self, clones_dir: Optional[Path] = None):
        self.clones_dir = clones_dir or get_clones_dir()
        self.desktop_dir = get_desktop_dir()

    def _clone_path(self, clone_id: str) -> Path:
        return self.clones_dir / clone_id

    def _config_path(self, clone_id: str) -> Path:
        return self._clone_path(clone_id) / "config.json"

    def _desktop_file_path(self, clone_id: str) -> Path:
        return self.desktop_dir / f"arch-cloner-{clone_id}.desktop"

    def _update_desktop_db(self) -> None:
        """Update desktop database so desktop launchers pick up new/removed entries."""
        try:
            subprocess.run(
                ["update-desktop-database", str(self.desktop_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def create_clone(
        self,
        app_info: AppInfo,
        clone_name: str,
        clone_id: Optional[str] = None,
        exec_cmd: Optional[str] = None,
        badge_color: str = "#3b82f6",
        badge_text: str = "",
        share_downloads: bool = False,
        share_documents: bool = False,
        share_pictures: bool = False,
        offline_mode: bool = False,
        custom_env: Optional[Dict[str, str]] = None,
    ) -> CloneConfig:
        """Create a new isolated application clone."""
        if not clone_id:
            base_slug = slugify(f"{app_info.name}-{clone_name}")
            clone_id = base_slug
            counter = 1
            while self._clone_path(clone_id).exists():
                clone_id = f"{base_slug}-{counter}"
                counter += 1
        else:
            clone_id = slugify(clone_id)

        clone_path = self._clone_path(clone_id)
        if clone_path.exists():
            raise FileExistsError(f"Clone with ID '{clone_id}' already exists.")

        # Create clone directory hierarchy
        clone_path.mkdir(parents=True, exist_ok=True)
        clone_home = clone_path / "data" / "home"
        clone_home.mkdir(parents=True, exist_ok=True)

        # Generate badged icon
        icon_dest = clone_path / "icon.png"
        create_badged_icon(
            src_icon_path=app_info.icon_path,
            dest_path=icon_dest,
            badge_color=badge_color,
            badge_text=badge_text or (clone_name[:2].upper() if len(clone_name) <= 3 else clone_name[:1].upper()),
            app_name=app_info.name,
        )

        now = datetime.now().isoformat(timespec="seconds")
        config = CloneConfig(
            id=clone_id,
            app_name=app_info.name,
            desktop_id=app_info.desktop_id,
            exec_cmd=exec_cmd or app_info.clean_exec,
            clone_name=clone_name,
            badge_color=badge_color,
            badge_text=badge_text,
            icon_path=str(icon_dest),
            share_downloads=share_downloads,
            share_documents=share_documents,
            share_pictures=share_pictures,
            offline_mode=offline_mode,
            custom_env=custom_env or {},
            created_at=now,
        )

        # Save config.json
        with open(self._config_path(clone_id), "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)

        # Create .desktop file
        self._write_desktop_file(config)
        self._update_desktop_db()

        return config

    def _write_desktop_file(self, config: CloneConfig) -> None:
        """Generate and save the .desktop entry for this clone."""
        desktop_file = self._desktop_file_path(config.id)
        clone_home = self._clone_path(config.id) / "data" / "home"

        # Determine full path to app-cloner CLI or fallback
        app_cloner_bin = shutil.which("app-cloner") or f"python3 -m app_cloner.cli"

        content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name={config.clone_name}
Comment=Cloned instance of {config.app_name} (Arch App Cloner)
Exec={app_cloner_bin} run {config.id} %U
Icon={config.icon_path}
Terminal=false
Categories=Utility;ArchAppCloner;
StartupWMClass=arch-cloner-{config.id}
Actions=OpenDataDir;

[Desktop Action OpenDataDir]
Name=Open Data Folder
Exec=xdg-open {clone_home}
"""
        with open(desktop_file, "w", encoding="utf-8") as f:
            f.write(content)

    def get_clone(self, clone_id: str) -> Optional[CloneConfig]:
        """Load configuration for a specific clone ID."""
        cfg_file = self._config_path(clone_id)
        if not cfg_file.exists():
            return None
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CloneConfig.from_dict(data)
        except Exception:
            return None

    def list_clones(self) -> List[Tuple[CloneConfig, Dict[str, Any]]]:
        """List all clones with their active status and disk footprint."""
        results = []
        if not self.clones_dir.exists():
            return results

        for child in sorted(self.clones_dir.iterdir()):
            if not child.is_dir():
                continue
            cfg = self.get_clone(child.name)
            if not cfg:
                continue

            pid_file = child / "run.pid"
            pid = read_pid_file(pid_file)
            is_running = pid is not None

            bytes_used, size_str = get_directory_size(child / "data")

            status = {
                "is_running": is_running,
                "pid": pid,
                "disk_bytes": bytes_used,
                "disk_size": size_str,
                "path": str(child),
                "has_desktop_shortcut": self._desktop_file_path(cfg.id).exists(),
            }
            results.append((cfg, status))

        return results

    def launch(
        self,
        clone_id: str,
        extra_args: Optional[List[str]] = None,
        detach: bool = True,
    ) -> Tuple[bool, str, Optional[int]]:
        """Launch a clone inside bubblewrap sandbox."""
        config = self.get_clone(clone_id)
        if not config:
            return False, f"Clone '{clone_id}' does not exist.", None

        # Validate that the executable command exists
        parts = shlex.split(config.exec_cmd) if config.exec_cmd else []
        main_bin = parts[0] if parts else ""
        if not (shutil.which(main_bin) or (os.path.isabs(main_bin) and os.path.isfile(main_bin) and os.access(main_bin, os.X_OK))):
            return False, (
                f"Cannot launch '{config.clone_name}':\n\n"
                f"The command '{main_bin}' was not found on your system.\n\n"
                f"Please install '{config.app_name}' or edit the clone's execution command."
            ), None

        clone_path = self._clone_path(clone_id)
        pid_file = clone_path / "run.pid"
        existing_pid = read_pid_file(pid_file)
        if existing_pid:
            return True, f"Clone '{config.clone_name}' is already running (PID: {existing_pid}).", existing_pid

        # Update last launched
        config.last_launched = datetime.now().isoformat(timespec="seconds")
        with open(self._config_path(clone_id), "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)

        try:
            proc = launch_in_sandbox(
                clone_dir=clone_path,
                exec_cmd=config.exec_cmd,
                extra_args=extra_args,
                share_downloads=config.share_downloads,
                share_documents=config.share_documents,
                share_pictures=config.share_pictures,
                custom_env=config.custom_env,
                offline_mode=config.offline_mode,
                detach=detach,
            )
            return True, f"Launched '{config.clone_name}' successfully.", proc.pid
        except Exception as e:
            clear_pid_file(pid_file)
            return False, f"Failed to launch clone '{clone_id}': {e}", None

    def update_clone(
        self,
        clone_id: str,
        clone_name: Optional[str] = None,
        exec_cmd: Optional[str] = None,
        badge_color: Optional[str] = None,
        badge_text: Optional[str] = None,
        share_downloads: Optional[bool] = None,
        share_documents: Optional[bool] = None,
        share_pictures: Optional[bool] = None,
        offline_mode: Optional[bool] = None,
    ) -> Tuple[bool, str, Optional[CloneConfig]]:
        """Update settings and configuration for an existing clone."""
        config = self.get_clone(clone_id)
        if not config:
            return False, f"Clone '{clone_id}' not found.", None

        if clone_name:
            config.clone_name = clone_name
        if exec_cmd:
            config.exec_cmd = exec_cmd.strip()
        if badge_color:
            config.badge_color = badge_color
        if badge_text is not None:
            config.badge_text = badge_text
        if share_downloads is not None:
            config.share_downloads = share_downloads
        if share_documents is not None:
            config.share_documents = share_documents
        if share_pictures is not None:
            config.share_pictures = share_pictures
        if offline_mode is not None:
            config.offline_mode = offline_mode

        # Regenerate icon if badge changed
        if badge_color or badge_text is not None:
            base_app = find_app(config.desktop_id) or find_app(config.app_name)
            src_icon = base_app.icon_path if base_app else None
            create_badged_icon(
                src_icon_path=src_icon,
                dest_path=Path(config.icon_path),
                badge_color=config.badge_color,
                badge_text=config.badge_text or (config.clone_name[:2].upper() if len(config.clone_name) <= 3 else config.clone_name[:1].upper()),
                app_name=config.app_name,
            )

        with open(self._config_path(clone_id), "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2)

        self._write_desktop_file(config)
        self._update_desktop_db()
        return True, f"Clone '{config.clone_name}' updated successfully.", config

    def stop(self, clone_id: str) -> Tuple[bool, str]:
        """Stop a running clone instance."""
        clone_path = self._clone_path(clone_id)
        if not clone_path.exists():
            return False, f"Clone '{clone_id}' not found."

        pid_file = clone_path / "run.pid"
        pid = read_pid_file(pid_file)
        if not pid:
            return False, f"Clone '{clone_id}' is not currently running."

        stopped = kill_process(pid)
        clear_pid_file(pid_file)
        if stopped:
            return True, f"Stopped clone '{clone_id}' (PID {pid})."
        else:
            return False, f"Could not stop process {pid}."

    def reset_data(self, clone_id: str) -> Tuple[bool, str]:
        """Clear all stored data/cache/credentials for a clone, keeping config."""
        config = self.get_clone(clone_id)
        if not config:
            return False, f"Clone '{clone_id}' not found."

        self.stop(clone_id)

        clone_home = self._clone_path(clone_id) / "data" / "home"
        if clone_home.exists():
            shutil.rmtree(clone_home, ignore_errors=True)
            clone_home.mkdir(parents=True, exist_ok=True)

        return True, f"All data and credentials for '{config.clone_name}' have been reset."

    def delete_clone(self, clone_id: str, keep_data: bool = False) -> Tuple[bool, str]:
        """Delete an app clone and remove its desktop integration."""
        clone_path = self._clone_path(clone_id)
        if not clone_path.exists():
            return False, f"Clone '{clone_id}' not found."

        self.stop(clone_id)

        # Remove desktop launcher
        desktop_file = self._desktop_file_path(clone_id)
        if desktop_file.exists():
            desktop_file.unlink(missing_ok=True)
            self._update_desktop_db()

        if keep_data:
            # Only remove config and icon
            (clone_path / "config.json").unlink(missing_ok=True)
            (clone_path / "icon.png").unlink(missing_ok=True)
            (clone_path / "run.pid").unlink(missing_ok=True)
            return True, f"Clone '{clone_id}' removed (data preserved in {clone_path / 'data'})."
        else:
            shutil.rmtree(clone_path, ignore_errors=True)
            return True, f"Clone '{clone_id}' deleted completely."

    def export_clone(self, clone_id: str, output_tar: Path) -> Tuple[bool, str]:
        """Export a clone (config, icon, and data) to a portable .tar.gz archive."""
        clone_path = self._clone_path(clone_id)
        if not clone_path.exists():
            return False, f"Clone '{clone_id}' not found."

        output_tar = Path(output_tar)
        output_tar.parent.mkdir(parents=True, exist_ok=True)

        with tarfile.open(output_tar, "w:gz") as tar:
            tar.add(clone_path, arcname=clone_id)

        return True, f"Clone '{clone_id}' exported to {output_tar}"

    def import_clone(self, input_tar: Path, new_clone_id: Optional[str] = None) -> Tuple[bool, str, Optional[CloneConfig]]:
        """Import a clone from a .tar.gz archive."""
        input_tar = Path(input_tar)
        if not input_tar.exists():
            return False, f"Archive {input_tar} does not exist.", None

        with tarfile.open(input_tar, "r:gz") as tar:
            members = tar.getmembers()
            if not members:
                return False, "Archive is empty.", None
            root_dir_name = members[0].name.split("/")[0]
            target_id = slugify(new_clone_id or root_dir_name)
            target_path = self._clone_path(target_id)

            if target_path.exists():
                return False, f"Target clone ID '{target_id}' already exists.", None

            # Extract archive
            tar.extractall(path=self.clones_dir)

            # If extracted dir name doesn't match target_id, rename
            extracted_path = self.clones_dir / root_dir_name
            if extracted_path != target_path:
                extracted_path.rename(target_path)

        cfg = self.get_clone(target_id)
        if not cfg:
            return False, "Invalid clone archive: config.json missing.", None

        # Update ID in config if changed
        if cfg.id != target_id:
            cfg.id = target_id
            cfg.icon_path = str(target_path / "icon.png")
            with open(self._config_path(target_id), "w", encoding="utf-8") as f:
                json.dump(cfg.to_dict(), f, indent=2)

        self._write_desktop_file(cfg)
        self._update_desktop_db()
        return True, f"Clone '{cfg.clone_name}' ({target_id}) imported successfully.", cfg
