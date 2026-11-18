# The Marvell Wi-Fi firmware is for x86 Surfaces only; Snapdragon Surfaces use Qualcomm Wi-Fi.
if amadeus-hw-surface && amadeus-hw-x86; then
  amadeus-pkg-add linux-firmware-marvell
fi
