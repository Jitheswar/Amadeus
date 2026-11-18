# Making a Bar Plugin

A bar plugin is a folder `~/.config/amadeus/plugins/<username>.<name>/` (its id, e.g. `alice.counter`) with a manifest, the widget, and its strings:

```json
{
  "schemaVersion": 1,
  "id": "alice.counter",
  "name": "Counter",
  "version": "1.0.0",
  "author": "alice",
  "description": "Counts clicks in the bar",
  "kinds": ["bar-widget"],
  "entryPoints": { "barWidget": "BarWidget.qml" },
  "barWidget": { "displayName": "Counter", "description": "Counts clicks in the bar", "category": "Tools", "allowMultiple": false, "defaultSection": "right" }
}
```

`BarWidget.qml` extends `BarWidget` and draws itself with `WidgetButton`, which gives it the bar's font, colors, hover, tooltip, and press feedback. Its `text` is the label (an icon-font glyph or words), `active: true` draws it in the urgent color, and `onPressed` gets the mouse button:

```qml
import QtQuick
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "alice.counter"
  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  property int count: 0

  Translations { id: strings; directory: Qt.resolvedUrl("i18n") }

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: String(root.count)
    tooltipText: strings.t("tooltip")
    onPressed: function(mouseButton) {
      if (mouseButton === Qt.RightButton) { root.count = 0 } else { root.count++ }
    }
  }
}
```

- Keep state in QML properties and drive time with a `Timer` that runs only while something is counting; an idle widget starts no timers or processes. Don't name a property after one every item already has (`state`, `visible`, `enabled`, `width`, `opacity`): `property int state` collides with the item's own `state`, and assigning to it fails.
- Run commands with `root.bar.run("amadeus-notification-send 'Counter' 'Reached 100'")`.
- Icons are Nerd Font glyphs written straight into the label text, as the built-in widgets do (`text: "󰐊"`). Find one by name in Nerd Fonts' table rather than by drawing the font, preferring the `md-` (Material Design) set the bar uses, then look at the widget to check it:

  ```bash
  curl -s https://raw.githubusercontent.com/ryanoasis/nerd-fonts/master/glyphnames.json \
    | jq -r 'to_entries[] | select(.key | test("^md-.*timer")) | "\(.key) \(.value.char)"'
  ```
- A card that opens on click is in [`plugin-popups.md`](plugin-popups.md).

Then check it, look at it, and put it on the bar. `amadeus agent look plugin <dir>` renders the widget in a bar strip with the current theme, without touching the running bar, and lists the QML errors it logged; open the image it prints and fix what looks wrong. Saving any file under the plugin folder reloads it on the bar:

```bash
amadeus plugin validate ~/.config/amadeus/plugins/alice.counter
amadeus agent look plugin ~/.config/amadeus/plugins/alice.counter
amadeus bar put alice.counter --section right
```
