DROP_IN=/etc/systemd/system/amadeus-agent.service.d/override.conf

cat <<EOF | sudo tee "$DROP_IN" >/dev/null
[Service]
ExecStart=$AMADEUS_PATH/bin/amadeus-agent
EOF
