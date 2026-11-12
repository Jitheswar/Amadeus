#!/bin/bash
# Draw the desktop shell and the Amadeus panel in a headless compositor and save pictures to out/preview/.
# Runs in the builder container. The compositor here is a stand-in (sway) and the shell runs with
# stand-in values (AMADEUS_DEMO), so this shows how the shell looks, not how windows behave.
set -u
export HOME=/tmp/home XDG_RUNTIME_DIR=/tmp/xdg PATH=/tmp/fake:/src/desktop/bin:/src/ai/bin:$PATH
export AMADEUS_DEMO=1 WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 QT_QPA_PLATFORM=wayland
node=$(for r in /sys/class/drm/renderD*; do [[ $(<"$r/device/vendor") == 0x8086 ]] && echo "/dev/dri/${r##*/}"; done | head -1)
[[ -n $node ]] && export WLR_RENDER_DRM_DEVICE=$node || export WLR_RENDERER=pixman QT_QUICK_BACKEND=software
OUT=/out/preview; rm -rf $OUT; mkdir -p $OUT $HOME/.config/amadeus $XDG_RUNTIME_DIR /tmp/fake /usr/share/amadeus-os; chmod 700 $XDG_RUNTIME_DIR
ln -sfn /src/desktop/shell /usr/share/amadeus-os/shell
cp /src/desktop/theme/theme.json /usr/share/amadeus-os/theme.json
cp /src/desktop/shell/bar.default.json $HOME/.config/amadeus/bar.json

chmod +x /tmp/fake/*

cat >/tmp/sway.conf <<'S'
output HEADLESS-1 resolution 1920x1080 scale 1
default_border none
S
shot() { sleep "${2:-1.2}"; grim "$OUT/$1.png" && echo "saved $1.png"; }
run() {
  export WAYLAND_DISPLAY=wayland-1
  for _ in $(seq 50); do [[ -S $XDG_RUNTIME_DIR/wayland-1 ]] && break; sleep 0.1; done
  quickshell -p /usr/share/amadeus-os/shell >/tmp/shell.log 2>&1 &
  sleep 2.5
  notify-send -a "Amadeus" "Update finished" "64 packages updated. A snapshot was taken before and after."
  notify-send -a "LocalSend" "File received" "holiday-photos.zip from Pixel 9" -A open=Open -A show="Show in Files" >/dev/null 2>&1 &
  shot 1-desktop 1.5
  ipc() { quickshell ipc -p /usr/share/amadeus-os/shell call "$@"; }
  ipc shell popover calendar 960; shot 5-calendar 0.8
  ipc shell popover power 1780; shot 6-power 0.8
  ipc shell popover wifi 1650; shot 7-wifi 0.8
  ipc shell popover sudo 800; shot 8-sudo 0.8
  ipc shell popover "" 0; sleep 0.4

  printf 'Apps\nInstall\nRemove\nUpdate\nDefaults\n' | amadeus-pick Amadeus >/dev/null 2>&1 &
  shot 2-menu; quickshell ipc -p /usr/share/amadeus-os/shell call pick cancel

  printf '%s\n' firefox foot fuzzel fzf gamemode gamescope gimp git git-lfs github-cli gnome-keyring go grim gst-plugins-good gtk4 handbrake htop imv inkscape |
    amadeus-pick --multi --preview 'printf "Repository      : extra\nName            : %s\nVersion         : 2.47.1-1\nDescription     : The fast distributed version control system\nArchitecture    : x86_64\nURL             : https://git-scm.com/\nLicenses        : GPL-2.0-only\nDepends On      : curl  expat  perl  openssl  pcre2  zlib-ng\nDownload Size   : 7.4 MiB\nInstalled Size  : 29.1 MiB\nPackager        : Arch Linux\nBuild Date      : Tue 03 Nov 2026\n" "$1"' Install >/dev/null 2>&1 &
  shot 3-install 1.5; quickshell ipc -p /usr/share/amadeus-os/shell call pick cancel

  # The panel, answered by the scripted model from the end-to-end test.
  python3 - <<'PY' &
import sys, threading; sys.path.insert(0, "/src/test")
import e2e, pathlib
srv = e2e.HTTPServer(("127.0.0.1", 18080), e2e.Model)
pathlib.Path("/tmp/home/.config/amadeus/config.toml").write_text('[ai]\nprovider = "local"\n[providers.local]\ntype = "openai"\nbase_url = "http://127.0.0.1:18080/v1"\nmodel = "scripted"\n')
srv.serve_forever()
PY
  sleep 0.5
  ama daemon >/tmp/daemon.log 2>&1 &
  sleep 1.5
  ama panel window; sleep 0.6
  ama panel ask "Why is the fan loud?"; sleep 2.5
  ama panel ask "Tidy the Downloads folder E2E:slow"
  shot 4-panel 1.5
  tail -3 /tmp/shell.log
}
export -f shot run; export OUT
dbus-run-session -- bash -c 'sway -c /tmp/sway.conf >/tmp/sway.log 2>&1 & sleep 1; run; grep -iE "error|warn" /tmp/shell.log | head -8; pkill sway'
