#!/bin/bash
# Build the Amadeus OS ISO in a container. Usage: distro/build.sh [iso|test|shell]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)" repo="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$here/out"
docker=(docker); docker info >/dev/null 2>&1 || docker=(sudo docker)
"${docker[@]}" build -q -t amadeus-builder "$here" >/dev/null
cache=(); [[ -d /var/cache/pacman/pkg ]] && cache=(-v /var/cache/pacman/pkg:/hostcache:ro)
run=("${docker[@]}" run --rm --privileged --device /dev/kvm -v "$repo:/src:ro" -v "$here/out:/out" "${cache[@]}" amadeus-builder)
case ${1:-iso} in
  iso)   "${run[@]}" bash /src/distro/mkiso.sh ;;
  test)  "${run[@]}" python3 /src/distro/test/vm-test.py "${@:2}" ;;
  shell) "${docker[@]}" run --rm -it --privileged --device /dev/kvm -v "$repo:/src:ro" -v "$here/out:/out" "${cache[@]}" amadeus-builder bash ;;
esac
