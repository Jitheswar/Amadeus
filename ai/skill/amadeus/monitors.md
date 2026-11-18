# Monitors: Scale, Resolution and Layout

Set a monitor's scale, resolution and position with the commands the monitor panel uses. They apply at once and save the choice for that physical monitor in `~/.local/state/amadeus/monitors/settings`, which wins over `monitors.lua`:
```bash
amadeus hyprland monitor scaling --monitor DP-1 1.6
amadeus hyprland monitor resolution --monitor DP-1 3840x2160
amadeus-hyprland-monitor-layout eDP-1=0x0 DP-1=1280x0   # logical pixels, after scale
```

Edit `~/.config/hypr/monitors.lua` only for what those don't cover: a mode the monitor panel doesn't offer (it already sets resolution, refresh rate and rotation), keeping a monitor off (`disabled = true`), 10-bit color, variable refresh rate, the default scale for monitors without a choice, or `GDK_SCALE`. The file ships with commented examples. If the user wants that file alone to set their monitors, overriding the monitor panel, add `amadeus_monitor_panel_settings = false` to it. Format:
```lua
hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "auto", scale = 1.5 })
```

List monitors and supported modes: `hyprctl monitors all`
