# Snapdragon cameras run through libcamera, which apps reach through
# PipeWire's libcamera backend.

if amadeus-hw-aarch64-qualcomm; then
  amadeus-pkg-add pipewire-libcamera
fi
