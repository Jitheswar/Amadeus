# Themes, Backgrounds, and Fonts

Read this before changing themes, backgrounds, fonts, or theme colors. Making or
customizing a theme is in [`making-themes.md`](making-themes.md).
## Theme Commands

```bash
amadeus theme list              # Show available themes
amadeus theme current           # Show current theme
amadeus theme set <name>        # Apply theme ("Tokyo Night" and "tokyo-night" both work)
amadeus theme bg next           # Cycle background
amadeus theme install <url>     # Install from git repo
```
## What a Theme Installed From a Repo May Not Contain

A theme the user wrote by hand in `~/.config/amadeus/themes` is unrestricted, as
are Amadeus's own themes. From a theme cloned by `amadeus theme install`, Amadeus
drops only what runs code: any `*.lua` (Hyprland requires a theme's
`hyprland.lua` and `gum_env.lua` at login, Neovim loads `neovim.lua` at startup),
the terminal configs `alacritty.toml`, `foot.ini`, `ghostty.conf` and
`kitty.conf` (each names the program the terminal launches), and `vscode.json`
(names a VS Code extension to install). Those are regenerated from `colors.toml`
through `$AMADEUS_PATH/default/themed/*.tpl`, and named on stderr.

Everything else a cloned theme ships is kept, including `btop.theme`,
`chromium.theme`, `helix.toml`, `keyboard.rgb` and `shell.toml`.
Amadeus tells a cloned theme from the user's own by the `.git` directory a clone
leaves behind.

To change how Amadeus themes an app for every theme, write the template rather
than the theme: `~/.config/amadeus/themed/<config-name>.tpl` overrides the
built-in one. See `docs/theming.md` in the Amadeus repo.
## Fonts

```bash
amadeus font list               # Available fonts
amadeus font current            # Current font
amadeus font set <name>         # Change font
```
