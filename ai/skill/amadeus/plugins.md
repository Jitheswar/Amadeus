# Amadeus Shell: Bar, Plugins, and Idle

Read this before changing the status bar, notifications, shell plugins,
widgets, or idle/lock behavior.

The bar, notification daemon, settings panel, and assorted overlays all run
inside a single long-running Quickshell process (`amadeus-shell`).

```
~/.config/amadeus/shell.json             # User overrides: bar, plugins, idle
~/.config/amadeus/plugins/<plugin-id>/   # User-owned shell plugins
$AMADEUS_PATH/config/amadeus/shell.json  # Canonical defaults
```

The shell hot-reloads `shell.json` on save — no restart needed for layout
changes. `idle.screensaver` and `idle.lock` are seconds since user idle began.

**Commands:** `amadeus restart shell`, `amadeus refresh shell`

## Plugin UI Safety

Plugins run inside Amadeus's long-lived, unsandboxed shell. Treat text from network responses, files, IPC, settings, environment variables, and command output as untrusted.

- QML `Text` defaults to `Text.AutoText`. Do not bind untrusted data to an AutoText sink: markup-shaped input such as `<img src="https://example.invalid/tracker">` can be interpreted as rich text and load a resource.
- For display text owned by the plugin, set `textFormat: Text.PlainText`. Prefer a local `PlainText` component when the plugin has multiple text elements.

```qml
Text {
  textFormat: Text.PlainText
  text: modelData.name
}
```

- When passing dynamic text to an Amadeus-owned component whose internal `Text` format the plugin cannot set, neutralize markup in the plugin first with a helper of its own, and add a regression test; Amadeus ships no such helper. Never edit the packaged component to add a plain-text option: that belongs in a pull request to Amadeus.
- Bound and validate downloaded data before displaying or saving it: limit response and collection sizes, string lengths, identifiers, and timestamps.
- Keep network access explicit. Use fixed HTTPS sources, timeouts, response-size limits, and validation. For periodic background refreshes, disclose the behavior and let users enable or disable it. Never execute downloaded content or interpolate untrusted values into shell commands.
- Add regression coverage for markup-shaped input and every shared tooltip or notification sink that receives dynamic text.

## Plugin Motion

Motion in a plugin should feel like the rest of the shell. Most of it comes free from Amadeus's kit in `qs.Ui`: a `KeyboardPanel` grows out of its bar icon and fades, morphs into a neighbouring panel in the same bar section, and grows to fit content that arrives late; a `PopupCard` grows and fades; a `Button` gives a little when pressed. Build on those rather than animating your own open and close.

For anything the plugin animates itself, `import qs.Commons` and:

- Give every duration as `Style.duration(ms)`, never a bare number. It returns 0 when the user has turned animations off with `amadeus toggle animations`.
- Ease movement and entrances with `Style.easeOut` (`easing.type: Easing.Bezier; easing.bezierCurve: Style.easeOut`) or `Easing.OutCubic`. Never an ease-in curve, no bounce, and linear only for constant motion such as a spinner.
- Keep it under 300ms, with exits shorter than entrances: about 180ms in, 120ms out.
- Never scale from 0; start at 0.95–0.97 with opacity 0.
- Don't animate what a single keystroke opens or dismisses many times a day; it should just appear or go.
- Animate only for a reason: showing where something came from or went, confirming an input, or keeping a change from jumping.

```qml
import QtQuick
import qs.Commons

Item {
  property bool shown: false
  opacity: shown ? 1 : 0
  scale: shown ? 1 : 0.97
  Behavior on opacity { NumberAnimation { duration: Style.duration(180); easing.type: Easing.OutCubic } }
  Behavior on scale {
    NumberAnimation { duration: Style.duration(180); easing.type: Easing.Bezier; easing.bezierCurve: Style.easeOut }
  }
}
```

The bar layout, built-in widgets and idle behaviour are in [`bar.md`](bar.md); translating a
plugin is in [`translations.md`](translations.md).
