# `>|` is a plain redirect with noclobber overridden, not a redirect into a pipe.
cat >|/etc/amadeus/agent.conf <<EOF
helper=$HOME/.local/share/amadeus/bin/amadeus-agent
EOF
