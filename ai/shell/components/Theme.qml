pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// One look for every Amadeus surface and every generated app. Values come from the
// system theme (passed in by the launcher), so everything matches and follows a theme change.
QtObject {
    // The personal theme file wins and is followed live, so a theme change reaches an open panel.
    function pick(name, fallback) { const own = personal[name.slice(4).toLowerCase()]; const v = Quickshell.env(name); return own ? own : v ? v : fallback }
    readonly property color bg: pick("AMA_BG", "#0f0e0d")
    readonly property color surface: pick("AMA_SURFACE", "#191715")
    readonly property color raised: pick("AMA_RAISED", "#26221e")
    readonly property color line: pick("AMA_LINE", "#342f29")
    readonly property color fg: pick("AMA_FG", "#f1ebe1")
    readonly property color dim: pick("AMA_DIM", "#9c948a")
    readonly property color accent: pick("AMA_ACCENT", "#ffa14a")
    readonly property color accent2: pick("AMA_ACCENT2", "#ff6f3c")
    readonly property color good: pick("AMA_GOOD", "#8fd19e")
    readonly property color warn: pick("AMA_WARN", "#f4c35b")
    readonly property color bad: pick("AMA_BAD", "#ff6b5e")
    readonly property string font: pick("AMA_FONT", "Inter")
    readonly property string mono: pick("AMA_MONO", "JetBrains Mono")
    property var personal: ({})
    property QtObject personalFile: FileView {
        path: Quickshell.env("XDG_CONFIG_HOME") ? Quickshell.env("XDG_CONFIG_HOME") + "/amadeus/theme.json" : Quickshell.env("HOME") + "/.config/amadeus/theme.json"
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: { try { personal = JSON.parse(text()) } catch (e) { personal = ({}) } }
        onLoadFailed: personal = ({})
    }
    readonly property int size: Math.max(9, Math.min(20, Number(personal.font_size || pick("AMA_FONT_SIZE", "14")) || 14))
    readonly property int gap: 12
    readonly property int radius: Number(pick("AMA_RADIUS", "12"))
    // Motion: short and decisive. Things arrive quickly and settle gently; nothing bounces.
    readonly property int fast: Number(pick("AMA_FAST", "110"))
    readonly property int normal: Number(pick("AMA_NORMAL", "180"))
    readonly property int slow: Number(pick("AMA_SLOW", "260"))
    readonly property int ease: Easing.OutCubic
}
