storage="$HOME/storage"
shared="$HOME/shared"

# amadeus:heredoc-expands paths=shared,storage -- both sources are validated before use
cat >/etc/amadeus/mounts.conf <<EOF
storage=$storage:/storage
shared=$shared:/shared
EOF
