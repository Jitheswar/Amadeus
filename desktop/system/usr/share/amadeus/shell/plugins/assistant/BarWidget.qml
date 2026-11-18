import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui

// The assistant in the bar: a click opens its panel, and while requests run the
// count shows beside the icon.
BarWidget {
  id: root
  moduleName: "amadeus.assistant"

  property int running: 0

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // The daemon writes what it is doing here; nothing is polled.
  FileView {
    path: (Quickshell.env("AMADEUS_RUN") || Quickshell.env("XDG_RUNTIME_DIR") + "/amadeus") + "/activity.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { try { root.running = Number(JSON.parse(text()).running) || 0 } catch (err) { root.running = 0 } }
    onLoadFailed: root.running = 0
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.running > 0 ? "󰚩 " + root.running : "󰚩"
    slotSize: Style.bar.statusSlot
    tooltipText: root.running > 0 ? root.running + " Amadeus request" + (root.running > 1 ? "s" : "") + " running" : "Amadeus"
    onPressed: Quickshell.execDetached(["ama", "panel"])
  }
}
