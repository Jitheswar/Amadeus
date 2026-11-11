#!/bin/bash
# Build and test Amadeus OS in a container; nothing is installed on the machine running this.
#   ./build.sh iso     build out/amadeus-os-<date>-x86_64.iso
#   ./build.sh test    install the ISO in a VM, boot it, run the self-test and both rollback paths
#   ./build.sh shell   a shell in the build container
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$here/out"
docker=(docker); docker info >/dev/null 2>&1 || docker=(sudo docker)
"${docker[@]}" build -q -t amadeus-builder "$here/iso" >/dev/null
cache=(); [[ -d /var/cache/pacman/pkg ]] && cache=(-v /var/cache/pacman/pkg:/hostcache:ro)
run=("${docker[@]}" run --rm --privileged --device /dev/kvm -v "$here:/src:ro" -v "$here/out:/out" "${cache[@]}")
case ${1:-iso} in
  iso)   "${run[@]}" amadeus-builder bash /src/iso/mkiso.sh ;;
  test)  "${run[@]}" amadeus-builder python3 /src/test/vm-test.py "${@:2}" ;;
  shell) "${run[@]}" -it amadeus-builder bash ;;
  *)     sed -n 2,5p "$0"; exit 1 ;;
esac
