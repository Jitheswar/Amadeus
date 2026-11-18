import QtQuick
import Quickshell
import "components"

Item {
    id: settings
    property var options: []
    property string selected: ""
    property string defaultName: ""
    property string message: ""
    property string kind: "Subscription"
    property bool editing: false
    property string apiType: "openai"
    readonly property var chosen: options.find(p => p.name === selected) || ({})
    property var tune: null
    property string effort: ""
    onChosenChanged: { if (chosen.kind) kind = chosen.kind; reset() }
    onTuneChanged: reset()
    function reset() { tuneModel.text = (tune || chosen).model || ""; effort = (tune || chosen).effort || "" }
    signal saveTune(string name, string model, string effort)
    signal tuneOnce(string model, string effort)
    signal choose(string name)
    signal makeDefault(string name)
    signal saveApi(string name, var fields, string key)
    signal refresh()
    signal close()
    function configure(add) {
        editing = true
        apiName.text = add ? "my-api" : chosen.name || "my-api"
        apiType = add ? "openai" : chosen.type || "openai"
        model.text = add ? "" : chosen.model || ""
        address.text = add ? "https://api.openai.com/v1" : chosen.base_url || (apiType === "anthropic" ? "https://api.anthropic.com" : "https://api.openai.com/v1")
        key.text = ""
    }
    function install() {
        const names = { "claude-cli": "claude", "codex-cli": "codex", "antigravity-cli": "antigravity-cli" }
        const name = names[chosen.type]
        if (name) Quickshell.execDetached(["xdg-terminal-exec", "amadeus-harness", "install", name])
    }
    function signIn() {
        const commands = { "claude-cli": ["claude", "auth", "login"], "codex-cli": ["codex", "login"], "antigravity-cli": ["agy"] }
        if (commands[chosen.type]) Quickshell.execDetached(["xdg-terminal-exec"].concat(commands[chosen.type]))
    }
    Flickable {
        anchors.fill: parent
        clip: true
        contentHeight: body.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        Column {
            id: body; width: parent.width; spacing: Theme.gap
            Row {
                width: parent.width; spacing: Theme.gap
                Txt { text: "Agent settings"; title: true; width: parent.width - done.width - Theme.gap }
                Btn { id: done; text: "Done"; onClicked: settings.close() }
            }
            Txt { width: parent.width; dim: true; text: "Choose an agent for the next request, or save it as the default for Amadeus." }
            Row {
                spacing: Theme.gap * 0.5
                Repeater { model: ["Subscription", "API", "Local"]
                    Btn { required property string modelData; text: modelData; selected: settings.kind === modelData
                          onClicked: { settings.kind = modelData; settings.editing = false } }
                }
            }
            Repeater {
                model: settings.options.filter(p => p.kind === settings.kind)
                Rectangle {
                    required property var modelData
                    width: body.width; height: info.implicitHeight + Theme.gap * 1.4
                    radius: Theme.radius; color: settings.selected === modelData.name ? Theme.raised : Theme.surface
                    border.width: 1; border.color: settings.selected === modelData.name ? Theme.accent : Theme.line
                    Column { id: info; anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: Theme.gap * 0.7 }
                        Txt { text: modelData.label + (modelData.name === settings.defaultName ? " · default" : "") }
                        Txt { dim: true; font.pixelSize: Theme.size * 0.85
                              text: modelData.model || (modelData.ready ? "Installed · use the CLI's existing sign-in" : "Setup required") }
                    }
                    MouseArea { anchors.fill: parent; onClicked: settings.choose(modelData.name) }
                }
            }
            Row {
                spacing: Theme.gap * 0.5
                Btn { text: "Set as default"; enabled: !!settings.chosen.name; onClicked: settings.makeDefault(settings.selected) }
                Btn { text: "Use default"; enabled: settings.selected !== settings.defaultName; onClicked: settings.choose("") }
                Btn { text: "Refresh"; onClicked: settings.refresh() }
            }
            Column {
                visible: !!settings.chosen.name; width: parent.width; spacing: Theme.gap * 0.6
                Txt { text: "Model"; label: true }
                Field { id: tuneModel; width: parent.width; placeholder: settings.chosen.kind === "Subscription" ? "Blank uses the agent's own default" : "Model name from your provider" }
                Txt { text: "Reasoning effort"; label: true; visible: (settings.chosen.effort_levels || []).length > 0 }
                Flow {
                    visible: (settings.chosen.effort_levels || []).length > 0
                    width: parent.width; spacing: Theme.gap * 0.5
                    Repeater { model: [""].concat(settings.chosen.effort_levels || [])
                        Btn { required property string modelData; text: modelData || "Default"; selected: settings.effort === modelData
                              onClicked: settings.effort = modelData }
                    }
                }
                Row { spacing: Theme.gap * 0.5
                    Btn { text: "Use for next request"; onClicked: settings.tuneOnce(tuneModel.text.trim(), settings.effort) }
                    Btn { text: "Save"; primary: true; onClicked: settings.saveTune(settings.selected, tuneModel.text.trim(), settings.effort) }
                }
            }
            Row {
                visible: settings.chosen.kind === "Subscription"; spacing: Theme.gap * 0.5
                Btn { text: "Install"; onClicked: settings.install() }
                Btn { text: "Sign in"; onClicked: settings.signIn() }
            }
            Row {
                visible: settings.kind !== "Subscription"; spacing: Theme.gap * 0.5
                Btn { text: "Configure selected"; enabled: settings.chosen.kind !== "Subscription"; onClicked: settings.configure(false) }
                Btn { text: "Add API"; onClicked: settings.configure(true) }
            }
            Column {
                visible: settings.editing; width: parent.width; spacing: Theme.gap * 0.6
                Txt { text: "Provider name"; label: true }
                Field { id: apiName; width: parent.width; placeholder: "my-api" }
                Row { spacing: Theme.gap * 0.5
                    Btn { text: "OpenAI compatible"; selected: settings.apiType === "openai"; onClicked: settings.apiType = "openai" }
                    Btn { text: "Claude API"; selected: settings.apiType === "anthropic"; onClicked: { settings.apiType = "anthropic"; address.text = "https://api.anthropic.com" } }
                }
                Txt { text: "Model"; label: true }
                Field { id: model; width: parent.width; placeholder: "Model name from your provider" }
                Txt { text: "Server address"; label: true }
                Field { id: address; width: parent.width; placeholder: "https://api.openai.com/v1" }
                Txt { text: "API key"; label: true }
                Field { id: key; width: parent.width; placeholder: "Leave blank to keep the saved key"; input.echoMode: TextInput.Password }
                Btn { text: "Save settings"; primary: true; onClicked: {
                    settings.saveApi(apiName.text.trim(), { type: settings.apiType, model: model.text.trim(), base_url: address.text.trim() }, key.text)
                    key.text = ""
                } }
            }
            Txt { width: parent.width; text: settings.message; color: Theme.warn; visible: text !== "" }
        }
    }
}
