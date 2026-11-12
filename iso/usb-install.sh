#!/bin/bash
# Runs in the builder container: boots the ISO in a VM whose only disk is a USB drive, shown in a window.
# The guided installer runs on screen as it would on a computer; the result boots from that drive.
# Usage (through build.sh): usb-install.sh /dev/sdX
set -euo pipefail
dev=$1
iso=$(ls /out/amadeus-os-*.iso | sort | tail -1)
vars=$(mktemp); cp /usr/share/edk2/x64/OVMF_VARS.4m.fd "$vars"
# The drive is given to the VM as a removable disk (so the installer makes a portable system),
# not as an emulated USB device: emulated USB gives up on a command after about 30 seconds,
# and a slow stick can take longer than that to finish one. Writes go straight to the drive,
# grouped into large pieces by the VM itself, so nothing waits on a large backlog.
exec qemu-system-x86_64 -enable-kvm -machine q35 -cpu host -smp 6 -m 6G \
  -drive if=pflash,format=raw,readonly=on,file=/usr/share/edk2/x64/OVMF_CODE.4m.fd \
  -drive if=pflash,format=raw,file="$vars" \
  -drive file="$iso",media=cdrom,if=none,id=cd,readonly=on -device ide-cd,drive=cd,bootindex=0 \
  -drive file="$dev",format=raw,if=none,id=stick,cache=none,aio=io_uring -device virtio-scsi-pci -device scsi-hd,drive=stick,removable=on \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -device virtio-vga -display gtk,zoom-to-fit=on -name "Amadeus OS installer"
