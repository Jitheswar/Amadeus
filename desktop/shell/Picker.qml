import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland

// One searchable list for the whole system: applications, menus, packages.
// A caller (amadeus-pick) hands over a file of lines and a pipe for the answer.
// Options: several choices at once, a details pane fed by a command, free text.
Scope {
    id: pick
    required property var style
    property bool open: false
    property string prompt: ""
    property string pipe: ""
    property string preview: ""       // shell command; the highlighted line is "$1"
    property string preview2: ""      // alternative details, toggled with Alt+B
    property string hint: ""
    property bool multi: false
    property bool allowNew: false
    property bool alt: false
    property var items: []
    property var shown: []
    property var marked: ({})
    property int index: 0
    property string detail: ""
    readonly property string current: shown.length ? shown[index] : ""
    // 0 when closed, 1 when open; everything on screen follows it, so opening and closing are one motion.
    property real t: open ? 1 : 0
    Behavior on t { NumberAnimation { duration: pick.open ? pick.style.normal : pick.style.fast; easing.type: Easing.OutCubic } }
    readonly property int nMarked: Object.keys(marked).length

    function label(line) { const t = line.indexOf("\t"); return t < 0 ? line : line.slice(0, t) }
    function start(prompt, infile, pipe, options) {
        if (open) finish("cancel", [])
        let o = {}
        try { o = JSON.parse(options) } catch (e) {}
        pick.prompt = prompt; pick.pipe = pipe
        pick.multi = !!o.multi; pick.allowNew = !!o.allowNew
        pick.preview = o.preview || ""; pick.preview2 = o.preview2 || ""; pick.hint = o.hint || ""
        pick.alt = false; pick.marked = ({}); pick.detail = ""; pick.items = []; pick.shown = []
        input.text = ""
        loader.path = infile
        loader.reload()
    }
    function refilter() {
        const words = input.text.toLowerCase().split(/\s+/).filter(w => w)
        if (!words.length) shown = items.slice(0, 300)
        else {
            const first = [], rest = []
            for (const it of items) {
                const l = label(it).toLowerCase()
                let ok = true
                for (const w of words) if (l.indexOf(w) < 0) { ok = false; break }
                if (ok) (l.startsWith(words[0]) ? first : rest).push(it)
            }
            first.sort((a, b) => a.length - b.length)
            shown = first.concat(rest).slice(0, 300)
        }
        index = 0
        view.positionViewAtBeginning()
        describe.restart()
    }
    function finish(status, lines) {
        if (pipe) Quickshell.execDetached(["sh", "-c", 'printf "%s\\n" "$@" > "$0"', pipe, status].concat(lines))
        pipe = ""; open = false; fetch.running = false
    }
    function accept() {
        if (multi && nMarked) finish("ok", Object.keys(marked))
        else if (current) finish("ok", [current])
        else if (allowNew && input.text.trim()) finish("new", [input.text.trim()])
    }
    function mark() {
        if (!multi || !current) return
        const m = Object.assign({}, marked)
        if (m[current]) delete m[current]; else m[current] = true
        marked = m
        if (index < shown.length - 1) index++
    }
    function move(by) { if (shown.length) { index = Math.max(0, Math.min(shown.length - 1, index + by)); describe.restart() } }

    FileView {
        id: loader
        onLoaded: { pick.items = text().split("\n").filter(l => l.length); pick.open = true; pick.refilter() }
        onLoadFailed: pick.finish("cancel", [])
    }
    Timer {
        id: describe
        interval: 120
        onTriggered: {
            const cmd = pick.alt && pick.preview2 ? pick.preview2 : pick.preview
            fetch.running = false
            if (!cmd || !pick.current) { pick.detail = ""; return }
            fetch.command = ["sh", "-c", cmd, "sh", pick.current]
            fetch.running = true
        }
    }
    Process { id: fetch; stdout: StdioCollector { onStreamFinished: pick.detail = text } }

    PanelWindow {
        visible: pick.open || pick.t > 0.01
        anchors { top: true; bottom: true; left: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: pick.open ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
        color: Qt.rgba(0, 0, 0, 0.5 * pick.t)
        onVisibleChanged: if (visible) input.forceActiveFocus()
        MouseArea { anchors.fill: parent; onClicked: pick.finish("cancel", []) }

        Rectangle {
            id: box
            readonly property bool wide: pick.preview !== ""
            anchors.centerIn: parent
            anchors.verticalCenterOffset: (1 - pick.t) * 10
            width: Math.min(parent.width - 80, wide ? 1080 : 600)
            // A short menu is a short box; long lists and anything with details get the full height.
            height: Math.min(parent.height - 120, wide ? 580 : 112 + Math.max(1, Math.min(pick.shown.length, 13)) * 34)
            Behavior on height { NumberAnimation { duration: pick.style.fast; easing.type: Easing.OutCubic } }
            radius: pick.style.radius + 4
            color: pick.style.surface
            border.color: pick.style.line
            border.width: 1
            opacity: pick.t
            scale: 0.97 + 0.03 * pick.t
            MouseArea { anchors.fill: parent }

            // Search row: what this list is, then what you typed.
            Rectangle {
                id: chip
                anchors { left: parent.left; top: parent.top; margins: 16 }
                width: title.implicitWidth + 20; height: 28; radius: 14
                color: Qt.rgba(pick.style.accent.r, pick.style.accent.g, pick.style.accent.b, 0.14)
                Text { id: title; anchors.centerIn: parent; text: pick.prompt; color: pick.style.accent
                       font.family: pick.style.font; font.pixelSize: 13; font.weight: Font.Medium }
            }
            TextInput {
                id: input
                anchors { left: chip.right; right: parent.right; verticalCenter: chip.verticalCenter; leftMargin: 14; rightMargin: 18 }
                color: pick.style.fg; selectionColor: pick.style.accent; selectedTextColor: pick.style.bg
                font.family: pick.style.font; font.pixelSize: 16; clip: true
                onTextChanged: if (pick.open) pick.refilter()
                Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; visible: !input.text; text: "Search"
                       color: pick.style.dim; font: input.font; opacity: 0.7 }
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Escape) pick.finish("cancel", [])
                    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) pick.accept()
                    else if (event.key === Qt.Key_Down) pick.move(1)
                    else if (event.key === Qt.Key_Up) pick.move(-1)
                    else if (event.key === Qt.Key_PageDown) pick.move(10)
                    else if (event.key === Qt.Key_PageUp) pick.move(-10)
                    else if (event.key === Qt.Key_Tab) pick.mark()
                    else if (event.key === Qt.Key_B && (event.modifiers & Qt.AltModifier) && pick.preview2) { pick.alt = !pick.alt; describe.restart() }
                    else return
                    event.accepted = true
                }
            }
            Rectangle { id: rule; height: 1; color: pick.style.line; anchors { left: parent.left; right: parent.right; top: chip.bottom; topMargin: 14 } }

            ListView {
                id: view
                anchors { left: parent.left; top: rule.bottom; bottom: foot.top; margins: 10 }
                width: box.wide ? 380 : parent.width - 20
                clip: true
                model: pick.shown
                currentIndex: pick.index
                boundsBehavior: Flickable.StopAtBounds
                // The highlight glides between rows instead of jumping.
                highlightMoveDuration: 90
                highlightMoveVelocity: -1
                highlightResizeDuration: 0
                highlight: Rectangle { width: view.width; radius: 8; color: pick.style.raised
                    Rectangle { width: 3; height: 16; radius: 2; color: pick.style.accent; anchors { left: parent.left; leftMargin: 4; verticalCenter: parent.verticalCenter } } }
                delegate: Item {
                    id: line
                    required property int index
                    required property string modelData
                    readonly property bool on: !!pick.marked[modelData]
                    width: view.width; height: 34
                    Text { anchors { verticalCenter: parent.verticalCenter; left: parent.left; right: tick.left; leftMargin: 16; rightMargin: 8 }
                           text: pick.label(line.modelData); elide: Text.ElideRight
                           color: line.on ? pick.style.accent : pick.style.fg; font.family: pick.style.font; font.pixelSize: 14 }
                    Rectangle { id: tick; visible: line.on; width: 8; height: 8; radius: 4; color: pick.style.accent
                                anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter } }
                    MouseArea { anchors.fill: parent; hoverEnabled: true
                                onPositionChanged: if (pick.index !== line.index) { pick.index = line.index; describe.restart() }
                                onClicked: { pick.index = line.index; pick.accept() } }
                }
                Text { anchors.centerIn: parent; visible: pick.shown.length === 0; color: pick.style.dim; font.family: pick.style.font; font.pixelSize: 14
                       text: pick.allowNew && input.text.trim() ? "Press Enter to ask Amadeus" : "Nothing matches" }
            }
            Rectangle { visible: box.wide; width: 1; color: pick.style.line; anchors { left: view.right; leftMargin: 10; top: rule.bottom; bottom: foot.top; bottomMargin: 10 } }
            Flickable {
                visible: box.wide
                anchors { left: view.right; right: parent.right; top: rule.bottom; bottom: foot.top; leftMargin: 26; rightMargin: 16; topMargin: 14; bottomMargin: 10 }
                clip: true
                contentHeight: info.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                Text { id: info; width: parent.width; text: pick.detail; color: pick.style.fg; opacity: 0.9
                       font.family: pick.style.mono; font.pixelSize: 12; lineHeight: 1.25; wrapMode: Text.Wrap }
            }
            Text {
                id: foot
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 18; rightMargin: 18; bottomMargin: 12 }
                color: pick.style.dim; font.family: pick.style.font; font.pixelSize: 12; elide: Text.ElideRight
                text: (pick.multi ? "Tab  select several" + (pick.nMarked ? " · " + pick.nMarked + " selected" : "") + "      " : "")
                    + "Enter  choose      Esc  close" + (pick.preview2 ? "      Alt+B  " + (pick.alt ? "details" : pick.hint || "more") : "")
            }
        }
    }
}
