#!/bin/bash

cat <<EOF | \
  sudo tee /etc/amadeus/review.conf
ExecStart=$HOME/.local/bin/payload
EOF
