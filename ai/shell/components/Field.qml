import QtQuick

Rectangle {
    id: f
    property alias text: input.text
    property string placeholder: ""
    property alias input: input
    signal accepted()
    implicitWidth: 240
    implicitHeight: input.implicitHeight + Theme.gap * 1.2
    radius: Theme.radius * 0.7
    color: Theme.surface
    border.color: input.activeFocus ? Theme.accent : Theme.line
    border.width: input.activeFocus ? 2 : 1
    TextInput {
        id: input
        anchors.fill: parent; anchors.margins: Theme.gap * 0.6
        verticalAlignment: TextInput.AlignVCenter
        color: Theme.fg; selectionColor: Theme.accent; selectedTextColor: Theme.bg
        font.family: Theme.font; font.pixelSize: Theme.size
        clip: true; selectByMouse: true
        onAccepted: f.accepted()
    }
    Text { anchors.fill: input; verticalAlignment: Text.AlignVCenter; text: f.placeholder; color: Theme.dim
           font: input.font; visible: !input.text && !input.activeFocus }
}
