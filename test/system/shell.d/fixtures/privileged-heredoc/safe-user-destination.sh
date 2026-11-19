mkdir -p ~/.config/amadeus

cat >~/.config/amadeus/agent.conf <<EOF
helper=$HOME/.local/share/amadeus/bin/amadeus-agent
EOF

cat >"$HOME/.local/bin/amadeus-shim" <<EOF
exec "$AMADEUS_PATH/bin/amadeus-agent" "$@"
EOF
