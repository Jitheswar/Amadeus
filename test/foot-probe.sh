#!/bin/bash
# Self-test helper: runs inside a terminal window, waits while the theme changes, then asks the terminal for its background colour.
sleep 5
printf '\033]11;?\033\\'
IFS= read -rs -t 3 -d '\' reply
printf '%s' "$reply" >/tmp/foot-probe.out
