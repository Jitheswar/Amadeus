# Configure pacman after package installation completes. Offline target package
# installs use the live ISO's offline pacman.conf until this final restore,
# which copies the platform's channel templates (install/helpers/pacman.sh) plus
# this machine's regional additions (amadeus-apply-pacman). A Mac's image brings
# its keyrings, as the ISO does on x86; every other aarch64 platform installs
# Arch Linux ARM's before its repositories replace the offline ones, and trust
# every installed keyring before the first signed sync.
source "$AMADEUS_PATH/install/helpers/pacman.sh"
source "$AMADEUS_PATH/install/helpers/pacman-keyring.sh"
source "$AMADEUS_PATH/install/helpers/image-target.sh"
platform=$(amadeus-hw-platform)
templates=$(amadeus_pacman_templates "$platform")
alarm_keyring=0
if [[ $platform == aarch64* && $platform != "aarch64-apple" ]]; then
  alarm_keyring=1
fi

if (( alarm_keyring )); then
  amadeus-pkg-add archlinuxarm-keyring
fi

# An install built for a channel this platform has no templates for (stable or
# rc on aarch64) gets the platform's default channel instead.
channel=${AMADEUS_MIRROR:-}
[[ -n $channel && -f $templates/pacman-$channel.conf ]] || channel=$(amadeus_pacman_default_channel "$platform")
"$AMADEUS_PATH/bin/amadeus-apply-pacman" "$channel"

# An image build leaves the keyring to each machine's first boot, so no two
# share a master key (install/helpers/image-target.sh). An install's keyring
# was started at the beginning of system setup (config/pacman-keyring.sh) and
# lands here, or is made here when it wasn't.
if (( alarm_keyring )); then
  if amadeus_image_init && amadeus_image_manifest_present; then
    install -m 0644 /dev/null "$amadeus_image_keyring_request"
  else
    amadeus_pacman_keyring_finish
  fi
fi

# Wait for CUPS to own the file, the way amadeus-desktop does, so pacman does
# not turn the override into a .pacnew during ISO package installation.
if [[ -f $AMADEUS_PATH/etc-overrides/cups-cups-files.conf && -f /etc/cups/cups-files.conf ]]; then
  install -m 0640 -o root -g cups "$AMADEUS_PATH/etc-overrides/cups-cups-files.conf" /etc/cups/cups-files.conf
  rm -f /etc/cups/cups-files.conf.pacnew
fi
