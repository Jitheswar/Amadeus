#!/bin/bash
# First-boot self-test for the VM harness. Runs as root on the installed system; reports to the answers disk.
exec > >(tee /dev/ttyS0 /var/log/amadeus-selftest.log) 2>&1
U=@USER@; UID_=$(id -u $U); R=/run/user/$UID_
pass=0 fail=0
ok()   { echo "PASS  $1"; pass=$((pass+1)); }
bad()  { echo "FAIL  $1 ${2:+— $2}"; fail=$((fail+1)); }
t()    { local name=$1; shift; local out; if out=$("$@" 2>&1); then ok "$name"; else bad "$name" "$(echo "$out" | tail -2 | tr '\n' ' ')"; fi; }
as()   { sudo -u $U env XDG_RUNTIME_DIR=$R DBUS_SESSION_BUS_ADDRESS=unix:path=$R/bus WAYLAND_DISPLAY=wayland-1 NIRI_SOCKET="$(ls $R/niri.*.sock 2>/dev/null | head -1)" HOME=/home/$U PATH=/usr/bin "$@"; }
export U R; export -f as
echo "AMADEUS-SELFTEST-BEGIN"
for _ in $(seq 60); do [[ -S $R/amadeus/daemon.sock ]] && pgrep -x niri >/dev/null && break; sleep 2; done
sleep 8
mkdir -p /mnt/auto; mount /dev/disk/by-label/AMADEUSAUTO /mnt/auto 2>/dev/null
STAGE=$(cat /mnt/auto/stage 2>/dev/null || echo 1)
healthy() {
  t "root is btrfs subvolume @"                bash -c 'findmnt -no FSTYPE,OPTIONS / | grep -qE "btrfs.*subvol=/@(,|$)"'
  t "no failed system units"                   bash -c '[[ -z $(systemctl --failed --no-legend) ]]'
  t "niri is running"                          pgrep -x niri
  t "kernel on the boot partition matches"     bash -c 'cmp /boot/vmlinuz-linux /usr/lib/modules/*/vmlinuz'
  t "snapshot history carried over"            bash -c 'snapper -c root list | grep -q "fresh install"'
  t "previous system kept"                     bash -c 'amadeus-rollback list | grep -q before-rollback'
}
finish() {
  echo "AMADEUS-SELFTEST-END stage=$STAGE pass=$pass fail=$fail"
  sleep 1
  if [[ $STAGE == 1 ]]; then
    as niri msg action screenshot-screen --write-to-disk true 2>/dev/null; sleep 2; cp "$(ls -t /home/$U/Pictures/Screenshots/*.png 2>/dev/null | head -1)" /mnt/auto/desktop.png 2>/dev/null
    journalctl -b -p warning --no-pager | tail -60 >/mnt/auto/journal-warnings.log
  fi
  (( fail )) && { as niri msg outputs; journalctl -b --no-pager _COMM=niri | tail -60; } >/mnt/auto/desktop-debug.log 2>&1
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
t "multilib enabled (Steam)"                   bash -c 'pacman -Sl multilib | head -1 | grep -q multilib'
t "core packages installed"                    pacman -Q niri quickshell steam libreoffice-fresh amadeus amadeus-desktop snap-pac
echo "--- snapshots"
t "snapshot of the fresh install exists"       bash -c 'snapper -c root list | grep -q "fresh install"'
before=$(snapper -c root list | wc -l)
t "installing a package works"                 pacman -S --noconfirm --needed tree
t "package change created pre/post snapshots"  bash -c "[[ \$(snapper -c root list | wc -l) -ge $((before+2)) ]]"
t "copy of /boot kept for rollback"            test -f /.bootbackup/vmlinuz-linux
n=$(snapper -c root list | awk '$3=="pre"{p=$1} END{print p}')
t "rollback removes the package again"         bash -c "snapper -c root undochange $n..$((n+1)) >/dev/null && ! test -e /usr/bin/tree"
echo "--- desktop session"
t "greeter service running"                    systemctl is-active greetd
t "niri is running"                            pgrep -x niri
t "shell is running"                           pgrep -f 'quickshell -p /usr/share/amadeus-os/shell'
shell() { as quickshell ipc -p /usr/share/amadeus-os/shell call "$@"; }; export -f shell
t "picker shows a list and returns the choice" bash -c '(printf "alpha\nbeta\n" | as amadeus-pick Test >/tmp/pick.out 2>&1 &); sleep 2; s=$(shell shell state); echo "$s"; echo "$s" | grep -q "\"picker\":true,\"pickerItems\":2" && shell pick choose beta && sleep 1 && grep -qx beta /tmp/pick.out'
t "picker closes without a choice"             bash -c '(printf "a\n" | as amadeus-pick Test >/tmp/pick2.out 2>&1; echo "rc=$?" >>/tmp/pick2.out) & sleep 2; shell pick cancel; sleep 1; grep -qx "rc=1" /tmp/pick2.out'
t "notifications are shown by the shell"       bash -c 'as notify-send "Self-test" "hello"; sleep 1; s=$(shell shell state); echo "$s"; echo "$s" | grep -q "\"notifications\":[1-9]"'
t "launcher lists installed applications"      bash -c 'as amadeus-launcher --print | grep -q "^Steam"'
t "no separate launcher or notification program" bash -c '! pacman -Q fuzzel mako 2>/dev/null | grep -q .'
t "AUR lookup works"                           bash -c 'as amadeus-aur info protonplus | grep -q "^Name"'
t "Amadeus menu installed and bound"           bash -c 'test -x /usr/bin/amadeus-menu && grep -q amadeus-menu /usr/share/amadeus-os/niri/default.kdl'
t "Super+K lists shortcuts and commands"       bash -c 'out=$(as amadeus-keys --print); echo "$out" | grep -q "^Super + K " && echo "$out" | grep -q "amadeus-rollback" && echo "$out" | grep -q "Super + Enter .*Terminal"'
t "system look applies to applications"        bash -c 'as gsettings get org.gnome.desktop.interface color-scheme | grep -q prefer-dark && fc-match sans-serif | grep -qi inter && test -f /usr/share/amadeus-os/theme.json'
t "desktop config is valid"                    as niri validate -c /home/$U/.config/niri/config.kdl
t "compositor answers over IPC"                bash -c 'out=$(as niri msg --json workspaces 2>&1); echo "$out" | grep -q idx || { echo "sock=$(ls $R/niri.*.sock 2>&1) out=$out"; false; }'
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
for p in protonplus brave-origin-bin claude-desktop claude-code herdr-bin localsend-bin; do t "$p installed" pacman -Q $p; done
echo "--- ama doctor"
as ama doctor || true
echo "--- resources"
awk '{printf "kernel to self-test start: %.0f s\n", $1}' /proc/uptime
free -m | sed -n 2p | awk '{print "memory used after login: " $3 " MB"}'
pacman -Qq | wc -l | awk '{print "packages installed: " $1}'
df -h / | tail -1 | awk '{print "disk used: " $3}'

echo "--- rollback from the running system"
printf x >>/.bootbackup/vmlinuz-linux   # a stale saved kernel, to exercise the repair path
snapper -c root create -d "rollback-test"
n=$(snapper -c root list | awk '/rollback-test/{print $1}')
touch /etc/rollback-marker
t "amadeus-rollback lists snapshots"           bash -c 'amadeus-rollback list | grep -q rollback-test'
t "amadeus-rollback to snapshot $n"            amadeus-rollback --yes "$n"
t "stale kernel was repaired"                  bash -c 'cmp /boot/vmlinuz-linux /usr/lib/modules/*/vmlinuz'
finish 2
