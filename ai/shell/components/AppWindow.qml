import QtQuick
import Quickshell

// Root of every generated app: a normal, themed, tiling-friendly window.
FloatingWindow {
    id: win
    default property alias content: body.data
    property int pad: Theme.gap * 1.5
    color: Theme.bg
    implicitWidth: 720
    implicitHeight: 480
    Item { id: body; anchors.fill: parent; anchors.margins: win.pad }
}
