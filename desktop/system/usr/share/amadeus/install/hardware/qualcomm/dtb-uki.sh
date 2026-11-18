# Embed every Qualcomm device tree for systemd-stub to select from SMBIOS data,
# and the machine's own for it to fall back on.
# DeviceTreeAuto requires literal paths, so the list is written here and
# refreshed before every boot image build, when a kernel update can bring new
# or renamed trees.

if amadeus-hw-aarch64-qualcomm; then
  amadeus-pkg-add systemd-ukify

  (
    export AMADEUS_QUALCOMM_DTB_ROOT AMADEUS_QUALCOMM_DTB_DIR AMADEUS_QUALCOMM_UKI_CONFIG AMADEUS_IMAGE_BOOT_REBUILD AMADEUS_PROC_ROOT
    amadeus-update-qualcomm-device-trees --install
  )

  # limine runs pre.d's executables before it builds any boot image, the
  # kernel update's included. Root runs them, so the hook points at the
  # packaged command rather than a path under AMADEUS_PATH a user may own.
  boot_hooks_dir=${AMADEUS_QUALCOMM_BOOT_HOOKS_DIR:-/etc/boot/hooks/pre.d}
  mkdir -p "$boot_hooks_dir"
  ln -sfn /usr/bin/amadeus-update-qualcomm-device-trees "$boot_hooks_dir/20-amadeus-qualcomm-device-trees"
fi
