tmp=$(mktemp)

cat >"$tmp" <<EOF
#!/bin/bash
exec "$HOME/.local/share/amadeus/bin/amadeus-agent" "$@"
EOF

sudo install -m 0755 "$tmp" /usr/local/bin/amadeus-agent-shim
