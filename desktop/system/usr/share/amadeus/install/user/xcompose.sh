# Set default XCompose that is triggered with Shift + CapsLock
tee ~/.XCompose >/dev/null <<EOF
# Run amadeus-restart-xcompose to apply changes

# Include fast emoji access
include "/usr/share/amadeus/default/xcompose"

# Identification
<Multi_key> <space> <n> : "$AMADEUS_USER_NAME"
<Multi_key> <space> <e> : "$AMADEUS_USER_EMAIL"
EOF
