import QtQuick
import Quickshell
import Quickshell.Io

// Bridge from a sandboxed app to the OS. Only the tools named in the app's
// manifest are reachable, and each call still passes system policy.
//   Os { id: os }
//   os.call("sys_status", {}, r => { if (r.ok) ... r.result ... })
//   os.ask("summarise this", r => ...)      // needs the "ai" permission
Item {
    id: os
    property var pending: ({})
    property int seq: 0
    readonly property bool ready: sock.connected
    function send(method, params, cb) {
        const id = ++seq
        pending[id] = cb
        sock.write(JSON.stringify({ id: id, method: method, params: params }) + "\n")
        sock.flush()
    }
    function call(tool, args, cb) { send("tool", { name: tool, args: args || {} }, cb) }
    function ask(prompt, cb) { send("ask", { prompt: prompt }, cb) }
    Socket {
        id: sock
        path: Quickshell.env("AMADEUS_APP_SOCK")
        connected: true
        parser: SplitParser {
            onRead: line => {
                let m
                try { m = JSON.parse(line) } catch (e) { return }
                const cb = os.pending[m.id]
                if (!cb) return
                delete os.pending[m.id]
                cb(m.error ? { ok: false, error: m.error } : { ok: true, result: m.result })
            }
        }
    }
}
