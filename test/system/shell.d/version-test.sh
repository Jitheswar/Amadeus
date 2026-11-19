#!/bin/bash

set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"

test_tmp=$(mktemp -d)
trap 'rm -rf "$test_tmp"' EXIT

stub_bin="$test_tmp/bin"
mkdir -p "$stub_bin"

# The edge channel installs amadeus-desktop. Older builds did not declare
# provides=(amadeus), so a query for plain amadeus finds nothing there.
cat >"$stub_bin/pacman" <<'STUB'
#!/bin/bash
[[ $1 == "-Q" ]] || exit 1
shift
for package in "$@"; do
  case ",${AMADEUS_TEST_PACKAGES:-}," in
    *",$package,"*)
      echo "$package ${AMADEUS_TEST_VERSION:-4.0.0-1}"
      exit 0
      ;;
  esac
done
echo "error: package '$1' was not found" >&2
exit 1
STUB
chmod +x "$stub_bin/pacman"

version() {
  AMADEUS_TEST_PACKAGES="$1" \
    AMADEUS_PATH="${2:-/usr/share/amadeus}" \
    PATH="$stub_bin:$PATH" \
    "$ROOT/bin/amadeus-version"
}

[[ $(version amadeus) == "4.0.0-1" ]] || fail "version reports the stable package"
pass "version reports the stable package"

[[ $(version amadeus-desktop) == "4.0.0-1" ]] || fail "version reports the edge package"
pass "version reports the edge package"

# A checkout reports its hash instead, so packages are irrelevant there.
[[ $(version "" "$test_tmp/checkout") == "dev" ]] || fail "version reports a dev checkout"
pass "version reports a dev checkout"

if version "" >/dev/null 2>&1; then
  fail "version fails when no Amadeus package is installed"
fi
pass "version fails when no Amadeus package is installed"
