import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Bluetooth
import Quickshell.Services.UPower
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray

// What drops down from the bar: calendar, power, Wi-Fi, Bluetooth, volume, display,
// background applications, administrator access. One card, placed under what was clicked,
// opening and closing as one motion.
Scope {
    id: pop
    required property var shell
    readonly property bool open: shell.pop !== ""
    property string showing: ""                       // stays set while closing, so the card does not empty mid-fade
    property real t: open ? 1 : 0
    Behavior on t { NumberAnimation { duration: pop.open ? pop.shell.normal : pop.shell.fast; easing.type: Easing.OutCubic } }
    onOpenChanged: if (open) showing = shell.pop
    Connections { target: pop.shell; function onPopChanged() { if (pop.shell.pop !== "") pop.showing = pop.shell.pop } }

    component Title: Text { color: pop.shell.dim; font.family: pop.shell.font; font.pixelSize: 11; font.letterSpacing: 0.8; font.weight: Font.Medium }
    component Body: Text { color: pop.shell.fg; font.family: pop.shell.font; font.pixelSize: 13 }
    // A row you can click: optional icon, text, optional note on the right, a tick when chosen.
    component Choice: Rectangle {
        id: choice
        property string icon: ""
        property string text: ""
        property string note: ""
        property bool chosen: false
        signal picked()
        width: parent ? parent.width : 0; height: 36; radius: 8
        color: over.containsMouse ? pop.shell.raised : "transparent"
        Behavior on color { ColorAnimation { duration: pop.shell.fast } }
        Icon { id: glyph; visible: choice.icon !== ""; name: choice.icon; size: 16; color: choice.chosen ? pop.shell.accent : pop.shell.fg
               anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter } }
        Body { text: choice.text; elide: Text.ElideRight; color: choice.chosen ? pop.shell.accent : pop.shell.fg
               anchors { left: glyph.visible ? glyph.right : parent.left; right: side.left; leftMargin: 10; rightMargin: 8; verticalCenter: parent.verticalCenter } }
        Row { id: side; spacing: 8; anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            Body { text: choice.note; color: pop.shell.dim; font.pixelSize: 12 }
            Icon { visible: choice.chosen; name: "check"; size: 14; color: pop.shell.accent; anchors.verticalCenter: parent.verticalCenter } }
        MouseArea { id: over; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: choice.picked() }
    }
    // A small selectable value, used for text size and scale.
    component Pill: Rectangle {
        id: pill
        property string text: ""
        property bool chosen: false
        signal picked()
        width: Math.max(52, label.implicitWidth + 20); height: 28; radius: 14
        color: pill.chosen ? pop.shell.accent : (over.containsMouse ? pop.shell.raised : "transparent")
        border.width: 1; border.color: pill.chosen ? pop.shell.accent : pop.shell.line
        Behavior on color { ColorAnimation { duration: pop.shell.fast } }
        Body { id: label; anchors.centerIn: parent; text: pill.text; font.pixelSize: 12
               color: pill.chosen ? pop.shell.bg : pop.shell.fg }
        MouseArea { id: over; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pill.picked() }
    }
    // An on/off switch whose knob slides.
    component Switch: Rectangle {
        id: sw
        property bool on: false
        signal flipped()
        width: 38; height: 22; radius: 11
        color: on ? pop.shell.accent : pop.shell.line
        Behavior on color { ColorAnimation { duration: pop.shell.fast } }
        Rectangle { width: 16; height: 16; radius: 8; y: 3; x: sw.on ? 19 : 3; color: sw.on ? pop.shell.bg : pop.shell.fg
                    Behavior on x { NumberAnimation { duration: pop.shell.fast; easing.type: Easing.OutCubic } } }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: sw.flipped() }
    }
    component Slider: Item {
        id: sl
        property real value: 0
        signal moved(real v)
        width: parent ? parent.width : 0; height: 28
        Rectangle { id: track; height: 6; radius: 3; color: pop.shell.line; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
            Rectangle { height: parent.height; radius: 3; color: pop.shell.accent; width: parent.width * Math.max(0, Math.min(1, sl.value)) } }
        Rectangle { width: 16; height: 16; radius: 8; color: pop.shell.fg; y: 6; x: (sl.width - 16) * Math.max(0, Math.min(1, sl.value))
                    scale: drag.pressed ? 1.15 : 1; Behavior on scale { NumberAnimation { duration: 80 } } }
        MouseArea { id: drag; anchors.fill: parent
                    function set(mx) { sl.moved(Math.max(0, Math.min(1, (mx - 8) / (sl.width - 16)))) }
                    onPressed: mouse => set(mouse.x); onPositionChanged: mouse => { if (pressed) set(mouse.x) } }
    }

    Component { id: calendar
        Column { id: cal; width: 280; spacing: 10
            property date shown: new Date()
            readonly property date today: new Date()
            function shift(n) { shown = new Date(shown.getFullYear(), shown.getMonth() + n, 1) }
            Item { width: parent.width; height: 28
                Body { text: Qt.formatDate(cal.shown, "MMMM yyyy"); font.pixelSize: 15; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter; x: 4 }
                Row { anchors { right: parent.right; verticalCenter: parent.verticalCenter } spacing: 4
                    Repeater { model: [["left", -1], ["right", 1]]
                        Rectangle { required property var modelData; width: 28; height: 28; radius: 8; color: arrow.containsMouse ? pop.shell.raised : "transparent"
                            Icon { anchors.centerIn: parent; name: parent.modelData[0]; size: 16; color: pop.shell.fg }
                            MouseArea { id: arrow; anchors.fill: parent; hoverEnabled: true; onClicked: cal.shift(parent.modelData[1]) } } } } }
            Grid { columns: 7; width: parent.width
                Repeater { model: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
                    Title { required property string modelData; text: modelData; width: 40; height: 24; horizontalAlignment: Text.AlignHCenter } }
                Repeater { model: 42
                    Item { id: cell; required property int index; width: 40; height: 34
                        // Monday first: the grid starts on the Monday on or before the 1st.
                        readonly property date day: { const first = new Date(cal.shown.getFullYear(), cal.shown.getMonth(), 1)
                                                      return new Date(first.getFullYear(), first.getMonth(), 1 - ((first.getDay() + 6) % 7) + index) }
                        readonly property bool inMonth: day.getMonth() === cal.shown.getMonth()
                        readonly property bool isToday: day.toDateString() === cal.today.toDateString()
                        Rectangle { anchors.centerIn: parent; width: 30; height: 30; radius: 15; color: cell.isToday ? pop.shell.accent : "transparent" }
                        Body { anchors.centerIn: parent; text: cell.day.getDate(); font.features: { "tnum": 1 }
                               color: cell.isToday ? pop.shell.bg : (cell.inMonth ? pop.shell.fg : pop.shell.dim); opacity: cell.inMonth || cell.isToday ? 1 : 0.45
                               font.weight: cell.isToday ? Font.DemiBold : Font.Normal } } } }
        }
    }
    Component { id: power
        Column { width: 280; spacing: 4
            readonly property var dev: UPower.displayDevice
            Title { text: "POWER"; x: 10 }
            Body { x: 10; visible: pop.shell.hasBattery; color: pop.shell.dim; font.pixelSize: 12; bottomPadding: 6
                   text: pop.shell.batteryPct + "% · " + (UPower.onBattery ? "on battery" : "plugged in") }
            Choice { icon: "leaf"; text: "Battery saver"; chosen: PowerProfiles.profile === PowerProfile.PowerSaver; onPicked: PowerProfiles.profile = PowerProfile.PowerSaver }
            Choice { icon: "scale"; text: "Balanced"; chosen: PowerProfiles.profile === PowerProfile.Balanced; onPicked: PowerProfiles.profile = PowerProfile.Balanced }
            Choice { icon: "bolt"; text: "Performance"; visible: PowerProfiles.hasPerformanceProfile; chosen: PowerProfiles.profile === PowerProfile.Performance; onPicked: PowerProfiles.profile = PowerProfile.Performance }
            Body { x: 10; width: parent.width - 20; wrapMode: Text.Wrap; color: pop.shell.dim; font.pixelSize: 11; topPadding: 6; visible: pop.shell.hasBattery
                   text: "Chosen for you when power changes: performance when plugged in, balanced on battery, battery saver under 20%." }
        }
    }
    Component { id: volume
        Column { id: vol; width: 300; spacing: 6
            readonly property var sink: pop.shell.demo ? null : Pipewire.defaultAudioSink
            Item { width: parent.width; height: 24
                Title { text: "VOLUME"; x: 10; anchors.verticalCenter: parent.verticalCenter }
                Body { text: pop.shell.demo ? Math.round(pop.shell.vol * 100) + "%"
                                           : (vol.sink && vol.sink.audio ? Math.round(vol.sink.audio.volume * 100) + "%" : "")
                       color: pop.shell.dim; font.features: { "tnum": 1 }
                       anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter } } }
            Item { width: parent.width - 20; x: 10; height: 28
                Slider { value: pop.shell.demo ? pop.shell.vol : (vol.sink && vol.sink.audio ? vol.sink.audio.volume : 0)
                         onMoved: v => { if (!pop.shell.demo && vol.sink && vol.sink.audio) vol.sink.audio.volume = v } } }
            Choice { icon: "volume-off"; text: "Mute"
                     chosen: pop.shell.demo ? false : !!(vol.sink && vol.sink.audio && vol.sink.audio.muted)
                     onPicked: if (!pop.shell.demo && vol.sink && vol.sink.audio) vol.sink.audio.muted = !vol.sink.audio.muted }
            Title { text: "OUTPUT"; x: 10; topPadding: 4 }
            Repeater { model: pop.shell.outputs.slice(0, 6)
                Choice { required property var modelData; icon: "volume"
                         text: modelData.description || modelData.nickname || modelData.name
                         chosen: pop.shell.demo ? modelData.id === 1 : Pipewire.defaultAudioSink === modelData
                         onPicked: if (!pop.shell.demo) Pipewire.preferredDefaultAudioSink = modelData } }
            Body { x: 10; visible: pop.shell.outputs.length === 0; color: pop.shell.dim; font.pixelSize: 12; height: 24; verticalAlignment: Text.AlignVCenter
                   text: "No output devices" }
            Title { text: "INPUT"; x: 10; topPadding: 4 }
            Repeater { model: pop.shell.inputs.slice(0, 6)
                Choice { required property var modelData; icon: "mic"
                         text: modelData.description || modelData.nickname || modelData.name
                         chosen: pop.shell.demo ? modelData.id === 3 : Pipewire.defaultAudioSource === modelData
                         onPicked: if (!pop.shell.demo) Pipewire.preferredDefaultAudioSource = modelData } }
            Body { x: 10; visible: pop.shell.inputs.length === 0; color: pop.shell.dim; font.pixelSize: 12; height: 24; verticalAlignment: Text.AlignVCenter
                   text: "No input devices" }
        }
    }
    Component { id: display
        Column { id: disp; width: 300; spacing: 8
            Item { width: parent.width; height: 24
                Title { text: "BRIGHTNESS"; x: 10; anchors.verticalCenter: parent.verticalCenter; visible: pop.shell.hasBattery }
                Body { text: Math.round(pop.shell.bright * 100) + "%"; color: pop.shell.dim; font.features: { "tnum": 1 }; visible: pop.shell.hasBattery
                       anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter } } }
            Item { width: parent.width - 20; x: 10; height: 28; visible: pop.shell.hasBattery
                Slider { value: pop.shell.bright; onMoved: v => pop.shell.setBright(Math.max(0.02, v)) } }
            Title { text: "TEXT SIZE"; x: 10 }
            Row { x: 10; spacing: 6
                Repeater { model: [90, 100, 110, 125, 150]
                    Pill { required property int modelData; text: modelData + "%"; chosen: pop.shell.textSize === modelData
                           onPicked: pop.shell.setTextSize(modelData) } } }
            Title { text: "SCALE"; x: 10; topPadding: 4 }
            Row { x: 10; spacing: 6
                Repeater { model: [1, 1.25, 1.5, 1.75, 2]
                    Pill { required property real modelData; text: Math.round(modelData * 100) + "%"
                           chosen: Math.abs(pop.shell.scale - modelData) < 0.01
                           onPicked: pop.shell.setScale(modelData) } } }
            Choice { icon: "display"; text: "More display settings…"
                     onPicked: { pop.shell.pop = ""; pop.shell.run(["amadeus-display"]) } }
        }
    }
    Component { id: wifi
        Column { width: 300; spacing: 4
            Item { width: parent.width; height: 32
                Title { text: "WI-FI"; x: 10; anchors.verticalCenter: parent.verticalCenter }
                Switch { on: pop.shell.wifiOn; onFlipped: pop.shell.run(["amadeus-wifi", pop.shell.wifiOn ? "off" : "on"]); anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter } } }
            Repeater { model: pop.shell.wifiOn ? pop.shell.nets.slice(0, 8) : []
                Choice { required property var modelData; icon: "wifi"; text: modelData.name; note: (modelData.secure ? "" : "open  ") + modelData.signal + "%"; chosen: modelData.active
                         onPicked: { pop.shell.run(["amadeus-wifi", "connect", modelData.name]); pop.shell.pop = "" } } }
            Body { x: 10; visible: !pop.shell.wifiOn || pop.shell.nets.length === 0; color: pop.shell.dim; font.pixelSize: 12; height: 30; verticalAlignment: Text.AlignVCenter
                   text: pop.shell.wifiOn ? "Looking for networks…" : "Wi-Fi is off" }
        }
    }
    Component { id: bluetooth
        Column { id: bt; width: 300; spacing: 4
            readonly property var adapter: Bluetooth.defaultAdapter
            Item { width: parent.width; height: 32
                Title { text: "BLUETOOTH"; x: 10; anchors.verticalCenter: parent.verticalCenter }
                Switch { visible: !!bt.adapter; on: !!(bt.adapter && bt.adapter.enabled); onFlipped: bt.adapter.enabled = !bt.adapter.enabled
                         anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter } } }
            Repeater { model: bt.adapter && bt.adapter.enabled ? Bluetooth.devices : []
                Choice { required property var modelData; icon: "bluetooth"; text: modelData.name || modelData.address; chosen: modelData.connected
                         note: modelData.connected ? (modelData.batteryAvailable ? Math.round(modelData.battery * 100) + "%" : "connected") : (modelData.paired ? "" : "new")
                         onPicked: modelData.connected ? modelData.disconnect() : (modelData.paired ? modelData.connect() : modelData.pair()) } }
            Choice { visible: !!(bt.adapter && bt.adapter.enabled); text: bt.adapter && bt.adapter.discovering ? "Looking for devices…" : "Look for new devices"; onPicked: bt.adapter.discovering = !bt.adapter.discovering }
            Body { x: 10; visible: !bt.adapter || !bt.adapter.enabled; color: pop.shell.dim; font.pixelSize: 12; height: 30; verticalAlignment: Text.AlignVCenter
                   text: bt.adapter ? "Bluetooth is off" : "This computer has no Bluetooth" }
        }
    }
    Component { id: tray
        Column { width: 280; spacing: 4
            Title { text: "RUNNING IN THE BACKGROUND"; x: 10; height: 26; verticalAlignment: Text.AlignVCenter }
            Repeater { model: SystemTray.items
                Choice { required property var modelData; text: modelData.tooltipTitle || modelData.title || modelData.id; onPicked: { modelData.activate(); pop.shell.pop = "" } } }
            Body { x: 10; visible: SystemTray.items.values.length === 0; color: pop.shell.dim; font.pixelSize: 12; height: 30; verticalAlignment: Text.AlignVCenter; text: "Nothing right now" }
        }
    }
    Component { id: sudo
        Column { width: 300; spacing: 4
            Title { text: "ADMINISTRATOR WITHOUT PASSWORD"; x: 10; height: 26; verticalAlignment: Text.AlignVCenter }
            Body { x: 10; width: parent.width - 20; wrapMode: Text.Wrap; color: pop.shell.dim; font.pixelSize: 12; bottomPadding: 6
                   text: pop.shell.sudoOn ? "On " + pop.shell.sudoUntil + ". Anything running as you can change the system without asking."
                                          : "While on, anything running as you can change the system without asking. You are asked for your password once to turn it on." }
            Repeater { model: pop.shell.sudoOn ? [] : [["15 minutes", "15m"], ["30 minutes", "30m"], ["1 hour", "1h"], ["Until I turn it off", "always"]]
                Choice { required property var modelData; icon: "unlock"; text: modelData[0]; onPicked: { pop.shell.run(["amadeus-sudo", "on", modelData[1]]); pop.shell.pop = "" } } }
            Choice { visible: pop.shell.sudoOn; icon: "lock"; text: "Turn off now"; onPicked: { pop.shell.run(["amadeus-sudo", "off"]); pop.shell.pop = "" } }
        }
    }
    readonly property var panels: ({ calendar: calendar, power: power, volume: volume, display: display, wifi: wifi, bluetooth: bluetooth, tray: tray, sudo: sudo })

    PanelWindow {
        visible: pop.open || pop.t > 0.01
        anchors { top: true; left: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        implicitHeight: 520
        color: "transparent"
        MouseArea { anchors.fill: parent; onClicked: pop.shell.pop = "" }
        Rectangle {
            id: card
            x: Math.max(10, Math.min(parent.width - width - 10, pop.shell.popX - width / 2))
            y: 50 - (1 - pop.t) * 8
            width: content.item ? content.item.width + 24 : 0
            height: content.item ? content.item.height + 24 : 0
            radius: pop.shell.radius + 2
            color: pop.shell.surface
            border.color: pop.shell.line; border.width: 1
            opacity: pop.t
            scale: 0.97 + 0.03 * pop.t
            transformOrigin: Item.Top
            Behavior on x { enabled: pop.open && pop.t > 0.5; NumberAnimation { duration: pop.shell.normal; easing.type: Easing.OutCubic } }
            Behavior on height { enabled: pop.t > 0.5; NumberAnimation { duration: pop.shell.fast; easing.type: Easing.OutCubic } }
            MouseArea { anchors.fill: parent }
            Loader { id: content; x: 12; y: 12; sourceComponent: pop.panels[pop.showing] || null }
        }
    }
}
