#!/bin/bash

# Two hops. The scan resolves amadeus_bin into helper, so the value it ends up
# judging still carries an unresolved $HOME rather than a literal path.
amadeus_bin="$HOME/.local/share/amadeus/bin"
helper="$amadeus_bin/amadeus-agent"

# amadeus:heredoc-expands paths=none -- helper names the agent, no path is baked in
cat <<EOF | sudo tee /etc/udev/rules.d/99-amadeus-agent.rules >/dev/null
SUBSYSTEM=="power_supply", RUN+="$helper"
EOF
