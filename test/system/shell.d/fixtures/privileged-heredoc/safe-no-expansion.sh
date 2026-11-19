cat <<EOF | sudo tee /etc/udev/rules.d/99-amadeus.rules >/dev/null
SUBSYSTEM=="power_supply", ATTR{type}=="Mains", RUN+="/usr/bin/amadeus-powerprofiles-set"
EOF
