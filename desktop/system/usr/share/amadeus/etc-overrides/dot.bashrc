# Amadeus environment (AMADEUS_PATH + PATH), needed even for non-interactive shells
[[ -r /usr/share/amadeus/default/bash/env-bootstrap ]] && source /usr/share/amadeus/default/bash/env-bootstrap

# If not running interactively, don't do anything else (leave this above the rc source)
[[ $- != *i* ]] && return

# All the default Amadeus aliases and functions
# (don't mess with these directly, just overwrite them here!)
source "$AMADEUS_PATH/default/bash/rc"

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# alias p='python'
