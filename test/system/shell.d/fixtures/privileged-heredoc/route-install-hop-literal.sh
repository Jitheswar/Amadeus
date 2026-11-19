#!/bin/bash

cat <<EOF >/tmp/amadeus-review-unit
[Service]
ExecStart=$HOME/.local/bin/payload
EOF
sudo install -m 644 /tmp/amadeus-review-unit /etc/systemd/system/review.service
