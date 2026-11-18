# Install Sound Open Firmware for Intel audio DSPs. The sof-audio-pci-intel-*
# driver family requires this firmware; without it PipeWire exposes only a
# Dummy Output sink.

if amadeus-hw-intel-sof; then
  amadeus-pkg-add sof-firmware
fi
