import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland

// The Amadeus OS bar. Its layout is data: ~/.config/amadeus/bar.json lists widget ids
// for left, center and right, and the bar rebuilds when that file changes, so both
// the user and Amadeus can rearrange it without touching code.
ShellRoot {
    id: root
    readonly property color bg: "#142620"
    readonly property color fg: "#d8e6df"
    readonly property color accent: "#8bcbb1"
    readonly property color dim: "#7f9a8f"
    readonly property color warn: "#e0af68"
    property var layout: ({ left: ["workspaces", "title"], center: ["clock"], right: ["gpu", "network", "volume", "battery", "amadeus"] })
    property var status: ({ battery: "", charging: false, net: "", volume: "", gpu: "" })

    function loadLayout(text) {
        try { const j = JSON.parse(text); if (j.left && j.center && j.right) root.layout = j } catch (e) {}
    }
    FileView {
        path: Quickshell.env("HOME") + "/.config/amadeus/bar.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: root.loadLayout(text())
    }
    Process {
        id: poll
        command: ["amadeus-bar-status"]
        stdout: SplitParser { onRead: line => { try { root.status = JSON.parse(line) } catch (e) {} } }
    }
    Timer { interval: 5000; running: true; repeat: true; triggeredOnStart: true; onTriggered: poll.running = true }
    SystemClock { id: clock; precision: SystemClock.Minutes }

    component Label: Text { color: root.fg; font.pixelSize: 13; font.family: "sans-serif"; verticalAlignment: Text.AlignVCenter }
    component Click: MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; property string run: ""; onClicked: Quickshell.execDetached(["sh", "-c", run]) }

    Component { id: wWorkspaces
        Row { spacing: 4
            Repeater {
                model: Hyprland.workspaces
                Rectangle {
                    required property var modelData
                    readonly property bool active: Hyprland.focusedWorkspace && Hyprland.focusedWorkspace.id === modelData.id
                    visible: modelData.id > 0
                    width: 26; height: 20; radius: 5
                    color: active ? root.accent : "transparent"
                    Label { anchors.centerIn: parent; text: modelData.name; color: parent.active ? root.bg : root.fg }
                    Click { run: "hyprctl dispatch 'hl.dsp.focus({ workspace = \"" + modelData.id + "\" })'" }
                }
            }
        }
    }
    Component { id: wTitle; Label { text: Hyprland.activeToplevel ? Hyprland.activeToplevel.title : ""; color: root.dim; elide: Text.ElideRight; width: Math.min(implicitWidth, 420) } }
    Component { id: wClock; Label { text: Qt.formatDateTime(clock.date, "ddd d MMM   HH:mm") } }
    Component { id: wGpu; Label { visible: root.status.gpu === "active"; text: "NVIDIA on"; color: root.warn } }
    Component { id: wNetwork; Label { text: root.status.net ? root.status.net.split(":").slice(1).join(":") : "offline"; color: root.status.net ? root.fg : root.warn; Click { run: "foot -e nmtui" } } }
    Component { id: wVolume; Label { text: root.status.volume === "" ? "" : (root.status.volume === "muted" ? "muted" : "vol " + root.status.volume + "%"); Click { run: "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle" } } }
    Component { id: wBattery; Label { visible: root.status.battery !== ""; text: (root.status.charging ? "+" : "") + root.status.battery + "%"; color: !root.status.charging && Number(root.status.battery) < 20 ? root.warn : root.fg } }
    Component { id: wAmadeus
        Rectangle { width: lbl.implicitWidth + 18; height: 20; radius: 5; color: root.accent
            Label { id: lbl; anchors.centerIn: parent; text: "Amadeus"; color: root.bg }
            Click { run: "ama palette" } } }
    readonly property var widgets: ({ workspaces: wWorkspaces, title: wTitle, clock: wClock, gpu: wGpu, network: wNetwork, volume: wVolume, battery: wBattery, amadeus: wAmadeus })

    component Section: Row {
        property var ids: []
        spacing: 14
        Repeater { model: parent.ids
            Loader { required property string modelData; sourceComponent: root.widgets[modelData] || null; anchors.verticalCenter: parent ? parent.verticalCenter : undefined } }
    }

    Variants {
        model: Quickshell.screens
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; left: true; right: true }
            implicitHeight: 30
            color: root.bg
            Section { ids: root.layout.left; anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter } }
            Section { ids: root.layout.center; anchors.centerIn: parent }
            Section { ids: root.layout.right; anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter } }
        }
    }
}
