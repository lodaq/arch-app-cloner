# Arch App Cloner 🚀

A lightweight, high-performance application cloner for **Arch Linux** (and any Linux system with Bubblewrap). Run multiple independent instances of any application—such as browsers, messengers (Telegram, Discord, Slack), development tools, or games—with fully isolated storage, cookies, credentials, and settings.

---

## 🌟 Features

- **True Data & Credential Isolation**:
  Each clone gets a clean, sandboxed `$HOME` directory. Configs (`~/.config`), cache (`~/.cache`), local data (`~/.local/share`), and dotfiles are isolated. The host system data is completely protected.
- **Private D-Bus Session (`dbus-run-session`)**:
  Prevents single-instance apps (Discord, Telegram, Chrome, Brave, VS Code) from hijacking an already running instance on the host. Each clone runs as an independent master instance.
- **IPC & Process Namespace Unsharing**:
  Apps cannot detect each other through POSIX message queues, shared memory segments, or process tree inspection.
- **Native Performance & Hardware Acceleration**:
  Direct GPU passthrough (`/dev/dri`), Wayland and X11 display socket support, and PipeWire / PulseAudio sound passthrough without VM overhead.
- **Automatic Visual Badging**:
  Dynamically renders badged app icons with custom colors and identifier chips (e.g. "Work", "2", "Personal", "DEV") so you can distinguish instances in your dock, taskbar, or app launcher.
- **Seamless Desktop Integration**:
  Automatically generates Freedesktop `.desktop` files in `~/.local/share/applications/` with badged icons and right-click desktop actions ("Open Data Folder"). Instant compatibility with Rofi, Wofi, Fuzzel, GNOME, KDE, and Hyprland.
- **Shared Folder Passthrough**:
  Optionally mount host `~/Downloads`, `~/Documents`, or `~/Pictures` into the clone when needed.
- **Both Modern GUI and Rich CLI**:
  A sleek PySide6 dark-themed GUI and an intuitive command-line utility.
- **Portable Backups**:
  One-click export and import of clones (`.tar.gz`) for transferring profiles or backing up configurations.

---

## 🏗️ Architecture

```
Host System
┌────────────────────────────────────────────────────────┐
│ Real $HOME (/home/$USER)                               │
│ Real ~/.config, ~/.local/share, ~/.cache               │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Bubblewrap Sandbox (Clone Instance)             │  │
│  │ ├─ Mounts root / (read-only)                     │  │
│  │ ├─ Virtualizes $HOME -> ~/.local/share/.../home  │  │
│  │ ├─ Passthrough: Wayland, X11, PipeWire, /dev/dri │  │
│  │ ├─ Isolated D-Bus daemon (dbus-run-session)      │  │
│  │ └─ Namespaces: unshare IPC, unshare PID          │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 💻 CLI Usage

The CLI command is `app-cloner`:

### 1. Search installed applications
```bash
app-cloner search telegram
app-cloner search brave
app-cloner search discord
```

### 2. Create a clone
```bash
# Clone Brave for work with an emerald badge
app-cloner create brave --name "Brave (Work)" --color "#10b981" --badge "W" --share-downloads

# Clone Telegram for a secondary phone number
app-cloner create telegram-desktop --name "Telegram (Personal)" --color "#3b82f6" --badge "P"

# Clone Discord with isolated offline data
app-cloner create discord --name "Discord (Alt)" --color "#8b5cf6" --badge "2"
```

### 3. List and inspect clones
```bash
app-cloner list
# Or detailed status
app-cloner status brave-work
```

### 4. Run / Launch
```bash
# Launches detached in background
app-cloner run brave-work

# Pass extra flags directly to the cloned app
app-cloner run brave-work -- --incognito https://github.com
```

### 5. Stop running instance
```bash
app-cloner stop brave-work
```

### 6. Reset clone data (start fresh without deleting configuration)
```bash
app-cloner reset brave-work
```

### 7. Export and Import
```bash
# Export clone to backup archive
app-cloner export brave-work my-work-profile.tar.gz

# Import on another Arch machine
app-cloner import my-work-profile.tar.gz --id brave-restored
```

### 8. Open clone data directory
```bash
app-cloner open brave-work
```

---

## 🖥️ Graphical Interface (GUI)

Launch the GUI anytime with:
```bash
app-cloner-gui
# Or:
app-cloner gui
```
Or open **"App Cloner"** from your system app launcher (Rofi, Wofi, GNOME, KDE, Hyprland).

### GUI Features:
- **My Clones**: Browse all active and stopped clones, view disk footprint, launch or terminate with one click, or reset profile data.
- **Clone New App**: Search through all installed applications, customize clone name, choose from a color palette or custom color picker, set badge characters, and toggle folder sharing.
- **Live Preview**: See the badged icon update in real-time as you tweak colors and text.

---

## 📦 Packaging & Installation on Arch Linux

### Requirements
- Arch Linux
- `bubblewrap` (`pacman -S bubblewrap`)
- `dbus`
- `python` & `python-pyside6` (`pacman -S python-pyside6`)

### Build Arch Package (`PKGBUILD`)
```bash
makepkg -si
```

### Or Local User Installation
The CLI (`app-cloner`) and GUI (`app-cloner-gui`) launchers can be symlinked into `~/.local/bin`:
```bash
ln -sf $(pwd)/bin/app-cloner ~/.local/bin/app-cloner
ln -sf $(pwd)/bin/app-cloner-gui ~/.local/bin/app-cloner-gui
cp assets/app-cloner.png ~/.local/share/icons/hicolor/256x256/apps/app-cloner.png
cp arch-app-cloner.desktop ~/.local/share/applications/arch-app-cloner.desktop
update-desktop-database ~/.local/share/applications
```

---

## 🧪 Running Tests

The test suite covers application scanning, icon badging, sandbox command generation, and clone lifecycle management:
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```
