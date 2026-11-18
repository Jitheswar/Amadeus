# Theming: one file colours everything

Read this before changing colours, light/dark, or the look of any application.

## How it works

A theme is a folder with a `colors.toml` (and optionally backgrounds and per-application
files). `amadeus-theme-set` renders a template per application from it into
`~/.config/amadeus/current/theme/`, then reloads what can reload: the shell, the
assistant's panel, terminals, the browser, the editor and more follow at once.
`amadeus-theme-list` and `amadeus-theme-current` show the state.

## Tasks

- **Switch theme:** `amadeus-theme-set NAME`. `amadeus-theme-install URL` adds a theme from a
  git repository; `amadeus-theme-remove NAME` removes an added one.
- **Make a theme:** create `colors.toml` in a new folder under `~/.config/amadeus/themes/`. Copy a shipped theme as the starting point; only background, foreground,
  accent and the six base colours are required, the rest is derived. Then set it.
- **Theme an application the system does not cover:** add a template to
  `~/.config/amadeus/themed/`, using the same `{{ name }}`, `{{ name_strip }}` (no `#`) and
  `{{ name_rgb }}` placeholders as the shipped templates, then point that
  application's configuration at the rendered file. Set the theme again to render it.
- **Change one colour everywhere:** change it in the theme file and set the theme
  again. Do not edit a rendered file: the next theme change replaces it.

## Pitfalls

- Open terminals are recoloured in place. A program that set its own colours inside a
  terminal (an editor's colour scheme, for example) keeps them: that is the program's
  setting, not the terminal's.
- A configuration file the user already owns is not overwritten. If an application
  ignores the theme, check whether its configuration includes the rendered file.
- Never write colours into shipped files, the shell source or the compositor defaults.
- Check contrast when making a light theme: the accent must stay readable on the
  background and under dark text.
