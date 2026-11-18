---
name: amadeus
description: >
  REQUIRED for end-user customization of Linux desktop, window manager, or system config.
  Use when editing ANY file in ~/.config/, ~/.config/hypr/, ~/.config/amadeus/,
  ~/.config/alacritty/, ~/.config/foot/, ~/.config/kitty/, or ~/.config/ghostty/.
  Triggers: Hyprland, window rules, window behavior, animations, keybindings, monitors, gaps, borders,
  blur, opacity, amadeus-shell, bar, widgets, terminal config, themes, fonts, background,
  night light, idle, lock screen, screenshots, screen recording, reminders, layer rules, workspace
  settings, display config, appearance changes, and user-facing amadeus commands. Excludes Amadeus
  source development through `amadeus dev link` workflows.
---

# Amadeus Skill

Manage [Amadeus](https://github.com/Jitheswar/Amadeus) Linux systems - a beautiful, fun, agentic Arch Linux distribution with Hyprland.

This skill is for end-user customization on installed systems.
It is not for contributing to Amadeus source code.

## Topic Guides

Deeper instructions for common areas live next to this file. Read the
matching guide before starting:

- [`hyprland.md`](hyprland.md) - keybindings, monitors, window rules, and other Hyprland config
- [`plugins.md`](plugins.md) - the Amadeus shell: bar layout, widgets, plugins, idle behavior
- [`theming.md`](theming.md) - themes, backgrounds, and fonts
- [`hooks.md`](hooks.md) - automation hooks that run on system events
- [`capture.md`](capture.md) - screenshots, screen recordings, OCR text capture, and file sharing
- [`contributing.md`](contributing.md) - reporting Amadeus bugs and submitting fixes upstream

## Critical Safety Rules

For privileged commands, follow the Privilege Escalation rules below: `sudo` when a terminal is available for the password prompt, `pkexec` when it is not. Do not wrap commands that already manage privilege elevation themselves.

**For end-user customization tasks, NEVER modify anything in `/usr/share/amadeus/`** - but READING is safe and encouraged.

This directory is owned by the amadeus package. Any local changes will be
overwritten on the next `amadeus update`.

```
/usr/share/amadeus/     # READ-ONLY - NEVER EDIT (reading is OK)
├── bin/                    # Command source (packaged binaries are on PATH)
├── config/                 # Default config templates
├── themes/                 # Stock themes
├── default/                # System defaults
├── shell/                  # Amadeus shell source and defaults
├── migrations/             # Update migrations
└── install/                # Installation scripts
```

**Reading `/usr/share/amadeus/` is SAFE and useful** - do it freely to:
- Understand how amadeus commands work: `amadeus theme set --help` or `cat $(which amadeus-theme-set)`
- See default configs before customizing: `cat "$AMADEUS_PATH/config/amadeus/shell.json"`
- Check stock theme files to copy for customization
- Reference default hyprland settings: `cat /usr/share/amadeus/default/hypr/*`

**Always use these safe locations instead:**
- `~/.config/` - User configuration (safe to edit)
- `~/.config/amadeus/themes/<custom-name>/` - Custom themes
- `~/.config/amadeus/hooks/` - Custom automation hooks

If the request is to develop Amadeus itself, this skill is out of scope. Follow repository development instructions instead of this skill.

## Privilege Escalation

For an interactive script or command run in a visible terminal, use `sudo` for
privileged work. Amadeus may grant passwordless `sudo` access to particular
commands, and the terminal is the appropriate place to request a password
when one is needed.

Use `pkexec` only when the caller cannot interact with a terminal or cannot
enter a password there, such as a command launched by an agent or a graphical
background process. Do not replace `sudo` with `pkexec` merely because a
command changes system state.

## System Architecture

Amadeus is built on:

| Component | Purpose | Config Location |
|-----------|---------|-----------------|
| **Arch Linux** | Base OS | `/etc/`, `~/.config/` |
| **Hyprland** | Wayland compositor/WM | `~/.config/hypr/` |
| **Amadeus shell** | Status bar + notifications (Quickshell) | `~/.config/amadeus/shell.json` |
| **Launcher/menus** | Quickshell menu | `~/.config/amadeus/extensions/amadeus-menu.jsonc` |
| **Alacritty/Foot/Kitty/Ghostty** | Terminals | `~/.config/<terminal>/` |
| **Amadeus OSD** | On-screen display | Quickshell plugin |

## Command Discovery

Amadeus ships a single `amadeus` CLI that dispatches to all `amadeus-*` binaries via `amadeus <group> <action>`. Always prefer this form — it is self-documenting and stable. The underlying `amadeus-*` binaries still exist on `PATH` and remain safe to read for source.

```bash
# List every documented command and its summary (--all includes hidden commands)
amadeus commands

# Show the commands inside a group
amadeus theme --help
amadeus refresh --help
amadeus restart --help

# Show help for a specific command (does not execute it)
amadeus theme set --help

# Machine-readable listing (binary, route, summary, args, aliases)
amadeus commands --json

# Read a command's source to understand it
cat $(which amadeus-theme-set)
```

### Command Groups

Run `amadeus --help` for the full list. The most common groups:

| Group | Purpose | Example |
|-------|---------|---------|
| `amadeus refresh` | Reset config to defaults (backs up first) | `amadeus refresh shell` |
| `amadeus restart` | Restart a service/app | `amadeus restart shell` |
| `amadeus toggle` | Toggle feature on/off | `amadeus toggle nightlight` |
| `amadeus theme` | Theme management | `amadeus theme set <name>` |
| `amadeus bar` | Bar layout and widgets | `amadeus bar move amadeus.clock --section right` |
| `amadeus plugin` | Manage/clone shell plugins | `amadeus plugin clone amadeus.clock` |
| `amadeus hook` | Install automation hooks | `amadeus hook install theme-set <script>` |
| `amadeus install` | Install optional software / packages | `amadeus install docker dbs` |
| `amadeus launch` | Launch apps | `amadeus launch browser` |
| `amadeus capture` | Screenshots and recordings | `amadeus capture screenshot` |
| `amadeus reminder` | Desktop notification reminders | `amadeus reminder 15 "Pickup Jack"` |
| `amadeus pkg` | Package management | `amadeus pkg add <pkg>` |
| `amadeus setup` | Interactive setup wizards | `amadeus setup security fingerprint` |
| `amadeus update` | System updates | `amadeus update` |

## Configuration Locations

Hyprland config lives in `~/.config/hypr/` — see [`hyprland.md`](hyprland.md).
The Amadeus shell (bar, notifications, plugins, idle) is configured in
`~/.config/amadeus/shell.json` — see [`plugins.md`](plugins.md).

### Terminals

```
~/.config/alacritty/alacritty.toml
~/.config/foot/foot.ini
~/.config/kitty/kitty.conf
~/.config/ghostty/config
```

**Command:** `amadeus restart terminal`

### Other Configs

| App | Location |
|-----|----------|
| btop | `~/.config/btop/btop.conf` |
| fastfetch | `/etc/fastfetch/config.jsonc` default; `~/.config/fastfetch/config.jsonc` user override |
| lazygit | `~/.config/lazygit/config.yml` |
| starship | `~/.config/starship.toml` |
| git | `~/.config/git/config` |

## Safe Customization Patterns

### Edit User Config Directly

For simple changes, edit files in `~/.config/`:

```bash
# 1. Read current config
cat ~/.config/hypr/bindings.lua

# 2. Backup before changes
cp ~/.config/hypr/bindings.lua ~/.config/hypr/bindings.lua.bak.$(date +%s)

# 3. Make changes with Edit tool

# 4. Apply changes
# - Hyprland: auto-reloads on save, but MUST validate with `hyprctl reload` and `hyprctl configerrors`
# - Amadeus shell: shell.json and user plugin code under ~/.config/amadeus/plugins/ hot-reload on save
# - Menus/launcher: ~/.config/amadeus/extensions/amadeus-menu.jsonc hot-reloads on save
# - Terminals: apply with `amadeus restart terminal` (reloads running terminals; foot picks changes up in new windows)
```

### Reset to Defaults -- ALWAYS SEEK USER CONFIRMATION BEFORE RUNNING

When customizations go wrong:

```bash
# Reset specific config (creates backup automatically)
amadeus refresh shell
amadeus refresh hyprland

# The refresh command:
# 1. Backs up current config with timestamp
# 2. Copies default from $AMADEUS_PATH/config/
# 3. Restarts the component where the refresh needs it (e.g. `refresh shell`)
```

## System Commands

```bash
amadeus update                  # Full system update
amadeus version                 # Show Amadeus version
amadeus debug --no-sudo --print # Debug info (ALWAYS use these flags)
amadeus system lock             # Lock screen
amadeus system shutdown         # Shutdown
amadeus system reboot           # Reboot
```

**IMPORTANT:** Always run `amadeus debug` with `--no-sudo --print` flags to avoid interactive sudo prompts that will hang the terminal.

## Troubleshooting

```bash
# Get debug information (ALWAYS use these flags to avoid interactive prompts)
amadeus debug --no-sudo --print

# Reset specific config to defaults
amadeus refresh <app>

# Refresh specific config file
# config-file path is relative to ~/.config/
# eg. `amadeus refresh config hypr/hyprland.lua` will refresh ~/.config/hypr/hyprland.lua
amadeus refresh config <config-file>

# Full reinstall of configs (nuclear option)
amadeus reinstall
```

## Decision Framework

When user requests system changes:

1. **Is it a stock amadeus command?** Use it directly
2. **Is it a config edit?** Edit in `~/.config/`, never `/usr/share/amadeus/`
3. **Is it a theme customization?** Follow [`theming.md`](theming.md); create a NEW custom theme directory
4. **Is it automation?** Follow [`hooks.md`](hooks.md); use `amadeus hook install` and the hook `.d` directories
5. **Is it a package install?** Use `amadeus pkg add <pkgs...>` (or `amadeus pkg aur add <pkgs...>` for AUR-only packages)
6. **Is it built-in shell/plugin code?** Follow [`plugins.md`](plugins.md); clone it with `amadeus plugin clone`, never edit the packaged copy
7. **Unsure if command exists?** Run `amadeus commands` (or `amadeus <group> --help` for one group)

### Reminder Requests

When the user asks to set a reminder, use `amadeus reminder <minutes> [message]` directly. Convert natural language durations to minutes and title-case short reminder labels when appropriate.

```bash
amadeus reminder 15 "Pickup Jack"
amadeus reminder 60 "Check laundry"
amadeus reminder show
amadeus reminder clear
```

## Out of Scope

This skill intentionally does not cover Amadeus source development. Do not use this skill for:
- Editing files in `/usr/share/amadeus/` (`bin/`, `config/`, `default/`, `shell/`, `themes/`, `migrations/`, etc.)
- Creating or editing migrations
- Running `amadeus dev ...` commands

## Example Requests

- "Change my theme to catppuccin" -> `amadeus theme set catppuccin`
- "Add a keybinding for Super+E to open file manager" -> Check existing bindings first, then use `o.rebind` to replace one or `o.bind` to add one in `~/.config/hypr/bindings.lua`
- "Configure my external monitor" -> Edit `~/.config/hypr/monitors.lua`
- "Make the window gaps smaller" -> Edit `~/.config/hypr/looknfeel.lua`
- "Turn on night light" -> `amadeus toggle nightlight` (for time-based schedules, edit `~/.config/hypr/hyprsunset.conf` profiles, then `amadeus restart hyprsunset`)
- "Set a reminder to pickup jack in 15 minutes" -> `amadeus reminder 15 "Pickup Jack"`
- "Show my reminders" -> `amadeus reminder show`
- "Clear all reminders" -> `amadeus reminder clear`
- "Customize the catppuccin theme colors" -> Overlay: put an edited `colors.toml` in `~/.config/amadeus/themes/catppuccin/`, then re-apply the theme (see `theming.md`)
- "Run a script every time I change themes" -> Install it with `amadeus hook install theme-set <script>`
- "Change how workspace labels are rendered" -> Clone `amadeus.workspaces`, which switches the bar to `<username>.workspaces`, then edit the clone
- "Lock after ten minutes" -> Set `idle.lock` to `600` in `~/.config/amadeus/shell.json`
- "Reset shell/bar to defaults" -> `amadeus refresh shell`
- "Record my screen" -> `amadeus screenrecord --fullscreen`, then `amadeus screenrecord --stop-recording` (see `capture.md`)
- "Report this bug to Amadeus" -> Gather diagnostics and a capture of the problem, then file it (see `contributing.md`)
