#!/bin/bash

set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/base-test.sh"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
export AMADEUS_PATH=$ROOT XDG_CONFIG_HOME=$work/config NOTIFY_LOG=$work/notify.log
mkdir -p "$work/stubs"
printf '#!/bin/bash\n' >"$work/stubs/amadeus-restart-shell"
printf '#!/bin/bash\necho "$@" >>"$NOTIFY_LOG"\n' >"$work/stubs/amadeus-notification-send"
chmod +x "$work/stubs/"*
export PATH="$work/stubs:$ROOT/bin:$PATH"
preference=$XDG_CONFIG_HOME/fontconfig/conf.d/50-amadeus-input-method.conf

[[ $(amadeus-font-cjk) == "default" ]] || fail "with no preference the CJK forms are the default" "$(amadeus-font-cjk)"
pass "with no preference the CJK forms are the default"

amadeus-font-cjk tc
grep -q 'Noto Sans CJK TC' "$preference" || fail "setting tc writes the preference"
[[ $(amadeus-font-cjk) == "tc" ]] || fail "the current forms read back as set" "$(amadeus-font-cjk)"
grep -q "$(amadeus-i18n font.cjkChanged)" "$NOTIFY_LOG" || fail "a change is announced" "$(cat "$NOTIFY_LOG")"
pass "setting the CJK forms writes, reads back and announces the choice"

# A preference the first input method seeded reads back and can be changed.
rm "$preference"
python3 "$ROOT/default/input-methods/configure.py" font --seed kr
[[ $(amadeus-font-cjk) == "kr" ]] || fail "a seeded preference reads back" "$(amadeus-font-cjk)"
amadeus-font-cjk hk
[[ $(amadeus-font-cjk) == "hk" ]] || fail "a seeded preference can be changed" "$(amadeus-font-cjk)"
pass "the preference an input method seeded is the one the command changes"

amadeus-font-cjk default
[[ $(amadeus-font-cjk) == "default" ]] || fail "default reads back" "$(amadeus-font-cjk)"
! grep -q 'CJK' "$preference" || fail "default names no CJK forms" "$(cat "$preference")"
python3 "$ROOT/default/input-methods/configure.py" font --seed kr
[[ $(amadeus-font-cjk) == "default" ]] || fail "a later language or input method keeps an explicit default" "$(amadeus-font-cjk)"
pass "default returns to the system's choice, and later seeding keeps it"

if amadeus-font-cjk cn 2>/dev/null; then
  fail "an unknown variant is refused"
fi
pass "an unknown variant is refused"

