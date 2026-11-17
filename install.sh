#!/usr/bin/env bash
set -e

echo "=== Installing Arch App Cloner ==="

# Check for required system dependencies
MISSING_PKGS=()
for cmd in bwrap dbus-run-session; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING_PKGS+=("$cmd")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo "Warning: The following required dependencies are missing: ${MISSING_PKGS[*]}"
    echo "On Arch Linux, run: sudo pacman -S bubblewrap dbus python python-pyside6"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APPS_DIR="${HOME}/.local/share/applications"
ICONS_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"

mkdir -p "$BIN_DIR" "$APPS_DIR" "$ICONS_DIR"

# Link binaries
ln -sf "${SCRIPT_DIR}/bin/app-cloner" "${BIN_DIR}/app-cloner"
ln -sf "${SCRIPT_DIR}/bin/app-cloner-gui" "${BIN_DIR}/app-cloner-gui"

# Install icon and desktop file
cp "${SCRIPT_DIR}/assets/app-cloner.png" "${ICONS_DIR}/app-cloner.png"
cp "${SCRIPT_DIR}/arch-app-cloner.desktop" "${APPS_DIR}/arch-app-cloner.desktop"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APPS_DIR"
fi

echo "✔ Arch App Cloner installed successfully!"
echo "  CLI binary: ${BIN_DIR}/app-cloner"
echo "  GUI binary: ${BIN_DIR}/app-cloner-gui"
echo ""
echo "Ensure ~/.local/bin is in your PATH. If not, add this to your ~/.bashrc or ~/.zshrc:"
echo '  export PATH="$HOME/.local/bin:$PATH"'
