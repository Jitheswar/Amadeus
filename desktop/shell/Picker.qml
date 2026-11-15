import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import "MenuSearch.js" as MenuSearch

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
    property bool globalSearch: false
    property bool multi: false
    property bool allowNew: false
    property string newLabel: ""
    property bool alt: false
    property var items: []
    property var shown: []
    property var globalIndex: []
    property var globalResults: ({})
    property var marked: ({})
    property int index: 0
    property string detail: ""
    property string filterText: ""
    property bool searchPinned: false
    property real cardTop: 0
    readonly property string current: shown.length ? shown[index] : ""
    // 0 when closed, 1 when open; everything on screen follows it, so opening and closing are one motion.
    property real t: open ? 1 : 0
    Behavior on t { NumberAnimation { duration: pick.open ? pick.style.normal : pick.style.fast; easing.type: Easing.OutCubic } }
    readonly property int nMarked: Object.keys(marked).length

    function geometry() { return { x: box.x, y: box.y + view.y, width: view.width, height: view.height, contentY: view.contentY } }
    function label(line) { const t = line.indexOf("\t"); return t < 0 ? line : line.slice(0, t) }
    function start(prompt, infile, pipe, options) {
        if (open) finish("cancel", [])
        let o = {}
        try { o = JSON.parse(options) } catch (e) {}
        pick.prompt = prompt; pick.pipe = pipe
        pick.globalSearch = !!o.globalSearch; pick.multi = !!o.multi; pick.allowNew = !!o.allowNew
        pick.preview = o.preview || ""; pick.preview2 = o.preview2 || ""; pick.hint = o.hint || ""; pick.newLabel = o.newLabel || "Press Enter to use what you typed"
        pick.alt = false; pick.marked = ({}); pick.detail = ""; pick.items = []; pick.shown = []
        pick.index = 0; pick.filterText = ""; pick.searchPinned = false; pointerGate.reset()
        input.text = ""
        loader.path = infile
        loader.reload()
        globalLoad.running = false
        globalLoad.running = pick.globalSearch
    }
    function search(text) { input.text = text }
    function refilter(preserve) {
        const selected = preserve ? current : ""
        if (input.text.trim() && !searchPinned) { cardTop = box.y; searchPinned = true }
        filterText = input.text
        const result = MenuSearch.rows(items, globalSearch && (!allowNew || items.length) ? globalIndex : [], input.text, prompt)
        globalResults = result.info
        shown = result.lines
        const prior = selected ? shown.indexOf(selected) : -1
        index = prior >= 0 ? prior : 0
        pointerGate.reset()
        if (!preserve) view.positionViewAtBeginning()
        describe.restart()
    }
    function finish(status, lines) {
        if (pipe) Quickshell.execDetached(["sh", "-c", 'printf "%s\\n" "$@" > "$0"', pipe, status].concat(lines))
        pipe = ""; open = false; fetch.running = false; pointerGate.reset()
    }
    function accept() {
        if (globalResults[current]) {
            const id = globalResults[current].id
            finish("cancel", [])
            Qt.callLater(() => Quickshell.execDetached(["amadeus-search", "--run", id]))
            return
        }
        if (multi && nMarked) finish("ok", Object.keys(marked))
        else if (current) finish("ok", [current])
        else if (allowNew && input.text.trim()) finish("new", [input.text.trim()])
    }
    function askAbout() {
        const context = { kind: "menu", label: prompt, selection: label(current), query: input.text }
        finish("cancel", [])
        Qt.callLater(() => Quickshell.execDetached(["ama", "panel", "context", JSON.stringify(context)]))
    }
    function mark() {
        if (!multi || !current || globalResults[current]) return
        const m = Object.assign({}, marked)
        if (m[current]) delete m[current]; else m[current] = true
        marked = m
        if (index < shown.length - 1) index++
    }
    function move(by) {
        pointerGate.reset()
        if (shown.length) {
            index = Math.max(0, Math.min(shown.length - 1, index + by))
            view.positionViewAtIndex(index, ListView.Contain)
            describe.restart()
        }
    }
    function select(i) { if (index !== i) { index = i; describe.restart() } }
    function selectFromPointer(i, item, mouse) {
        if (pointerGate.moved(item, mouse)) select(i)
    }
    PointerMoveGate { id: pointerGate; referenceItem: screenArea }

    FileView {
        id: loader
        onLoaded: { pick.items = text().split("\n").filter(l => l.length); pick.open = true; pick.refilter() }
        onLoadFailed: pick.finish("cancel", [])
    }
    Timer {
        id: describe
        interval: 120
        onTriggered: {
            if (pick.globalResults[pick.current]) {
                pick.detail = pick.globalResults[pick.current].path + " · " + pick.globalResults[pick.current].label
                return
            }
            const cmd = pick.alt && pick.preview2 ? pick.preview2 : pick.preview
            fetch.running = false
            if (!cmd || !pick.current) { pick.detail = ""; return }
            fetch.command = ["sh", "-c", cmd, "sh", pick.current]
            fetch.running = true
        }
    }
    Process {
        id: globalLoad
        command: ["amadeus-search", "--index"]
        stdout: StdioCollector { onStreamFinished: {
            try { pick.globalIndex = JSON.parse(text) } catch (e) { pick.globalIndex = [] }
            if (pick.open) pick.refilter(true)
        } }
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
        MouseArea { id: screenArea; anchors.fill: parent; onClicked: pick.finish("cancel", []) }

        Rectangle {
            id: box
            readonly property bool wide: pick.preview !== ""
            x: (parent.width - width) / 2
            y: (pick.searchPinned ? Math.max(24, Math.min(pick.cardTop, parent.height - height - 24)) : (parent.height - height) / 2) + (1 - pick.t) * 10
            width: Math.min(parent.width - 80, wide ? 1080 : 600)
            // A short menu is a short box; long lists and anything with details get the full height.
            height: Math.min(parent.height - 120, wide ? 580 : 112 + Math.max(1, Math.min(pick.shown.length, 13)) * (pick.filterText.trim() ? 52 : 34))
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
                       font.family: pick.style.font; font.pixelSize: pick.style.fontPixels(13); font.weight: Font.Medium }
            }
            TextInput {
                id: input
                anchors { left: chip.right; right: parent.right; verticalCenter: chip.verticalCenter; leftMargin: 14; rightMargin: 18 }
                color: pick.style.fg; selectionColor: pick.style.accent; selectedTextColor: pick.style.bg
                font.family: pick.style.font; font.pixelSize: pick.style.fontPixels(16); clip: true
                onTextChanged: if (pick.open) pick.refilter(false)
                Text { anchors.fill: parent; verticalAlignment: Text.AlignVCenter; visible: !input.text; text: pick.items.length ? "Search" : "Type here"
                       color: pick.style.dim; font: input.font; opacity: 0.7 }
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Escape) { if (input.text) input.text = ""; else pick.finish("cancel", []) }
                    else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && (event.modifiers & Qt.ControlModifier)) pick.askAbout()
                    else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) pick.accept()
                    else if (event.key === Qt.Key_Down) pick.move(1)
                    else if (event.key === Qt.Key_Up) pick.move(-1)
                    else if (event.key === Qt.Key_PageDown) { if (!event.isAutoRepeat) pick.move(10) }
                    else if (event.key === Qt.Key_PageUp) { if (!event.isAutoRepeat) pick.move(-10) }
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
                    width: view.width; height: pick.filterText.trim() ? 52 : 34
                    Text { anchors { verticalCenter: parent.verticalCenter; verticalCenterOffset: pick.filterText.trim() ? -8 : 0; left: parent.left; right: tick.left; leftMargin: 16; rightMargin: 8 }
                           text: pick.label(line.modelData); textFormat: Text.PlainText; elide: Text.ElideRight
                           color: line.on ? pick.style.accent : pick.style.fg; font.family: pick.style.font; font.pixelSize: pick.style.fontPixels(14) }
                    Text { anchors { left: parent.left; leftMargin: 16; right: parent.right; rightMargin: 16; bottom: parent.bottom; bottomMargin: 6 }
                           visible: !!input.text.trim(); text: pick.globalResults[line.modelData] ? pick.globalResults[line.modelData].path : pick.prompt
                           textFormat: Text.PlainText; elide: Text.ElideRight; color: pick.style.dim; font.family: pick.style.font; font.pixelSize: pick.style.fontPixels(11) }
                    Rectangle { id: tick; visible: line.on; width: 8; height: 8; radius: 4; color: pick.style.accent
                                anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter } }
                    MouseArea { anchors.fill: parent; hoverEnabled: true
                                onEntered: pick.selectFromPointer(line.index, line, { x: mouseX, y: mouseY })
                                onPositionChanged: mouse => pick.selectFromPointer(line.index, line, mouse)
                                onClicked: { pick.select(line.index); pick.accept() } }

                }
                Text { anchors.centerIn: parent; visible: pick.shown.length === 0; color: pick.style.dim; font.family: pick.style.font; font.pixelSize: pick.style.fontPixels(14)
                       text: pick.allowNew ? (input.text.trim() ? pick.newLabel : "Type, then press Enter") : "Nothing matches" }
            }
            Rectangle { visible: box.wide; width: 1; color: pick.style.line; anchors { left: view.right; leftMargin: 10; top: rule.bottom; bottom: foot.top; bottomMargin: 10 } }
            Flickable {
                visible: box.wide
                anchors { left: view.right; right: parent.right; top: rule.bottom; bottom: foot.top; leftMargin: 26; rightMargin: 16; topMargin: 14; bottomMargin: 10 }
                clip: true
                contentHeight: info.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                Text { id: info; textFormat: Text.PlainText; width: parent.width; text: pick.detail; color: pick.style.fg; opacity: 0.9
                       font.family: pick.style.mono; font.pixelSize: pick.style.fontPixels(12); lineHeight: 1.25; wrapMode: Text.Wrap }
            }
            Text {
                id: foot
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 18; rightMargin: 18; bottomMargin: 12 }
                color: pick.style.dim; font.family: pick.style.font; font.pixelSize: pick.style.fontPixels(12); elide: Text.ElideRight
                text: (pick.multi ? "Tab  select several" + (pick.nMarked ? " · " + pick.nMarked + " selected" : "") + "      " : "")
                    + "Enter  choose      Esc  clear/close      Ctrl+Enter  ask Amadeus" + (pick.preview2 ? "      Alt+B  " + (pick.alt ? "details" : pick.hint || "more") : "")
            }
        }
    }
}
