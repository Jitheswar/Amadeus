-- Amadeus OS desktop defaults. Shipped in /usr/share/amadeus-os and updated with the system.
-- Personal changes belong in ~/.config/hypr/hyprland.lua, which loads this file first.
-- Nothing here selects a dedicated GPU: the compositor and ordinary applications render on the
-- GPU the screen is wired to, and Amadeus (or `amadeus-gpu-run <app>`) sends single applications
-- to the dedicated one.

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

-- Graphics, following the hardware. Read from sysfs only: reading PCI configuration would wake a
-- sleeping NVIDIA card, and a configuration reload has a time budget.
local function first_line(path)
  local f = io.open(path)
  if not f then return nil end
  local line = f:read("l"); f:close(); return line
end
local nvidia, nvidia_gsp, nvidia_display, other_display = false, false, false, false
local devices = io.popen("ls -d /sys/bus/pci/devices/* 2>/dev/null")
for dev in devices:lines() do
  if (first_line(dev .. "/class") or ""):sub(1, 4) == "0x03" then
    local boot = first_line(dev .. "/boot_vga") == "1"
    if first_line(dev .. "/vendor") == "0x10de" then
      nvidia = true
      nvidia_gsp = nvidia_gsp or (tonumber(first_line(dev .. "/device") or "0") or 0) >= 0x1e00
      nvidia_display = nvidia_display or boot
    elseif boot then
      other_display = true
    end
  end
end
devices:close()
if nvidia and first_line("/sys/module/nvidia/version") then
  hl.env("NVD_BACKEND", nvidia_gsp and "direct" or "egl")
  -- On hybrid laptops the screen is wired to the integrated GPU, and forcing NVIDIA's video and GL
  -- drivers for everything breaks video in Chromium-based browsers; only when NVIDIA drives the screen.
  if nvidia_display or not other_display then
    if nvidia_gsp then hl.env("LIBVA_DRIVER_NAME", "nvidia") end
    hl.env("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
  end
end
-- nouveau (an NVIDIA card running without NVIDIA's driver) hides the hardware cursor on many cards.
local nouveau = first_line("/sys/module/nouveau/refcnt") ~= nil and not io.open("/etc/modprobe.d/nvidia.conf")

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

if nouveau then hl.config({ cursor = { no_hardware_cursors = true } }) end
-- A virtual machine usually draws on the processor, where every animation costs a frame.
local vm = io.popen("systemd-detect-virt --vm --quiet && echo vm")
if vm then
  if vm:read("l") == "vm" then hl.config({ animations = { enabled = false } }) end
  vm:close()
end

-- The chosen theme's colours, written by amadeus-theme; until one is chosen the values above stand.
pcall(dofile, (os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")) .. "/amadeus/current/theme/hyprland.lua")

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
  hl.exec_cmd("amadeus-display auto")
  -- Audio fixes this computer's hardware needs (ASUS mixer, AMD microphones, Dell XPS speaker
  -- tuning). Once per user: it needs the audio server, so it cannot run at install.
  hl.exec_cmd("amadeus-hardware user --once")
  -- Your own scripts in ~/.config/amadeus/hooks/post-boot(.d), once per login.
  hl.exec_cmd("amadeus-hook post-boot")
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
o.bind("SUPER + ALT + A", "Ask Amadeus about selected text", "ama panel selection")
o.bind("SUPER + SHIFT + ESCAPE", "Stop all Amadeus tasks", "ama stop")
o.bind("SUPER + B", "Browser", "xdg-open https://")
o.bind("SUPER + E", "Files", "nautilus --new-window")
o.bind("SUPER + SHIFT + F", "Files (your default application)", "xdg-open ~")
o.bind("SUPER + ESCAPE", "System: lock, suspend, restart, shut down", "amadeus-power-menu")
o.bind("SUPER + CTRL + L", "Lock", "swaylock -f")

-- Clipboard dispatch adapted from Omarchy (MIT; see the packaged OMARCHY-LICENSE).
-- A virtual keyboard merges physically held SUPER into the chord. Dispatch explicit
-- modifier state to the focused surface instead, including layer-shell panels.
local function clipboard_shortcut(key)
  return function()
    local window = hl.get_active_window()
    local terminal = false
    for _, tag in ipairs(window and window.tags or {}) do
      if tag:gsub("%*$", "") == "terminal" then terminal = true end
    end
    local mods = terminal and "CTRL SHIFT" or "CTRL"
    hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "down" }))
    hl.timer(function()
      hl.dispatch(hl.dsp.send_key_state({ mods = mods, key = key, state = "up" }))
    end, { timeout = 50, type = "oneshot" })
  end
end
o.window("^(Alacritty|com\\.mitchellh\\.ghostty|foot|footclient|kitty|org\\.wezfurlong\\.wezterm|org\\.gnome\\.Ptyxis|org\\.gnome\\.Console|org\\.gnome\\.Terminal|konsole|herdr|TUI\\..*)$", { tag = "+terminal" })
o.bind("SUPER + C", "Universal copy", clipboard_shortcut("C"))
o.bind("SUPER + V", "Universal paste", clipboard_shortcut("V"))
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
