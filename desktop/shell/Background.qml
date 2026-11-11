import QtQuick
import Quickshell
import Quickshell.Wayland

// The desktop background, drawn by the shell: warm black with two soft glows in the
// accent colours. No image file and no wallpaper program; it follows the theme.
Scope {
    id: back
    required property var style
    Variants {
        model: Quickshell.screens
        PanelWindow {
            required property var modelData
            screen: modelData
            anchors { top: true; bottom: true; left: true; right: true }
            exclusionMode: ExclusionMode.Ignore
            WlrLayershell.layer: WlrLayer.Background
            color: back.style.bg
            Canvas {
                id: art
                anchors.fill: parent
                readonly property color a: back.style.accent
                readonly property color b: back.style.accent2
                onAChanged: requestPaint()
                onBChanged: requestPaint()
                onPaint: {
                    const c = getContext("2d"), w = width, h = height
                    c.clearRect(0, 0, w, h)
                    function glow(x, y, r, col, strength) {
                        const g = c.createRadialGradient(x, y, 0, x, y, r)
                        g.addColorStop(0, Qt.rgba(col.r, col.g, col.b, strength))
                        g.addColorStop(0.5, Qt.rgba(col.r, col.g, col.b, strength * 0.35))
                        g.addColorStop(1, Qt.rgba(col.r, col.g, col.b, 0))
                        c.fillStyle = g
                        c.fillRect(0, 0, w, h)
                    }
                    glow(w * 0.16, h * 1.05, h * 0.95, a, 0.20)
                    glow(w * 0.92, h * -0.10, h * 0.80, b, 0.12)
                }
            }
        }
    }
}
