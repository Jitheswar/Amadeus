#!/bin/bash
# Draw the Amadeus panel and the login screen in a headless compositor and save pictures to out/preview/.
# Runs in the builder container. The compositor here is a stand-in (sway), so this shows how they look,
# not how windows behave. The desktop shell itself needs Hyprland: the VM test captures it instead.
set -u
export HOME=/tmp/home XDG_RUNTIME_DIR=/tmp/xdg PATH=/tmp/fake:/src/desktop/bin:/src/ai/bin:$PATH
export AMADEUS_DEMO=1 WLR_BACKENDS=headless WLR_LIBINPUT_NO_DEVICES=1 QT_QPA_PLATFORM=wayland
node=$(for r in /sys/class/drm/renderD*; do [[ $(<"$r/device/vendor") == 0x8086 ]] && echo "/dev/dri/${r##*/}"; done | head -1)
[[ -n $node ]] && export WLR_RENDER_DRM_DEVICE=$node || export WLR_RENDERER=pixman QT_QUICK_BACKEND=software
OUT=/out/preview; rm -rf $OUT; mkdir -p $OUT $HOME/.config/amadeus/current/theme $XDG_RUNTIME_DIR /tmp/fake; chmod 700 $XDG_RUNTIME_DIR
SYSTEM=/src/desktop/system/usr/share/amadeus
# The panel's colours, rendered from a theme the way amadeus-theme-set does.
theme() {
  python3 - "$SYSTEM/themes/$1/colors.toml" "$SYSTEM/default/themed/assistant.json.tpl" "$HOME/.config/amadeus/current/theme/assistant.json" <<'PY'
import re, sys, tomllib
colors = tomllib.load(open(sys.argv[1], "rb"))
text = re.sub(r"\{\{ (\w+) \}\}", lambda m: str(colors.get(m.group(1), "#888888")), open(sys.argv[2]).read())
open(sys.argv[3], "w").write(text)
PY
}
theme tokyo-night

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
  # A goal runs in the background and shows in Tasks, done only after its own check.
  ama goal "E2E:goal Keep my Downloads folder tidy" >/dev/null; sleep 3
  ama goal list | grep -q "done .*round 3" || { ama goal list; return 1; }
  ama panel tasks; shot 21-goals 1.0
  # Modes: a saved one sticks, full access only arms the confirmation.
  quickshell ipc -p /src/ai/shell/panel.qml call panel mode auto; sleep 0.6
  quickshell ipc -p /src/ai/shell/panel.qml call panel mode full
  shot 19-execution-mode 1.0
  ama panel state >"$OUT/mode-panel.json"
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert (d["mode"], d["savedMode"], d["confirmFull"]) == ("auto", "auto", True), d' "$OUT/mode-panel.json" || return 1
  [[ $(ama mode) == "mode: auto" ]] || return 1
  quickshell ipc -p /src/ai/shell/panel.qml call panel mode ask
  ama panel settings; quickshell ipc -p /src/ai/shell/panel.qml call panel agent codex-cli
  shot 11-agent-settings 1.0
  mkdir -p "$HOME/.local/share/amadeus/tasks"
  printf '%s\n' '{"id":"daily-report","label":"Daily workspace summary","prompt":"Summarise open work and suggest next steps.","trigger":"timer","calendar":"*-*-* 09:00:00","enabled":false,"provider":"","cooldown":300}' >"$HOME/.local/share/amadeus/tasks/daily-report.json"
  ama panel tasks
  shot 17-tasks 1.0
  ama panel context '{"source":"Settings","menu":"Display","query":"make text easier to read"}'
  shot 18-ai-context 1.0
  # The panel follows the active theme live.
  theme catppuccin-latte; shot 20-light-theme 1.2; theme tokyo-night
  ama panel hide
  # The login screen, in SDDM's own test mode (it authenticates nobody).
  sddm-greeter-qt6 --test-mode --theme "$SYSTEM/default/sddm/amadeus" >"$OUT/login.log" 2>&1 &
  greeter=$!
  sleep 3; kill -0 "$greeter" || { cat "$OUT/login.log"; return 1; }
  shot 15-login 0.5
  kill "$greeter"; wait "$greeter" 2>/dev/null
  if grep -iE "qml.*(error|is not a type|unavailable)|file not found" "$OUT/login.log"; then return 1; fi
  return 0
}
export -f shot run theme; export OUT SYSTEM
dbus-run-session -- bash -c 'sway -c /tmp/sway.conf >/tmp/sway.log 2>&1 & sleep 1; run; rc=$?; pkill sway; exit $rc'
