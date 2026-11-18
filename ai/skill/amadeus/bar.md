# The Bar, Built-In Widgets, Idle and Lock

## Bar Layout

Use the `amadeus bar` group to move and manage widgets:

```bash
amadeus bar move amadeus.clock --section right
```

For layout edits beyond what the commands cover, edit the bar configuration
in `~/.config/amadeus/shell.json`; it hot-reloads on save.

`bar.layout` has five sections, in the order they run along the bar: `left`,
`centerBegin`, `center`, `centerEnd`, and `right`, plus `tray`, drawn inside
the tray's drawer. `center` is a box in the middle of the bar whose widgets
are centered as one group; `centerBegin` and `centerEnd` hang off its two
edges. Put a widget beside the clock in `centerBegin` or `centerEnd`, not in
`center`, or the clock moves off center.
## Customizing Built-In Plugins and Widgets

To customize a built-in bar widget, never edit `$AMADEUS_PATH/shell/plugins/`.
Clone it into the user plugin directory instead:

```bash
amadeus plugin clone amadeus.workspaces
# Edit ~/.config/amadeus/plugins/<username>.workspaces/; saved changes reload automatically.
```

Cloning switches the bar to the cloned copy (e.g. `<username>.workspaces`),
which is yours to edit and survives updates.

Saving a file anywhere under `~/.config/amadeus/plugins/` reloads plugin code
automatically. If a change somehow fails to apply, force a reload with
`amadeus-shell shell reloadPlugins`.
## Idle and Lock

Set `idle.screensaver` and `idle.lock` in `~/.config/amadeus/shell.json`,
in seconds since user idle began. Example: "lock after ten minutes" means
setting `idle.lock` to `600`.
