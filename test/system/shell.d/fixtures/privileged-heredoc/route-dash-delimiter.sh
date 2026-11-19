if true; then
  cat <<-EOF | sudo tee /etc/amadeus/indented.conf >/dev/null
	helper=$HOME/.local/share/amadeus/bin/amadeus-agent
	EOF
fi
