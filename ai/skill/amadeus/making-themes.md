# Making and Customizing Themes

## Making a New Theme

A theme is a directory in `~/.config/amadeus/themes/<slug>/` (the slug becomes the name: `tea-house` shows as "Tea House") with two things in it:

- `colors.toml`, the palette. Amadeus generates every app's colors from it when the theme is applied: terminals, btop, Hyprland borders, Neovim, VS Code, the shell, the keyboard backlight, and the rest (from `$AMADEUS_PATH/default/themed/*.tpl`). Don't write those files; a file the theme ships replaces the generated one, so write one only to override it. (Stock themes ship `neovim.lua` and `vscode.json` because each names a published Neovim or VS Code color scheme of the same name, and `preview.png`, `unlock.png` and `preview-unlock.png`, which are screenshots taken when a theme is published. A new theme has none of them, so it leaves them all out.)
- `backgrounds/`, two to four wallpapers named `1-<name>.jpg`, `2-<name>.jpg`, and so on, each at least 1920x1080.

1. Copy the `colors.toml` of a stock theme with the same `mode` (dark or light) from `/usr/share/amadeus/themes/` and change its values. It must keep every key: `mode`, `accent`, `selection`, `muted`, `background`, `dark_background`, `darker_background`, `lighter_background`, `foreground`, `dark_foreground`, `light_foreground`, `bright_foreground`, `red`, `yellow`, `green`, `cyan`, `blue`, `magenta`, `orange`, `brown`, and `bright_` versions of red through magenta. Keep body text readable: `foreground` on `background` at 7:1 contrast or more, `accent` and the colors at 3:1 or more.
2. Download photographs or artwork for the backgrounds. Never draw them with ImageMagick or code: generated scenes come out as blurry blobs. Wallhaven's API searches wallpapers by short tag and needs no key; `categories=100` keeps to general images (no anime), and `+` joins words:

   ```bash
   mkdir -p /tmp/candidates && cd /tmp/candidates
   for q in lantern+night misty+temple paper+lantern; do
     curl -s "https://wallhaven.cc/api/v1/search?q=$q&categories=100&purity=100&atleast=1920x1080&ratios=landscape&sorting=relevance" \
       | jq -r '.data[:4][].path'
   done | while read -r url; do curl -sLO "$url"; done
   ```

   Use one or two words per query, and change the queries until the results fit. Then look at all the candidates at once, with each file's name under it, and pick by eye. Numbers like brightness can't tell a lantern from a cartoon:

   ```bash
   magick montage -font "$(fc-match -f '%{file}' sans)" -label '%f' /tmp/candidates/* -resize 480x270^ -gravity center -extent 480x270 -geometry +4+4 -tile 4x -depth 8 -quality 85 /tmp/candidates.jpg
   ```

   Open `/tmp/candidates.jpg` and look at it (a JPEG, so a sheet of thirty stays small enough to view). Copy the two to four that fit the theme's mood and colors into `backgrounds/` as `1-<name>.jpg`, `2-<name>.jpg`, and so on.
3. Look at the result before calling it done. `amadeus agent look theme ~/.config/amadeus/themes/<slug>` draws the theme as a desktop (the first background, the bar, a terminal and a window in its colors) without applying it, checks the palette's keys and contrast and the backgrounds' size, and prints the image's path. Open the image, fix every problem it lists and any color that clashes with the background, and run it again until it's clean.
4. When done with the theme, run `amadeus theme set "Name of new theme"`.

Additional user backgrounds for any theme (stock or custom) go in
`~/.config/amadeus/backgrounds/<theme-slug>/`.
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
