import QtQuick
import "components"

Flickable {
    id: root
    property var jobs: []
    property var providers: []
    property string message: ""
    property string formError: ""
    property string schedule: "Daily"
    property string provider: ""
    signal refresh()
    signal manage(var args)
    signal runTask(var job)
    signal stopTask(string session)
    signal close()
    clip: true
    contentHeight: body.height
    boundsBehavior: Flickable.StopAtBounds
    Column {
        id: body
        width: parent.width
        spacing: Theme.gap
        Row {
            width: parent.width; spacing: Theme.gap * 0.5
            Txt { text: "Tasks"; title: true; width: parent.width - reload.width - done.width - Theme.gap }
            Btn { id: reload; text: "Refresh"; onClicked: root.refresh() }
            Btn { id: done; text: "Done"; onClicked: root.close() }
        }
        Txt { width: parent.width; dim: true; text: "Scheduled and event-triggered work runs only when enabled. Changes still need your approval. Nothing is captured continuously." }
        Txt { width: parent.width; text: root.formError || root.message; visible: !!text; color: Theme.warn }
        Repeater {
            model: root.jobs
            Card {
                required property var modelData
                width: body.width
                implicitHeight: saved.height + Theme.gap * 2
                Column {
                    id: saved
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 0 }
                    spacing: Theme.gap * 0.6
                    Txt { text: modelData.label; font.weight: Font.DemiBold; width: parent.width }
                    Txt { width: parent.width; dim: true; text: (modelData.enabled ? "Enabled" : "Disabled") + " · " + (modelData.trigger === "timer" ? modelData.calendar : modelData.event + " · " + modelData.match) + " · " + (modelData.provider || "Default agent") }
                    Txt { width: parent.width; text: modelData.prompt }
                    Txt { width: parent.width; dim: true; visible: !!modelData.last; text: modelData.last ? "Last: " + modelData.last.state + (modelData.last.summary ? " · " + modelData.last.summary : "") : "" }
                    Flow {
                        width: parent.width; spacing: Theme.gap * 0.5
                        Btn { text: modelData.enabled ? "Disable" : "Enable"; onClicked: root.manage({action: modelData.enabled ? "disable" : "enable", id: modelData.id}) }
                        Btn { text: "Run"; enabled: modelData.enabled; onClicked: root.runTask(modelData) }
                        Btn { text: "Stop"; visible: !!modelData.last && modelData.last.state === "running"; onClicked: root.stopTask(modelData.last.session) }
                        Btn { text: "Remove"; onClicked: root.manage({action: "remove", id: modelData.id}) }
                    }
                }
            }
        }
        Txt { visible: root.jobs.length === 0; text: "No saved tasks. Ask Amadeus to create one, or add it below."; width: parent.width; dim: true }
        Txt { text: "New task"; label: true }
        Field { id: label; width: parent.width; placeholder: "Task name" }
        Field { id: prompt; width: parent.width; placeholder: "What should Amadeus do?" }
        Flow { width: parent.width; spacing: Theme.gap * 0.5
            Repeater { model: ["Daily", "Hourly", "App focus", "Low battery", "Network change"]
                Btn { required property string modelData; text: modelData; selected: root.schedule === modelData; onClicked: root.schedule = modelData }
            }
        }
        Field { id: when; width: parent.width; visible: root.schedule === "Daily"; text: "09:00"; placeholder: "Time (24-hour HH:MM)" }
        Field { id: match; width: parent.width; visible: root.schedule === "App focus"; placeholder: "App id, e.g. firefox (leave blank for any app)" }
        Txt { text: "Agent"; label: true }
        Flow { width: parent.width; spacing: Theme.gap * 0.5
            Btn { text: "Use default"; selected: !root.provider; onClicked: root.provider = "" }
            Repeater { model: root.providers
                Btn { required property var modelData; text: modelData.label; selected: root.provider === modelData.name; onClicked: root.provider = modelData.name }
            }
        }
        Btn {
            text: "Save disabled"; primary: true; enabled: label.text.trim() && prompt.text.trim()
            onClicked: {
                let args = { action: "save", id: "task-" + Date.now().toString(36), label: label.text.trim(), prompt: prompt.text.trim(), provider: root.provider, enabled: false }
                if (root.schedule === "Daily" || root.schedule === "Hourly") {
                    if (root.schedule === "Daily" && !/^([01][0-9]|2[0-3]):[0-5][0-9]$/.test(when.text)) { root.formError = "Enter a time as HH:MM."; return }
                    args.trigger = "timer"; args.calendar = root.schedule === "Daily" ? "*-*-* " + when.text + ":00" : "hourly"
                } else {
                    args.trigger = "event"
                    args.event = root.schedule === "App focus" ? "app-focused" : root.schedule === "Low battery" ? "battery-low" : "network-changed"
                    args.match = root.schedule === "App focus" ? match.text.trim() || "*" : "*"
                }
                root.formError = ""
                root.manage(args)
            }
        }
    }
}
