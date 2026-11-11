import QtQuick
import Quickshell
import "Amadeus"

// System monitor. Its manifest grants exactly one thing: the sys_status tool.
AppWindow {
    id: win
    title: "System"
    implicitWidth: 460
    implicitHeight: 400
    property var s: null
    function refresh() { os.call("sys_status", {}, r => { if (r.ok) win.s = r.result }) }
    Os { id: os; onReadyChanged: if (ready) win.refresh() }
    Timer { interval: 3000; running: true; repeat: true; onTriggered: win.refresh() }

    Column {
        anchors.fill: parent
        spacing: Theme.gap * 1.4
        Txt { text: "System"; title: true }
        Txt { visible: !win.s; dim: true; text: os.ready ? "Reading…" : "Waiting for Amadeus…" }
        Row {
            visible: !!win.s
            spacing: Theme.gap * 3
            Stat { label: "Load"; value: win.s ? win.s.load[0].toFixed(2) : "" }
            Stat { label: "CPU temp"; value: win.s ? (win.s.temps_c.x86_pkg_temp || "–") + "°" : ""
                   tone: win.s && win.s.temps_c.x86_pkg_temp > 85 ? Theme.bad : Theme.fg }
            Stat { label: "NVIDIA"; value: win.s ? win.s.gpu.nvidia : ""
                   tone: win.s && win.s.gpu.nvidia === "active" ? Theme.warn : Theme.good }
            Stat { label: "Battery"; value: win.s && win.s.battery.percent ? win.s.battery.percent + "%" : "–" }
        }
        Meter { visible: !!win.s; width: parent.width; label: "Memory"
                value: win.s ? 1 - win.s.mem_mb.MemAvailable / win.s.mem_mb.MemTotal : 0
                caption: win.s ? Math.round((win.s.mem_mb.MemTotal - win.s.mem_mb.MemAvailable) / 1024 * 10) / 10 + " / " + Math.round(win.s.mem_mb.MemTotal / 1024) + " GB" : "" }
        Meter { visible: !!win.s; width: parent.width; label: "Disk"
                value: win.s ? 1 - win.s.disk_root_gb.free / win.s.disk_root_gb.total : 0
                caption: win.s ? win.s.disk_root_gb.free + " GB free" : "" }
        Txt { visible: !!win.s; dim: true; text: win.s ? "Power profile: " + win.s.power_profile + (win.s.root_mode ? "  ·  root mode ON" : "") : "" }
    }
}
