# Boot keyboards that leave Fn-lock to Linux (ASUS laptops and keyboards, Apple
# and Apple-style keyboards such as the Lofree Flow84) with media keys on the
# top row; Fn gives F1-F12. Set up already, by Amadeus or an administrator, it
# stays as it is. Apple Silicon is left alone: the amadeus-mac package owns its
# keyboard mode. Setup's last step builds the boot image, so none is built here.
modprobe_dir="${AMADEUS_MODPROBE_DIR:-/etc/modprobe.d}"
fn_option='^[[:space:]]*options[[:space:]]+(hid_apple[[:space:]].*fnmode|(hid_asus|asus_wmi)[[:space:]].*fnlock_default)='
if ! amadeus-hw-aarch64-apple && ! grep -qsE "$fn_option" "$modprobe_dir"/*.conf; then
  amadeus-device-keyboard-toprow mediakeys --no-rebuild
fi
