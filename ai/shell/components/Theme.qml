pragma Singleton
import QtQuick
import Quickshell

// One palette for every Amadeus surface. Values come from the desktop theme,
// passed in by the launcher, so generated apps always match the system.
QtObject {
    function pick(name, fallback) { const v = Quickshell.env(name); return v ? v : fallback }
    readonly property color bg: pick("AMA_BG", "#1a1b26")
    readonly property color fg: pick("AMA_FG", "#c0caf5")
    readonly property color accent: pick("AMA_ACCENT", "#7aa2f7")
    readonly property color good: pick("AMA_GOOD", "#9ece6a")
    readonly property color warn: pick("AMA_WARN", "#e0af68")
    readonly property color bad: pick("AMA_BAD", "#f7768e")
    readonly property color surface: Qt.tint(bg, Qt.rgba(fg.r, fg.g, fg.b, 0.06))
    readonly property color raised: Qt.tint(bg, Qt.rgba(fg.r, fg.g, fg.b, 0.12))
    readonly property color line: Qt.rgba(fg.r, fg.g, fg.b, 0.16)
    readonly property color dim: Qt.rgba(fg.r, fg.g, fg.b, 0.6)
    readonly property string font: pick("AMA_FONT", "sans-serif")
    readonly property string mono: pick("AMA_MONO", "monospace")
    readonly property int size: 14
    readonly property int gap: 12
    readonly property int radius: 10
}
