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
    function move(by) { if (shown.length) { index = Math.max(0, Math.min(shown.length - 1, index + by)); view.positionViewAtIndex(index, ListView.Contain); describe.restart() } }

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
        visible: pick.open
        anchors { top: true; bottom: true; left: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
        color: "#99000000"
        onVisibleChanged: if (visible) input.forceActiveFocus()
        MouseArea { anchors.fill: parent; onClicked: pick.finish("cancel", []) }

        Rectangle {
            id: box
            readonly property bool wide: pick.preview !== ""
            anchors.centerIn: parent
            width: Math.min(parent.width - 80, wide ? 1040 : 560)
            height: Math.min(parent.height - 120, 560)
            radius: 12
            color: pick.style.bg
            border.color: pick.style.accent
            border.width: 2
            MouseArea { anchors.fill: parent }

            Text { id: title; text: pick.prompt; color: pick.style.accent; font.pixelSize: 14; font.bold: true
                   anchors { left: parent.left; top: parent.top; margins: 16 } }
            TextInput {
                id: input
                anchors { left: title.right; right: parent.right; verticalCenter: title.verticalCenter; leftMargin: 12; rightMargin: 16 }
                color: pick.style.fg; selectionColor: pick.style.accent; font.pixelSize: 15; clip: true
                onTextChanged: if (pick.open) pick.refilter()
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
            Rectangle { id: rule; height: 1; color: pick.style.muted; anchors { left: parent.left; right: parent.right; top: title.bottom; margins: 12 } }

            ListView {
                id: view
                anchors { left: parent.left; top: rule.bottom; bottom: foot.top; margins: 12 }
                width: box.wide ? 360 : parent.width - 24
                clip: true
                model: pick.shown
                delegate: Rectangle {
                    required property int index
                    required property string modelData
                    width: view.width; height: 26; radius: 6
                    color: index === pick.index ? pick.style.muted : "transparent"
                    Text { anchors { verticalCenter: parent.verticalCenter; left: parent.left; right: parent.right; leftMargin: 8; rightMargin: 8 }
                           text: (pick.marked[parent.modelData] ? "● " : "") + pick.label(parent.modelData)
                           color: pick.marked[parent.modelData] ? pick.style.accent : pick.style.fg; font.pixelSize: 13; elide: Text.ElideRight }
                    MouseArea { anchors.fill: parent; onClicked: { pick.index = parent.index; pick.accept() } }
                }
                Text { anchors.centerIn: parent; visible: pick.shown.length === 0; color: pick.style.dim; font.pixelSize: 13
                       text: pick.allowNew && input.text.trim() ? "Enter: ask Amadeus" : "Nothing matches" }
            }
            Flickable {
                visible: box.wide
                anchors { left: view.right; right: parent.right; top: rule.bottom; bottom: foot.top; margins: 12 }
                clip: true
                contentHeight: info.implicitHeight
                Text { id: info; width: parent.width; text: pick.detail; color: pick.style.fg; font.family: "monospace"; font.pixelSize: 12; wrapMode: Text.Wrap }
            }
            Text {
                id: foot
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12 }
                color: pick.style.dim; font.pixelSize: 11; elide: Text.ElideRight
                text: (pick.multi ? "Tab: select several" + (pick.nMarked ? " (" + pick.nMarked + " selected)" : "") + "   " : "")
                    + "Enter: choose   Esc: close" + (pick.preview2 ? "   Alt+B: " + (pick.alt ? "details" : pick.hint || "more") : "")
            }
        }
    }
}
