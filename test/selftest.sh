#!/bin/bash
# First-boot self-test for the VM harness. Runs as root on the installed system; reports to the answers disk.
exec > >(tee /dev/ttyS0 /var/log/amadeus-selftest.log) 2>&1
U=@USER@; UID_=$(id -u $U); R=/run/user/$UID_
pass=0 fail=0
ok()   { echo "PASS  $1"; pass=$((pass+1)); }
bad()  { echo "FAIL  $1 ${2:+— $2}"; fail=$((fail+1)); }
# Each check gets 90 seconds; a check that hangs fails instead of stopping the whole run.
t()    { local name=$1; shift; local out; if out=$(timeout 90 bash -c '"$@"' _ "$@" 2>&1 </dev/null); then ok "$name"; else bad "$name" "$(echo "$out" | tail -2 | tr '\n' ' ')"; fi; }
as()   { sudo -u $U env XDG_RUNTIME_DIR=$R DBUS_SESSION_BUS_ADDRESS=unix:path=$R/bus WAYLAND_DISPLAY=wayland-1 HYPRLAND_INSTANCE_SIGNATURE="$(ls $R/hypr 2>/dev/null | head -1)" HOME=/home/$U PATH=/usr/bin "$@"; }
export U R; export -f as
echo "AMADEUS-SELFTEST-BEGIN"
for _ in $(seq 60); do [[ -S $R/amadeus/daemon.sock ]] && pgrep -x Hyprland >/dev/null && break; sleep 2; done
sleep 8
mkdir -p /mnt/auto; mount /dev/disk/by-label/AMADEUSAUTO /mnt/auto 2>/dev/null
STAGE=$(cat /mnt/auto/stage 2>/dev/null || echo 1)
healthy() {
  t "root is btrfs subvolume @"                bash -c 'findmnt -no FSTYPE,OPTIONS / | grep -qE "btrfs.*subvol=/@(,|$)"'
  t "no failed system units"                   bash -c '[[ -z $(systemctl --failed --no-legend) ]]'
  t "Hyprland is running"                      pgrep -x Hyprland
  t "kernel on the boot partition matches"     bash -c 'cmp /boot/vmlinuz-linux-cachyos /usr/lib/modules/*/vmlinuz'
  t "snapshot history carried over"            bash -c 'snapper -c root list | grep -q "rollback-test"'
  t "previous system kept"                     bash -c 'amadeus-rollback list | grep -q before-rollback'
}
finish() {
  echo "AMADEUS-SELFTEST-END stage=$STAGE pass=$pass fail=$fail"
  sleep 1
  if [[ $STAGE == 1 ]]; then
    as grim /tmp/desktop.png 2>/dev/null && cp /tmp/desktop.png /mnt/auto/desktop.png
    journalctl -b -p warning --no-pager | tail -60 >/mnt/auto/journal-warnings.log
  fi
  (( fail )) && { as hyprctl monitors; as hyprctl configerrors; journalctl -b -p warning --no-pager | tail -60; } >/mnt/auto/desktop-debug.log 2>&1
  cp /var/log/amadeus-selftest.log /mnt/auto/selftest-$STAGE.log
  echo "$1" >/mnt/auto/stage
  sync; umount /mnt/auto
  systemctl poweroff
  exit 0
}
if [[ $STAGE == 2 ]]; then
  echo "--- after a rollback from the running system"
  healthy
  t "change made after the snapshot is gone"   bash -c '! test -e /etc/rollback-marker'
  t "clean removes the previous system"        bash -c 'amadeus-rollback clean && ! amadeus-rollback list | grep -q before-rollback'
  snapper -c root create -d "rescue-test"
  touch /etc/rescue-marker
  echo "SNAPSHOT=$(snapper -c root list | awk '/rescue-test/{print $1}')" >/mnt/auto/rescue.conf
  finish 3
fi
if [[ $STAGE == 3 ]]; then
  echo "--- after a rollback from the USB stick"
  healthy
  t "change made after the snapshot is gone"   bash -c '! test -e /etc/rescue-marker'
  finish done
fi

echo "--- base system"
t "system identifies as Amadeus OS"            grep -q '^ID=amadeus' /etc/os-release
t "root is btrfs subvolume @"                  bash -c 'findmnt -no FSTYPE,OPTIONS / | grep -q "btrfs.*subvol=/@"'
t "root is on an unlocked LUKS volume"         bash -c 'cryptsetup status root | grep -q "is active"'
t "separate @home, @log, @pkg subvolumes"      bash -c 'findmnt /home && findmnt /var/log && findmnt /var/cache/pacman/pkg'
t "zram swap active"                           bash -c 'swapon --show | grep -q zram'
t "booted with systemd-boot"                   bash -c 'bootctl status 2>/dev/null | grep -q systemd-boot'
t "no failed system units"                     bash -c '[[ -z $(systemctl --failed --no-legend) ]]'
t "network is up"                              bash -c 'nmcli -t general status | grep -q "^connected"'
t "root account is locked"                     bash -c 'passwd -S root | grep -q " L "'
t "CachyOS kernel is running"                  bash -c 'uname -r | grep -q cachyos'
t "CachyOS repositories come first"            bash -c 'pacman-conf --repo-list | head -1 | grep -q cachyos && pacman -Q cachyos-settings linux-cachyos'
t "multilib enabled (Steam)"                   bash -c 'pacman-conf --repo-list | grep -qx multilib'
t "core packages installed"                    pacman -Q hyprland quickshell steam libreoffice-fresh amadeus amadeus-desktop snapper
t "package lists are ready"                    bash -c 'pacman -Si foot >/dev/null'
t "mirror ranking tools installed"             pacman -Q curl reflector
echo "--- snapshots"
t "installing a package takes no snapshot"   bash -c 'before=$(snapper -c root list | wc -l); pacman -Sy --noconfirm --needed tree >/dev/null && [[ $(snapper -c root list | wc -l) == $before ]]'
t "copy of /boot kept for rollback"            test -f /.bootbackup/vmlinuz-linux-cachyos
# What amadeus-update does before updating, seven times: only five snapshots may remain.
for i in 1 2 3 4 5 6 7; do snapper -c root create --cleanup-algorithm number --description "before update test $i"; snapper -c root cleanup number; done
t "only the newest five snapshots are kept"    bash -c '[[ $(snapper -c root list --columns number | tail -n +3 | grep -cv "^ *0") -le 5 ]] && snapper -c root list | grep -q "before update test 7"'
echo "--- desktop session"
t "greeter service running"                    systemctl is-active greetd
t "Hyprland is running"                        pgrep -x Hyprland
t "shell is running"                           pgrep -f 'quickshell -p /usr/share/amadeus-os/shell'
shell() { as quickshell ipc -p /usr/share/amadeus-os/shell call "$@"; }; export -f shell
t "picker shows a list and returns the choice" bash -c '(printf "alpha\nbeta\n" | as amadeus-pick Test >/tmp/pick.out 2>&1 &); sleep 2; s=$(shell shell state); echo "$s"; echo "$s" | grep -q "\"picker\":true,\"pickerItems\":2" && shell pick choose beta && sleep 1 && grep -qx beta /tmp/pick.out'
t "picker closes without a choice"             bash -c '(printf "a\n" | as amadeus-pick Test >/tmp/pick2.out 2>&1; echo "rc=$?" >>/tmp/pick2.out) & sleep 2; shell pick cancel; sleep 1; grep -qx "rc=1" /tmp/pick2.out'
t "bar drop-downs open and close"              bash -c 'shell shell popover calendar 600; sleep 0.5; shell shell state | grep -q "\"popover\":\"calendar\"" && shell shell popover display 900; sleep 0.5; shell shell state | grep -q "\"popover\":\"display\"" && shell shell popover volume 1700; sleep 0.5; shell shell state | grep -q "\"popover\":\"volume\"" && shell shell popover "" 0'
t "stay awake switches"                        bash -c 'shell shell awake true; shell shell state | grep -q "\"awake\":true" && shell shell awake false'
t "passwordless administrator switch works and ends" bash -c '/usr/lib/amadeus-os/sudo-helper on 15m '$U' && as amadeus-sudo | grep -q "^on until" && sudo -u '$U' sudo -n true && /usr/lib/amadeus-os/sudo-helper off && ! sudo -u '$U' sudo -n true 2>/dev/null && as amadeus-sudo | grep -qx off'
t "notifications are shown by the shell"       bash -c 'as notify-send "Self-test" "hello"; sleep 1; s=$(shell shell state); echo "$s"; echo "$s" | grep -q "\"notifications\":[1-9]"'
t "launcher lists installed applications"      bash -c 'as amadeus-launcher --print | grep -q "^Steam"'
t "no separate launcher or notification program" bash -c '! pacman -Q fuzzel mako 2>/dev/null | grep -q .'
t "AUR lookup works"                           bash -c 'as amadeus-aur info protonplus | grep -q "^Name"'
t "AUR leaves repository packages to pacman"  bash -c 'out=$(as amadeus-aur install foot 2>&1); echo "$out"; grep -q "system repositories" <<<"$out"'
t "mirror ranking reports the official choice" bash -c 'as amadeus-mirrors --print | grep -q "^Server = "'
t "sound services are running"                 bash -c 'as systemctl --user is-active --quiet pipewire.socket pipewire-pulse.socket wireplumber.service'
t "terminal configuration is valid"            bash -c 'as foot --check-config'
t "Amadeus menu installed and bound"           bash -c 'test -x /usr/bin/amadeus-menu && grep -q amadeus-menu /usr/share/amadeus-os/hypr/default.lua'
t "Super+K lists shortcuts and commands"       bash -c 'out=$(as amadeus-keys --print); echo "$out" | grep -q "^Super + K " && echo "$out" | grep -q "amadeus-rollback" && echo "$out" | grep -q "Super + Enter .*Terminal"'
t "file manager shortcut is listed"            bash -c 'as amadeus-keys --print | grep -q "^Super + Shift + F .*Files"'
t "system look applies to applications"        bash -c 'as gsettings get org.gnome.desktop.interface color-scheme | grep -q prefer-dark && fc-match sans-serif | grep -qi inter && test -f /usr/share/amadeus-os/theme.json'
t "text size can be set and restored"          bash -c 'as amadeus-display text 110% >/dev/null && as gsettings get org.gnome.desktop.interface text-scaling-factor | grep -q "1.1" && as amadeus-display text 100% >/dev/null'
t "display scale can be set and restored"      bash -c 'as amadeus-display scale 1.25 >/dev/null && as amadeus-display scale | grep -q 1.25 && as amadeus-display scale 1 >/dev/null'
t "the install worked without internet"       bash -c 'grep -q "Claude Code is set up once you are online" /var/log/amadeus-install.log'
t "a harness installs through mise (Claude Code)" bash -c 'as bash -lc "amadeus-harness install claude" >/dev/null 2>&1; as bash -lc "mise ls --global" | grep -q "^claude" && as bash -lc "claude --version"'
t "harness list comes from mise"               bash -c 'out=$(as bash -lc "amadeus-harness list"); echo "$out" | grep -q "Claude Code  (installed)" && echo "$out" | grep -q "^Codex"'
t "defaults: terminal, editor, harness"        bash -c 'out=$(as amadeus-default); echo "$out"; echo "$out" | grep -q "terminal *foot" && echo "$out" | grep -q "harness *claude" && as amadeus-default editor nano | grep -q "Default editor: nano"'
t "default harness resolves to a program"      bash -c 'as bash -lc "amadeus-harness run claude --version"'
t "text files open with the default editor"    bash -c 'as xdg-mime query default text/plain | grep -q amadeus-editor'
t "install catalogue resolves its sources"     bash -c 'for c in terminal browser editor ai development; do n=$(as bash -lc "amadeus-catalog $c" | wc -l); echo "$c $n"; [[ $n -ge 3 ]] || exit 1; done; as bash -lc "amadeus-catalog ai" | grep -q "^Claude Desktop  (installed)"'
t "web app list works with none installed"     bash -c '! as amadeus-webapp list | grep .'
t "web app can be added and removed"           bash -c 'as amadeus-webapp install "Self Test" example.org >/dev/null; as amadeus-webapp list | grep -q "^Self Test" && as amadeus-launcher --print | grep -q "^Self Test" && as amadeus-webapp remove "Self Test" >/dev/null && ! as amadeus-webapp list | grep -q "Self Test"'
t "web app address keeps its percent signs"    bash -c 'as amadeus-webapp install Pct "https://example.org/a%20b" >/dev/null; grep -q "a%%20b" /home/'$U'/.local/share/applications/amadeus-webapp-pct.desktop && as amadeus-webapp remove Pct'
t "clipboard history records copies"           bash -c 'echo amadeus-clip-test | as wl-copy >/dev/null 2>&1; sleep 1; as cliphist list | grep -q amadeus-clip-test'
t "system menu and about are present"          bash -c 'test -x /usr/bin/amadeus-power-menu && as fastfetch | grep -q "Amadeus OS"'
t "GPU choice is offered only where there is one" bash -c '[[ $(as amadeus-gpu) == one ]] && ! as amadeus-gpu set nvidia >/dev/null 2>&1 && test -e /dev/dri/intel-card -o -z "$(ls /sys/bus/pci/drivers/i915 2>/dev/null)"'
t "GPU wrapper sets the offload variables"      bash -c 'as amadeus-gpu-run env | grep -q "^__NV_PRIME_RENDER_OFFLOAD=1$" && as amadeus-gpu-run env | grep -q "^__GLX_VENDOR_LIBRARY_NAME=nvidia$" && as amadeus-gpu-run env | grep -q "^__VK_LAYER_NV_optimus=NVIDIA_only$"'
t "desktop config has no errors"             bash -c '[[ -z $(as hyprctl configerrors | tr -d "[:space:]") ]]'
t "every shortcut has a description"           bash -c 'as hyprctl -j binds | python3 -c "import json,sys; b=json.load(sys.stdin); missing=[x[\"key\"] for x in b if not x[\"mouse\"] and not x[\"description\"]]; print(missing); assert len(b) > 40 and not missing"'
t "screenshot is saved and copied"             bash -c 'as amadeus-screenshot screen >/dev/null 2>&1 & sleep 3; ls /home/'$U'/Pictures/Screenshots/screenshot-*.png >/dev/null && as wl-paste --list-types | grep -q image/png'
rec_test() {   # starts a recording of the first screen as amadeus-record would, then stops it through amadeus-record
  local mon; mon=$(as hyprctl -j monitors | python3 -c 'import json, sys; print(json.load(sys.stdin)[0]["name"])')
  as bash -c "gpu-screen-recorder -w $mon -f 30 -fallback-cpu-encoding yes -o /tmp/amadeus-rec.mp4 >/dev/null 2>&1 & echo \$! >\$XDG_RUNTIME_DIR/amadeus-record.pid; echo /tmp/amadeus-rec.mp4 >\$XDG_RUNTIME_DIR/amadeus-record.file"
  sleep 4; timeout 20 bash -c "$(declare -f as); as amadeus-record stop" >/dev/null 2>&1 & sleep 6
  test -s /tmp/amadeus-rec.mp4
}
export -f rec_test
t "screen recording saves when stopped"        rec_test
t "scratchpad shows and hides"                 bash -c 'as hyprctl dispatch "hl.dsp.workspace.toggle_special(\"scratchpad\")" >/dev/null; sleep 0.5; as hyprctl -j monitors | grep -q "special:scratchpad" && as hyprctl dispatch "hl.dsp.workspace.toggle_special(\"scratchpad\")" >/dev/null'
t "Super+K reads the live shortcuts"           bash -c 'as amadeus-keys --print | grep -q "^Super + K .*Shortcuts"' 
t "compositor answers over IPC"                bash -c 'as hyprctl -j workspaces | grep -q "\"id\""'
t "X11 applications supported"                 bash -c 'ls /tmp/.X11-unix/ | grep -q "^X"'
echo "--- Amadeus"
t "daemon running in the user session"         test -S $R/amadeus/daemon.sock
t "ama status"                                 as ama status
t "sandboxed command runs"                     bash -c "sudo -u $U env XDG_RUNTIME_DIR=$R HOME=/home/$U PATH=/usr/bin ama tool shell_run '{\"command\":\"echo sandbox-ok\"}' | grep -q sandbox-ok"
t "sandbox has no network and no home"         bash -c "! sudo -u $U env XDG_RUNTIME_DIR=$R HOME=/home/$U PATH=/usr/bin ama tool shell_run '{\"command\":\"ls /home/$U/.config || true; curl -sm3 https://archlinux.org >/dev/null && echo LEAK\"}' | grep -qE 'LEAK|hypr'"
t "protected paths are refused"                bash -c "sudo -u $U env XDG_RUNTIME_DIR=$R HOME=/home/$U PATH=/usr/bin ama tool fs_read '{\"path\":\"~/.ssh/id_ed25519\"}' | grep -q 'protected'"
t "desktop state readable through Amadeus"     bash -c "as ama tool desktop_state | grep -q monitors"
t "bar layout readable through Amadeus"        bash -c "as ama tool desktop_bar | grep -q workspaces"
t "privileged tools refused (root mode off)"   bash -c "as ama tool pkg_manage '{\"action\":\"install\",\"packages\":[\"htop\"]}' | grep -q 'root mode'"
t "root helper is root-owned"                  bash -c '[[ $(stat -c %U /usr/lib/amadeus/amadeus-priv) == root ]]'
t "system describes itself (ama discover)"     bash -c "as ama discover --json | python3 -c 'import json,sys; m=json.load(sys.stdin); assert m[\"commands\"][\"amadeus-rollback\"] and len(m[\"tools\"]) > 30 and m[\"system\"][\"packages\"][\"amadeus\"]'"
t "agent skill installed for Claude Code"      test -f /home/$U/.claude/skills/amadeus/SKILL.md
t "Amadeus panel opens and reaches the daemon" bash -c 'as ama panel show; sleep 2; s=$(as ama panel state); echo "$s"; echo "$s" | grep -q "\"open\": true.*\"connected\": true"'
t "panel takes a window as context"            bash -c 'as ama panel window; as ama panel hide; sleep 1; as ama panel state | grep -q "\"open\": false"'
t "audit log chain intact"                     as ama audit verify
echo "--- AI requests end to end (scripted model; everything else is real)"
while read -r line; do
  echo "$line"
  case $line in PASS*) pass=$((pass+1)) ;; FAIL*) fail=$((fail+1)) ;; esac
done < <(as python3 /usr/local/bin/amadeus-e2e 2>&1)
echo "--- applications outside the Arch repositories"
for p in protonplus brave-origin-bin claude-desktop herdr-bin localsend-bin; do t "$p installed" pacman -Q $p; done
echo "--- ama doctor"
as ama doctor || true
echo "--- resources"
awk '{printf "kernel to self-test start: %.0f s\n", $1}' /proc/uptime
free -m | sed -n 2p | awk '{print "memory used after login: " $3 " MB"}'
pacman -Qq | wc -l | awk '{print "packages installed: " $1}'
df -h / | tail -1 | awk '{print "disk used: " $3}'

echo "--- rollback from the running system"
printf x >>/.bootbackup/vmlinuz-linux-cachyos   # a stale saved kernel, to exercise the repair path
snapper -c root create -d "rollback-test"
n=$(snapper -c root list | awk '/rollback-test/{print $1}')
touch /etc/rollback-marker
t "amadeus-rollback lists snapshots"           bash -c 'amadeus-rollback list | grep -q rollback-test'
t "amadeus-rollback to snapshot $n"            amadeus-rollback --yes "$n"
t "stale kernel was repaired"                  bash -c 'cmp /boot/vmlinuz-linux-cachyos /usr/lib/modules/*/vmlinuz'
finish 2
