import QtQuick
import Quickshell
import "components"

// Approval prompt for actions that did not start in a terminal.
// Nothing is approved by default: Enter and Escape both decline.
FloatingWindow {
    id: win
    readonly property var req: JSON.parse(Quickshell.env("AMA_REQ") || "{}")
    readonly property bool serious: req.risk === "destructive" || req.risk === "privileged"
    title: "Amadeus — approval"
    color: Theme.bg
    implicitWidth: 560
    implicitHeight: col.implicitHeight + 48
    function decide(d) { console.log("DECISION " + d); Qt.quit() }
    onClosed: decide("no")

    Column {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 24 }
        spacing: Theme.gap
        focus: true
        Keys.onEscapePressed: win.decide("no")
        Keys.onReturnPressed: win.decide("no")
        Txt { text: "Amadeus wants to run"; dim: true }
        Txt { text: win.req.tool || ""; title: true; color: win.serious ? Theme.warn : Theme.fg }
        Txt { width: parent.width; dim: true
              text: (win.req.origin || "ai") + "  ·  " + (win.req.capability || "") + "  ·  " + (win.req.risk || "") }
        Card {
            width: parent.width
            implicitHeight: Math.min(args.implicitHeight, 260) + pad * 2
            clip: true
            Txt { id: args; width: parent.width; mono: true; wrapMode: Text.WrapAnywhere
                  text: JSON.stringify(win.req.args || {}, null, 2) }
        }
        Row {
            spacing: Theme.gap
            anchors.right: parent.right
            Btn { text: "Deny"; onClicked: win.decide("no") }
            Btn { text: "Always this session"; visible: !win.serious; onClicked: win.decide("always") }
            Btn { text: "Allow once"; primary: true; onClicked: win.decide("yes") }
        }
    }
}
