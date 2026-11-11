import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Bluetooth
import Quickshell.Services.UPower
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray

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
        function state(): string { return JSON.stringify({ picker: picker.open, pickerItems: picker.items.length, notifications: notifications.count, popover: root.pop, awake: root.awake }) }
        // For automation and tests: open a drop-down at a horizontal position, or close it with "".
        function popover(name: string, x: int): void { root.popX = x; root.pop = name }
        function awake(on: bool): void { root.awake = on }
    }

    // ---- bar layout: ~/.config/amadeus/bar.json lists widget ids for left, center and right
    property var layout: ({ left: ["workspaces", "title"], center: ["sudo", "awake", "clock", "weather"],
                            right: ["gpu", "tray", "bluetooth", "network", "volume", "brightness", "battery", "power", "amadeus"] })
    FileView {
        path: Quickshell.env("HOME") + "/.config/amadeus/bar.json"
        watchChanges: true
        onFileChanged: reload()
        onLoaded: { try { const j = JSON.parse(text()); if (j.left && j.center && j.right) root.layout = j } catch (e) {} }
    }
    SystemClock { id: clock; precision: SystemClock.Minutes }
    function run(argv) { Quickshell.execDetached(argv) }

    // ---- what drops down from the bar
    property string pop: ""
    property real popX: 0
    function toggle(name, item) {
        if (pop === name) { pop = ""; return }
        popX = item.mapToItem(null, item.width / 2, 0).x
        pop = name
        if (name === "wifi") scan.running = true
        if (name === "brightness") readBright.running = true
    }
    Popover { shell: root }

    // ---- state behind the toggles. Everything here follows events; nothing is polled except the weather.
    readonly property bool demo: Quickshell.env("AMADEUS_DEMO") === "1"     // stand-in values for ./build.sh preview
    property bool awake: false
    readonly property var battery: UPower.displayDevice
    readonly property bool hasBattery: demo || !!(battery && battery.isLaptopBattery)
    readonly property int batteryPct: demo ? 82 : (battery ? Math.round(battery.percentage <= 1 ? battery.percentage * 100 : battery.percentage) : 0)
    readonly property bool lowBattery: hasBattery && UPower.onBattery && batteryPct < 20
    // Power follows the cable: performance when plugged in, balanced on battery, battery saver under 20%.
    // A choice made by hand in the menu holds until the cable or that threshold changes again.
    function autoProfile() {
        if (demo || !battery || !battery.isLaptopBattery) return
        PowerProfiles.profile = !UPower.onBattery ? (PowerProfiles.hasPerformanceProfile ? PowerProfile.Performance : PowerProfile.Balanced)
                              : (batteryPct < 20 ? PowerProfile.PowerSaver : PowerProfile.Balanced)
    }
    onLowBatteryChanged: autoProfile()
    Connections { target: UPower; function onOnBatteryChanged() { root.autoProfile() } }
    Timer { interval: 3000; running: true; onTriggered: root.autoProfile() }      // once, after the services have answered

    PwObjectTracker { objects: [Pipewire.defaultAudioSink] }
    readonly property var sink: Pipewire.defaultAudioSink
    readonly property real vol: demo ? 0.45 : (sink && sink.audio ? sink.audio.volume : 0)
    readonly property bool muted: !demo && !!(sink && sink.audio && sink.audio.muted)

    property real bright: 0.7
    Process { id: readBright; command: ["brightnessctl", "-m"]
              stdout: SplitParser { onRead: line => { const f = line.split(","); if (f.length > 3) root.bright = parseInt(f[3]) / 100 } } }
    function setBright(v) { bright = v; run(["brightnessctl", "-q", "set", Math.round(v * 100) + "%"]) }

    property bool wifiOn: demo
    property var nets: demo ? [{ name: "Home", signal: 82, secure: true, active: true }] : []
    readonly property var activeNet: nets.find(n => n.active) || null
    Process { id: scan; command: ["sh", "-c", "amadeus-wifi state; amadeus-wifi list"]
              property var found: []
              stdout: SplitParser { onRead: line => {
                  if (line === "enabled" || line === "disabled") { root.wifiOn = line === "enabled"; scan.found = []; return }
                  const f = line.split(":"); if (f.length >= 4) scan.found.push({ active: f[0] === "*", name: f.slice(1, f.length - 2).join(":"), signal: parseInt(f[f.length - 2]) || 0, secure: f[f.length - 1] !== "" && f[f.length - 1] !== "--" }) } }
              onExited: if (!root.demo) root.nets = scan.found.slice().sort((a, b) => (b.active - a.active) || (b.signal - a.signal)) }
    // NetworkManager says when something changed; only then is the list read again.
    Process { command: ["nmcli", "monitor"]; running: !root.demo; stdout: SplitParser { onRead: line => rescan.restart() } }
    Timer { id: rescan; interval: 800; onTriggered: scan.running = true }
    Component.onCompleted: if (!demo) { scan.running = true; readBright.running = true }

    property string sudoRaw: ""
    readonly property bool sudoOn: sudoRaw !== ""
    readonly property string sudoUntil: sudoRaw === "always" ? "until you turn it off" : "until " + Qt.formatDateTime(new Date(Number(sudoRaw) * 1000), "h:mm AP")
    FileView { path: "/run/amadeus-sudo"; watchChanges: true; onFileChanged: reload()
               onLoaded: root.sudoRaw = text().trim(); onLoadFailed: root.sudoRaw = "" }

    property string weather: demo ? "18°|Partly cloudy" : ""
    Process { id: sky; command: ["curl", "-fsS", "-m", "10", "https://wttr.in/?format=%t|%C"]
              stdout: SplitParser { onRead: line => { if (line.indexOf("|") > 0 && line.length < 60) root.weather = line.replace("+", "").replace("C|", "|").replace("F|", "|") } } }
    Timer { interval: 1800000; running: !root.demo && root.layout.center.concat(root.layout.left, root.layout.right).indexOf("weather") >= 0
            repeat: true; triggeredOnStart: true; onTriggered: sky.running = true }

    // The NVIDIA card's power state and whether a cable network is up: two sysfs reads when the network changes.
    property bool gpuOn: false
    property bool wired: false
    Process { id: hw; command: ["sh", "-c", "for d in /sys/bus/pci/devices/*; do [ \"$(cat $d/vendor)\" = 0x10de ] && case $(cat $d/class) in 0x03*) cat $d/power/runtime_status;; esac; done; nmcli -t -f TYPE,STATE device | grep -q '^ethernet:connected' && echo wired"]
              property var seen: []
              stdout: SplitParser { onRead: line => hw.seen.push(line) }
              onExited: { root.gpuOn = hw.seen.indexOf("active") >= 0; root.wired = hw.seen.indexOf("wired") >= 0; hw.seen = [] } }
    Timer { interval: 30000; running: !root.demo; repeat: true; triggeredOnStart: true; onTriggered: hw.running = true }

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
    // A control in the bar: an icon, sometimes a short reading beside it. Lit when its thing is on,
    // raised while pointed at or while its panel is open.
    component Tool: Item {
        id: tool
        property string icon: ""
        property string reading: ""
        property string panel: ""           // the drop-down this opens, if any
        property bool lit: false
        property bool alert: false
        property bool shown: true
        signal act()
        implicitWidth: inner.implicitWidth + 16; implicitHeight: 28
        Rectangle { anchors.fill: parent; radius: 8
                    color: over.containsMouse || (tool.panel !== "" && root.pop === tool.panel) ? root.raised : "transparent"
                    Behavior on color { ColorAnimation { duration: root.fast } } }
        Row { id: inner; anchors.centerIn: parent; spacing: 6
            Icon { name: tool.icon; size: 16; anchors.verticalCenter: parent.verticalCenter
                   color: tool.alert ? root.warn : (tool.lit ? root.accent : root.fg) }
            Label { visible: tool.reading !== ""; text: tool.reading; font.pixelSize: 12; font.features: { "tnum": 1 }
                    color: tool.alert ? root.warn : root.fg; anchors.verticalCenter: parent.verticalCenter } }
        scale: over.pressed ? 0.94 : 1
        Behavior on scale { NumberAnimation { duration: 80 } }
        MouseArea { id: over; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: tool.panel !== "" ? root.toggle(tool.panel, tool) : tool.act() }
    }

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
                    MouseArea { id: hit; anchors.fill: parent; anchors.margins: -8; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: root.run(["niri", "msg", "action", "focus-workspace", String(dot.modelData.idx)]) }
                }
            }
        }
    }
    Component { id: wTitle
        Label { id: title; color: root.dim; elide: Text.ElideRight; width: Math.min(implicitWidth, 380)
            property string want: root.focusedTitle
            // Cross-fade when the focused window changes.
            onWantChanged: swap.restart()
            SequentialAnimation { id: swap
                NumberAnimation { target: title; property: "opacity"; to: 0; duration: 70 }
                ScriptAction { script: title.text = title.want }
                NumberAnimation { target: title; property: "opacity"; to: 1; duration: root.fast } }
            Component.onCompleted: text = want } }
    Component { id: wSudo; Tool { icon: root.sudoOn ? "unlock" : "lock"; lit: root.sudoOn; panel: "sudo"; opacity: root.sudoOn ? 1 : 0.6 } }
    Component { id: wAwake; Tool { icon: "coffee"; lit: root.awake; opacity: root.awake ? 1 : 0.6; onAct: root.awake = !root.awake } }
    Component { id: wClock
        Item { id: time; implicitWidth: face.implicitWidth + 20; implicitHeight: 28
            Rectangle { anchors.fill: parent; radius: 8; color: tap.containsMouse || root.pop === "calendar" ? root.raised : "transparent"
                        Behavior on color { ColorAnimation { duration: root.fast } } }
            Row { id: face; anchors.centerIn: parent; spacing: 9
                Label { text: Qt.formatDateTime(clock.date, "ddd d MMM"); color: root.dim }
                Label { text: Qt.formatDateTime(clock.date, "h:mm AP"); font.weight: Font.DemiBold; font.features: { "tnum": 1 } } }
            MouseArea { id: tap; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.toggle("calendar", time) } } }
    Component { id: wWeather
        Row { property bool shown: root.weather !== ""; spacing: 6
            readonly property var parts: root.weather.split("|")
            Icon { size: 16; color: root.dim; anchors.verticalCenter: parent.verticalCenter
                   name: /rain|drizzle|shower|thunder/i.test(parent.parts[1] || "") ? "rain" : (/sun|clear/i.test(parent.parts[1] || "") ? "sun" : "cloud") }
            Label { text: (parent.parts[0] || "").trim(); color: root.dim; font.features: { "tnum": 1 } } } }
    Component { id: wGpu; Tool { shown: root.gpuOn; icon: "bolt"; reading: "NVIDIA"; alert: true } }
    Component { id: wTray; Tool { shown: SystemTray.items.values.length > 0; icon: "layers"; reading: String(SystemTray.items.values.length); panel: "tray" } }
    Component { id: wBluetooth
        Tool { readonly property var a: Bluetooth.defaultAdapter
               shown: root.demo || !!a; icon: root.demo || (a && a.enabled) ? "bluetooth" : "bluetooth-off"; panel: "bluetooth"
               lit: !!(a && a.enabled && Bluetooth.devices.values.some(d => d.connected)); opacity: root.demo || (a && a.enabled) ? 1 : 0.6 } }
    Component { id: wNetwork
        Tool { icon: root.wifiOn && root.activeNet ? "wifi" : "wifi-off"; panel: "wifi"; alert: !root.activeNet && !root.wired
               reading: root.activeNet ? "" : (root.wired ? "" : "") } }
    Component { id: wVolume
        Tool { icon: root.muted ? "volume-off" : (root.vol < 0.4 ? "volume-low" : "volume"); panel: "volume"; opacity: root.muted ? 0.6 : 1 } }
    Component { id: wBrightness; Tool { shown: root.hasBattery; icon: "sun"; panel: "brightness" } }
    Component { id: wBattery
        Tool { shown: root.hasBattery; icon: !root.demo && !UPower.onBattery ? "bolt" : "battery"; reading: root.batteryPct + "%"; panel: "power"; alert: root.lowBattery } }
    Component { id: wPower; Tool { shown: !root.hasBattery; icon: "power"; panel: "power" } }
    Component { id: wAmadeus
        Rectangle { id: chip; width: row.implicitWidth + 20; height: 26; radius: 13
            color: over.containsMouse ? root.accent : "transparent"; border.color: root.accent; border.width: 1
            scale: over.pressed ? 0.96 : 1
            Behavior on color { ColorAnimation { duration: root.fast } }
            Behavior on scale { NumberAnimation { duration: 80 } }
            Row { id: row; anchors.centerIn: parent; spacing: 7
                Rectangle { width: 6; height: 6; radius: 3; anchors.verticalCenter: parent.verticalCenter; color: over.containsMouse ? root.bg : root.accent }
                Label { text: "Amadeus"; font.weight: Font.Medium; color: over.containsMouse ? root.bg : root.accent } }
            MouseArea { id: over; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.run(["ama", "panel"]) } } }
    readonly property var widgets: ({ workspaces: wWorkspaces, title: wTitle, sudo: wSudo, awake: wAwake, clock: wClock, weather: wWeather, gpu: wGpu,
                                      tray: wTray, bluetooth: wBluetooth, network: wNetwork, volume: wVolume, brightness: wBrightness,
                                      battery: wBattery, power: wPower, amadeus: wAmadeus })

    component Section: Row {
        property var ids: []
        spacing: 4
        Repeater { model: parent.ids
            Loader { required property string modelData; sourceComponent: root.widgets[modelData] || null
                     visible: !!item && item.shown !== false; anchors.verticalCenter: parent ? parent.verticalCenter : undefined } }
    }

    Variants {
        model: Quickshell.screens
        // A floating bar: it sits a few pixels in from the screen edges, like the windows below it.
        PanelWindow {
            id: barWindow
            required property var modelData
            screen: modelData
            anchors { top: true; left: true; right: true }
            implicitHeight: 46
            color: "transparent"
            // Stay awake: while on, the screen does not dim, lock or sleep by itself.
            IdleInhibitor { window: barWindow; enabled: root.awake }
            Rectangle {
                anchors { fill: parent; topMargin: 8; leftMargin: 10; rightMargin: 10 }
                radius: root.radius
                color: Qt.rgba(root.surface.r, root.surface.g, root.surface.b, 0.94)
                border.color: root.line; border.width: 1
                Section { ids: root.layout.left; spacing: 14; anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter } }
                Section { ids: root.layout.center; anchors.centerIn: parent }
                Section { ids: root.layout.right; anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter } }
            }
        }
    }
}
