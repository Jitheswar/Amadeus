# Hyprland Configuration

Read this before changing keybindings, monitors, window rules, or any other
Hyprland (window manager) configuration.

Amadeus configures Hyprland in Lua. User files are loaded after Amadeus's
defaults, so overrides go here:

```
~/.config/hypr/
├── hyprland.lua       # Main config (loads Amadeus defaults, then user files)
├── bindings.lua       # Keybindings
├── monitors.lua       # Display configuration
├── input.lua          # Keyboard/mouse settings
├── looknfeel.lua      # Appearance (gaps, borders, animations)
├── autostart.lua      # Startup applications
├── hyprsunset.conf    # Night light / blue light filter
└── xdph.conf          # Screen sharing / desktop portal
```

**Key behaviors (the `.lua` files):**
- Hyprland auto-reloads on config save (no restart needed for most changes)
- Use `hyprctl reload` to force reload
- After ANY Hyprland Lua config change, validate with `hyprctl reload` followed by `hyprctl configerrors`
- If `hyprctl configerrors` reports errors, address them and rerun validation until clean or until a real blocker is identified
- Use `amadeus refresh hyprland` to reset the Lua config files to defaults

The two `.conf` files are read by separate processes, so `hyprctl` neither
applies nor validates them:
- `hyprsunset.conf` (night light): apply changes with `amadeus restart hyprsunset`; reset with `amadeus refresh hyprsunset`
- `xdph.conf` (screen-sharing portal): applies when the portal restarts, e.g. on next login
## Keybindings

Edit `~/.config/hypr/bindings.lua`. Format:
```lua
o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")
o.bind("SUPER + B", "Browser", { launch = "chromium" })  -- launch wraps with uwsm-app
o.bind("SUPER + M", "Theme menu", { menu = "theme" })     -- toggle an Amadeus menu route
o.bind("SUPER + N", "Network", { panel = "amadeus.network" })  -- toggle a shell panel
```

Prefer `{ menu = ... }` and `{ panel = ... }` over running `amadeus-menu toggle ...` or `amadeus-shell shell toggle ...` as a command. Routes and panels listed in `$AMADEUS_PATH/default/amadeus/shortcuts` go straight to the running shell as Hyprland global shortcuts, with no process started on each press; any other route or panel still works, through the command.

View current bindings: `amadeus menu keybindings --print`

**IMPORTANT: When re-binding an existing key:**

1. First check existing bindings: `amadeus menu keybindings --print`
2. If the key is already bound, use `o.rebind(...)` to remove the existing binding and add its replacement. It takes the same arguments as `o.bind(...)`.
3. Inform the user what the key was previously bound to

Example - rebinding SUPER+F (which is bound to fullscreen by default):
```lua
-- Replace SUPER+F (was: fullscreen) with the file manager.
o.rebind("SUPER + F", "File manager", { launch = "nautilus" })
```

Tell the user which action was replaced. Use `hl.unbind(...)` to remove a binding without replacing it.
## Window Rules

**CRITICAL: Hyprland window rules syntax changes frequently between versions.**

Before writing ANY window rules, you MUST fetch the current documentation from the official Hyprland wiki:
- https://wiki.hypr.land/Configuring/Basics/Window-Rules/

DO NOT rely on cached or memorized window rule syntax. The format has changed multiple times and using outdated syntax will cause errors or unexpected behavior.

Window rules go in `~/.config/hypr/hyprland.lua` or a required Lua module. Prefer Amadeus's `o.window(match, rules)` helper — see examples in `$AMADEUS_PATH/default/hypr/windows.lua`.

Monitors (scale, resolution, layout) are in [`monitors.md`](monitors.md).
