#!/bin/bash
# Build one AUR package inside the builder container. Usage: aur-build.sh NAME REPO_DIR CACHE_DIR
# A package already built at the current AUR version is reused from CACHE_DIR.
set -euo pipefail
name=$1 repo=$2 keep=$3
rm -rf /tmp/aur-$name
git clone -q --depth 1 https://aur.archlinux.org/$name.git /tmp/aur-$name
chown -R build /tmp/aur-$name; cd /tmp/aur-$name
want=$(basename "$(sudo -u build makepkg --packagelist | grep -v -- '-debug-' | head -1)")
mkdir -p "$keep"
if [[ -f $keep/$want ]]; then cp "$keep/$want" "$repo/"; echo "   reusing $want"; exit 0; fi
info=$(sudo -u build makepkg --printsrcinfo)
need='^(makedepends|checkdepends)$'; flags=(--nodeps)
# Packages that compile need their libraries; repackaged upstream binaries do not.
if grep -q '^build()' PKGBUILD; then need='^(depends|makedepends|checkdepends)$'; flags=(); fi
deps=$(awk -v n="$need" '$1 ~ n {print $3}' <<<"$info")
cache=(--cachedir /var/cache/pacman/pkg); [[ -d /hostcache ]] && cache+=(--cachedir /hostcache)
# shellcheck disable=SC2086
[[ -z $deps ]] || pacman -Syu --noconfirm --needed "${cache[@]}" $deps >/dev/null
sudo -u build env PKGDEST="$repo" makepkg -f "${flags[@]}" >/tmp/aur-$name.log 2>&1 || { tail -30 /tmp/aur-$name.log; exit 1; }
rm -f "$repo"/*-debug-*.pkg.tar.zst
cp "$repo/$want" "$keep/"; echo "   built $want"
