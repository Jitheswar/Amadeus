tmp=/tmp/amadeus-generated
copy=$tmp
cat >"$tmp" <<EOF
command=$HOME/.local/share/amadeus/bin/example
EOF
sudo install -m644 "$copy" /etc/amadeus/example.conf
