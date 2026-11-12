#!/bin/bash
# Build and test Amadeus OS in a container; nothing is installed on the machine running this.
#   ./build.sh iso     build out/amadeus-os-<date>-x86_64.iso
#   ./build.sh test    install the ISO in a VM, boot it, run the self-test and both rollback paths
#   ./build.sh shell   a shell in the build container
#   ./build.sh preview draw the shell, picker, notifications and panel headless; pictures land in out/preview/
#   ./build.sh usb /dev/sdX   install onto a USB drive: the guided installer runs in a window, the VM sees only that drive
#   ./build.sh check   fast checks without a container: syntax, unit tests, guides match the repo
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
[[ ${1:-} == check ]] && exec python3 "$here/test/check.py"
mkdir -p "$here/out"
docker=(docker); docker info >/dev/null 2>&1 || docker=(sudo docker)
"${docker[@]}" build -q -t amadeus-builder "$here/iso" >/dev/null
cache=(); [[ -d /var/cache/pacman/pkg ]] && cache=(-v /var/cache/pacman/pkg:/hostcache:ro)
run=("${docker[@]}" run --rm --privileged --device /dev/kvm -v "$here:/src:ro" -v "$here/out:/out" "${cache[@]}")
case ${1:-iso} in
  iso)   "${run[@]}" amadeus-builder bash /src/iso/mkiso.sh ;;
  test)  "${run[@]}" amadeus-builder python3 /src/test/vm-test.py "${@:2}" ;;
  preview) "${run[@]}" amadeus-builder bash /src/test/preview.sh ;;
  usb)
    dev=${2:?name the USB drive, for example /dev/sdb}
    [[ $(lsblk -dno TRAN "$dev" 2>/dev/null) == usb ]] || { echo "$dev is not a USB drive; nothing was changed."; exit 1; }
    echo "Everything on $dev ($(lsblk -dno SIZE,MODEL "$dev" | xargs)) will be erased when you confirm in the installer."
    # Unmount it here, so this computer is not using it while the VM writes to it.
    for p in $(lsblk -lnpo NAME,MOUNTPOINT "$dev" | awk 'NF == 2 {print $1}'); do udisksctl unmount -b "$p" >/dev/null 2>&1 || sudo umount "$p"; done
    xdg=${XDG_RUNTIME_DIR:?}; wl=${WAYLAND_DISPLAY:?this needs a desktop session}
    "${docker[@]}" run --rm --privileged --device /dev/kvm --device "$dev" -v "$here:/src:ro" -v "$here/out:/out" \
      -v "$xdg/$wl:/tmp/xdg/$wl" -e XDG_RUNTIME_DIR=/tmp/xdg -e WAYLAND_DISPLAY="$wl" -e GDK_BACKEND=wayland \
      amadeus-builder bash /src/iso/usb-install.sh "$dev" ;;
  shell) "${run[@]}" -it amadeus-builder bash ;;
  *)     sed -n 2,8p "$0"; exit 1 ;;
esac
