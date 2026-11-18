# Drivers, firmware and fixes for this computer's hardware, and JACK and ALSA tools for PipeWire
# The installer now chooses drivers for the hardware it finds and installs all device firmware;
# a system installed before that gets the same here, including model fixes such as the Dell G15
# 5530 touchpad.
sudo pacman -S --needed --noconfirm linux-firmware alsa-utils || echo "  linux-firmware or alsa-utils could not be installed; amadeus-update will retry." >&2
# pipewire-jack replaces a separate JACK server; pacman asks before removing one.
pacman -Q jack2 >/dev/null 2>&1 || sudo pacman -S --needed --noconfirm pipewire-jack || true
sudo amadeus-hardware setup
