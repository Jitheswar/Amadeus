# Theming: one file colours everything

Read this before changing colours, light/dark, or the look of any application.

## How it works

A theme is one `colors.toml`. `amadeus-theme` renders a template per application from
it, swaps the results in as a whole, and reloads what can reload. The shell and the
panel follow live. Applications installed later are already themed, because their
first configuration includes the rendered file. Read the command's header for the
exact locations; `amadeus-theme list` and `amadeus-theme current` show the state.

## Tasks

- **Switch theme:** `amadeus-theme set NAME`.
- **Make a theme:** create `colors.toml` in a new folder under the user's themes
  directory. Copy a shipped theme as the starting point; only background, foreground,
  accent and the six base colours are required, the rest is derived. Then set it.
- **Theme an application the system does not cover:** add a template to the user's
  template directory, using the same `{{ name }}`, `{{ name_strip }}` (no `#`) and
  `{{ name_rgb }}` placeholders as the shipped templates, then point that
  application's configuration at the rendered file. Set the theme again to render it.
- **Change one colour everywhere:** change it in the theme file and set the theme
  again. Do not edit a rendered file: the next theme change replaces it.

## Pitfalls

- Open terminals keep their colours until a new window is opened. Say so.
- A configuration file the user already owns is not overwritten. If an application
  ignores the theme, check whether its configuration includes the rendered file.
- Never write colours into shipped files, the shell source or the compositor defaults.
- Check contrast when making a light theme: the accent must stay readable on the
  background and under dark text.
