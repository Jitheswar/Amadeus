import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import Quickshell.Wayland

// Desktop notifications, shown by the shell itself: cards in the top right corner that
// slide in, make room for each other, and fade out. Click one to dismiss it.
// Urgent ones stay until dismissed.
Scope {
    id: notes
    required property var style
    readonly property int count: server.trackedNotifications.values.length

    NotificationServer {
        id: server
        bodySupported: true
        actionsSupported: true
        onNotification: n => { n.tracked = true }
    }

    PanelWindow {
        visible: notes.count > 0 || cards.contentHeight > 1
        anchors { top: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        WlrLayershell.layer: WlrLayer.Overlay
        implicitWidth: 404
        implicitHeight: Math.max(1, cards.contentHeight + 66)
        color: "transparent"

        ListView {
            id: cards
            x: 12; y: 54
            width: parent.width - 24
            height: contentHeight
            spacing: 10
            interactive: false
            model: server.trackedNotifications
            add: Transition { ParallelAnimation {
                NumberAnimation { property: "x"; from: 48; to: 0; duration: notes.style.normal; easing.type: Easing.OutCubic }
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: notes.style.fast } } }
            remove: Transition { ParallelAnimation {
                NumberAnimation { property: "opacity"; to: 0; duration: notes.style.fast }
                NumberAnimation { property: "x"; to: 24; duration: notes.style.fast; easing.type: Easing.InCubic } } }
            displaced: Transition { NumberAnimation { properties: "y"; duration: notes.style.normal; easing.type: Easing.OutCubic } }
            delegate: Rectangle {
                id: card
                required property var modelData
                readonly property bool urgent: modelData.urgency === NotificationUrgency.Critical
                width: cards.width
                height: body.implicitHeight + 28
                radius: notes.style.radius
                color: over.containsMouse ? notes.style.raised : notes.style.surface
                border.color: urgent ? notes.style.warn : notes.style.line
                border.width: 1
                Behavior on color { ColorAnimation { duration: notes.style.fast } }
                Rectangle { width: 3; radius: 2; color: card.urgent ? notes.style.warn : notes.style.accent
                            anchors { left: parent.left; top: parent.top; bottom: parent.bottom; leftMargin: 8; topMargin: 14; bottomMargin: 14 } }
                MouseArea { id: over; anchors.fill: parent; hoverEnabled: true; onClicked: card.modelData.dismiss() }
                // The countdown waits while the pointer is on the card.
                Timer { interval: card.modelData.expireTimeout > 0 ? card.modelData.expireTimeout * 1000 : 6000
                        running: !card.urgent && !over.containsMouse; onTriggered: card.modelData.expire() }
                Column {
                    id: body
                    anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: 22; rightMargin: 16; topMargin: 14 }
                    spacing: 3
                    Text { width: parent.width; text: card.modelData.appName.toUpperCase(); visible: text !== ""; color: notes.style.dim
                           font.family: notes.style.font; font.pixelSize: 10; font.letterSpacing: 0.8; font.weight: Font.Medium; elide: Text.ElideRight }
                    Text { width: parent.width; text: card.modelData.summary; color: notes.style.fg; wrapMode: Text.Wrap
                           font.family: notes.style.font; font.pixelSize: 14; font.weight: Font.DemiBold }
                    Text { width: parent.width; text: card.modelData.body; visible: text !== ""; color: notes.style.fg; opacity: 0.82
                           font.family: notes.style.font; font.pixelSize: 13; lineHeight: 1.2
                           wrapMode: Text.Wrap; textFormat: Text.PlainText; maximumLineCount: 6; elide: Text.ElideRight }
                    Row {
                        spacing: 8
                        topPadding: 6
                        visible: card.modelData.actions.length > 0
                        Repeater {
                            model: card.modelData.actions
                            Rectangle {
                                id: act
                                required property var modelData
                                width: label.implicitWidth + 20; height: 26; radius: 13
                                color: tap.containsMouse ? notes.style.accent : notes.style.raised
                                Behavior on color { ColorAnimation { duration: notes.style.fast } }
                                Text { id: label; anchors.centerIn: parent; text: act.modelData.text; font.family: notes.style.font; font.pixelSize: 12
                                       color: tap.containsMouse ? notes.style.bg : notes.style.fg }
                                MouseArea { id: tap; anchors.fill: parent; hoverEnabled: true; onClicked: act.modelData.invoke() }
                            }
                        }
                    }
                }
            }
        }
    }
}
