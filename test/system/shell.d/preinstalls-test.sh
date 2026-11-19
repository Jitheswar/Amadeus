#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"

test_tmp=$(mktemp -d)
trap 'rm -rf "$test_tmp"' EXIT

mock_bin="$test_tmp/bin"
test_home="$test_tmp/home"
marker="$test_home/.local/state/amadeus/preinstalls-removed"
mise_config="$test_tmp/etc/mise/config.toml"
pkg_log="$test_tmp/packages"
mkdir -p "$mock_bin" "$test_home/.local/state/amadeus"

for command in amadeus-webapp-remove-all amadeus-tui-remove-all amadeus-refresh-applications hyprctl; do
  printf '#!/bin/bash\nexit 0\n' >"$mock_bin/$command"
done

cat >"$mock_bin/gum" <<'SH'
#!/bin/bash
[[ $1 == confirm ]] && exit "${AMADEUS_TEST_CONFIRM:-0}"
exit 0
SH

cat >"$mock_bin/amadeus-pkg-add" <<'SH'
#!/bin/bash
printf '%s\n' "$@" >"$AMADEUS_TEST_PKG_LOG"
exit "${AMADEUS_TEST_PKG_ADD_STATUS:-0}"
SH

cat >"$mock_bin/amadeus-pkg-drop" <<'SH'
#!/bin/bash
printf '%s\n' "$@" >"$AMADEUS_TEST_PKG_LOG"
SH

cat >"$mock_bin/mise" <<'SH'
#!/bin/bash
printf '%s\n' "$*" >>"$AMADEUS_TEST_MISE_LOG"
[[ $* == 'reshim --system' ]] && exit "${AMADEUS_TEST_RESHIM_STATUS:-0}"
exit 0
SH

cat >"$mock_bin/amadeus-pkg-present" <<'SH'
#!/bin/bash
exit 1
SH

chmod +x "$mock_bin"/*

# $ROOT/bin after the mocks, so the real helpers answer wherever a mock does not
# shadow them.
export PATH="$mock_bin:$ROOT/bin:$PATH"
export HOME="$test_home"
export AMADEUS_PATH="$ROOT"
export AMADEUS_MISE_CONFIG_PATH="$mise_config"
export AMADEUS_TEST_MISE_LOG="$test_tmp/mise-log"
mkdir -p "$(dirname "$mise_config")"
cp "$ROOT/etc/mise/conf.d/amadeus-tools.toml" "$mise_config"
# The user's own setting must survive the opt-out round trip, and the opt-out
# line must start on a line of its own.
miserc="$test_home/.config/mise/miserc.toml"
ignore_line="ignored_config_paths = [\"$mise_config\"]"
mkdir -p "$(dirname "$miserc")"
printf 'env = ["work"]' >"$miserc"
export AMADEUS_TEST_PKG_LOG="$pkg_log"

# Both scripts restore and remove the same set, and every package in it has to be
# one Amadeus actually ships, or Remove Preinstalls takes out an app the user
# chose from the menu and Install Preinstalls puts back one we retired.
mapfile -t shipped < <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$ROOT/install/amadeus-base.packages")

"$ROOT/bin/amadeus-install-preinstalls" >/dev/null
mapfile -t restored <"$pkg_log"
grep -Fx 'reshim --system' "$AMADEUS_TEST_MISE_LOG" >/dev/null || fail "Install Preinstalls rebuilds the mise shims"
pass "Install Preinstalls rebuilds the mise shims"

: >"$AMADEUS_TEST_MISE_LOG"
"$ROOT/bin/amadeus-remove-preinstalls" >/dev/null
mapfile -t dropped <"$pkg_log"
[[ $(<"$miserc") == "env = [\"work\"]"$'\n'"$ignore_line" ]] ||
  fail "Remove Preinstalls has mise skip Amadeus's declarations for this user" "$(<"$miserc")"
grep -Fx 'reshim' "$AMADEUS_TEST_MISE_LOG" >/dev/null || fail "Remove Preinstalls retires the lazy shims"
pass "Remove Preinstalls has mise skip Amadeus's declarations for this user"

"$ROOT/bin/amadeus-install-preinstalls" >/dev/null
[[ $(<"$miserc") == 'env = ["work"]' ]] || fail "Install Preinstalls removes only its own miserc line" "$(<"$miserc")"
pass "Install Preinstalls removes only its own miserc line"

rm "$miserc"
"$ROOT/bin/amadeus-mise-default-tools" disable >/dev/null
"$ROOT/bin/amadeus-mise-default-tools" disable >/dev/null
[[ $(<"$miserc") == "$ignore_line" ]] || fail "opting out twice adds the line once" "$(<"$miserc")"
"$ROOT/bin/amadeus-mise-default-tools" enable >/dev/null
[[ ! -e $miserc ]] || fail "opting back in removes a miserc that held only the opt-out"
pass "opting out is idempotent and reversible"

# A list the user wrote is theirs to edit. Once it names the file, both
# directions agree that the user has opted out.
printf 'ignored_config_paths = ["~/old"]\n' >"$miserc"
"$ROOT/bin/amadeus-mise-default-tools" disable >/dev/null 2>&1 && status=0 || status=$?
((status == 1)) || fail "opting out refuses to add a second ignored_config_paths" "exit status was $status"
[[ $(<"$miserc") == 'ignored_config_paths = ["~/old"]' ]] || fail "opting out leaves the user's list alone"
printf 'ignored_config_paths = ["~/old", "%s"]\n' "$mise_config" >"$miserc"
"$ROOT/bin/amadeus-mise-default-tools" disable >/dev/null || fail "opting out accepts the file in the user's own list"
"$ROOT/bin/amadeus-mise-default-tools" declares codex && fail "a user's own list keeps Amadeus's tools undeclared"
"$ROOT/bin/amadeus-mise-default-tools" enable >/dev/null 2>&1 && status=0 || status=$?
((status == 1)) || fail "opting back in reports a list it cannot edit" "exit status was $status"
rm "$miserc"
pass "an existing ignored_config_paths is left to the user"

printf '# %s\n' "$ignore_line" >"$miserc"
"$ROOT/bin/amadeus-mise-default-tools" declares codex || fail "a commented-out opt-out keeps Amadeus's tools declared"
"$ROOT/bin/amadeus-mise-default-tools" disable >/dev/null
grep -qxF "$ignore_line" "$miserc" || fail "opting out is not skipped by a commented-out opt-out"
"$ROOT/bin/amadeus-mise-default-tools" enable >/dev/null || fail "opting back in succeeds past a commented-out opt-out"
rm "$miserc"
pass "a commented-out opt-out does not count"
"$ROOT/bin/amadeus-remove-preinstalls" >/dev/null

[[ ${restored[*]} == "${dropped[*]}" ]] ||
  fail "Install and Remove Preinstalls cover the same packages" \
    "restored: ${restored[*]}
dropped:  ${dropped[*]}"
pass "Install and Remove Preinstalls cover the same packages"

for package in "${restored[@]}"; do
  grep -qxF "$package" <<<"$(printf '%s\n' "${shipped[@]}")" ||
    fail "every preinstall is shipped in amadeus-base.packages" "$package is not shipped"
done
pass "every preinstall is shipped in amadeus-base.packages"

for package in omacut monologue omacalc omawrite hype signed; do
  grep -qxF "$package" <<<"$(printf '%s\n' "${restored[@]}")" ||
    fail "preinstalls cover the Omacom apps" "$package is missing"
done
pass "preinstalls cover the Omacom apps"

# The bindings key off the marker, so clearing it before the packages land would
# point them at apps that never came back.
touch "$marker"
AMADEUS_TEST_PKG_ADD_STATUS=1 "$ROOT/bin/amadeus-install-preinstalls" >/dev/null && status=0 || status=$?
(( status == 1 )) || fail "restore reports a failed package transaction" "exit status was $status"
[[ -f $marker ]] || fail "restore keeps the opt-out marker when packages fail to install"
pass "restore keeps the opt-out marker when packages fail to install"

for failure in AMADEUS_TEST_RESHIM_STATUS; do
  touch "$marker"
  : >"$pkg_log"
  env "$failure=1" "$ROOT/bin/amadeus-install-preinstalls" >/dev/null && status=0 || status=$?
  (( status == 1 )) || fail "restore reports a failed tool setup" "$failure returned $status"
  [[ -f $marker ]] || fail "restore keeps the opt-out marker after failed tool setup" "$failure"
  [[ ! -s $pkg_log ]] || fail "restore stops before installing packages when tool setup fails" "$failure"
done
pass "restore stops and preserves opt-out when shim setup fails"


"$ROOT/bin/amadeus-install-preinstalls" >/dev/null
[[ ! -e $marker ]] || fail "restore clears the opt-out marker once the packages are back"
pass "restore clears the opt-out marker once the packages are back"

rm -f "$marker"
AMADEUS_TEST_CONFIRM=1 "$ROOT/bin/amadeus-remove-preinstalls" >/dev/null
[[ ! -e $marker ]] || fail "declining Remove Preinstalls changes nothing"
pass "declining Remove Preinstalls changes nothing"

"$ROOT/bin/amadeus-remove-preinstalls" >/dev/null
[[ -f $marker ]] || fail "Remove Preinstalls records the opt-out"
pass "Remove Preinstalls records the opt-out"

mkdir -p "$(dirname "$mise_config")"
touch "$mise_config"
"$ROOT/bin/amadeus-remove-preinstalls" >/dev/null
[[ -f $mise_config ]] || fail "Remove Preinstalls leaves the package-owned mise declarations in place"
pass "Remove Preinstalls leaves the package-owned mise declarations in place"
