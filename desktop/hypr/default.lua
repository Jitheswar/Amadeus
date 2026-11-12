-- Amadeus OS desktop defaults. Shipped in /usr/share/amadeus-os and updated with the system.
-- Personal changes belong in ~/.config/hypr/hyprland.lua, which loads this file first.
-- Nothing here selects the NVIDIA card: the compositor and ordinary applications render on
-- the Intel GPU, and Amadeus (or `amadeus-gpu-run <app>`) sends individual applications to NVIDIA.

-- Small helper layer used by this file and by Amadeus when it adds shortcuts and rules.
-- Every shortcut made with o.bind carries a description; Super+K lists them.
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

hl.monitor({ output = "", mode = "preferred", position = "auto", scale = "auto" })

hl.env("XCURSOR_SIZE", "24")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "auto")
hl.env("EDITOR", "amadeus-editor")
hl.env("VISUAL", "amadeus-editor")

hl.config({
  general = {
    gaps_in = 5, gaps_out = 10, border_size = 2, layout = "dwindle",
    col = { active_border = { colors = { "rgba(ffa14aff)", "rgba(ff6f3cff)" }, angle = 45 }, inactive_border = "rgba(342f29ff)" },
  },
  decoration = {
    rounding = 12,
    blur = { enabled = false },
    shadow = { enabled = true, range = 24, render_power = 3, color = "rgba(00000066)" },
  },
  animations = { enabled = true },
  dwindle = { preserve_split = true },
  misc = { force_default_wallpaper = 0, disable_hyprland_logo = true, disable_splash_rendering = true, background_color = "rgb(0f0e0d)" },
  input = { kb_layout = "us", follow_mouse = 1, touchpad = { natural_scroll = true, tap_to_click = true, disable_while_typing = true } },
})

-- Motion: short and decisive. Things arrive quickly and settle gently; nothing bounces,
-- and nothing runs longer than a quarter of a second.
hl.curve("arrive", { type = "bezier", points = { { 0.16, 1 }, { 0.3, 1 } } })
hl.curve("leave", { type = "bezier", points = { { 0.4, 0 }, { 1, 1 } } })
hl.animation({ leaf = "global", enabled = true, speed = 2.2, bezier = "arrive" })
hl.animation({ leaf = "windowsOut", enabled = true, speed = 1.4, bezier = "leave" })
hl.animation({ leaf = "fade", enabled = true, speed = 1.6, bezier = "arrive" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 2.4, bezier = "arrive" })
hl.animation({ leaf = "specialWorkspace", enabled = true, speed = 2.0, bezier = "arrive" })
hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

hl.on("hyprland.start", function()
  hl.exec_cmd("quickshell -p /usr/share/amadeus-os/shell")
  hl.exec_cmd("swayidle -w")
  hl.exec_cmd("/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1")
  -- Clipboard history: remembers what was copied so Super+Ctrl+V can bring it back.
  hl.exec_cmd("wl-paste --type text --watch cliphist store")
  hl.exec_cmd("wl-paste --type image --watch cliphist store")
end)

-- Applications
o.bind("SUPER + K", "Shortcuts and commands", "amadeus-keys")
o.bind("SUPER + RETURN", "Terminal", "amadeus-terminal")
o.bind("SUPER + SHIFT + RETURN", "AI coding harness", "amadeus-terminal -e amadeus-harness run")
o.bind("SUPER + SPACE", "Amadeus menu", "amadeus-menu")
o.bind("SUPER + Z", "Amadeus panel", "ama panel")
o.bind("SUPER + A", "Ask Amadeus about this window", "ama panel window")
o.bind("SUPER + B", "Browser", "xdg-open https://")
o.bind("SUPER + E", "Files", "nautilus --new-window")
o.bind("SUPER + SHIFT + F", "Files (your default application)", "xdg-open ~")
o.bind("SUPER + ESCAPE", "System: lock, suspend, restart, shut down", "amadeus-power-menu")
o.bind("SUPER + CTRL + L", "Lock", "swaylock -f")

-- Clipboard. Copy and paste work the same in every application, terminals included.
o.bind("SUPER + C", "Copy", "wtype -M ctrl -k Insert")
o.bind("SUPER + V", "Paste", "wtype -M shift -k Insert")
o.bind("SUPER + CTRL + V", "Clipboard history", "amadeus-clipboard")

-- Capture. The screen freezes while you choose: drag an area, click a window, or click empty
-- space for the whole screen. Screenshots are saved and copied.
o.bind("PRINT", "Screenshot", "amadeus-screenshot")
o.bind("ALT + PRINT", "Record the screen, or stop recording", "amadeus-record toggle")

-- Scratchpad: windows kept out of the way, shown over everything with one key.
o.bind("SUPER + S", "Scratchpad", hl.dsp.workspace.toggle_special("scratchpad"))
o.bind("SUPER + ALT + S", "Send window to scratchpad", hl.dsp.window.move({ workspace = "special:scratchpad", follow = false }))

-- Windows
o.bind("SUPER + W", "Close window", hl.dsp.window.close())
o.bind("SUPER + F", "Fullscreen", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
o.bind("SUPER + M", "Maximise", hl.dsp.window.fullscreen({ mode = "maximized" }))
o.bind("SUPER + T", "Toggle floating", hl.dsp.window.float({ action = "toggle" }))
o.bind("SUPER + J", "Toggle split direction", hl.dsp.layout("togglesplit"))
o.bind("SUPER + CTRL + C", "Centre window", hl.dsp.window.center())
for key, dir in pairs({ LEFT = "l", RIGHT = "r", UP = "u", DOWN = "d" }) do
  local name = ({ l = "left", r = "right", u = "up", d = "down" })[dir]
  o.bind("SUPER + " .. key, "Focus " .. name, hl.dsp.focus({ direction = dir }))
  o.bind("SUPER + SHIFT + " .. key, "Move window " .. name, hl.dsp.window.swap({ direction = dir }))
end
for i = 1, 10 do
  local key = i % 10
  o.bind("SUPER + " .. key, "Workspace " .. i, hl.dsp.focus({ workspace = tostring(i) }))
  o.bind("SUPER + SHIFT + " .. key, "Move window to workspace " .. i, hl.dsp.window.move({ workspace = tostring(i), follow = false }))
end
hl.bind("SUPER + mouse:272", hl.dsp.window.drag(), { mouse = true })
hl.bind("SUPER + mouse:273", hl.dsp.window.resize(), { mouse = true })

-- Hardware keys
local hw = { locked = true, repeating = true }
o.bind("XF86AudioRaiseVolume", "Volume up", "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+", hw)
o.bind("XF86AudioLowerVolume", "Volume down", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", { locked = true, repeating = true })
o.bind("XF86AudioMute", "Mute", "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", { locked = true })
o.bind("XF86AudioMicMute", "Mute microphone", "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", { locked = true })
o.bind("XF86MonBrightnessUp", "Brightness up", "brightnessctl -e4 -n2 set 5%+", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Brightness down", "brightnessctl -e4 -n2 set 5%-", { locked = true, repeating = true })
o.bind("XF86AudioPlay", "Play or pause", "playerctl play-pause", { locked = true })
o.bind("XF86AudioNext", "Next track", "playerctl next", { locked = true })
o.bind("XF86AudioPrev", "Previous track", "playerctl previous", { locked = true })

-- Amadeus approval prompts float in the centre.
o.window({ class = "^org\\.quickshell$", title = "^Amadeus" }, { float = true, center = true })
-- Games get the whole screen.
o.window({ class = "^steam_app_.*$" }, { fullscreen = true })
