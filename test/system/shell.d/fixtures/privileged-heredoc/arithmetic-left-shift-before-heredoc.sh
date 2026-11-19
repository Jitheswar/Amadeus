mask=$((1 << bits))

cat >/etc/amadeus/agent.conf <<EOF
helper=$HOME/.local/share/amadeus/bin/amadeus-agent
EOF
