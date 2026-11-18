-- Learn how to configure Hyprland: https://wiki.hypr.land/Configuring/Start/

-- Amadeus's bootstrap keeps path setup out of this user config.
dofile((os.getenv("AMADEUS_PATH") or "/usr/share/amadeus") .. "/default/hypr/bootstrap.lua")

-- Disable all Amadeus default bindings. Add your own in hypr/bindings.lua.
-- amadeus_default_bindings = false


-- Load Amadeus defaults.
require("default.hypr.amadeus")

-- Put your personal overrides in these files. They're loaded after Amadeus's
-- defaults so package updates can improve the defaults without rewriting your
-- ~/.config/hypr files.
require("hypr.monitors")
require("hypr.input")
require("hypr.bindings")
require("hypr.looknfeel")
require("hypr.autostart")

-- Toggle config flags dynamically.
require("default.hypr.toggles")

-- Add any other personal Hyprland configuration below.
-- o.window("qemu", { workspace = "5" })
