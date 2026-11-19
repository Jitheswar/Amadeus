#!/bin/bash

# Test the real orchestration with fixed privileged paths redirected to harmless
# stand-ins. No host sudo, package transaction, namespace root, or exploit runs.
boundary_tmp=$(mktemp -d)
trap 'rm -rf "$boundary_tmp"' EXIT
export SUDO_TEST_ROOT="$boundary_tmp/amadeus"
export SUDO_TEST_LOG="$boundary_tmp/events"
export SUDO_TEST_CACHE="$boundary_tmp/cache"
export AMADEUS_PATH="$SUDO_TEST_ROOT"
export SUDO_TEST_HOME="$boundary_tmp/home"
# The machine the render reads its region marker from. It starts global; a test
# writes etc/amadeus/region here to model a regional install, never the host's.
export SUDO_TEST_TARGET="$boundary_tmp/target"
mkdir -p "$SUDO_TEST_HOME" "$SUDO_TEST_TARGET/etc"
mkdir -p "$SUDO_TEST_ROOT/bin" "$SUDO_TEST_ROOT/mock" "$SUDO_TEST_ROOT/default"
: >"$SUDO_TEST_LOG"

copy_boundary_file() {
  python3 - "$ROOT" "$SUDO_TEST_ROOT" "$1" <<'PY'
import sys
from pathlib import Path
source, target, name = map(Path,sys.argv[1:])
p=target/name
p.parent.mkdir(parents=True,exist_ok=True)
s=(source/name).read_text().replace('$HOME', '$SUDO_TEST_HOME')
for command in ['sudo','pkexec','pacman','amadeus-pkg-missing','systemd-inhibit','setpriv','snapper']:
 s=s.replace('/usr/bin/'+command, str(target/'mock'/command))
s=s.replace('PATH=/usr/bin:/usr/sbin:/bin:/sbin', 'PATH="'+str(target/'bin')+':/usr/bin:/usr/sbin:/bin:/sbin"')
p.write_text(s)
p.chmod((source/name).stat().st_mode & 0o777)
PY
}

copy_boundary_file bin/amadeus-security-functions
copy_boundary_file bin/amadeus-update-pacman
# Channel changes copy the platform's templates; the copy itself is a stand-in.
cp -r "$ROOT/default/pacman" "$SUDO_TEST_ROOT/default/"

# Channel changes ask for the platform. x86 unless a test says otherwise, so no
# test reads the host's hardware.
cat >"$SUDO_TEST_ROOT/bin/amadeus-hw-platform" <<'STUB'
#!/bin/bash
echo "${SUDO_TEST_PLATFORM:-x86}"
STUB
chmod +x "$SUDO_TEST_ROOT/bin/amadeus-hw-platform"

cat >"$SUDO_TEST_ROOT/mock/sudo" <<'STUB'
#!/bin/bash
set -euo pipefail
printf 'sudo' >>"$SUDO_TEST_LOG"
printf ' %q' "$@" >>"$SUDO_TEST_LOG"
printf '\n' >>"$SUDO_TEST_LOG"
if [[ ${1:-} == "-k" || ${1:-} == "-K" ]]; then
  /usr/bin/rm -f "$SUDO_TEST_CACHE"
  exit 0
fi
if [[ ${1:-} == "-n" && ! -e $SUDO_TEST_CACHE ]]; then
  # Non-interactive sudo cannot authenticate without a cached credential.
  exit 1
fi
[[ ${SUDO_TEST_SUDO_FAIL:-0} != "1" ]] || exit 1
# A password given once stays good for the rest of the timeout.
touch "$SUDO_TEST_CACHE"
background=0
while (( $# )); do
  case "$1" in
    -n) shift ;;
    -b) background=1; shift ;;
    -v) exit 0 ;;
    -u|--user) shift 2 ;;
    --) shift; break ;;
    *) break ;;
  esac
done
(( $# )) || exit 0
if (( background )); then
  "$@" &
else
  "$@"
fi
STUB
chmod +x "$SUDO_TEST_ROOT/mock/sudo"
# The commands call sudo and their helpers by name from the caller's PATH. Put
# the stand-ins first so no test can ever reach the host's sudo or commands.
ln -s ../mock/sudo "$SUDO_TEST_ROOT/bin/sudo"
export PATH="$SUDO_TEST_ROOT/bin:$PATH"

cat >"$SUDO_TEST_ROOT/bin/test-step" <<'STUB'
#!/bin/bash
set -euo pipefail
step=${0##*/}
printf 'step:%s %s\n' "$step" "$*" >>"$SUDO_TEST_LOG"
if [[ $step == "systemd-run" ]]; then
  # amadeus-update-pacman registers the transaction as a PID 1 scope on booted
  # hosts. Run the wrapped command in place so the pacman step still executes.
  while (( $# )) && [[ $1 == -* ]]; do shift; done
  exec "$@"
fi
# amadeus update shares one authorization with its post-update hook, mise and
# AUR builds, so none of them prompts again.
if [[ $step == "amadeus-hook" && ${1:-} == "post-update" ]] || [[ $step == "amadeus-update-mise" || $step == "yay" ]]; then
  [[ -e $SUDO_TEST_CACHE ]] || exit 94
fi
if [[ ${SUDO_TEST_FAIL_STEP:-} == "$step" ]]; then
  # Model a misbehaving child failing. This never invokes real sudo.
  exit 17
fi
if [[ ${SUDO_TEST_SIGNAL_STEP:-} == "$step" ]]; then
  kill -TERM "$PPID"
  exit 0
fi
case "$step" in
  amadeus-update-system-pkgs|amadeus-update-keyring|amadeus-snapshot)
    sudo /usr/bin/true
    ;;
esac
STUB
chmod +x "$SUDO_TEST_ROOT/bin/test-step"
for step in amadeus-update-lock amadeus-update-requires-free-space amadeus-update-confirm amadeus-update-pkg-prune amadeus-snapshot amadeus-update-stay-awake amadeus-update-dev amadeus-update-boot amadeus-update-keyring amadeus-update-system-pkgs amadeus-migrate amadeus-hook amadeus-update-aur-pkgs amadeus-update-mise amadeus-update-orphan-pkgs amadeus-update-analyze-logs amadeus-shell amadeus-update-restart amadeus-pkg-aur-accessible amadeus-notification-dismiss amadeus-restart-shell pacman systemd-run cp yay; do
  ln -s test-step "$SUDO_TEST_ROOT/bin/$step"
done
ln -s ../bin/test-step "$SUDO_TEST_ROOT/mock/pacman"

reset_boundary() {
  : >"$SUDO_TEST_LOG"
  /usr/bin/rm -f "$SUDO_TEST_CACHE"
  unset SUDO_TEST_FAIL_STEP SUDO_TEST_SIGNAL_STEP SUDO_TEST_SUDO_FAIL SUDO_TEST_PLATFORM
}
