#!/bin/bash
# Run the desktop system's own test suite (test/system) against this checkout, laid out as its tests expect.
# Run it with ./build.sh system: the tests start commands that act on a desktop session,
# so they run only in the build container, never in the session of the machine you work on.
# Usage: test/system.sh [shell|cli|all]   or   test/system.sh NAME-test.sh ...   (default: shell)
set -euo pipefail
[[ -e /.dockerenv ]] || { echo "Run this with ./build.sh system: it runs only in the build container." >&2; exit 1; }
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
system=$here/desktop/system/usr/share/amadeus
root=$(mktemp -d "${TMPDIR:-/tmp}/amadeus-system-test.XXXXXX")
trap 'rm -rf "$root"' EXIT

# The tests take their root from where they sit: give them a copy of the system's folders, its
# commands and Amadeus's own in one bin, the system configuration as etc, the migrations, and the
# default package set built from the installer's lists as the desktop package builds it.
cp -a "$system/." "$root/"
cp -a "$here"/desktop/bin/. "$root/bin/"
cp -a "$here/desktop/system/etc" "$root/etc"
cp -a "$here/desktop/migrations" "$root/migrations"
sed 's/#.*//' "$here"/installer/packages.{base,desktop,system} | tr -s ' \t' '\n' | grep . >"$root/install/amadeus-base.packages"
# The built-in skills point at the AI package's copy, which is not installed here.
for skill in "$here"/ai/skill/*/; do
  rm -f "$root/default/agents/skills/$(basename "$skill")"
  cp -a "$skill" "$root/default/agents/skills/"
done
cp -a "$here/test/system" "$root/test"

export PATH="$root/bin:$PATH"
# A session's private runtime directory, as a login has; some tests refuse to run without one.
export XDG_RUNTIME_DIR="$root/run"
mkdir -m 700 "$XDG_RUNTIME_DIR"
cd "$root"
if [[ ${1:-} == *-test.sh ]]; then
  status=0
  for name in "$@"; do bash "test/shell.d/$name" || status=1; done
  exit "$status"
fi
bash "test/${1:-shell}"
