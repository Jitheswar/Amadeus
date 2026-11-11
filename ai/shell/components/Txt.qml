import QtQuick

Text {
    property bool dim: false
    property bool mono: false
    property bool title: false
    color: dim ? Theme.dim : Theme.fg
    font.family: mono ? Theme.mono : Theme.font
    font.pixelSize: title ? Theme.size * 1.5 : Theme.size
    font.weight: title ? Font.DemiBold : Font.Normal
    wrapMode: Text.Wrap
}
