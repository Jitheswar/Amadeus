import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io

// Hands the assistant the desktop events its scheduled tasks wait for: an application
// gaining focus and a network connection coming or going. Only events a task listens for
// are sent (the assistant lists them in automation-events.json), so an idle system sends nothing.
Item {
  id: root

  // Injected by the shell's service loader.
  property var shell: null

  property var wanted: []
  property var connections: []

  FileView {
    path: (Quickshell.env("AMADEUS_CONFIG") || Quickshell.env("HOME") + "/.config/amadeus") + "/automation-events.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { try { const e = JSON.parse(text()); root.wanted = Array.isArray(e) ? e : [] } catch (err) { root.wanted = [] } }
    onLoadFailed: root.wanted = []
  }

  function publish(event, data) {
    if (root.wanted.indexOf(event) < 0) return
    Quickshell.execDetached(["ama", "event", event, JSON.stringify(data)])
  }

  readonly property var focused: Hyprland.activeToplevel
  readonly property string focusedApp: focused ? (focused.wayland ? focused.wayland.appId : String((focused.lastIpcObject || {}).class || "")) : ""
  onFocusedAppChanged: if (focusedApp) publish("app-focused", { app: focusedApp, title: String(focused.title || "").slice(0, 250) })

  // NetworkManager says when something changed; the active connections are then read once.
  Process {
    running: root.wanted.indexOf("network-changed") >= 0
    command: ["nmcli", "monitor"]
    stdout: SplitParser { onRead: readConnections.running = true }
  }
  Process {
    id: readConnections
    command: ["nmcli", "-t", "--escape", "yes", "-f", "NAME,TYPE", "connection", "show", "--active"]
    stdout: StdioCollector {
      onStreamFinished: {
        const next = text.trim().split("\n").filter(l => l && !l.endsWith(":loopback")).map(l => l.slice(0, l.lastIndexOf(":")).replace(/\\([:\\])/g, "$1"))
        const changed = next.filter(n => root.connections.indexOf(n) < 0).concat(root.connections.filter(n => next.indexOf(n) < 0))
        root.connections = next
        for (const name of changed)
          root.publish("network-changed", { connection: name.slice(0, 100), connected: next.indexOf(name) >= 0, connections: next.slice(0, 8) })
      }
    }
  }
}
