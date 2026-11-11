import QtQuick
import Quickshell
import Quickshell.Io
import "components"

// The Amadeus panel: docked to the right edge, always available (Super+Z).
// Each request is a task. Tasks run side by side, show their steps on demand,
// can be stopped, and everything one task changed can be undone together.
ShellRoot {
    id: root
    property bool open: false
    property int seq: 0
    property int nextTask: 0
    property int current: -1            // task that Enter continues
    property var about: null            // window the next request is about: { id, app, title }
    property var byRequest: ({})        // request id -> { task, kind }
    property var tasks: ({})            // task id -> { session, running, steps, changed, showSteps, stopped }
    readonly property int running: { let n = 0; for (const k in tasks) if (tasks[k].running) n++; return n }

    function send(method, params) {
        const id = ++seq
        sock.write(JSON.stringify({ id: id, method: method, params: params }) + "\n")
        sock.flush()
        return id
    }
    function setTask(t, patch) {
        const all = Object.assign({}, tasks)
        all[t] = Object.assign({}, all[t] || {}, patch)
        tasks = all
    }
    function add(t, kind, body, extra) {
        log.append(Object.assign({ task: t, kind: kind, body: body, aid: "", serious: false, pending: false }, extra || {}))
        view.positionViewAtEnd()
    }
    function submit(fresh) {
        const q = input.text.trim()
        if (!q) return
        let t = current
        const cont = !fresh && t >= 0 && tasks[t] && !tasks[t].running
        if (!cont) {
            t = nextTask++
            setTask(t, { session: "panel-" + Date.now().toString(36) + "-" + t, running: false, steps: 0, changed: 0, showSteps: false, stopped: false })
            add(t, "task", q)
            current = t
        } else add(t, "user", q)
        let prompt = q
        if (about) {
            prompt = "[The user is pointing at a window: id " + about.id + ", application " + about.app + ", title \"" + about.title + "\". "
                   + "\"This\" in the request means that window.]\n" + q
            add(t, "about", about.app + " · " + about.title)
            about = null
        }
        input.text = ""
        setTask(t, { running: true, stopped: false })
        const rid = send("ask", { prompt: prompt, session: tasks[t].session, interactive: true })
        const m = Object.assign({}, byRequest); m[rid] = { task: t, kind: "ask" }; byRequest = m
    }
    function stop(t) { send("stop", { session: tasks[t].session }); setTask(t, { stopped: true }) }
    function stopAll() { for (const k in tasks) if (tasks[k].running) stop(k) }
    function undo(t) {
        const rid = send("undo", { session: tasks[t].session })
        const m = Object.assign({}, byRequest); m[rid] = { task: t, kind: "undo" }; byRequest = m
    }
    function decide(index, aid, d) {
        send("approve", { aid: aid, decision: d })
        log.setProperty(index, "pending", false)
        log.setProperty(index, "body", log.get(index).body + "\n→ " + (d === "no" ? "denied" : "allowed"))
    }
    function handle(m) {
        const r = byRequest[m.id]
        if (!r) return
        const t = r.task
        if (r.kind === "undo") {
            if (m.result !== undefined) { add(t, "note", m.result.length ? "Undone:\n" + m.result.join("\n") : "Nothing to undo."); setTask(t, { changed: 0 }) }
            return
        }
        if (m.event === "text") add(t, "ai", m.data.text)
        else if (m.event === "tool") { add(t, "tool", m.data.name + "  " + JSON.stringify(m.data.args).slice(0, 110)); setTask(t, { steps: tasks[t].steps + 1 }) }
        else if (m.event === "approval") add(t, "approval", m.data.tool + "   [" + m.data.capability + " · " + m.data.risk + "]\n" + JSON.stringify(m.data.args, null, 2),
            { aid: m.data.aid, pending: true, serious: m.data.risk === "destructive" || m.data.risk === "privileged" })
        else if (m.error) { add(t, "error", m.error); setTask(t, { running: false }) }
        else if (m.result) {
            if (m.result.stopped) add(t, "note", "Stopped.")
            setTask(t, { running: false, changed: m.result.changed || 0 })
        }
    }

    Socket {
        id: sock
        path: Quickshell.env("XDG_RUNTIME_DIR") + "/amadeus/daemon.sock"
        connected: true
        parser: SplitParser { onRead: line => { try { root.handle(JSON.parse(line)) } catch (e) {} } }
    }
    IpcHandler {
        target: "panel"
        function toggle(): void { root.open = !root.open; if (root.open) input.input.forceActiveFocus() }
        function show(): void { root.open = true; input.input.forceActiveFocus() }
        function hide(): void { root.open = false }
        function window(json: string): void {
            try { root.about = JSON.parse(json) } catch (e) { root.about = null }
            root.open = true; input.input.forceActiveFocus()
        }
        function state(): string { return JSON.stringify({ open: root.open, tasks: root.nextTask, running: root.running, connected: sock.connected }) }
    }
    ListModel { id: log }

    PanelWindow {
        visible: root.open
        anchors { top: true; bottom: true; right: true }
        implicitWidth: 440
        focusable: true
        color: Theme.bg

        Rectangle { anchors { left: parent.left; top: parent.top; bottom: parent.bottom } width: 1; color: Theme.line }
        Item {
            anchors.fill: parent
            anchors.margins: Theme.gap
            Keys.onEscapePressed: root.open = false

            Row {
                id: head
                anchors { left: parent.left; right: parent.right; top: parent.top }
                spacing: Theme.gap
                Txt { text: "Amadeus"; font.pixelSize: Theme.size * 1.25; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                Txt { dim: true; anchors.verticalCenter: parent.verticalCenter
                      text: !sock.connected ? "not running" : root.running ? root.running + " working" : "" }
                Item { width: Math.max(0, head.width - x - stopAllBtn.width - Theme.gap); height: 1 }
                Btn { id: stopAllBtn; text: "Stop all"; visible: root.running > 0; onClicked: root.stopAll() }
            }

            ListView {
                id: view
                anchors { left: parent.left; right: parent.right; top: head.bottom; bottom: foot.top; topMargin: Theme.gap; bottomMargin: Theme.gap }
                model: log
                spacing: 6
                clip: true
                delegate: Column {
                    id: row
                    required property int index
                    required property int task
                    required property string kind
                    required property string body
                    required property string aid
                    required property bool serious
                    required property bool pending
                    readonly property var t: root.tasks[task] || ({})
                    readonly property bool hidden: kind === "tool" && !t.showSteps
                    width: view.width
                    visible: !hidden
                    height: hidden ? 0 : implicitHeight
                    spacing: 6

                    // A task opens with its request and its controls.
                    Rectangle {
                        visible: row.kind === "task"
                        width: parent.width; height: visible ? title.implicitHeight + bar.height + Theme.gap * 2 : 0
                        radius: Theme.radius; color: Theme.surface; border.color: root.current === row.task ? Theme.accent : Theme.line
                        MouseArea { anchors.fill: parent; onClicked: root.current = row.task }
                        Txt { id: title; text: row.body; color: Theme.accent; wrapMode: Text.Wrap
                              anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.gap * 0.8 } }
                        Row {
                            id: bar
                            anchors { left: parent.left; bottom: parent.bottom; margins: Theme.gap * 0.6 }
                            spacing: Theme.gap * 0.6
                            Txt { dim: true; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: Theme.size * 0.85
                                  text: row.t.running ? (row.t.stopped ? "stopping…" : "working…") : "done" }
                            Btn { text: "Stop"; visible: !!row.t.running && !row.t.stopped; onClicked: root.stop(row.task) }
                            Btn { text: row.t.showSteps ? "Hide steps" : "Show steps (" + (row.t.steps || 0) + ")"; visible: (row.t.steps || 0) > 0
                                  onClicked: root.setTask(row.task, { showSteps: !row.t.showSteps }) }
                            Btn { text: "Undo all (" + (row.t.changed || 0) + ")"; visible: !row.t.running && (row.t.changed || 0) > 0; onClicked: root.undo(row.task) }
                        }
                    }
                    Txt {
                        visible: row.kind !== "task"
                        width: parent.width
                        text: (row.kind === "user" ? "› " : row.kind === "tool" ? "· " : row.kind === "about" ? "About: " : "") + row.body
                        mono: row.kind === "tool" || row.kind === "approval"
                        dim: row.kind === "tool" || row.kind === "note" || row.kind === "about"
                        textFormat: row.kind === "ai" ? Text.MarkdownText : Text.PlainText
                        color: row.kind === "user" ? Theme.accent : row.kind === "error" ? Theme.bad : row.kind === "approval" ? Theme.warn : (dim ? Theme.dim : Theme.fg)
                        font.pixelSize: row.kind === "tool" ? Theme.size * 0.85 : Theme.size
                    }
                    Row {
                        visible: row.kind === "approval" && row.pending
                        spacing: Theme.gap * 0.6
                        Btn { text: "Deny"; onClicked: root.decide(row.index, row.aid, "no") }
                        Btn { text: "Always this session"; visible: !row.serious; onClicked: root.decide(row.index, row.aid, "always") }
                        Btn { text: "Allow once"; primary: true; onClicked: root.decide(row.index, row.aid, "yes") }
                    }
                }
                Txt { anchors.centerIn: parent; visible: log.count === 0; dim: true; horizontalAlignment: Text.AlignHCenter
                      text: sock.connected ? "Ask for anything.\nThe system does it." : "Amadeus is not running\nsystemctl --user start amadeusd" }
            }

            Column {
                id: foot
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                spacing: Theme.gap * 0.6
                Rectangle {
                    visible: root.about !== null
                    width: parent.width; height: visible ? chip.implicitHeight + Theme.gap : 0
                    radius: Theme.radius * 0.7; color: Theme.raised
                    Txt { id: chip; elide: Text.ElideRight
                          anchors { left: parent.left; right: clear.left; verticalCenter: parent.verticalCenter; margins: Theme.gap * 0.6 }
                          text: root.about ? "About this window: " + root.about.app + " · " + root.about.title : "" }
                    Txt { id: clear; text: "✕"; dim: true; anchors { right: parent.right; verticalCenter: parent.verticalCenter; rightMargin: Theme.gap * 0.6 }
                          MouseArea { anchors.fill: parent; anchors.margins: -6; onClicked: root.about = null } }
                }
                Row {
                    width: parent.width
                    spacing: Theme.gap * 0.6
                    Field {
                        id: input
                        width: parent.width - newBtn.width - Theme.gap * 0.6
                        placeholder: root.current >= 0 && root.tasks[root.current] && !root.tasks[root.current].running ? "Continue, or New for another task" : "What should the system do?"
                        onAccepted: root.submit(false)
                        Keys.onEscapePressed: root.open = false
                    }
                    Btn { id: newBtn; text: "New"; onClicked: root.submit(true) }
                }
            }
        }
    }
}
