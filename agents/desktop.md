# Changing the desktop

Read `AGENTS.md` first, especially "Refresh pattern" and "Command naming".

`desktop/` builds the `amadeus-desktop` package: compositor defaults in `desktop/hypr/`,
the shell (bar, picker, notifications) in `desktop/shell/`, system commands in `desktop/bin/`, and the files every new
user starts with in `desktop/skel/`.

## Rules

- **Two layers.** Defaults are shipped and replaced on update. The user's file includes
  them. Never put something the user would want to change only in the shipped file with
  no way to override it, and never make an update depend on editing a user's file.
- **The compositor config must load.** Check it with `Hyprland --verify-config --config FILE`;
  the configuration language changes between releases, so check against the installed
  version, not memory. Every shortcut is made with `o.bind` and carries a description.
- **Key bindings** are defined once, in the shipped defaults, each with an overlay title.
  Before adding one, read that file for conflicts.
- **The bar's layout is data.** A new widget is a component plus an id in the widget
  table in the bar, and the same id in the AI layer's list of bar widgets in
  `ai/amadeus/tools/desktop.py`. Both or neither.
- **One theme.** Colours, fonts, corner radius and animation timings come from
  `desktop/theme/theme.json`. Shell and panel code reads them; it never contains a
  colour or a duration of its own. Files that cannot read the theme (compositor, lock
  screen, terminal) may only repeat its colours, and `./build.sh check` enforces that.
- **Motion has three speeds** (fast, normal, slow in the theme) and one easing. A surface
  opens and closes from one animated value so it can reverse midway. If an animation
  does not show where something came from or went, remove it.
- **Look at what you changed.** `./build.sh preview` draws the shell, picker,
  notifications and panel headless into `out/preview/`. Read the pictures before you
  commit a visual change.
- **Software a user can install is a catalogue line, not code.** Add it to the right file
  in `desktop/catalog/`, system repository source first, AUR second. Read the AUR recipe
  and list it only if it downloads the publisher's own build or builds the publisher's
  source.
- **Never name a terminal, editor or harness in code.** Call `amadeus-terminal`,
  `amadeus-editor` or `amadeus-harness run`; the user chooses what they are.
- **One picker.** Every list a user chooses from goes through `desktop/bin/amadeus-pick`,
  which the shell draws. Do not add another menu program.
- **State comes from events.** The bar reads the compositor's event stream. Do not add a
  timer where an event exists.
- **Commands** follow the naming rule and carry their description on line 2. A command
  that changes the system confirms first and says how to undo.
- **Nothing here selects the NVIDIA card.** The desktop renders on the Intel GPU.

## Checking your change

`./build.sh check`. Then, because the desktop only truly runs in a session,
`./build.sh iso` and `./build.sh test`, with a self-test line for anything new.
