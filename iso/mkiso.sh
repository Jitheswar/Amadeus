#!/bin/bash
# Runs inside the builder container: packages Amadeus, assembles the archiso profile, builds the ISO.
set -euo pipefail
SRC=/src OUT=/out
P=/tmp/profile REPO=/tmp/repo
rm -rf $P $REPO /tmp/work /tmp/pkgsrc && mkdir -p $REPO

echo "==> Packaging amadeus and amadeus-desktop"
mkdir /tmp/pkgsrc && cp -r $SRC/ai $SRC/desktop $SRC/docs $SRC/README.md /tmp/pkgsrc/ && chown -R build /tmp/pkgsrc $REPO
for d in ai desktop; do
  (cd /tmp/pkgsrc/$d && sudo -u build env PKGDEST=$REPO makepkg -f --nodeps >/dev/null)
done

echo "==> Packaging applications that are not in the Arch repositories (from their AUR recipes)"
for p in $(grep -hv '^#' $SRC/installer/packages.aur); do
  bash /src/iso/aur-build.sh $p $REPO $OUT/pkgcache || echo "   WARNING: $p could not be built; the ISO will not include it"
done

echo "==> Fetching the CachyOS signing key and mirror lists"
# The installer needs these before it can use the CachyOS repositories. They are looked up in
# the repository's own index, so no version is written down here.
curl -fsSL -o /tmp/cachyos.db https://mirror.cachyos.org/repo/x86_64/cachyos/cachyos.db
for p in cachyos-keyring cachyos-mirrorlist cachyos-v3-mirrorlist; do
  f=$(tar -xOf /tmp/cachyos.db --wildcards "$p-[0-9]*/desc" | awk '/%FILENAME%/{getline; print; exit}')
  curl -fsSL -o "$REPO/$f" "https://mirror.cachyos.org/repo/x86_64/cachyos/$f" && echo "   $f"
done
repo-add -q $REPO/amadeus.db.tar.gz $REPO/*.pkg.tar.zst
ls $REPO/*.pkg.tar.zst

echo "==> Collecting every package the installation needs, so it works without internet"
# A fresh, empty package database stands in for the new system: whatever pacman would download
# to install the package lists and the bundled applications into it is exactly what is collected.
# Packages are checked against their signatures as they are collected. They are the builds for
# x86-64-v3 processors, which this machine has; others install from the internet instead.
OFF=/tmp/offline ROOT=/tmp/offroot
rm -rf $OFF $ROOT && mkdir -p $OFF $ROOT/db
pacman-key --init >/dev/null 2>&1; pacman-key --populate archlinux >/dev/null 2>&1
pacman -U --noconfirm --needed $REPO/cachyos-keyring-*.pkg.tar.zst $REPO/cachyos-mirrorlist-*.pkg.tar.zst $REPO/cachyos-v3-mirrorlist-*.pkg.tar.zst >/dev/null
pacman-key --populate cachyos >/dev/null 2>&1
{
  echo "[options]"; echo "Architecture = x86_64 x86_64_v3"; echo "SigLevel = Required DatabaseOptional"; echo "LocalFileSigLevel = Optional"
  echo "ParallelDownloads = 8"; echo "CacheDir = $OFF/"
  for r in cachyos-v3 cachyos-core-v3 cachyos-extra-v3; do printf '[%s]\nInclude = /etc/pacman.d/cachyos-v3-mirrorlist\n' $r; done
  printf '[cachyos]\nInclude = /etc/pacman.d/cachyos-mirrorlist\n'
  for r in core extra multilib; do printf '[%s]\nInclude = /etc/pacman.d/mirrorlist\n' $r; done
} >/tmp/offline.conf
pc=(pacman --config /tmp/offline.conf --root $ROOT --dbpath $ROOT/db --noconfirm)
"${pc[@]}" -Sy >/dev/null
# shellcheck disable=SC2046
want=$(grep -hv '^#' $SRC/installer/packages.{base,desktop,apps,nvidia} | tr '\n' ' ')
local_pkgs=$(ls $REPO/*.pkg.tar.zst | grep -vE '/cachyos-(keyring|mirrorlist|v3-mirrorlist)-')
# Packages this machine already downloaded are copied rather than fetched again.
if [[ -d /hostcache ]]; then
  # shellcheck disable=SC2086
  { "${pc[@]}" -Sp --print-format '%f' $want; "${pc[@]}" -Up --print-format '%f' $local_pkgs; } 2>/dev/null | sort -u |
    while read -r f; do [[ -f /hostcache/$f ]] && cp -n /hostcache/$f $OFF/; done
fi
# shellcheck disable=SC2086
"${pc[@]}" -Sw $want >/dev/null
# shellcheck disable=SC2086
"${pc[@]}" -Uw $local_pkgs >/dev/null
rm -f $OFF/*.part
repo-add -q $OFF/amadeus-offline.db.tar.gz $OFF/*.pkg.tar.zst
echo "   $(ls $OFF/*.pkg.tar.zst | wc -l) packages, $(du -sh $OFF | cut -f1)"

echo "==> Assembling the profile"
cp -r /usr/share/archiso/configs/releng $P
A=$P/airootfs
install -d $A/opt $A/usr/local/bin $A/usr/share/amadeus-install $A/etc/systemd/system/multi-user.target.wants
cp -r $REPO $A/opt/amadeus-repo
cp -r $OFF $A/opt/amadeus-offline
install -m755 $SRC/installer/amadeus-install $SRC/installer/amadeus-setup $SRC/iso/live/amadeus-autoinstall $SRC/desktop/bin/amadeus-rollback $A/usr/local/bin/
install -m644 $SRC/installer/packages.* $A/usr/share/amadeus-install/
install -m644 $SRC/iso/live/amadeus-autoinstall.service $A/etc/systemd/system/
ln -sf ../amadeus-autoinstall.service $A/etc/systemd/system/multi-user.target.wants/
cp $SRC/iso/live/motd $A/etc/motd
echo amadeus-live >$A/etc/hostname
printf 'pciutils\nrsync\ngum\n' >>$P/packages.x86_64
# The guided installer starts by itself on the first screen, unless an unattended install is under way.
cat >>$A/root/.zlogin <<'Z'
if [[ $(tty) == /dev/tty1 && ! -e /dev/disk/by-label/AMADEUSAUTO ]]; then amadeus-setup; fi
Z

label="AMADEUS_$(date +%Y%m)"
sed -i "s|^iso_name=.*|iso_name=\"amadeus-os\"|; s|^iso_label=.*|iso_label=\"$label\"|; s|^iso_publisher=.*|iso_publisher=\"Amadeus OS\"|; s|^iso_application=.*|iso_application=\"Amadeus OS installer\"|; s|^install_dir=.*|install_dir=\"amadeus\"|" $P/profiledef.sh
sed -i 's|^file_permissions=(|file_permissions=(\n  ["/usr/local/bin/amadeus-install"]="0:0:755"\n  ["/usr/local/bin/amadeus-autoinstall"]="0:0:755"\n  ["/usr/local/bin/amadeus-setup"]="0:0:755"\n  ["/usr/local/bin/amadeus-rollback"]="0:0:755"|' $P/profiledef.sh
# Boot menu: our name, and a serial console so the ISO can be tested headless.
for f in $P/efiboot/loader/entries/*.conf $P/syslinux/*.cfg $P/grub/*.cfg; do
  [[ -f $f ]] || continue
  sed -i 's/Arch Linux install medium/Amadeus OS installer/g; s/Arch Linux/Amadeus OS/g' "$f"
  sed -i -E 's/(archisosearchuuid=%ARCHISO_UUID%)/\1 console=ttyS0,115200 console=tty0/' "$f"
done
sed -i 's/^timeout .*/timeout 3/' $P/efiboot/loader/loader.conf
# Reuse packages the host already downloaded.
[[ -d /hostcache ]] && sed -i 's|^\[options\]|[options]\nCacheDir = /var/cache/pacman/pkg/\nCacheDir = /hostcache/|' $P/pacman.conf

echo "==> Building the ISO"
mkarchiso -w /tmp/work -o $OUT $P
ls -lh $OUT/*.iso
