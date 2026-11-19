cat <<'EOF' | sudo tee /etc/udev/rules.d/99-amadeus.rules >/dev/null
SUBSYSTEM=="power_supply", RUN+="/usr/bin/amadeus-powerprofiles-set $HOME"
EOF

cat <<"XML" | sudo tee /etc/amadeus/agent.xml >/dev/null
<config path="$HOME/.local/share/amadeus" />
XML
