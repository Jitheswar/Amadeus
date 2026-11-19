#!/bin/bash

# amadeus:heredoc-expands paths=none -- review regression fixture
sudo tee /etc/amadeus/review.conf >/dev/null <<EOF
ExecStart=${target:-$HOME/.local/bin/payload}
EOF
