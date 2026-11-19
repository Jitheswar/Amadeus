sudo dd status=none of=/etc/amadeus/boot.conf <<EOF
cmdline=$boot_params
EOF
