import QtQuick
import Quickshell
import Quickshell.Services.Notifications
import Quickshell.Wayland

// Desktop notifications, shown by the shell itself: cards in the top right corner.
// Click a card to dismiss it. Urgent ones stay until dismissed.
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
        visible: notes.count > 0
        anchors { top: true; right: true }
        exclusionMode: ExclusionMode.Ignore
        implicitWidth: 396
        implicitHeight: Math.max(1, cards.implicitHeight + 16)
        color: "transparent"

        Column {
            id: cards
            x: 8; y: 8
            width: parent.width - 16
            spacing: 8
            Repeater {
                model: server.trackedNotifications
                Rectangle {
                    id: card
                    required property var modelData
                    readonly property bool urgent: modelData.urgency === NotificationUrgency.Critical
                    width: cards.width
                    height: body.implicitHeight + 24
                    radius: 10
                    color: notes.style.bg
                    border.color: urgent ? notes.style.warn : notes.style.accent
                    border.width: urgent ? 2 : 1
                    MouseArea { anchors.fill: parent; onClicked: card.modelData.dismiss() }
                    Timer { interval: card.modelData.expireTimeout > 0 ? card.modelData.expireTimeout * 1000 : 6000
                            running: !card.urgent; onTriggered: card.modelData.expire() }
                    Column {
                        id: body
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 12 }
                        spacing: 4
                        Text { width: parent.width; text: card.modelData.appName; visible: text !== ""; color: notes.style.dim; font.pixelSize: 11; elide: Text.ElideRight }
                        Text { width: parent.width; text: card.modelData.summary; color: notes.style.fg; font.pixelSize: 13; font.bold: true; wrapMode: Text.Wrap }
                        Text { width: parent.width; text: card.modelData.body; visible: text !== ""; color: notes.style.fg; font.pixelSize: 12
                               wrapMode: Text.Wrap; textFormat: Text.PlainText; maximumLineCount: 6; elide: Text.ElideRight }
                        Row {
                            spacing: 8
                            visible: card.modelData.actions.length > 0
                            Repeater {
                                model: card.modelData.actions
                                Rectangle {
                                    required property var modelData
                                    width: label.implicitWidth + 16; height: 22; radius: 5; color: notes.style.muted
                                    Text { id: label; anchors.centerIn: parent; text: parent.modelData.text; color: notes.style.fg; font.pixelSize: 12 }
                                    MouseArea { anchors.fill: parent; onClicked: parent.modelData.invoke() }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
