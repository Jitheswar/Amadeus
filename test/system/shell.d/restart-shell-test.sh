#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"

test_tmp=$(mktemp -d)
restart_pid_one=""
restart_pid_two=""

cleanup() {
  [[ -n $restart_pid_one ]] && kill "$restart_pid_one" 2>/dev/null || true
  [[ -n $restart_pid_two ]] && kill "$restart_pid_two" 2>/dev/null || true
  rm -rf "$test_tmp"
}
trap cleanup EXIT

restart_root="$test_tmp/restart-root"
restart_bin="$restart_root/bin"
restart_state="$test_tmp/restart-pids"
restart_log="$test_tmp/restart.log"
restart_env_log="$test_tmp/restart-env.log"
dispatch_log="$test_tmp/dispatch.log"
ipc_log="$test_tmp/ipc.log"
runtime_dir="$test_tmp/runtime"
mkdir -p "$restart_root/shell" "$restart_bin" "$runtime_dir"
touch "$restart_root/shell/shell.qml"
ln -s "$ROOT/bin/amadeus-shell" "$restart_bin/amadeus-shell"
ln -s "$ROOT/bin/amadeus-launch-shell" "$restart_bin/amadeus-launch-shell"
ln -s "$ROOT/bin/amadeus-cmd-missing" "$restart_bin/amadeus-cmd-missing"
ln -s "$ROOT/bin/amadeus-hyprland-session-locked" "$restart_bin/amadeus-hyprland-session-locked"

cat >"$restart_bin/qs" <<'SH'
#!/bin/bash

printf '%s\n' "$*" >>"$AMADEUS_TEST_IPC_LOG"

case "$*" in
  *'shell ping')
    [[ $* == *"-p $AMADEUS_TEST_SESSION_PATH/shell"* ]] &&
      grep -Fx '303' "$AMADEUS_TEST_QS_STATE" >/dev/null &&
      printf 'ok\n'
    ;;
  *'lock lock')
    touch "$AMADEUS_TEST_QS_STATE.locked"
    printf 'ok\n'
    ;;
  *'lock status')
    if [[ -f $AMADEUS_TEST_QS_STATE.locked ]]; then
      printf '{"secure": true, "requested": true}\n'
    else
      printf '{"secure": false, "requested": false}\n'
    fi
    ;;
esac
SH

cat >"$restart_bin/quickshell" <<'SH'
#!/bin/bash

printf '%s\n' "$*" >>"$AMADEUS_TEST_QS_LOG"

# Other configs' instances, one "<config dir> <pid>" per line.
strays=${AMADEUS_TEST_QS_STRAYS:-/nonexistent}

case " $* " in
  *' list '*)
    [[ -f $strays ]] && jq -R -s -c 'split("\n") | map(select(length > 0) | split(" ") | {config_path: (.[0] + "/shell.qml"), pid: (.[1] | tonumber)})' "$strays"
    ;;
  *' kill -p '*)
    if [[ $3 != "$AMADEUS_TEST_SESSION_PATH/shell" ]]; then
      pid=$(awk -v dir="$3" '$1 == dir { print $2; exit }' "$strays" 2>/dev/null)
      [[ $pid =~ ^[0-9]+$ ]] || exit 1
      # The instance outlasts the client's timeout and exits a moment later.
      (
        sleep 0.5
        kill "$pid" 2>/dev/null
        awk -v dir="$3" '$1 != dir' "$strays" >"$strays.next"
        mv "$strays.next" "$strays"
      ) &
      exit 124
    fi

    pid=$(head -n 1 "$AMADEUS_TEST_QS_STATE")
    [[ $pid =~ ^[0-9]+$ ]] || exit 1
    kill "$pid" 2>/dev/null
    while kill -0 "$pid" 2>/dev/null; do sleep 0.01; done
    awk 'NR > 1' "$AMADEUS_TEST_QS_STATE" >"$AMADEUS_TEST_QS_STATE.next"
    mv "$AMADEUS_TEST_QS_STATE.next" "$AMADEUS_TEST_QS_STATE"
    ;;
  *' -n -p '*)
    printf '%s\n' "${AMADEUS_TEST_TRANSIENT_ENV-unset}" >"$AMADEUS_TEST_QS_ENV_LOG"
    printf '303\n' >"$AMADEUS_TEST_QS_STATE"
    [[ ! -f $strays ]] || cp "$strays" "$strays.at-launch"
    ;;
esac
SH

cat >"$restart_bin/hyprctl" <<'SH'
#!/bin/bash

if [[ ${1:-} == "-j" && ${2:-} == "monitors" ]]; then
  # Hyprland reports an active session lock as a reason the monitor cannot hand
  # a client the whole screen, not as a workspace.
  if [[ ${AMADEUS_TEST_SESSION_LOCKED:-0} == 1 ]]; then
    printf '[{"name":"eDP-1","solitaryBlockedBy":["WINDOWED","LOCK","CANDIDATE"]}]\n'
  else
    printf '[{"name":"eDP-1","solitaryBlockedBy":["WINDOWED","CANDIDATE"]}]\n'
  fi
elif [[ ${1:-} == "dispatch" && ${2:-} == hl.dsp.exec_cmd* ]]; then
  printf '%s\n' "${2:-}" >>"$AMADEUS_TEST_DISPATCH_LOG"
  AMADEUS_PATH="$AMADEUS_TEST_SESSION_PATH" \
    env -u AMADEUS_TEST_TRANSIENT_ENV amadeus-launch-shell
  printf 'ok\n'
elif [[ ${1:-} == "dispatch" ]]; then
  exit 1
fi
SH

# Keep the test hermetic where journald has no usable stream socket.
cat >"$restart_bin/systemd-cat" <<'SH'
#!/bin/bash

while (( $# > 0 )); do
  [[ $1 == "--" ]] && { shift; break; }
  shift
done
exec "$@"
SH

cat >"$restart_bin/systemctl" <<'SH'
#!/bin/bash

if [[ ${1:-} == "--user" && ${2:-} == "show-environment" ]]; then
  printf 'AMADEUS_PATH=%s\n' "$AMADEUS_TEST_SESSION_PATH"
elif [[ ${1:-} == "--user" && ${2:-} == "try-restart" ]]; then
  exit 0
else
  exit 1
fi
SH

cat >"$restart_bin/busctl" <<'SH'
#!/bin/bash
if [[ -z ${AMADEUS_TEST_NOTIFICATION_CHECKS:-} ]]; then
  echo 'b false'
else
  checks=0
  [[ ! -f $AMADEUS_TEST_NOTIFICATION_CHECKS ]] || read -r checks <"$AMADEUS_TEST_NOTIFICATION_CHECKS"
  (( checks += 1 ))
  printf '%s\n' "$checks" >"$AMADEUS_TEST_NOTIFICATION_CHECKS"
  # The service was running before the restart and, when asked to, never
  # comes back afterwards.
  if [[ ${AMADEUS_TEST_NOTIFICATIONS_DIE:-0} == 1 ]]; then
    (( checks == 1 )) && echo 'b true' || echo 'b false'
    exit 0
  fi
  if (( checks == 1 || checks >= 4 )); then
    echo 'b true'
  else
    echo 'b false'
  fi
fi
SH

chmod +x "$restart_bin/qs" "$restart_bin/quickshell" "$restart_bin/hyprctl" "$restart_bin/systemd-cat" "$restart_bin/systemctl" "$restart_bin/busctl"

sleep 30 &
restart_pid_one=$!
sleep 30 &
restart_pid_two=$!
printf '%s\n%s\n' "$restart_pid_one" "$restart_pid_two" >"$restart_state"

caller_root="$test_tmp/caller-root"
mkdir -p "$caller_root/shell"
touch "$caller_root/shell/shell.qml"

PATH="$restart_bin:$PATH" \
AMADEUS_PATH="$caller_root" \
XDG_RUNTIME_DIR="$runtime_dir" \
AMADEUS_TEST_QS_STATE="$restart_state" \
AMADEUS_TEST_QS_LOG="$restart_log" \
AMADEUS_TEST_QS_ENV_LOG="$restart_env_log" \
AMADEUS_TEST_DISPATCH_LOG="$dispatch_log" \
AMADEUS_TEST_IPC_LOG="$ipc_log" \
AMADEUS_TEST_SESSION_PATH="$restart_root" \
AMADEUS_TEST_TRANSIENT_ENV=leaked \
AMADEUS_TEST_NOTIFICATION_CHECKS="$test_tmp/notification-checks" \
  timeout 5 "$ROOT/bin/amadeus-restart-shell"

if kill -0 "$restart_pid_one" 2>/dev/null; then
  fail "restart stops the first matching shell instance"
fi
if kill -0 "$restart_pid_two" 2>/dev/null; then
  fail "restart stops duplicate matching shell instances"
fi
wait "$restart_pid_one" 2>/dev/null || true
wait "$restart_pid_two" 2>/dev/null || true
restart_pid_one=""
restart_pid_two=""
[[ $(<"$restart_state") == 303 ]] || fail "restart leaves exactly one fresh shell instance"
[[ $(grep -c '^-n -p ' "$restart_log") == 1 ]] || fail "restart launches one fresh shell process"
grep -F "kill -p $restart_root/shell --any-display" "$restart_log" >/dev/null || fail "restart stops the shell from the session checkout"
[[ $(<"$restart_env_log") == "unset" ]] || fail "restart uses the Hyprland session environment for the fresh shell"
grep -F 'hl.dsp.exec_cmd("amadeus-launch-shell")' "$dispatch_log" >/dev/null || fail "restart launches the fresh shell through Hyprland"
grep -F "ipc -n -p $restart_root/shell call -- shell ping" "$ipc_log" >/dev/null || fail "restart checks readiness in the session checkout"
pass "restart replaces duplicate shell instances from the session checkout"
[[ $(<"$test_tmp/notification-checks") == 4 ]] || fail "restart waits for the existing notification service after core IPC is ready"
pass "restart waits for notification readiness before one-time update hooks"

: >"$restart_log"
printf '303\n' >"$restart_state"
touch "$restart_state.locked"

locked_error=$(PATH="$restart_bin:$PATH" \
  AMADEUS_PATH="$restart_root" \
  XDG_RUNTIME_DIR="$runtime_dir" \
  AMADEUS_TEST_SESSION_LOCKED=1 \
  AMADEUS_TEST_QS_STATE="$restart_state" \
  AMADEUS_TEST_QS_LOG="$restart_log" \
  AMADEUS_TEST_DISPATCH_LOG="$dispatch_log" \
  AMADEUS_TEST_IPC_LOG="$ipc_log" \
  AMADEUS_TEST_SESSION_PATH="$restart_root" \
  "$ROOT/bin/amadeus-restart-shell" 2>&1) && fail "restart refuses while the shell lock is active"

[[ $locked_error == "Refusing to restart Amadeus shell while the session is locked." ]] || fail "locked restart explains why it was refused" "$locked_error"
[[ $(<"$restart_state") == 303 ]] || fail "locked restart preserves the running shell"
[[ ! -s $restart_log ]] || fail "locked restart does not stop or launch Quickshell"
pass "restart preserves the shell while its lock is active"

# A LOCK session without an active locker — dead shell or a crash-handler
# relaunch holding no lock — is the failsafe: restart must proceed,
# re-acquire the session lock, and wait for it to report secure.
sleep 30 &
restart_pid_one=$!
printf '%s\n' "$restart_pid_one" >"$restart_state"
rm -f "$restart_state.locked"
: >"$restart_log"
: >"$ipc_log"

PATH="$restart_bin:$PATH" \
AMADEUS_PATH="$restart_root" \
XDG_RUNTIME_DIR="$runtime_dir" \
AMADEUS_TEST_SESSION_LOCKED=1 \
AMADEUS_TEST_QS_STATE="$restart_state" \
AMADEUS_TEST_QS_LOG="$restart_log" \
AMADEUS_TEST_QS_ENV_LOG="$restart_env_log" \
AMADEUS_TEST_DISPATCH_LOG="$dispatch_log" \
AMADEUS_TEST_IPC_LOG="$ipc_log" \
AMADEUS_TEST_SESSION_PATH="$restart_root" \
  timeout 5 "$ROOT/bin/amadeus-restart-shell" || fail "locked restart recovers when the lock client is dead"

if kill -0 "$restart_pid_one" 2>/dev/null; then
  fail "dead-lock recovery stops the stale shell instance"
fi
wait "$restart_pid_one" 2>/dev/null || true
restart_pid_one=""
[[ $(<"$restart_state") == 303 ]] || fail "dead-lock recovery leaves one fresh shell instance"
grep -F "ipc -n -p $restart_root/shell call -- lock lock" "$ipc_log" >/dev/null || fail "dead-lock recovery re-acquires the session lock"
grep -F "ipc -n -p $restart_root/shell call -- lock status" "$ipc_log" >/dev/null || fail "dead-lock recovery waits for the lock to become secure"
pass "restart recovers a locked session whose lock client died"

# Lock recovery must not wait on the notification plugin: a stranded user gets
# the lock back even when notifications never return, and the restart then
# reports the missing service rather than claiming success.
sleep 30 &
restart_pid_one=$!
printf '%s\n' "$restart_pid_one" >"$restart_state"
rm -f "$restart_state.locked" "$test_tmp/notification-checks"
: >"$restart_log"
: >"$ipc_log"

if PATH="$restart_bin:$PATH" \
  AMADEUS_PATH="$restart_root" \
  XDG_RUNTIME_DIR="$runtime_dir" \
  AMADEUS_TEST_SESSION_LOCKED=1 \
  AMADEUS_TEST_QS_STATE="$restart_state" \
  AMADEUS_TEST_QS_LOG="$restart_log" \
  AMADEUS_TEST_QS_ENV_LOG="$restart_env_log" \
  AMADEUS_TEST_DISPATCH_LOG="$dispatch_log" \
  AMADEUS_TEST_IPC_LOG="$ipc_log" \
  AMADEUS_TEST_SESSION_PATH="$restart_root" \
  AMADEUS_TEST_NOTIFICATION_CHECKS="$test_tmp/notification-checks" \
  AMADEUS_TEST_NOTIFICATIONS_DIE=1 \
  timeout 10 "$ROOT/bin/amadeus-restart-shell" >"$test_tmp/dead-notifications.out" 2>&1; then
  fail "a restart whose notification service never returns must not report success"
fi
wait "$restart_pid_one" 2>/dev/null || true
restart_pid_one=""
grep -F "ipc -n -p $restart_root/shell call -- lock lock" "$ipc_log" >/dev/null || fail "lock recovery waited on the notification service" "$(cat "$ipc_log")"
[[ -f $restart_state.locked ]] || fail "lock recovery did not re-secure the session without notifications"
grep -q "notification service did not become ready" "$test_tmp/dead-notifications.out" || fail "a missing notification service is not reported" "$(cat "$test_tmp/dead-notifications.out")"
pass "restart recovers the lock even when the notification service never returns"

# A worktree's shell left running after a visual check holds the notification
# server and is out of amadeus-shell's reach, so a restart stops it too. A
# Quickshell config that is not an Amadeus tree is someone else's and stays.
worktree_root="$test_tmp/worktree"
other_root="$test_tmp/other"
mkdir -p "$worktree_root/shell" "$worktree_root/bin" "$other_root/shell"
ln -s "$ROOT/bin/amadeus-launch-shell" "$worktree_root/bin/amadeus-launch-shell"
sleep 30 &
restart_pid_one=$!
sleep 30 &
restart_pid_two=$!
printf '%s %s\n%s %s\n' "$worktree_root/shell" "$restart_pid_one" "$other_root/shell" "$restart_pid_two" >"$test_tmp/strays"
printf '303\n' >"$restart_state"
rm -f "$restart_state.locked" "$test_tmp/notification-checks"
: >"$restart_log"

PATH="$restart_bin:$PATH" \
AMADEUS_PATH="$restart_root" \
XDG_RUNTIME_DIR="$runtime_dir" \
AMADEUS_TEST_QS_STATE="$restart_state" \
AMADEUS_TEST_QS_STRAYS="$test_tmp/strays" \
AMADEUS_TEST_QS_LOG="$restart_log" \
AMADEUS_TEST_QS_ENV_LOG="$restart_env_log" \
AMADEUS_TEST_DISPATCH_LOG="$dispatch_log" \
AMADEUS_TEST_IPC_LOG="$ipc_log" \
AMADEUS_TEST_SESSION_PATH="$restart_root" \
  timeout 5 "$ROOT/bin/amadeus-restart-shell" || fail "restart with a worktree shell running succeeds"

if kill -0 "$restart_pid_one" 2>/dev/null; then
  fail "restart stops a worktree's shell" "$(cat "$restart_log")"
fi
! grep -q "^$worktree_root/shell " "$test_tmp/strays.at-launch" || fail "restart waits for a slow worktree shell to exit before launching"
kill -0 "$restart_pid_two" 2>/dev/null || fail "restart leaves a Quickshell config outside Amadeus running"
wait "$restart_pid_one" 2>/dev/null || true
restart_pid_one=""
[[ $(<"$restart_state") == 303 ]] || fail "restart with a worktree shell leaves one fresh session shell"
pass "restart stops a worktree's shell and leaves other Quickshell configs alone"
