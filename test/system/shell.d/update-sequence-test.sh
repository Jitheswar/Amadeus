#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"
source "$SHELL_TEST_DIR/fixtures/sudo-boundary-test.sh"
copy_boundary_file bin/amadeus-update
test_tmp="$boundary_tmp"
stub_bin="$SUDO_TEST_ROOT/bin"

# Every step amadeus-update runs, recorded in order with the unattended flag it
# was handed. One of them can be told to fail. amadeus-update-available is here
# so a recheck after the update would show up as an unexpected step.
steps=(
  amadeus-update-lock
  amadeus-update-requires-free-space
  amadeus-update-confirm
  amadeus-update-pkg-prune
  amadeus-snapshot
  amadeus-update-stay-awake
  amadeus-mirrors
  amadeus-update-dev
  amadeus-hardware
  amadeus-update-boot
  amadeus-update-keyring
  amadeus-update-system-pkgs
  amadeus-migrate
  amadeus-restart-shell
  amadeus-hook
  amadeus-update-aur-pkgs
  amadeus-update-mise
  amadeus-update-orphan-pkgs
  amadeus-update-analyze-logs
  amadeus-shell
  amadeus-update-available
  amadeus-update-restart
)

for step in "${steps[@]}"; do
  rm -f "$stub_bin/$step"
  cat >"$stub_bin/$step" <<'STUB'
#!/bin/bash
step=${0##*/}
# The pending check is a step of its own, so the order around the restart shows.
if [[ $step == "amadeus-migrate" && ${1:-} == "--pending" ]]; then
  step+=":--pending"
fi
printf '%s unattended=%s\n' "$step" "${AMADEUS_UPDATE_UNATTENDED:-}" >>"$STEP_LOG"
[[ $step != "amadeus-migrate:--pending" || ${NO_PENDING:-} != 1 ]] || exit 1
if [[ ${0##*/} == "amadeus-update-orphan-pkgs" ]]; then
  printf '%s\n' "$@" >"$STEP_LOG.orphan-args"
fi
if [[ ${0##*/} == "amadeus-shell" ]]; then
  printf '%s\n' "$*" >"$STEP_LOG.shell-args"
fi
[[ ${FAILING_STEP:-} != "${0##*/}" ]] || exit 1
STUB
  chmod +x "$stub_bin/$step"
done

# AMADEUS_UPDATE_LOGGED stands in for the script(1) wrapper the update re-execs
# itself under; the stubbed lock reports itself already held.
run_update() {
  : >"$test_tmp/steps"
  STEP_LOG="$test_tmp/steps" \
    FAILING_STEP="${FAILING_STEP:-}" \
    AMADEUS_UPDATE_LOGGED=1 \
    PATH="$stub_bin:$PATH" \
    "$SUDO_TEST_ROOT/bin/amadeus-update" "$@" >"$test_tmp/out" 2>"$test_tmp/err"
}

steps_run() {
  cut -d' ' -f1 "$test_tmp/steps"
}

# Every step of a whole update, in order. $1 asks for the one a person confirms;
# an empty $2 leaves out the shell restart, for an update with nothing to migrate.
# Stay Awake bookends the work, so it is here twice.
expected_steps() {
  printf '%s\n' \
    amadeus-update-lock \
    amadeus-update-requires-free-space \
    ${1:+amadeus-update-confirm} \
    amadeus-update-pkg-prune \
    amadeus-snapshot \
    amadeus-update-stay-awake \
    amadeus-mirrors \
    amadeus-update-dev \
    amadeus-update-keyring \
    amadeus-update-system-pkgs \
    amadeus-migrate:--pending \
    ${2-amadeus-restart-shell} \
    amadeus-migrate \
    amadeus-update-orphan-pkgs \
    amadeus-hardware \
    amadeus-update-analyze-logs \
    amadeus-shell \
    amadeus-update-restart \
    amadeus-hook \
    amadeus-update-mise \
    amadeus-update-aur-pkgs \
    amadeus-update-boot \
    amadeus-update-stay-awake \
    amadeus-update-restart
}

run_update -y || fail "an update where everything works reports a failure"
diff <(expected_steps) <(steps_run) >"$test_tmp/order" ||
  fail "an update where everything works does not run every step in order" "$(cat "$test_tmp/order")"
pass "an update where every step works runs all of them, in order"
[[ $(cat "$test_tmp/steps.orphan-args") == "-y" ]] || fail "an unattended update approves orphan removal"
pass "an unattended update approves orphan removal"
[[ $(cat "$test_tmp/steps.shell-args") == "-q amadeus.system-update clear" ]] ||
  fail "a finished update clears the shell update indicator" "$(cat "$test_tmp/steps.shell-args")"
pass "a finished update clears the shell update indicator without rechecking"

grep -q '^amadeus-update-system-pkgs unattended=1$' "$test_tmp/steps" ||
  fail "-y does not mark the update unattended"
run_update </dev/null || fail "a confirmed update reports a failure"
diff <(expected_steps confirmed) <(steps_run) >"$test_tmp/order" ||
  fail "a confirmed update runs a different set of steps" "$(cat "$test_tmp/order")"
grep -q '^amadeus-update-system-pkgs unattended=$' "$test_tmp/steps" ||
  fail "an update a person confirmed is treated as unattended"
pass "-y is what marks an update unattended, not the update itself"
[[ $(cat "$test_tmp/steps.orphan-args") == "-y" ]] || fail "a confirmed update approves orphan removal"
pass "a confirmed update approves orphan removal"

NO_PENDING=1 run_update -y || fail "an update with nothing to migrate reports a failure"
diff <(expected_steps "" "") <(steps_run) >"$test_tmp/order" ||
  fail "an update with nothing to migrate restarts the shell anyway" "$(cat "$test_tmp/order")"
pass "an update restarts the shell before migrating only when migrations are pending"

# Migrations ship with the packages the upgrade installs and are written against
# them. Running them against what is still on disk is the failure this ordering
# exists to prevent, so the update stops where the packages did.
if FAILING_STEP=amadeus-update-system-pkgs run_update -y; then
  fail "an update whose packages did not upgrade passes for a whole one"
fi
for step in amadeus-migrate amadeus-restart-shell amadeus-hook amadeus-update-aur-pkgs amadeus-update-restart; do
  if grep -q "^$step " "$test_tmp/steps"; then
    fail "a blocked package upgrade still runs $step"
  fi
done
pass "a blocked package upgrade stops the update before it migrates"

# Optional tools may fail after system packages have already changed. Finish
# AUR work, verify boot files and release Stay Awake before offering a reboot.
FAILING_STEP=amadeus-update-mise run_update -y || fail "a failed mise update prevents system update completion"
diff <(expected_steps) <(steps_run) >"$test_tmp/order" ||
  fail "a failed mise update skips later update steps" "$(cat "$test_tmp/order")"
grep -q "amadeus update mise" "$test_tmp/err" || fail "the tool update failure has no retry guidance"
pass "a mise failure still finishes the update, offers a reboot and explains how to retry"
