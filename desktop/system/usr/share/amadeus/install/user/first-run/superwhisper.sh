#!/bin/bash

# Superwhisper ships as the default dictation backend, but its per-user setup
# (service, shortcuts, bar panel) needs a live session, so it runs here rather
# than in the image. Unattended: no settings window, no toast. An image built
# without the package is left alone, since first-run cannot ask for sudo.

set -e

if amadeus-pkg-present superwhisper-bin && [[ $(amadeus-default-dictation 2>/dev/null) == "superwhisper" ]]; then
  amadeus-install-dictation-superwhisper --background
fi
