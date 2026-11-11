-- Your Hyprland configuration. System defaults load first; anything below overrides them.
-- Reference: https://wiki.hypr.land/Configuring/Start/
dofile("/usr/share/amadeus-os/hypr/default.lua")

-- Examples:
-- o.bind("SUPER + SHIFT + B", "Bluetooth", "foot -e bluetoothctl")
-- hl.config({ input = { kb_layout = "us,in" } })
-- hl.monitor({ output = "HDMI-A-1", mode = "2560x1440@144", position = "auto", scale = 1 })

-- Shortcuts and rules that Amadeus adds on your behalf live in amadeus.lua.
local managed = os.getenv("HOME") .. "/.config/hypr/amadeus.lua"
local f = io.open(managed)
if f then f:close(); dofile(managed) end
