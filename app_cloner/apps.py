"""Desktop application scanner and icon resolver for Arch Linux."""

import glob
import os
import re
import shlex
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app_cloner.utils import clean_desktop_exec


def is_command_available(cmd_name: str) -> bool:
    """Check if command is an executable file or found in PATH."""
    if not cmd_name:
        return False
    cmd_name = cmd_name.strip()
    if (cmd_name.startswith('"') and cmd_name.endswith('"')) or (cmd_name.startswith("'") and cmd_name.endswith("'")):
        cmd_name = cmd_name[1:-1]
    if os.path.isabs(cmd_name):
        return os.path.isfile(cmd_name) and os.access(cmd_name, os.X_OK)
    return shutil.which(cmd_name) is not None


def clean_cmd_parts_available(clean_exec: str) -> bool:
    """Extract primary binary from exec string and verify it is available."""
    if not clean_exec:
        return False
    try:
        parts = shlex.split(clean_exec)
        first_token = parts[0] if parts else ""
    except Exception:
        first_token = clean_exec.split()[0] if clean_exec else ""
    # Strip env prefix if exec is like "env FOO=BAR app"
    if first_token == "env" and len(parts) > 1:
        for p in parts[1:]:
            if "=" not in p and not p.startswith("-"):
                first_token = p
                break
    return is_command_available(first_token)


@dataclass
class AppInfo:
    """Represents an installed application discovered from desktop files."""
    desktop_id: str
    desktop_path: str
    name: str
    exec: str
    clean_exec: str
    icon_name: str = ""
    icon_path: Optional[str] = None
    categories: List[str] = field(default_factory=list)
    comment: str = ""
    terminal: bool = False
    startup_wm_class: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "desktop_id": self.desktop_id,
            "desktop_path": self.desktop_path,
            "name": self.name,
            "exec": self.exec,
            "clean_exec": self.clean_exec,
            "icon_name": self.icon_name,
            "icon_path": self.icon_path,
            "categories": self.categories,
            "comment": self.comment,
            "terminal": self.terminal,
            "startup_wm_class": self.startup_wm_class,
        }


class IconResolver:
    """Discovers and resolves icon names to high-resolution PNG or SVG files."""

    def __init__(self):
        self._cache: Dict[str, Optional[str]] = {}
        self.search_roots = [
            Path.home() / ".local" / "share" / "icons",
            Path.home() / ".icons",
            Path("/usr/share/icons"),
            Path("/usr/share/pixmaps"),
            Path("/usr/local/share/icons"),
            Path("/var/lib/flatpak/exports/share/icons"),
        ]

    def resolve(self, icon_name: str) -> Optional[str]:
        """Resolve icon_name or path to an absolute image file path."""
        if not icon_name:
            return None
        icon_name = icon_name.strip()
        if icon_name in self._cache:
            return self._cache[icon_name]

        # Case 1: Already an absolute path
        if os.path.isabs(icon_name) and os.path.exists(icon_name):
            self._cache[icon_name] = icon_name
            return icon_name

        # Case 2: Pixmaps direct match (with or without extension)
        pixmaps = Path("/usr/share/pixmaps")
        if pixmaps.exists():
            for ext in ["", ".png", ".svg", ".xpm"]:
                candidate = pixmaps / f"{icon_name}{ext}"
                if candidate.exists() and candidate.is_file():
                    res = str(candidate)
                    self._cache[icon_name] = res
                    return res

        # Case 3: Search standard icon hierarchies
        # Preference: 256x256, 512x512, 128x128, scalable, then any
        preferred_sizes = ["512x512", "256x256", "128x128", "scalable", "96x96", "64x64", "48x48", "32x32"]
        name_no_ext = re.sub(r"\.(png|svg|xpm|ico)$", "", icon_name)

        found_candidates: List[str] = []
        for root in self.search_roots:
            if not root.exists():
                continue
            # Search hicolor theme first, then all
            for theme in ["hicolor", "*"]:
                theme_dir = root / theme
                if not theme_dir.exists() and theme != "*":
                    continue
                for size in preferred_sizes:
                    pattern = f"{root}/{theme}/{size}/*/{name_no_ext}.*"
                    matches = glob.glob(pattern)
                    if matches:
                        res = matches[0]
                        self._cache[icon_name] = res
                        return res
                # Broader glob within theme
                matches = glob.glob(f"{root}/{theme}/*/*/{name_no_ext}.*")
                if matches:
                    found_candidates.extend(matches)

        if found_candidates:
            # Pick the candidate with the highest size or SVG
            def rank_icon(p: str) -> int:
                if "scalable" in p or p.endswith(".svg"):
                    return 1000
                for sz in [512, 256, 128, 96, 64, 48, 32]:
                    if f"{sz}x{sz}" in p:
                        return sz
                return 0

            found_candidates.sort(key=rank_icon, reverse=True)
            res = found_candidates[0]
            self._cache[icon_name] = res
            return res

        self._cache[icon_name] = None
        return None


def parse_desktop_file(file_path: Path, icon_resolver: IconResolver) -> Optional[AppInfo]:
    """Parse a single .desktop file into an AppInfo object."""
    if not file_path.exists() or not file_path.is_file():
        return None

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return None

    in_main_section = False
    data: Dict[str, str] = {}

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            if line == "[Desktop Entry]":
                in_main_section = True
            else:
                in_main_section = False
            continue

        if in_main_section and "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            # Only save the first occurrence of standard un-localized key
            if key not in data and not key.endswith("]"):
                data[key] = val

    # Verify essentials
    if data.get("Type") != "Application":
        return None
    if data.get("NoDisplay", "").lower() == "true":
        return None
    if data.get("Hidden", "").lower() == "true":
        return None

    # Check TryExec if specified by the desktop entry
    try_exec = data.get("TryExec")
    if try_exec and not is_command_available(try_exec):
        return None

    name = data.get("Name")
    exec_cmd = data.get("Exec")
    if not name or not exec_cmd:
        return None

    clean_exec = clean_desktop_exec(exec_cmd)
    if not clean_cmd_parts_available(clean_exec):
        return None

    # Don't re-index app-cloner clones to prevent clutter
    if file_path.name.startswith("arch-cloner-"):
        return None

    icon_name = data.get("Icon", "")
    icon_path = icon_resolver.resolve(icon_name) if icon_name else None

    raw_cats = data.get("Categories", "")
    categories = [c.strip() for c in raw_cats.split(";") if c.strip()]
    terminal = data.get("Terminal", "").lower() == "true"
    startup_wm_class = data.get("StartupWMClass")

    return AppInfo(
        desktop_id=file_path.name,
        desktop_path=str(file_path),
        name=name,
        exec=exec_cmd,
        clean_exec=clean_desktop_exec(exec_cmd),
        icon_name=icon_name,
        icon_path=icon_path,
        categories=categories,
        comment=data.get("Comment", ""),
        terminal=terminal,
        startup_wm_class=startup_wm_class,
    )


def scan_installed_apps() -> List[AppInfo]:
    """Scan all standard application desktop directories and return sorted list of apps."""
    search_dirs = [
        Path.home() / ".local" / "share" / "applications",
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
        Path("/var/lib/flatpak/exports/share/applications"),
        Path.home() / ".local" / "share" / "flatpak" / "exports" / "share" / "applications",
    ]

    resolver = IconResolver()
    apps_by_id: Dict[str, AppInfo] = {}

    for app_dir in search_dirs:
        if not app_dir.exists():
            continue
        for desktop_file in sorted(app_dir.glob("*.desktop")):
            if desktop_file.name in apps_by_id:
                continue
            app_info = parse_desktop_file(desktop_file, resolver)
            if app_info:
                apps_by_id[desktop_file.name] = app_info

    # Sort alphabetically by display name
    return sorted(apps_by_id.values(), key=lambda a: a.name.lower())


def find_app(query: str, apps: Optional[List[AppInfo]] = None) -> Optional[AppInfo]:
    """Find an app matching query (by exact desktop_id, binary name, or fuzzy name)."""
    if apps is None:
        apps = scan_installed_apps()

    q = query.strip().lower()

    # 1. Exact desktop_id match
    for app in apps:
        if app.desktop_id.lower() == q or app.desktop_id.lower() == f"{q}.desktop":
            return app

    # 2. Exact name match
    for app in apps:
        if app.name.lower() == q:
            return app

    # 3. Exact clean exec command match (first token)
    for app in apps:
        first_token = app.clean_exec.split()[0] if app.clean_exec else ""
        binary_name = Path(first_token).name.lower()
        if binary_name == q:
            return app

    # 4. Substring in name
    for app in apps:
        if q in app.name.lower():
            return app

    # 5. Substring in desktop_id
    for app in apps:
        if q in app.desktop_id.lower():
            return app

    return None
