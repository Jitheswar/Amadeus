-- Amadeus OS desktop defaults. Shipped in /usr/share/amadeus-os and updated with the system.
-- Personal changes belong in ~/.config/hypr/hyprland.lua, which loads this file first.

-- Small helper layer used by this file and by Amadeus when it adds shortcuts and rules.
o = o or {}
local rule_n = 0
function o.bind(keys, description, action, options)
  local opts = options or {}
  if description then opts.description = description end
  if type(action) == "string" then action = hl.dsp.exec_cmd(action) end
  hl.bind(keys, action, opts)
end
function o.window(match, rules)
  rule_n = rule_n + 1
  rules.match = type(match) == "string" and { class = match } or match
  rules.name = rules.name or ("amadeus-" .. rule_n)
  hl.window_rule(rules)
end

local theme = { bg = "142620", fg = "d8e6df", accent = "8bcbb1", muted = "2b5147" }

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.env("XCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")
-- Nothing here selects the NVIDIA card. The compositor and ordinary apps render on the
-- Intel GPU; Amadeus (or `gpu-run <app>`) offloads individual apps to NVIDIA.

hl.config({
  general = {
    gaps_in = 4, gaps_out = 8, border_size = 2, layout = "dwindle",
    col = { active_border = "rgba(" .. theme.accent .. "ff)", inactive_border = "rgba(" .. theme.muted .. "aa)" },
  },
  decoration = { rounding = 8, blur = { enabled = false }, shadow = { enabled = false } },
  animations = { enabled = true },
  dwindle = { preserve_split = true },
  misc = { force_default_wallpaper = 0, disable_hyprland_logo = true, disable_splash_rendering = true, background_color = "rgb(" .. theme.bg .. ")" },
  input = { kb_layout = "us", follow_mouse = 1, touchpad = { natural_scroll = true, tap_to_click = true } },
})
hl.animation({ leaf = "global", enabled = true, speed = 3, bezier = "default" })
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

hl.on("hyprland.start", function()
  hl.exec_cmd("quickshell -p /usr/share/amadeus-os/bar")
  hl.exec_cmd("mako")
  hl.exec_cmd("hypridle")
  hl.exec_cmd("systemctl --user start hyprpolkitagent")
end)

-- Applications
o.bind("SUPER + RETURN", "Terminal", "foot")
o.bind("SUPER + SPACE", "Launcher", "fuzzel")
o.bind("SUPER + Z", "Amadeus", "ama palette")
o.bind("SUPER + B", "Browser", "xdg-open https://")
o.bind("SUPER + E", "Files", "nautilus --new-window")
o.bind("SUPER + ESCAPE", "Power menu", "amadeus-power-menu")
o.bind("SUPER + CTRL + L", "Lock", "hyprlock")
o.bind("PRINT", "Screenshot region", "amadeus-screenshot")

-- Windows
o.bind("SUPER + W", "Close window", hl.dsp.window.close())
o.bind("SUPER + F", "Fullscreen", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
o.bind("SUPER + M", "Maximise", hl.dsp.window.fullscreen({ mode = "maximized" }))
o.bind("SUPER + T", "Toggle floating", hl.dsp.window.float({ action = "toggle" }))
o.bind("SUPER + J", "Toggle split", hl.dsp.layout("togglesplit"))
for key, dir in pairs({ LEFT = "l", RIGHT = "r", UP = "u", DOWN = "d" }) do
  o.bind("SUPER + " .. key, "Focus " .. dir, hl.dsp.focus({ direction = dir }))
end
for i = 1, 10 do
  local key = i % 10
  o.bind("SUPER + " .. key, "Workspace " .. i, hl.dsp.focus({ workspace = tostring(i) }))
  o.bind("SUPER + SHIFT + " .. key, "Move to workspace " .. i, hl.dsp.window.move({ workspace = tostring(i), follow = false }))
end
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Hardware keys
local hw = { locked = true, repeating = true }
hl.bind("XF86AudioRaiseVolume", hl.dsp.exec_cmd("wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+"), hw)
hl.bind("XF86AudioLowerVolume", hl.dsp.exec_cmd("wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-"), hw)
hl.bind("XF86AudioMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"), { locked = true })
hl.bind("XF86AudioMicMute", hl.dsp.exec_cmd("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle"), { locked = true })
hl.bind("XF86MonBrightnessUp", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%+"), hw)
hl.bind("XF86MonBrightnessDown", hl.dsp.exec_cmd("brightnessctl -e4 -n2 set 5%-"), hw)
hl.bind("XF86AudioPlay", hl.dsp.exec_cmd("playerctl play-pause"), { locked = true })
hl.bind("XF86AudioNext", hl.dsp.exec_cmd("playerctl next"), { locked = true })
hl.bind("XF86AudioPrev", hl.dsp.exec_cmd("playerctl previous"), { locked = true })

-- Amadeus surfaces (palette, approval prompts) float in the centre.
o.window({ class = "^org\\.quickshell$", title = "^Amadeus" }, { float = true, center = true })
-- Games get the whole screen without tearing protection in the way.
o.window({ class = "^steam_app_.*$" }, { fullscreen = true })
