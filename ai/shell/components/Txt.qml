import QtQuick

Text {
    textFormat: Text.PlainText
    property bool dim: false
    property bool mono: false
    property bool title: false
    property bool label: false      // names a group of controls
    color: dim || label ? Theme.dim : Theme.fg
    font.family: mono ? Theme.mono : Theme.font
    font.pixelSize: title ? Theme.size * 1.5 : label ? Theme.size * 0.78 : Theme.size
    font.capitalization: label ? Font.AllUppercase : Font.MixedCase
    font.letterSpacing: label ? 0.8 : 0
    font.weight: title ? Font.DemiBold : label ? Font.Medium : Font.Normal
    wrapMode: Text.Wrap
}
