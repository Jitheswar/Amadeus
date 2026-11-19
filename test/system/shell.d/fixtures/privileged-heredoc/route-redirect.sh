# A plain redirect into /etc, no sudo: the command re-execs itself as root.
cat >/etc/amadeus/agent.conf <<EOF
helper=$HOME/.local/share/amadeus/bin/amadeus-agent
EOF
