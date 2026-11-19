#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/base-test.sh"

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

home="$tmpdir/home"
amadeus_path="$tmpdir/amadeus"

mkdir -p "$home/.config/hypr" "$amadeus_path/config/hypr"

cat >"$amadeus_path/config/hypr/bindings.lua" <<'EOF'
-- refreshed from AMADEUS_PATH
EOF

cat >"$home/.config/hypr/bindings.lua" <<'EOF'
-- existing user config
EOF

HOME="$home" AMADEUS_PATH="$amadeus_path" "$ROOT/bin/amadeus-refresh-config" hypr/bindings.lua >/dev/null

cmp -s "$amadeus_path/config/hypr/bindings.lua" "$home/.config/hypr/bindings.lua" ||
  fail "refresh-config copies from AMADEUS_PATH/config"

backup=$(find "$home/.config/hypr" -name 'bindings.lua.bak.*' -print -quit)
[[ -n $backup ]] || fail "refresh-config backs up replaced user config"
grep -Fq -- '-- existing user config' "$backup" ||
  fail "refresh-config backup contains previous user config"

pass "refresh-config copies from AMADEUS_PATH/config and backs up existing files"

if HOME="$home" AMADEUS_PATH="$amadeus_path" "$ROOT/bin/amadeus-refresh-config" hypr/missing.lua >"$tmpdir/out" 2>"$tmpdir/err"; then
  fail "refresh-config rejects configs missing from AMADEUS_PATH/config"
fi

grep -Fq 'Not a shipped user config: hypr/missing.lua' "$tmpdir/err" ||
  fail "refresh-config reports missing shipped config"

pass "refresh-config validates against AMADEUS_PATH/config"

# Both sides of a traversal have to exist for the escape to be live: without a
# mirrored source the pre-existing "Not a shipped user config" check rejects it
# anyway, and the test passes with the guard deleted.
escape="$home/escape"
echo "do not touch" >"$escape"
echo "-- traversal source" >"$amadeus_path/escape"

refuses() {
  local config_file="$1"

  if HOME="$home" AMADEUS_PATH="$amadeus_path" "$ROOT/bin/amadeus-refresh-config" "$config_file" >"$tmpdir/out" 2>"$tmpdir/err"; then
    fail "refresh-config rejects $config_file"
  fi

  grep -Fq "Invalid config path: $config_file" "$tmpdir/err" ||
    fail "refresh-config reports $config_file as an invalid config path" "$(cat "$tmpdir/err")"

  [[ $(cat "$escape") == "do not touch" ]] ||
    fail "refresh-config leaves files outside .config untouched: $config_file"
}

refuses ../escape
refuses hypr/../../escape
refuses ..
refuses hypr/..
refuses /etc/passwd

pass "refresh-config rejects paths escaping .config"
