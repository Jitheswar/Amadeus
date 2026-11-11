import QtQuick

Rectangle {
    id: b
    property alias text: label.text
    property bool primary: false
    signal clicked()
    implicitWidth: label.implicitWidth + Theme.gap * 2.4
    implicitHeight: label.implicitHeight + Theme.gap * 1.2
    radius: Theme.radius * 0.7
    color: primary ? Theme.accent : (area.containsMouse ? Theme.raised : Theme.surface)
    border.color: primary ? "transparent" : Theme.line
    opacity: enabled ? (area.pressed ? 0.75 : 1) : 0.4
    activeFocusOnTab: true
    Keys.onReturnPressed: b.clicked()
    Keys.onSpacePressed: b.clicked()
    Text { id: label; anchors.centerIn: parent; color: b.primary ? Theme.bg : Theme.fg; font.family: Theme.font; font.pixelSize: Theme.size }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clicked() }
    Rectangle { anchors.fill: parent; radius: parent.radius; color: "transparent"; border.color: Theme.accent; border.width: 2; visible: b.activeFocus }
}
