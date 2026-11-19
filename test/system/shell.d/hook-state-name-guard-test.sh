#!/bin/bash

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/base-test.sh"

work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

fake_home="$work_dir/home"
mkdir -p "$fake_home/.config/amadeus/hooks" "$fake_home/.local/state/amadeus"

# A hook or state name is a label, not a path. One carrying a slash, or one
# that is a bare `.` or `..`, would reach outside the hooks or state directory:
# the runner would run a script from there, the installer would mkdir/cp
# there, and state set would touch a file there.

# --- names that stay inside the directory ------------------------------------

cat >"$fake_home/.config/amadeus/hooks/test-hook" <<'SH'
touch "$HOME/hook-ran"
SH

HOME="$fake_home" "$ROOT/bin/amadeus-hook" test-hook
[[ -f $fake_home/hook-ran ]] ||
  fail "amadeus hook runs a named hook from the hooks directory"
pass "amadeus hook runs a named hook from the hooks directory"

# Dots inside a name are not a path. a..b stays inside the hooks directory.
cat >"$fake_home/.config/amadeus/hooks/a..b" <<'SH'
touch "$HOME/dotted-hook-ran"
SH

HOME="$fake_home" "$ROOT/bin/amadeus-hook" a..b
[[ -f $fake_home/dotted-hook-ran ]] ||
  fail "amadeus hook accepts a hook name with dots in the middle"
pass "amadeus hook accepts a hook name with dots in the middle"

source_hook="$work_dir/source-hook"
cat >"$source_hook" <<'SH'
#!/bin/bash
true
SH

HOME="$fake_home" "$ROOT/bin/amadeus-hook-install" post-update "$source_hook" >/dev/null
[[ -f $fake_home/.config/amadeus/hooks/post-update.d/source-hook ]] ||
  fail "amadeus hook install still installs a named hook"
pass "amadeus hook install still installs a named hook"

HOME="$fake_home" "$ROOT/bin/amadeus-hook-install" a..b "$source_hook" >/dev/null
[[ -f $fake_home/.config/amadeus/hooks/a..b.d/source-hook ]] ||
  fail "amadeus hook install accepts a hook name with dots in the middle"
pass "amadeus hook install accepts a hook name with dots in the middle"

state_dir="$fake_home/.local/state/amadeus"

HOME="$fake_home" "$ROOT/bin/amadeus-state" set reboot-required
[[ -f $state_dir/reboot-required ]] ||
  fail "amadeus state set still creates a plain state file"
pass "amadeus state set still creates a plain state file"

HOME="$fake_home" "$ROOT/bin/amadeus-state" set v1..2
[[ -f $state_dir/v1..2 ]] ||
  fail "amadeus state set accepts a state name with dots in the middle"
pass "amadeus state set accepts a state name with dots in the middle"

# --- names that would leave it ------------------------------------------------

# This file sits where a hook name of ../../evil would resolve: hooks/../.. is
# ~/.config. The same name is ~/.config/evil.d to the installer and
# ~/.local/evil to state set.
cat >"$fake_home/.config/evil" <<'SH'
touch "$HOME/escape-ran"
SH
chmod +x "$fake_home/.config/evil"

snapshot() {
  find "$fake_home" | sort
}

# A refused name exits 2 and leaves the home exactly as it was: nothing run,
# nothing created.
refused() {
  local description=$1 before after status=0
  shift
  before=$(snapshot)
  HOME="$fake_home" "$@" >/dev/null 2>&1 || status=$?
  after=$(snapshot)
  (( status == 2 )) || fail "$description" "exit: $status"
  [[ $after == "$before" ]] || fail "$description" "$(diff <(printf '%s\n' "$before") <(printf '%s\n' "$after"))"
  pass "$description"
}

for name in . .. ../../evil sub/dir; do
  refused "amadeus hook refuses a hook name of $name" "$ROOT/bin/amadeus-hook" "$name"
  refused "amadeus hook install refuses a hook name of $name" "$ROOT/bin/amadeus-hook-install" "$name" "$source_hook"
  refused "amadeus state set refuses a state name of $name" "$ROOT/bin/amadeus-state" set "$name"
done

# clear takes patterns by design ("state-name-or-pattern") and matches
# basenames through find -name, so it can never walk out of the directory.
touch "$state_dir/restart-a-required" "$state_dir/restart-b-required" "$state_dir/keep-me"
HOME="$fake_home" "$ROOT/bin/amadeus-state" clear "restart-*-required"
[[ ! -e $state_dir/restart-a-required && ! -e $state_dir/restart-b-required && -f $state_dir/keep-me ]] ||
  fail "amadeus state clear still clears matching patterns only"
pass "amadeus state clear still clears matching patterns only"
