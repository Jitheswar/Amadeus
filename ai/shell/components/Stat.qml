import QtQuick

Column {
    property string label: ""
    property string value: ""
    property color tone: Theme.fg
    spacing: 2
    Text { text: parent.label; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.size * 0.85 }
    Text { text: parent.value; color: parent.tone; font.family: Theme.font; font.pixelSize: Theme.size * 1.7; font.weight: Font.DemiBold }
}
