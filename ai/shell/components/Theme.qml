pragma Singleton
import QtQuick
import Quickshell

// One look for every Amadeus surface and every generated app. Values come from the
// system theme (passed in by the launcher), so everything matches and follows a theme change.
QtObject {
    function pick(name, fallback) { const v = Quickshell.env(name); return v ? v : fallback }
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
    readonly property int size: 14
    readonly property int gap: 12
    readonly property int radius: Number(pick("AMA_RADIUS", "12"))
    // Motion: short and decisive. Things arrive quickly and settle gently; nothing bounces.
    readonly property int fast: Number(pick("AMA_FAST", "110"))
    readonly property int normal: Number(pick("AMA_NORMAL", "180"))
    readonly property int slow: Number(pick("AMA_SLOW", "260"))
    readonly property int ease: Easing.OutCubic
}
