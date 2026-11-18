# Themes, Backgrounds, and Fonts

Read this before changing themes, backgrounds, fonts, or theme colors.

## Theme Commands

```bash
amadeus theme list              # Show available themes
amadeus theme current           # Show current theme
amadeus theme set <name>        # Apply theme ("Tokyo Night" and "tokyo-night" both work)
amadeus theme bg next           # Cycle background
amadeus theme install <url>     # Install from git repo
```

## Making a New Theme

1. Create a directory under `~/.config/amadeus/themes`.
2. See how an existing theme is done via `/usr/share/amadeus/themes/catppuccin`.
3. Download a matching background (or several) from the internet and put them in `~/.config/amadeus/themes/<name-of-new-theme>/backgrounds/`.
4. When done with the theme, run `amadeus theme set "Name of new theme"`.

Additional user backgrounds for any theme (stock or custom) go in
`~/.config/amadeus/backgrounds/<theme-slug>/`.

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
`chromium.theme`, `helix.toml`, `icons.theme`, `keyboard.rgb` and `shell.toml`.
Amadeus tells a cloned theme from the user's own by the `.git` directory a clone
leaves behind.

To change how Amadeus themes an app for every theme, write the template rather
than the theme: `~/.config/amadeus/themed/<config-name>.tpl` overrides the
built-in one. See `docs/theming.md` in the Amadeus repo.

## Customizing a Stock Theme

Never edit stock themes under `/usr/share/amadeus/themes/` — changes are lost
on update. Two safe options:

Both write into `~/.config/amadeus/themes`, where a theme the user wrote is
unrestricted — the list above applies only to a theme cloned from a repo.

**Overlay (preferred for small tweaks):** create a user theme directory with
the SAME slug containing only the files you want to change. When the theme is
applied, the stock theme is copied first and your files win on top:

```bash
mkdir -p ~/.config/amadeus/themes/catppuccin
cp /usr/share/amadeus/themes/catppuccin/colors.toml ~/.config/amadeus/themes/catppuccin/
# Edit the copied colors.toml, then re-apply:
amadeus theme set catppuccin
```

**Fork:** copy the whole stock theme under a new name for a fully independent
variant:

```bash
cp -r /usr/share/amadeus/themes/catppuccin ~/.config/amadeus/themes/catppuccin-custom
# Edit ~/.config/amadeus/themes/catppuccin-custom/, then:
amadeus theme set catppuccin-custom
```

## Fonts

```bash
amadeus font list               # Available fonts
amadeus font current            # Current font
amadeus font set <name>         # Change font
```
