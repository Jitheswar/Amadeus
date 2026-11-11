#!/bin/bash
# Amadeus installer.
#   ./install.sh            user-level: `ama` command, session daemon, palette shortcut. No root.
#   ./install.sh --system   additionally builds and installs the pacman package, which provides
#                           the root-owned helper that `ama root on` needs. Asks for sudo.
#   ./install.sh --remove   undo the user-level install.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
bin="$HOME/.local/bin" unit="$HOME/.config/systemd/user/amadeusd.service"

if [[ ${1:-} == --remove ]]; then
  systemctl --user disable --now amadeusd.service 2>/dev/null || true
  rm -f "$bin/ama" "$unit"
  PYTHONPATH="$here" /usr/bin/python3 -c 'from amadeus.tools import desktop; desktop.desktop_keybind({"keys": "SUPER + Z", "remove": True}, None)' 2>/dev/null || true
  echo "Removed. Config (~/.config/amadeus), apps and audit log were kept."
  exit 0
fi

for dep in python3 bwrap quickshell hyprctl git; do
  command -v "$dep" >/dev/null || { echo "missing dependency: $dep" >&2; exit 1; }
done

if [[ ${1:-} == --system ]]; then
  (cd "$here/packaging" && makepkg -f --noconfirm)
  sudo pacman -U --noconfirm "$here"/packaging/amadeus-*.pkg.tar.zst
  ama=/usr/bin/ama
  rm -f "$bin/ama" "$unit"          # the package's copies take over
  systemctl --user daemon-reload
else
  mkdir -p "$bin" "$(dirname "$unit")"
  ln -sfn "$here/bin/ama" "$bin/ama"
  ama="$bin/ama"
  sed "s|@AMA@|$ama|" "$here/systemd/amadeusd.service" >"$unit"
  systemctl --user daemon-reload
fi

# Stop a development daemon if one holds the socket, then start the service.
sock="$XDG_RUNTIME_DIR/amadeus/daemon.sock"
pid=$(ss -xlpH 2>/dev/null | grep -F "$sock" | grep -o 'pid=[0-9]*' | cut -d= -f2 | head -1 || true)
[[ -n ${pid:-} ]] && kill "$pid" 2>/dev/null && sleep 0.5
systemctl --user enable --now amadeusd.service
sleep 1

# Palette on SUPER+Z. Written to ~/.config/hypr/amadeus.lua; `ama undo` reverts it.
PYTHONPATH="$here" /usr/bin/python3 -c 'from amadeus.tools import desktop; print(desktop.desktop_keybind({"keys": "SUPER + Z", "description": "Amadeus", "command": "ama palette"}, None))'
"$ama" status
echo
echo "Ready. Press SUPER+Z, or run: ama \"what's using my battery?\""
