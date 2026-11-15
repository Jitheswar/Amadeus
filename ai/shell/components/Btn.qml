import QtQuick

// One button, three weights: primary is the single main action of a view, selected marks
// the current choice in a group, and everything else stays quiet.
Rectangle {
    id: b
    property alias text: label.text
    property bool primary: false
    property bool selected: false
    signal clicked()
    implicitWidth: label.implicitWidth + Theme.gap * 1.8
    implicitHeight: label.implicitHeight + Theme.gap * 0.9
    radius: Theme.radius * 0.6
    color: primary ? (area.containsMouse ? Qt.lighter(Theme.accent, 1.08) : Theme.accent)
         : selected ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.16)
         : (area.containsMouse ? Qt.lighter(Theme.raised, 1.25) : Theme.raised)
    opacity: enabled ? 1 : 0.4
    scale: area.pressed ? 0.97 : 1
    activeFocusOnTab: true
    Behavior on color { ColorAnimation { duration: Theme.fast } }
    Behavior on scale { NumberAnimation { duration: Theme.fast; easing.type: Theme.ease } }
    Keys.onReturnPressed: b.clicked()
    Keys.onSpacePressed: b.clicked()
    Text { id: label; anchors.centerIn: parent; color: b.primary ? Theme.bg : b.selected ? Theme.accent : Theme.fg
           font.family: Theme.font; font.pixelSize: Theme.size - 1; font.weight: Font.Medium }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clicked() }
    Rectangle { anchors.fill: parent; anchors.margins: -3; radius: b.radius + 3; color: "transparent"; border.color: Theme.accent; border.width: 2; visible: b.activeFocus }
}
