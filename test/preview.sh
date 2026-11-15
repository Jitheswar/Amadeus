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

cat >/tmp/fake/ama <<'A'
#!/bin/bash
if [[ ${1:-} == usage ]]; then
  printf '%s\n' '{"recentRequests":18,"providers":[{"name":"codex-cli","label":"Codex","kind":"Subscription","plan":"Plus","status":"Current limits","limits":[{"label":"Session","used":0.28,"resets":""},{"label":"Weekly","used":0.46,"resets":""}]},{"name":"claude-cli","label":"Claude Code","kind":"Subscription","plan":"Pro","status":"Current limits","limits":[{"label":"Session","used":0.12,"resets":""}]}]}'
else
  exec /src/ai/bin/ama "$@"
fi
A
chmod +x /tmp/fake/*

cat >/tmp/sway.conf <<'S'
output HEADLESS-1 resolution 1920x1080 scale 1
default_border none
S
shot() { sleep "${2:-1.2}"; grim "$OUT/$1.png" && echo "saved $1.png"; }
run() {
  export WAYLAND_DISPLAY=wayland-1
  export SWAYSOCK=$(python3 -c 'import glob; print(glob.glob("/tmp/xdg/sway-ipc.*.sock")[0])')
  for _ in $(seq 50); do [[ -S $XDG_RUNTIME_DIR/wayland-1 ]] && break; sleep 0.1; done
  quickshell -p /usr/share/amadeus-os/shell >/tmp/shell.log 2>&1 &
  sleep 2.5
  notify-send -a "Amadeus" "Update finished" "64 packages updated. A snapshot was taken before and after."
  notify-send -a "LocalSend" "File received" "holiday-photos.zip from Pixel 9" -A open=Open -A show="Show in Files" >/dev/null 2>&1 &
  shot 1-desktop 1.5
  quickshell ipc -p /usr/share/amadeus-os/shell call shell state >"$OUT/desktop-state.json"
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["audioInputs"] == ["Built-in microphone"]; assert d["audioOutputs"] == ["Built-in speakers", "HDMI output"]' "$OUT/desktop-state.json" || return 1
  ipc() { quickshell ipc -p /usr/share/amadeus-os/shell call "$@"; }
  ipc shell popover calendar 960; shot 5-calendar 0.8
  ipc shell popover power 1780; shot 6-power 0.8
  ipc shell popover wifi 1650; shot 7-wifi 0.8
  ipc shell popover sudo 800; shot 8-sudo 0.8
  ipc shell popover volume 1750; shot 9-volume 0.8
  ipc shell popover display 1660; shot 10-display 0.8
  ipc shell popover agents 1750; shot 12-agent-usage 1.2
  ipc shell popover "" 0; sleep 0.4

  amadeus-menu >/dev/null 2>&1 &
  shot 2-menu
  ipc shell state >"$OUT/menu-before.json"
  # Headless sway has no pointer device. Synthetic hover/scroll is covered in tst_menu.qml;
  # this checks that separate real key events each advance the actual picker once.
  wtype -s 150 -k Down -s 150 -k Down; sleep 0.4
  ipc shell state >"$OUT/menu-keyboard.json"
  python3 -c 'import json,sys; a,b=[json.load(open(p)) for p in sys.argv[1:]]; assert b["pickerIndex"] == a["pickerIndex"]+2, (a,b)' "$OUT/menu-before.json" "$OUT/menu-keyboard.json" || return 1
  quickshell ipc -p /usr/share/amadeus-os/shell call pick cancel

  printf '%s\n' firefox foot fuzzel fzf gamemode gamescope gimp git git-lfs github-cli gnome-keyring go grim gst-plugins-good gtk4 handbrake htop imv inkscape |
    amadeus-pick --multi --preview 'printf "Repository      : extra\nName            : %s\nVersion         : 2.47.1-1\nDescription     : The fast distributed version control system\nArchitecture    : x86_64\nURL             : https://git-scm.com/\nLicenses        : GPL-2.0-only\nDepends On      : curl  expat  perl  openssl  pcre2  zlib-ng\nDownload Size   : 7.4 MiB\nInstalled Size  : 29.1 MiB\nPackager        : Arch Linux\nBuild Date      : Tue 03 Nov 2026\n" "$1"' Install >/dev/null 2>&1 &
  shot 3-install 1.5; quickshell ipc -p /usr/share/amadeus-os/shell call pick cancel

  printf 'Only this menu option\n' | amadeus-pick Chat >/dev/null 2>&1 &
  sleep 0.8; ipc pick query sound; shot 13-universal-search 1.2; ipc pick cancel

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
  ama panel settings; quickshell ipc -p /src/ai/shell/panel.qml call panel agent codex-cli
  shot 11-agent-settings 1.0
  mkdir -p "$HOME/.local/share/amadeus/tasks"
  printf '%s\n' '{"id":"daily-report","label":"Daily workspace summary","prompt":"Summarise open work and suggest next steps.","trigger":"timer","calendar":"*-*-* 09:00:00","enabled":false,"provider":"","cooldown":300}' >"$HOME/.local/share/amadeus/tasks/daily-report.json"
  ama panel tasks
  shot 17-tasks 1.0
  ama panel context '{"source":"Settings","menu":"Display","query":"make text easier to read"}'
  shot 18-ai-context 1.0
  printf '%s\n' '{"font_size":20}' >"$HOME/.config/amadeus/theme.json"
  shot 14-large-text 1.0
  ipc shell state >"$OUT/large-text-shell.json"
  ama panel state >"$OUT/large-text-panel.json"
  python3 -c 'import json,sys; assert all(json.load(open(p))["fontSize"] == 20 for p in sys.argv[1:])' "$OUT/large-text-shell.json" "$OUT/large-text-panel.json" || return 1
  tail -3 /tmp/shell.log
  ama panel hide
  quickshell ipc -p /usr/share/amadeus-os/shell call shell popover "" 0
  pkill -f '^quickshell -p /usr/share/amadeus-os/shell$'
  mkdir -p /run/dbus
  dbus-uuidgen --ensure=/etc/machine-id
  dbus-daemon --system --fork
  /usr/lib/accounts-daemon >"$OUT/accounts.log" 2>&1 &
  sleep 0.5
  # The same GTK/Cage greeter as a real login, with upstream's non-authenticating demo mode.
  python3 /src/desktop/greeter/render-theme.py /src/desktop/theme/theme.json /usr/share/amadeus-os/greeter
  mkdir -p /var/lib/regreet
  python3 /src/desktop/greeter/profiles.py /var/lib/regreet/state.toml
  mkdir -p /usr/share/amadeus-os/greeter/wayland-sessions
  cp /src/desktop/greeter/wayland-sessions/*.desktop /usr/share/amadeus-os/greeter/wayland-sessions/
  WLR_BACKENDS=wayland GTK_USE_PORTAL=0 GDK_DEBUG=no-portals XDG_DATA_DIRS=/usr/share/amadeus-os/greeter:/usr/share cage -d -- regreet --demo --verbose --config /usr/share/amadeus-os/greeter/regreet.toml --style /usr/share/amadeus-os/greeter/regreet.css >"$OUT/greeter.log" 2>&1 &
  greeter=$!
  sleep 3; kill -0 "$greeter" && pgrep -x regreet >/dev/null || return 1
  shot 15-login 0.5
  kill "$greeter"; wait "$greeter" 2>/dev/null
  WLR_BACKENDS=wayland GTK_USE_PORTAL=0 GDK_DEBUG=no-portals XDG_DATA_DIRS=/usr/share/amadeus-os/greeter:/usr/share cage -d -- regreet --demo --verbose --config /usr/share/amadeus-os/greeter/try.toml --style /usr/share/amadeus-os/greeter/regreet.css >"$OUT/try-greeter.log" 2>&1 &
  greeter=$!
  sleep 3; kill -0 "$greeter" && pgrep -x regreet >/dev/null || return 1
  shot 16-try-login 0.5
  kill "$greeter"; wait "$greeter" 2>/dev/null
  if grep -iE "(panicked|theme pars(er|ing) error|could not load|failed to load (css|background))" "$OUT/greeter.log" "$OUT/try-greeter.log"; then return 1; fi
  return 0
}
export -f shot run; export OUT
dbus-run-session -- bash -c 'sway -c /tmp/sway.conf >/tmp/sway.log 2>&1 & sleep 1; run; rc=$?; grep -iE "error|warn" /tmp/shell.log | head -8; pkill sway; exit $rc'
