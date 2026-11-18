# A VM usually renders on the CPU, where animations and transparency cost
# every frame, so start it without them and with opaque windows.
# amadeus-toggle-animations and Appearance > Windows > Window Opacity bring them
# back. This runs before any Hyprland session exists, so place the flags
# directly rather than through the commands, which reload Hyprland.
if amadeus-hw-vm; then
  echo "Detected a virtual machine. Turning off animations and transparency."
  mkdir -p "$HOME/.local/state/amadeus/toggles/hypr"
  cp "$AMADEUS_PATH/default/hypr/toggles/no-animations.lua" "$HOME/.local/state/amadeus/toggles/hypr/"
  cp "$AMADEUS_PATH/default/hypr/toggles/window-opaque.lua" "$HOME/.local/state/amadeus/toggles/hypr/"
fi
