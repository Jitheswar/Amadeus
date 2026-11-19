#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# The default set is the installer's lists, shipped as install/amadeus-base.packages.
mkdir -p "$work/amadeus/install" "$work/stubs"
printf '# The base system\nbase\nlinux-cachyos\n\n# Sound\npipewire\npipewire-jack  # JACK programs\n' \
  >"$work/amadeus/install/amadeus-base.packages"
cat >"$work/stubs/amadeus-update-pacman" <<'SH'
#!/bin/bash
printf 'pacman %s\n' "$*" >>"$STUB_LOG"
SH
cat >"$work/stubs/amadeus-hardware" <<'SH'
#!/bin/bash
printf 'hardware %s\n' "$*" >>"$STUB_LOG"
SH
cat >"$work/stubs/amadeus-hw-platform" <<'SH'
#!/bin/bash
echo generic
SH
# INSTALLED names the packages pacman reports as installed.
cat >"$work/stubs/pacman" <<'SH'
#!/bin/bash
[[ $1 == "-Q" && $2 == "--" ]] && grep -Fxq "$3" <<<"${INSTALLED:-}"
SH
chmod +x "$work/stubs/"*

reinstall() {
  : >"$STUB_LOG"
  AMADEUS_PATH="$work/amadeus" PATH="$work/stubs:$ROOT/bin:$PATH" amadeus-reinstall-pkgs
}

export STUB_LOG="$work/log"
reinstall
[[ $(<"$STUB_LOG") == $'pacman -Syu --noconfirm --ask 4 --needed base linux-cachyos pipewire pipewire-jack\nhardware setup' ]] ||
  fail "reinstall installs the default set, then this computer's drivers" "$(<"$STUB_LOG")"
pass "reinstall installs the default set, then this computer's drivers"

for server in jack2 jack; do
  INSTALLED=$server reinstall
  [[ $(head -n 1 "$STUB_LOG") == "pacman -Syu --noconfirm --ask 4 --needed base linux-cachyos pipewire" ]] ||
    fail "reinstall keeps an installed $server" "$(<"$STUB_LOG")"
done
pass "reinstall leaves pipewire-jack out where jack or jack2 is installed"
