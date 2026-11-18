# Desktop: compositor, shortcuts, windows, bar, menu

Read this before changing how the desktop behaves or looks apart from colours
(colours are in `theming.md`).

## Who owns what

- The compositor's defaults ship with the system and load first; the user's file is
  loaded after them and wins. `ama discover` shows both paths. Never edit the shipped one.
- Shortcuts, window rules and free-form compositor settings: use the tools
  `desktop_keybind` and `desktop_config`. They write the user's layer, verify the whole
  configuration and put the old content back if it does not load.
- The top bar is data: `desktop_bar` reads the layout and the widget ids that exist,
  and rearranges, adds or removes them. Do not edit bar source.
- Text size, display scale, GPU mode, default applications and similar switches:
  `desktop_settings`, or the command the map lists for it.
- Anything a person would reach through the Amadeus menu: `os_menu` searches the same
  routes and can open one.

## Method

1. `hyprctl version`, then read the shipped defaults: the syntax changes between
   releases and that file is the current, working example.
2. `hyprctl -j binds` before adding a shortcut. Every shortcut has a description and
   no key is bound twice.
3. Change the user's layer through the tool. If you must write the file yourself,
   run `Hyprland --verify-config --config FILE` and restore the old file on any error.
4. Check the result by looking: `hyprctl -j` for state, `hyprctl configerrors` for load
   errors.

## Pitfalls

- Never name a terminal, editor or agent in a shortcut. Call `xdg-terminal-exec`,
  `amadeus-launch-editor` or `amadeus-harness run`; the user chooses what those are.
- Menus belong in the Amadeus menu (`amadeus-menu`). Do not add another menu program.
- An entry missing from Apps may be hidden on purpose: the shipped hide list and the
  user's own are named in the launcher's header.
- Changing which GPU draws the desktop needs a new login. Say so; do not restart the
  session yourself.
