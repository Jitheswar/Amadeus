# Changing the desktop

Read `AGENTS.md` first, especially "Refresh pattern" and "Command naming".

`desktop/` builds the `amadeus-desktop` package. Most of the desktop is the desktop
system in `desktop/system/`, laid out as it lands on disk: its commands, the Quickshell
shell with its plugins (bar, menu, notifications, dock, OSD, lock screen, clipboard),
the modular Hyprland defaults, the theme templates and themes, system configuration and
the user skeleton, all under `desktop/system/usr/share/amadeus/` and `desktop/system/etc/`.
`desktop/bin/` holds the commands only Amadeus has: hardware detection, GPU modes,
updates, migrations, hooks, AUR and harness management, the catalogue, mirrors,
rollback, and the launcher and search the assistant uses.

## Rules

- **Two layers.** Shipped defaults live in `usr/share/amadeus/default/` and are replaced
  on update; the user's own files come from the skeleton and are theirs. Never make an
  update depend on editing a user's file; a change that must reach existing users is a
  migration in `desktop/migrations/`.
- **Hyprland is modules.** `default/hypr/amadeus.lua` requires each module; add a module
  rather than growing an unrelated one. The assistant's shortcuts live in
  `default/hypr/bindings/assistant.lua` (so `amadeus_default_bindings = false` turns them off
  with the rest) and its window rules in `default/hypr/assistant.lua`. Every shortcut is made with `o.bind` and carries a
  description; a key may run several actions within one module, but two modules must not
  claim the same key (`./build.sh check` enforces both).
- **The compositor config must load.** Check it with `Hyprland --verify-config` against
  the installed version, not memory: the configuration language changes between releases.
- **The menu is data.** Entries live in `default/amadeus/amadeus-menu.jsonc`; add a line
  there rather than a new menu program. Users and plugins extend it with their own files.
- **The bar's layout is data** in `config/amadeus/shell.json`; widgets are plugins. The
  assistant's bar tool in `ai/amadeus/tools/desktop.py` knows the sections; keep them in step.
- **Colours are rendered, not repeated.** A theme is a folder with a `colors.toml` under
  `usr/share/amadeus/themes/`; `amadeus-theme-set` renders `default/themed/*.tpl` for each
  application. Theme a new application by adding a template, never by writing colours
  into its configuration. The assistant's panel is themed the same way
  (`default/themed/assistant.json.tpl`).
- **Software a user can install is a menu entry or a catalogue line, not code.** Catalogue
  lines in `desktop/catalog/` name the system repository source first, AUR second. Read
  the AUR recipe and list it only if it downloads the publisher's own build or builds the
  publisher's source.
- **Never name a terminal, editor or agent in code.** Call `xdg-terminal-exec`,
  `amadeus-launch-editor` or `amadeus-harness run`; the user chooses what they are.
- **State comes from events.** The bar reads the compositor's event stream. Do not add a
  timer where an event exists.
- **Commands** follow the naming rule. Amadeus's own carry their description on line 2;
  the desktop system's keep their `# amadeus:summary=` header. A command that changes the
  system confirms first and says how to undo.
- **The integrated GPU draws the desktop.** Only an explicit user GPU-mode choice may
  change that. Do not wake NVIDIA merely to read its state.
- **Settings have different owners.** Application defaults use `amadeus-default-*`; the
  panel's default agent uses the AI configuration. Keep them independent.
- **Usage follows intent.** Read the default-agent label without starting an idle
  daemon; collect usage only when opened or explicitly refreshed.

## Checking your change

`./build.sh check`. Then, because the desktop only truly runs in a session,
`./build.sh iso` and `./build.sh test`, with a self-test line for anything new.
