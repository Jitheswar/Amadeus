import QtQuick
import Quickshell
import Quickshell.Io

// The Amadeus OS shell: background, bar, picker (applications, menus, packages) and notifications.
// Colours, fonts and timings come from one theme file; the bar's layout from another.
// Both are data that the user or Amadeus can change, and both apply the moment they are saved.
ShellRoot {
    id: root

    // ---- theme: /usr/share/amadeus-os/theme.json, overridden by ~/.config/amadeus/theme.json
    property var theme: ({ bg: "#0f0e0d", surface: "#191715", raised: "#26221e", line: "#342f29", fg: "#f1ebe1", dim: "#9c948a",
                           accent: "#ffa14a", accent2: "#ff6f3c", good: "#8fd19e", warn: "#f4c35b", bad: "#ff6b5e",
                           font: "Inter", mono: "JetBrains Mono", radius: 12, fast: 110, normal: 180, slow: 260 })
    property var shipped: ({})
    property var personal: ({})
    function retheme() { theme = Object.assign({}, theme, shipped, personal) }
    FileView { path: "/usr/share/amadeus-os/theme.json"; watchChanges: true; onFileChanged: reload()
               onLoaded: { try { root.shipped = JSON.parse(text()) } catch (e) {} root.retheme() } }
    FileView { path: Quickshell.env("HOME") + "/.config/amadeus/theme.json"; watchChanges: true; onFileChanged: reload()
               onLoaded: { try { root.personal = JSON.parse(text()) } catch (e) { root.personal = ({}) } root.retheme() }
               onLoadFailed: { root.personal = ({}); root.retheme() } }
    readonly property color bg: theme.bg
    readonly property color surface: theme.surface
    readonly property color raised: theme.raised
    readonly property color line: theme.line
    readonly property color fg: theme.fg
    readonly property color dim: theme.dim
    readonly property color accent: theme.accent
    readonly property color accent2: theme.accent2
    readonly property color warn: theme.warn
    readonly property string font: theme.font
    readonly property string mono: theme.mono
    readonly property int radius: theme.radius
    readonly property int fast: theme.fast
    readonly property int normal: theme.normal
    readonly property int slow: theme.slow

    Background { style: root }
    Picker { id: picker; style: root }
    Notifications { id: notifications; style: root }
    IpcHandler {
        target: "pick"
        function start(prompt: string, infile: string, pipe: string, options: string): void { picker.start(prompt, infile, pipe, options) }
        // For automation and tests: choose a line by its text, or close.
        function choose(line: string): void { if (picker.open) picker.finish("ok", [line]) }
        function cancel(): void { if (picker.open) picker.finish("cancel", []) }
    }
    IpcHandler {
        target: "shell"
        function state(): string { return JSON.stringify({ picker: picker.open, pickerItems: picker.items.length, notifications: notifications.count }) }
    }

    // ---- bar layout: ~/.config/amadeus/bar.json lists widget ids for left, center and right
    property var layout: ({ left: ["workspaces", "title"], center: ["clock"], right: ["gpu", "network", "volume", "battery", "amadeus"] })
    property var status: ({ battery: "", charging: false, net: "", volume: "", gpu: "" })
    FileView {
        path: Quickshell.env("HOME") + "/.config/amadeus/bar.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: { try { const j = JSON.parse(text()); if (j.left && j.center && j.right) root.layout = j } catch (e) {} }
    }
    Process {
        id: poll
        command: ["amadeus-bar-status"]
        stdout: SplitParser { onRead: line => { try { root.status = JSON.parse(line) } catch (e) {} } }
    }
    Timer { interval: 5000; running: true; repeat: true; triggeredOnStart: true; onTriggered: poll.running = true }
    SystemClock { id: clock; precision: SystemClock.Minutes }

    // ---- compositor state, kept current from niri's event stream
    property var workspaces: []
    property var windows: ({})
    property var focusedId: null
    readonly property string focusedTitle: focusedId !== null && windows[focusedId] ? (windows[focusedId].title || "") : ""
    function onEvent(e) {
        if (e.WorkspacesChanged) root.workspaces = e.WorkspacesChanged.workspaces.slice().sort((a, b) => a.idx - b.idx)
        else if (e.WorkspaceActivated) {
            const id = e.WorkspaceActivated.id
            const hit = root.workspaces.find(w => w.id === id)
            if (hit) root.workspaces = root.workspaces.map(w => w.output !== hit.output ? w
                : Object.assign({}, w, { is_active: w.id === id, is_focused: e.WorkspaceActivated.focused ? w.id === id : w.is_focused }))
        }
        else if (e.WindowsChanged) {
            const m = {}; let f = null
            for (const w of e.WindowsChanged.windows) { m[w.id] = w; if (w.is_focused) f = w.id }
            root.windows = m; root.focusedId = f
        }
        else if (e.WindowOpenedOrChanged) {
            const w = e.WindowOpenedOrChanged.window, m = Object.assign({}, root.windows)
            m[w.id] = w; root.windows = m
            if (w.is_focused) root.focusedId = w.id
        }
        else if (e.WindowClosed) {
            const m = Object.assign({}, root.windows); delete m[e.WindowClosed.id]; root.windows = m
            if (root.focusedId === e.WindowClosed.id) root.focusedId = null
        }
        else if (e.WindowFocusChanged) root.focusedId = e.WindowFocusChanged.id
    }
    Process {
        id: events
        command: ["niri", "msg", "--json", "event-stream"]
        running: true
        stdout: SplitParser { onRead: line => { try { root.onEvent(JSON.parse(line)) } catch (e) {} } }
        onExited: restart.start()
    }
    Timer { id: restart; interval: 2000; onTriggered: events.running = true }

    // ---- bar widgets
    component Label: Text { color: root.fg; font.pixelSize: 13; font.family: root.font; verticalAlignment: Text.AlignVCenter
                            Behavior on color { ColorAnimation { duration: root.fast } } }
    component Click: MouseArea { anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                 property string run: ""; onClicked: Quickshell.execDetached(["sh", "-c", run]) }

    Component { id: wWorkspaces
        Row { spacing: 6
            Repeater {
                model: root.workspaces
                // The active workspace is a wide lit pill; the others are small dots that grow when pointed at.
                Rectangle {
                    id: dot
                    required property var modelData
                    readonly property bool active: modelData.is_active
                    anchors.verticalCenter: parent.verticalCenter
                    width: active ? 26 : (hit.containsMouse ? 14 : 8); height: 8; radius: 4
                    color: active ? root.accent : (hit.containsMouse ? root.fg : root.dim)
                    opacity: active ? 1 : 0.55
                    Behavior on width { NumberAnimation { duration: root.normal; easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: root.fast } }
                    Behavior on opacity { NumberAnimation { duration: root.fast } }
                    Click { id: hit; anchors.margins: -8; run: "niri msg action focus-workspace " + dot.modelData.idx }
                }
            }
        }
    }
    Component { id: wTitle
        Label { id: title; color: root.dim; elide: Text.ElideRight; width: Math.min(implicitWidth, 420)
            property string want: root.focusedTitle
            // Cross-fade when the focused window changes.
            onWantChanged: swap.restart()
            SequentialAnimation { id: swap
                NumberAnimation { target: title; property: "opacity"; to: 0; duration: 70 }
                ScriptAction { script: title.text = title.want }
                NumberAnimation { target: title; property: "opacity"; to: 1; duration: root.fast } }
            Component.onCompleted: text = want } }
    Component { id: wClock
        Row { spacing: 10
            Label { text: Qt.formatDateTime(clock.date, "HH:mm"); font.weight: Font.DemiBold; font.features: { "tnum": 1 } }
            Label { text: Qt.formatDateTime(clock.date, "ddd d MMM"); color: root.dim } } }
    // A status reading: a small caption saying what it is, then the value.
    component Reading: Item {
        id: reading
        property string caption: ""
        property string value: ""
        property bool alert: false
        property string run: ""
        visible: value !== ""
        implicitWidth: pair.implicitWidth; implicitHeight: pair.implicitHeight
        Row { id: pair; spacing: 6
            Label { text: reading.caption; color: root.dim; opacity: 0.7; font.pixelSize: 10; font.letterSpacing: 0.8; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
            Label { text: reading.value; color: reading.alert ? root.warn : root.fg; font.features: { "tnum": 1 } } }
        Click { enabled: reading.run !== ""; run: reading.run }
    }
    Component { id: wGpu; Reading { caption: "GPU"; value: root.status.gpu === "active" ? "NVIDIA on" : ""; alert: true } }
    Component { id: wNetwork; Reading { caption: "NET"; value: root.status.net ? root.status.net.split(":").slice(1).join(":") : "Offline"; alert: !root.status.net; run: "foot -e nmtui" } }
    Component { id: wVolume; Reading { caption: "VOL"; value: root.status.volume === "" ? "" : (root.status.volume === "muted" ? "Muted" : root.status.volume + "%")
                                       run: "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle" } }
    Component { id: wBattery; Reading { caption: "BAT"; value: root.status.battery === "" ? "" : (root.status.charging ? "+" : "") + root.status.battery + "%"
                                        alert: !root.status.charging && root.status.battery !== "" && Number(root.status.battery) < 20 } }
    Component { id: wAmadeus
        Rectangle { id: chip; width: row.implicitWidth + 20; height: 24; radius: 12
            color: over.containsMouse ? root.accent : "transparent"; border.color: root.accent; border.width: 1
            scale: over.pressed ? 0.96 : 1
            Behavior on color { ColorAnimation { duration: root.fast } }
            Behavior on scale { NumberAnimation { duration: 80 } }
            Row { id: row; anchors.centerIn: parent; spacing: 7
                Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: over.containsMouse ? root.bg : root.accent }
                Label { text: "Amadeus"; font.weight: Font.Medium; color: over.containsMouse ? root.bg : root.accent } }
            Click { id: over; run: "ama panel" } } }
    readonly property var widgets: ({ workspaces: wWorkspaces, title: wTitle, clock: wClock, gpu: wGpu, network: wNetwork, volume: wVolume, battery: wBattery, amadeus: wAmadeus })

    component Section: Row {
        property var ids: []
        spacing: 16
        Repeater { model: parent.ids
            Loader { required property string modelData; sourceComponent: root.widgets[modelData] || null; anchors.verticalCenter: parent ? parent.verticalCenter : undefined } }
    }

    Variants {
        model: Quickshell.screens
        // A floating bar: it sits a few pixels in from the screen edges, like the windows below it.
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; left: true; right: true }
            implicitHeight: 46
            color: "transparent"
            Rectangle {
                anchors { fill: parent; topMargin: 8; leftMargin: 10; rightMargin: 10 }
                radius: root.radius
                color: Qt.rgba(root.surface.r, root.surface.g, root.surface.b, 0.94)
                border.color: root.line; border.width: 1
                Section { ids: root.layout.left; anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter } }
                Section { ids: root.layout.center; anchors.centerIn: parent }
                Section { ids: root.layout.right; anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter } }
            }
        }
    }
}
