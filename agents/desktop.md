# Changing the desktop

Read `AGENTS.md` first, especially "Refresh pattern" and "Command naming".

`desktop/` builds the `amadeus-desktop` package: compositor defaults in `desktop/niri/`,
the shell (bar, picker, notifications) in `desktop/shell/`, system commands in `desktop/bin/`, and the files every new
user starts with in `desktop/skel/`.

## Rules

- **Two layers.** Defaults are shipped and replaced on update. The user's file includes
  them. Never put something the user would want to change only in the shipped file with
  no way to override it, and never make an update depend on editing a user's file.
- **The compositor config must validate.** Check it with the compositor's own validator
  inside the build container (see [build-and-test.md](build-and-test.md));
  the syntax changes between releases, so check against the installed version, not memory.
- **Key bindings** are defined once, in the shipped defaults, each with an overlay title.
  Before adding one, read that file for conflicts.
- **The bar's layout is data.** A new widget is a component plus an id in the widget
  table in the bar, and the same id in the AI layer's list of bar widgets in
  `ai/amadeus/tools/desktop.py`. Both or neither.
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
