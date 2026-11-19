tmp=/tmp/amadeus-generated
cat >"$tmp" <<EOF
command=$HOME/.local/share/amadeus/bin/example
EOF
sudo install -m644 "${tmp}" /etc/amadeus/example.conf
