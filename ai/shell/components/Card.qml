import QtQuick

Rectangle {
    default property alias content: inner.data
    property int pad: Theme.gap
    color: Theme.surface
    border.color: Theme.line
    border.width: 1
    radius: Theme.radius
    implicitWidth: inner.childrenRect.width + pad * 2
    implicitHeight: inner.childrenRect.height + pad * 2
    Item { id: inner; anchors.fill: parent; anchors.margins: parent.pad }
}
