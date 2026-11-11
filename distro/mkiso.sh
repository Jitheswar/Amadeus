#!/bin/bash
# Runs inside the builder container: packages Amadeus, assembles the archiso profile, builds the ISO.
set -euo pipefail
SRC=/src OUT=/out
P=/tmp/profile REPO=/tmp/repo
rm -rf $P $REPO /tmp/work /tmp/pkgsrc && mkdir -p $REPO

echo "==> Packaging amadeus and amadeus-desktop"
cp -r $SRC /tmp/pkgsrc && chown -R build /tmp/pkgsrc $REPO
for d in packaging distro/desktop; do
  (cd /tmp/pkgsrc/$d && sudo -u build env PKGDEST=$REPO makepkg -f --nodeps >/dev/null)
done

echo "==> Packaging ProtonPlus (not in the Arch repositories; built from its AUR recipe)"
bash /src/distro/aur-build.sh protonplus $REPO $OUT/pkgcache || echo "   WARNING: ProtonPlus could not be built; the ISO will not include it"
repo-add -q $REPO/amadeus.db.tar.gz $REPO/*.pkg.tar.zst
ls $REPO/*.pkg.tar.zst

echo "==> Assembling the profile"
cp -r /usr/share/archiso/configs/releng $P
A=$P/airootfs
install -d $A/opt $A/usr/local/bin $A/usr/share/amadeus-install $A/etc/systemd/system/multi-user.target.wants
cp -r $REPO $A/opt/amadeus-repo
install -m755 $SRC/distro/installer/amadeus-install $SRC/distro/live/amadeus-autoinstall $SRC/distro/desktop/bin/amadeus-rollback $A/usr/local/bin/
install -m644 $SRC/distro/installer/packages.* $A/usr/share/amadeus-install/
install -m644 $SRC/distro/live/amadeus-autoinstall.service $A/etc/systemd/system/
ln -sf ../amadeus-autoinstall.service $A/etc/systemd/system/multi-user.target.wants/
install -Dm644 /keyrings/omarchy* -t $A/usr/share/pacman/keyrings/ 2>/dev/null || echo "   (no third-party keyring supplied; extras will be skipped at install time)"
cp $SRC/distro/live/motd $A/etc/motd
echo amadeus-live >$A/etc/hostname
printf 'pciutils\nrsync\n' >>$P/packages.x86_64

label="AMADEUS_$(date +%Y%m)"
sed -i "s|^iso_name=.*|iso_name=\"amadeus-os\"|; s|^iso_label=.*|iso_label=\"$label\"|; s|^iso_publisher=.*|iso_publisher=\"Amadeus OS\"|; s|^iso_application=.*|iso_application=\"Amadeus OS installer\"|; s|^install_dir=.*|install_dir=\"amadeus\"|" $P/profiledef.sh
sed -i 's|^file_permissions=(|file_permissions=(\n  ["/usr/local/bin/amadeus-install"]="0:0:755"\n  ["/usr/local/bin/amadeus-autoinstall"]="0:0:755"\n  ["/usr/local/bin/amadeus-rollback"]="0:0:755"|' $P/profiledef.sh
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
