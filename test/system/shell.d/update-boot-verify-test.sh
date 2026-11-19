#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"
source "$SHELL_TEST_DIR/fixtures/sudo-boundary-test.sh"

# amadeus update's boot check through the real amadeus-update-boot, dispatcher
# and platform detector, inside the sudo boundary fixture: every other update
# step is a stub that records itself, and sudo records its arguments. A fake
# boot package's update-verify records itself and exits with the status it is
# given.
require_platform_fixtures "amadeus update's boot check on platform fixtures"

copy_boundary_file bin/amadeus-update
rm "$SUDO_TEST_ROOT/bin/amadeus-update-boot"
for command in amadeus-update-boot amadeus-lifecycle-dispatch amadeus-hw-platform; do
  ln -sfn "$ROOT/bin/$command" "$SUDO_TEST_ROOT/bin/$command"
done
export AMADEUS_UPDATE_LOGGED=1

tmp=$boundary_tmp/boot
mkdir -p "$tmp"
for platform in aarch64-apple aarch64 x86; do
  fake_platform "$tmp/$platform" "$platform"
done

# A lifecycle root whose update-verify exits with $2.
boot_package() {
  local lifecycle=$1 verify=$2
  rm -rf "$lifecycle"
  mkdir -p "$lifecycle/usr/lib/amadeus/mac-boot"
  printf '#!/bin/bash\necho update-verify >>%q\necho "the boot files do not match" >&2\nexit %s\n' "$tmp/boot-ran" "$verify" \
    >"$lifecycle/usr/lib/amadeus/mac-boot/update-verify"
  chmod 755 "$lifecycle"/usr/lib/amadeus/mac-boot/*
  chmod -R go-w "$lifecycle"
}
boot_package "$tmp/passing" 0
boot_package "$tmp/failing" 9
boot_package "$tmp/unverified" 1
mkdir -p "$tmp/none" "$tmp/older/usr/lib/amadeus/mac-boot" "$tmp/older/var/lib/pacman/local/amadeus-mac-boot-20260921-10"

# amadeus update -y on platform $1 with the boot package in lifecycle root $2.
# The platform's uname goes beside the stubbed steps, first on the PATH.
run_update() {
  local platform=$1 lifecycle=$2
  reset_boundary
  rm -f "$tmp/boot-ran"
  /usr/bin/cp "$tmp/$platform/bin/uname" "$SUDO_TEST_ROOT/bin/uname"
  status=0
  AMADEUS_PROC_ROOT="$tmp/$platform/proc" AMADEUS_LIFECYCLE_ROOT="$lifecycle" \
    "$SUDO_TEST_ROOT/bin/amadeus-update" -y >"$tmp/out" 2>"$tmp/err" || status=$?
}

# The line number of the first event in the sudo log that starts with $1.
at() {
  grep -n -m 1 -F -- "$1" "$SUDO_TEST_LOG" | cut -d: -f1
}

reboot_offered() {
  grep -q '^step:amadeus-update-restart --reboot-only' "$SUDO_TEST_LOG"
}

# x86 and plain aarch64: the boot check is a no-op, even with a
# failing boot-package entrypoint on disk, and nothing asks for root.
for platform in x86 aarch64; do
  run_update "$platform" "$tmp/failing"
  (( status == 0 )) || fail "$platform: an update reports success" "status $status: $(cat "$tmp/err")"
  [[ ! -e $tmp/boot-ran ]] || fail "$platform: no boot-package entrypoint runs" "$(cat "$tmp/boot-ran")"
  ! grep -q 'amadeus-lifecycle-dispatch' "$SUDO_TEST_LOG" || fail "$platform: the boot check asks for no root" "$(cat "$SUDO_TEST_LOG")"
  [[ ! -s $tmp/err ]] || fail "$platform: the boot check prints nothing" "$(cat "$tmp/err")"
  reboot_offered || fail "$platform: the reboot is offered" "$(cat "$SUDO_TEST_LOG")"
done
pass "x86 and plain aarch64 updates are unchanged: no boot check runs, nothing asks for root and the reboot is offered"

# Apple: verify runs once the last package step, AUR, is done, under the
# update's one authorization, before the reboot offer.
run_update aarch64-apple "$tmp/passing"
(( status == 0 )) || fail "apple: an update whose boot check passes reports success" "status $status: $(cat "$tmp/err")"
[[ $(cat "$tmp/boot-ran") == "update-verify" ]] || fail "apple: verify runs once" "$(cat "$tmp/boot-ran")"
aur=$(at 'step:amadeus-update-aur-pkgs') verify=$(at 'sudo amadeus-lifecycle-dispatch update-verify') hook=$(at 'step:amadeus-hook post-update')
[[ -n $aur && -n $verify && -n $hook ]] && (( hook < aur && aur < verify )) ||
  fail "apple: verify follows AUR" "$(cat "$SUDO_TEST_LOG")"
! grep -q '^sudo -k$' "$SUDO_TEST_LOG" ||
  fail "apple: verification shares the update's authorization" "$(cat "$SUDO_TEST_LOG")"
reboot_offered || fail "apple: a verified update offers the reboot"
pass "apple: verify runs as root through the boot package, and a verified update offers the reboot"

# amadeus-update-boot takes no operation, so a caller still asking for a
# preflight is a usage error rather than a verification.
status=0
"$SUDO_TEST_ROOT/bin/amadeus-update-boot" preflight >/dev/null 2>&1 || status=$?
(( status == 2 )) || fail "amadeus-update-boot refuses an argument" "status $status"
pass "amadeus-update-boot refuses an argument"

# A failed verification lets the update finish its remaining steps, then fails
# it without offering the reboot.
run_update aarch64-apple "$tmp/unverified"
(( status == 1 )) || fail "apple: a failed verification fails the update" "status $status: $(cat "$tmp/err")"
! reboot_offered || fail "apple: a failed verification offers no reboot"
grep -q '^step:amadeus-update-stay-awake stop' "$SUDO_TEST_LOG" ||
  fail "apple: after a failed verification Stay Awake is released" "$(cat "$SUDO_TEST_LOG")"
grep -q 'the boot files do not match' "$tmp/err" && grep -q 'The update is not finished' "$tmp/err" ||
  fail "apple: a failed verification says why, and that the update is not finished" "$(cat "$tmp/err")"
! grep -q 'Something went wrong during the update' "$tmp/out" "$tmp/err" || fail "apple: a failed verification is not reported as a crash"
pass "apple: a failed verification fails the update, explained, with no reboot offered"

# A Mac without the boot package at all predates it: the update warns that its
# boot files were not verified and finishes, asking for no root.
run_update aarch64-apple "$tmp/none"
(( status == 0 )) && reboot_offered || fail "apple without the boot package: the update finishes and offers the reboot" "status $status: $(cat "$tmp/err")"
grep -q 'update-verify on aarch64-apple needs amadeus-mac-boot' "$tmp/err" && grep -q 'The boot files were not verified' "$tmp/err" ||
  fail "apple without the boot package: the update says the boot files were not verified" "$(cat "$tmp/err")"
! grep -q 'amadeus-lifecycle-dispatch' "$SUDO_TEST_LOG" || fail "apple without the boot package: nothing asks for root"
pass "apple: without the boot package the update warns that the boot files were not verified"

# A boot package from before update-verify is one package update away.
run_update aarch64-apple "$tmp/older"
(( status == 1 )) && ! reboot_offered || fail "apple: a boot package without update-verify fails the update" "status $status: $(cat "$tmp/err")"
grep -q 'which amadeus-mac-boot 20260921-10 does not provide; update amadeus-mac-boot' "$tmp/err" ||
  fail "apple: a boot package without update-verify is named with its version" "$(cat "$tmp/err")"
pass "apple: a boot package without update-verify fails the update and asks for its update"
