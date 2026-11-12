-- Your desktop configuration. System defaults load first; anything below overrides them.
-- Reference: https://wiki.hypr.land/Configuring/Start/
dofile("/usr/share/amadeus-os/hypr/default.lua")

-- Examples:
-- o.bind("SUPER + SHIFT + B", "Bluetooth", "amadeus-terminal -e bluetoothctl")
-- hl.config({ input = { kb_layout = "us,in" } })

-- Resolution and scaling (Super+Space, Setup, Display), then what Amadeus adds on your behalf.
for _, name in ipairs({ "display.lua", "amadeus.lua" }) do
  local path = os.getenv("HOME") .. "/.config/hypr/" .. name
  local f = io.open(path)
  if f then f:close(); dofile(path) end
end
