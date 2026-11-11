import QtQuick

// A labelled horizontal bar for a 0..1 value.
Column {
    id: m
    property string label: ""
    property real value: 0
    property string caption: Math.round(value * 100) + "%"
    spacing: 4
    Row { width: m.width
        Text { width: parent.width / 2; text: m.label; color: Theme.dim; font.family: Theme.font; font.pixelSize: Theme.size * 0.85 }
        Text { width: parent.width / 2; horizontalAlignment: Text.AlignRight; text: m.caption; color: Theme.fg; font.family: Theme.font; font.pixelSize: Theme.size * 0.85 }
    }
    Rectangle { width: m.width; height: 6; radius: 3; color: Theme.raised
        Rectangle { width: parent.width * Math.max(0, Math.min(1, m.value)); height: parent.height; radius: 3
                    color: m.value > 0.9 ? Theme.bad : (m.value > 0.75 ? Theme.warn : Theme.accent)
                    Behavior on width { NumberAnimation { duration: 200 } } }
    }
}
