import QtQuick
import Quickshell
import Quickshell.Io
import "components"

// The desktop entry point to Amadeus: type a request, watch it act, approve inline.
FloatingWindow {
    id: win
    title: "Amadeus"
    color: Theme.bg
    implicitWidth: 760
    implicitHeight: 480
    property string session: ""
    property bool busy: false
    property int seq: 0
    property int askId: 0

    function send(method, params) {
        const id = ++seq
        sock.write(JSON.stringify({ id: id, method: method, params: params }) + "\n")
        sock.flush()
        return id
    }
    function submit() {
        const q = input.text.trim()
        if (!q || busy) return
        log.append({ kind: "user", body: q, aid: "", serious: false, open: false })
        input.text = ""
        busy = true
        askId = send("ask", { prompt: q, session: session || null, interactive: true })
    }
    function decide(index, aid, d) {
        send("approve", { aid: aid, decision: d })
        log.setProperty(index, "open", false)
        log.setProperty(index, "body", log.get(index).body + "\n→ " + (d === "no" ? "denied" : "allowed"))
    }
    function handle(m) {
        if (m.id !== askId) return
        if (m.event === "text") log.append({ kind: "ai", body: m.data.text, aid: "", serious: false, open: false })
        else if (m.event === "tool") log.append({ kind: "tool", body: m.data.name + "  " + JSON.stringify(m.data.args).slice(0, 110), aid: "", serious: false, open: false })
        else if (m.event === "approval") log.append({ kind: "approval", aid: m.data.aid, open: true,
            serious: m.data.risk === "destructive" || m.data.risk === "privileged",
            body: m.data.tool + "   [" + m.data.capability + " · " + m.data.risk + "]\n" + JSON.stringify(m.data.args, null, 2) })
        else if (m.error) { log.append({ kind: "error", body: m.error, aid: "", serious: false, open: false }); busy = false }
        else if (m.result) { session = m.result.session; busy = false }
        view.positionViewAtEnd()
    }

    Socket {
        id: sock
        path: Quickshell.env("XDG_RUNTIME_DIR") + "/amadeus/daemon.sock"
        connected: true
        parser: SplitParser { onRead: line => { try { win.handle(JSON.parse(line)) } catch (e) {} } }
    }
    ListModel { id: log }

    Item {
        anchors.fill: parent
        anchors.margins: 18
        Keys.onEscapePressed: Qt.quit()

        ListView {
            id: view
            anchors { left: parent.left; right: parent.right; top: parent.top; bottom: bar.top; bottomMargin: Theme.gap }
            model: log
            spacing: 8
            clip: true
            delegate: Column {
                id: row
                required property int index
                required property string kind
                required property string body
                required property string aid
                required property bool serious
                required property bool open
                width: view.width
                spacing: 6
                Txt {
                    width: parent.width
                    text: (row.kind === "user" ? "› " : row.kind === "tool" ? "· " : "") + row.body
                    mono: row.kind === "tool" || row.kind === "approval"
                    dim: row.kind === "tool"
                    textFormat: row.kind === "ai" ? Text.MarkdownText : Text.PlainText
                    color: row.kind === "user" ? Theme.accent : row.kind === "error" ? Theme.bad : row.kind === "approval" ? Theme.warn : (dim ? Theme.dim : Theme.fg)
                    font.pixelSize: row.kind === "tool" ? Theme.size * 0.85 : Theme.size
                }
                Row {
                    visible: row.kind === "approval" && row.open
                    spacing: Theme.gap
                    Btn { text: "Deny"; onClicked: win.decide(row.index, row.aid, "no") }
                    Btn { text: "Always this session"; visible: !row.serious; onClicked: win.decide(row.index, row.aid, "always") }
                    Btn { text: "Allow once"; primary: true; onClicked: win.decide(row.index, row.aid, "yes") }
                }
            }
            Txt { anchors.centerIn: parent; visible: log.count === 0; dim: true
                  text: sock.connected ? "Ask for anything. The system does it." : "Amadeus is not running  ·  systemctl --user start amadeusd" }
        }
        Row {
            id: bar
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            spacing: Theme.gap
            Field {
                id: input
                width: parent.width - go.width - Theme.gap
                placeholder: win.busy ? "Working…" : "What should the system do?"
                onAccepted: win.submit()
                Component.onCompleted: input.input.forceActiveFocus()
                Keys.onEscapePressed: Qt.quit()
            }
            Btn { id: go; text: win.busy ? "…" : "Run"; primary: true; enabled: !win.busy; onClicked: win.submit() }
        }
    }
}
