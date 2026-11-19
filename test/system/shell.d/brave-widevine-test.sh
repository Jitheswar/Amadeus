#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"


test_tmp=$(mktemp -d)
trap 'rm -rf "$test_tmp"' EXIT
stub_bin="$test_tmp/bin"
amadeus_path="$test_tmp/amadeus"
opt_path="$test_tmp/opt"
cdm="$opt_path/WidevineCdm/chromium"
calls="$test_tmp/calls.log"
mkdir -p "$stub_bin" "$test_tmp/home" "$amadeus_path/install/helpers" "$amadeus_path/config"

# The real policy helper writes under /etc without sudo when run as root, so
# stand it in; this test covers only the CDM link. Its as_root goes through the
# sudo stub, which logs every link, whatever the test's EUID.
printf 'browser_policy_setup_dir() { :; }\nas_root() { sudo "$@"; }\n' >"$amadeus_path/install/helpers/browser-policy.sh"
cp "$ROOT/config/chromium-flags.conf" "$amadeus_path/config/"

for command in amadeus-pkg-add amadeus-pkg-aur-add amadeus-install-chromium-copy-url amadeus-install-chromium-ytdlp amadeus-theme-set-browser amadeus-lifecycle-dispatch; do
  printf '#!/bin/bash\nexit 0\n' >"$stub_bin/$command"
done
cat >"$stub_bin/sudo" <<'SH'
#!/bin/bash
printf 'sudo:%s\n' "$*" >>"$TEST_LOG"
"$@"
SH
chmod +x "$stub_bin"/*

reset_opt() {
  rm -rf "$opt_path"
  mkdir -p "$opt_path"
  local dir
  for dir in "$@"; do
    mkdir -p "$opt_path/$dir"
  done
}

run() {
  : >"$calls"
  HOME="$test_tmp/home" AMADEUS_PATH="$amadeus_path" AMADEUS_OPT_PATH="$opt_path" \
    TEST_LOG="$calls" PATH="$stub_bin:$PATH" "$@" >/dev/null
}

install_browser() {
  run bash "$ROOT/bin/amadeus-install-browser" "$1"
}

links_made() {
  grep -c '^sudo:ln ' "$calls" || true
}

assert_cdm_linked() {
  [[ -L $opt_path/$1/WidevineCdm && $(readlink "$opt_path/$1/WidevineCdm") == "$cdm" ]] ||
    fail "$2" "$(ls -la "$opt_path/$1" 2>&1)"
}

for browser in brave brave-origin; do
  install_dir=$browser-bin

  reset_opt WidevineCdm/chromium "$install_dir"
  install_browser "$browser"
  assert_cdm_linked "$install_dir" "$browser install links the system Widevine CDM into $install_dir"
  install_browser "$browser"
  (( $(links_made) == 0 )) || fail "$browser reinstall keeps the existing CDM link" "$(<"$calls")"
  assert_cdm_linked "$install_dir" "$browser reinstall keeps the existing CDM link"
  pass "$browser install links the system Widevine CDM into $install_dir once"

  reset_opt "$install_dir"
  install_browser "$browser"
  [[ ! -e $opt_path/$install_dir/WidevineCdm && ! -L $opt_path/$install_dir/WidevineCdm ]] ||
    fail "$browser install links nothing without the widevine package"
  pass "$browser install links nothing without the widevine package"

  reset_opt WidevineCdm/chromium "$install_dir" own-cdm
  ln -s "$opt_path/own-cdm" "$opt_path/$install_dir/WidevineCdm"
  install_browser "$browser"
  [[ $(readlink "$opt_path/$install_dir/WidevineCdm") == "$opt_path/own-cdm" ]] ||
    fail "$browser install keeps a CDM the browser already has"
  pass "$browser install keeps a CDM the browser already has"
done

reset_opt WidevineCdm/chromium
install_browser chromium
(( $(links_made) == 0 )) || fail "Chromium install leaves Widevine to the widevine package" "$(<"$calls")"
pass "Chromium install leaves Widevine to the widevine package"
