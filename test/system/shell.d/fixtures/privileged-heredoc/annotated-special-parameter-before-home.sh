# amadeus:heredoc-expands paths=none -- the positional argument is a scalar
sudo tee /etc/amadeus/example.conf <<EOF
argument=$1
command=$HOME/.local/share/amadeus/bin/example
EOF
