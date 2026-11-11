#!/bin/bash
# Build one AUR package inside the builder container. Usage: aur-build.sh NAME REPO_DIR CACHE_DIR
set -euo pipefail
name=$1 repo=$2 keep=$3
rm -rf /tmp/aur-$name
git clone -q --depth 1 https://aur.archlinux.org/$name.git /tmp/aur-$name
chown -R build /tmp/aur-$name; cd /tmp/aur-$name
want=$(basename "$(sudo -u build makepkg --packagelist | head -1)")
mkdir -p "$keep"
if [[ -f $keep/$want ]]; then cp "$keep/$want" "$repo/"; echo "   reusing $want"; exit 0; fi
cache=(--cachedir /var/cache/pacman/pkg); [[ -d /hostcache ]] && cache+=(--cachedir /hostcache)
# shellcheck disable=SC2046
pacman -Syu --noconfirm --needed "${cache[@]}" $(sudo -u build makepkg --printsrcinfo | awk '$1 ~ /^(depends|makedepends|checkdepends)$/ {print $3}') >/dev/null
sudo -u build env PKGDEST="$repo" makepkg -f >/tmp/aur-$name.log 2>&1 || { tail -30 /tmp/aur-$name.log; exit 1; }
cp "$repo/$want" "$keep/"; echo "   built $want"
