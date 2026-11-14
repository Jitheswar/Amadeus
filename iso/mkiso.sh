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
local_pkgs=$(ls $REPO/*.pkg.tar.zst | grep -vE '/cachyos-(keyring|mirrorlist|v3-mirrorlist)-' || true)
# Packages this machine already downloaded are copied rather than fetched again.
if [[ -d /hostcache ]]; then
  # shellcheck disable=SC2086
  { "${pc[@]}" -Sp --print-format '%f' $want; "${pc[@]}" -Up --print-format '%f' $local_pkgs; } 2>/dev/null | sort -u |
    while read -r f; do if [[ -f /hostcache/$f ]]; then cp -n "/hostcache/$f" $OFF/; fi; done || true   # only saves downloading
fi
# shellcheck disable=SC2086
"${pc[@]}" -Sw $want >/dev/null || { echo "   could not collect the packages in the package lists"; exit 1; }
# shellcheck disable=SC2086
"${pc[@]}" -Uw $local_pkgs >/dev/null || { echo "   could not collect what the bundled applications need"; exit 1; }
rm -f $OFF/*.part
repo-add -q $OFF/amadeus-offline.db.tar.gz $OFF/*.pkg.tar.zst
# The package lists that describe exactly what was collected. The installer copies them
# onto a system installed without a connection, and the try session uses them before it
# can sync; pacman reads only the repositories configured on the running system.
install -d $OFF/sync && cp $ROOT/db/sync/*.db $OFF/sync/
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
# "Try Amadeus OS": the desktop on the live medium, running from memory. Its files, the
# packages it adds, and a boot entry with amadeus.try that switches them on.
cp -a $SRC/iso/live/try/. $A/
{ grep -hv '^#' $SRC/iso/live/packages.try; grep -hv '^#' $SRC/installer/packages.desktop | tr ' ' '\n' | grep -v '^lib32-'; } | tr ' ' '\n' | grep . | sort -u >>$P/packages.x86_64
printf '\n[amadeus]\nSigLevel = Optional TrustAll\nServer = file://%s\n' "$REPO" >>$P/pacman.conf
echo amadeus-live >$A/etc/hostname
printf 'pciutils\nrsync\ngum\n' >>$P/packages.x86_64
# The guided installer starts by itself on the first screen, unless an unattended install is under way.
cat >>$A/root/.zlogin <<'Z'
if [[ $(tty) == /dev/tty1 && ! -e /dev/disk/by-label/AMADEUSAUTO ]] && ! grep -qw amadeus.try /proc/cmdline; then amadeus-setup; fi
Z

label="AMADEUS_$(date +%Y%m)"
sed -i "s|^iso_name=.*|iso_name=\"amadeus-os\"|; s|^iso_label=.*|iso_label=\"$label\"|; s|^iso_publisher=.*|iso_publisher=\"Amadeus OS\"|; s|^iso_application=.*|iso_application=\"Amadeus OS installer\"|; s|^install_dir=.*|install_dir=\"amadeus\"|" $P/profiledef.sh
sed -i 's|^file_permissions=(|file_permissions=(\n  ["/etc/sudoers.d/10-try"]="0:0:440"\n  ["/usr/local/bin/amadeus-try-setup"]="0:0:755"\n  ["/usr/local/bin/amadeus-try-check"]="0:0:755"\n  ["/usr/local/bin/amadeus-install"]="0:0:755"\n  ["/usr/local/bin/amadeus-autoinstall"]="0:0:755"\n  ["/usr/local/bin/amadeus-setup"]="0:0:755"\n  ["/usr/local/bin/amadeus-rollback"]="0:0:755"|' $P/profiledef.sh
# Boot menu: our name, and a serial console so the ISO can be tested headless.
for f in $P/efiboot/loader/entries/*.conf $P/syslinux/*.cfg $P/grub/*.cfg; do
  [[ -f $f ]] || continue
  sed -i 's/Arch Linux install medium/Amadeus OS installer/g; s/Arch Linux/Amadeus OS/g' "$f"
  sed -i -E 's/(archisosearchuuid=%ARCHISO_UUID%)/\1 console=ttyS0,115200 console=tty0/' "$f"
done
# Quiet boot: the installer and the try session draw their own screens.
sed -i -E 's/^(options .*)$/\1 quiet loglevel=3/' $P/efiboot/loader/entries/01-archiso-linux.conf
sed -i 's/^title .*/title    Install Amadeus OS/' $P/efiboot/loader/entries/01-archiso-linux.conf
sed -e 's/^title .*/title    Try Amadeus OS (nothing is written to any disk)/; s/^sort-key .*/sort-key 00/' \
    -e 's/^\(options .*\)$/\1 amadeus.try cow_spacesize=4G/' \
    $P/efiboot/loader/entries/01-archiso-linux.conf >$P/efiboot/loader/entries/00-amadeus-try.conf
sed -i 's/^timeout .*/timeout 5/; s/^default .*/default 00-amadeus-try.conf/' $P/efiboot/loader/loader.conf
# The BIOS menu gets the same choice. The label is copied from the installer's, so the
# kernel, initrd and search uuid are written once, then it is put first and made the
# default, like the UEFI menu.
sed -n '/^LABEL arch$/,/^APPEND /p' $P/syslinux/archiso_sys-linux.cfg |
  sed -e 's/^LABEL arch$/LABEL try/' \
      -e 's/^MENU LABEL .*/MENU LABEL Try Amadeus OS (nothing is written to any disk)/' \
      -e 's/^Boot the Amadeus OS installer on BIOS\./Start the full desktop from this stick, without installing./' \
      -e 's/^It allows you to install Amadeus OS or perform system maintenance\./Everything runs in memory; nothing is written to any disk./' \
      -e 's/^\(APPEND .*\)$/\1 quiet loglevel=3 amadeus.try cow_spacesize=4G/' \
      > /tmp/amadeus-try-label
grep -q '^APPEND .*amadeus\.try' /tmp/amadeus-try-label ||
  { echo "   could not build the BIOS try entry from archiso's menu"; exit 1; }
{ cat /tmp/amadeus-try-label; echo; cat $P/syslinux/archiso_sys-linux.cfg; } > /tmp/amadeus-sys-linux.cfg
mv /tmp/amadeus-sys-linux.cfg $P/syslinux/archiso_sys-linux.cfg
sed -i 's/^DEFAULT arch$/DEFAULT try/; s/^TIMEOUT .*/TIMEOUT 50/' $P/syslinux/archiso_sys.cfg
sed -i 's/^MENU ROWS 7$/MENU ROWS 8/' $P/syslinux/archiso_head.cfg
# Reuse packages the host already downloaded.
[[ -d /hostcache ]] && sed -i 's|^\[options\]|[options]\nCacheDir = /var/cache/pacman/pkg/\nCacheDir = /hostcache/|' $P/pacman.conf

echo "==> Building the ISO"
mkarchiso -w /tmp/work -o $OUT $P
ls -lh $OUT/*.iso
