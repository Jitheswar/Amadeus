import QtQuick

Rectangle {
    id: b
    property alias text: label.text
    property bool primary: false
    signal clicked()
    implicitWidth: label.implicitWidth + Theme.gap * 2.2
    implicitHeight: label.implicitHeight + Theme.gap * 1.1
    radius: height / 2
    color: primary ? (area.containsMouse ? Qt.lighter(Theme.accent, 1.08) : Theme.accent) : (area.containsMouse ? Theme.raised : "transparent")
    border.color: primary ? "transparent" : Theme.line
    opacity: enabled ? 1 : 0.4
    scale: area.pressed ? 0.96 : 1
    activeFocusOnTab: true
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Behavior on scale { NumberAnimation { duration: 80; easing.type: Theme.ease } }
    Keys.onReturnPressed: b.clicked()
    Keys.onSpacePressed: b.clicked()
    Text { id: label; anchors.centerIn: parent; color: b.primary ? Theme.bg : Theme.fg; font.family: Theme.font; font.pixelSize: Theme.size - 1; font.weight: Font.Medium }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clicked() }
    Rectangle { anchors.fill: parent; anchors.margins: -3; radius: height / 2; color: "transparent"; border.color: Theme.accent; border.width: 2; visible: b.activeFocus }
}
