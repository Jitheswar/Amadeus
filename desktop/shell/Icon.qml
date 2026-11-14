import QtQuick
import QtQuick.Shapes

// The system's icons: one family of line drawings on a 24-unit grid, drawn as vectors so
// they stay sharp at any size and take any colour. A new icon is one more named path here,
// in the same style: 1.8 stroke, round ends, no fills. Shapes after Feather Icons (MIT).
Item {
    id: icon
    property string name: ""
    property color color: "white"
    property real size: 18
    property real weight: 1.8
    width: size; height: size
    readonly property var paths: ({
        "wifi": "M5 12.55a11 11 0 0 1 14.08 0 M1.42 9a16 16 0 0 1 21.16 0 M8.53 16.11a6 6 0 0 1 6.95 0 M12 20h.01",
        "wifi-off": "M2 2l20 20 M16.72 11.06A10.94 10.94 0 0 1 19 12.55 M5 12.55a10.94 10.94 0 0 1 5.17-2.39 M10.71 5.05A16 16 0 0 1 22.58 9 M1.42 9a15.91 15.91 0 0 1 4.7-2.88 M8.53 16.11a6 6 0 0 1 6.95 0 M12 20h.01",
        "wired": "M9 2h6v6H9z M3 16h6v6H3z M15 16h6v6h-6z M12 8v4 M6 16v-4h12v4",
        "bluetooth": "M6.5 6.5l11 11L12 23V1l5.5 5.5-11 11",
        "bluetooth-off": "M6.5 6.5l11 11L12 23v-9 M12 9V1l5.5 5.5-2.7 2.7 M2 2l20 20",
        "volume": "M11 5L6 9H2v6h4l5 4V5z M15.54 8.46a5 5 0 0 1 0 7.07 M19.07 4.93a10 10 0 0 1 0 14.14",
        "volume-low": "M11 5L6 9H2v6h4l5 4V5z M15.54 8.46a5 5 0 0 1 0 7.07",
        "volume-off": "M11 5L6 9H2v6h4l5 4V5z M23 9l-6 6 M17 9l6 6",
        "sun": "M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 1v2 M12 21v2 M4.22 4.22l1.42 1.42 M18.36 18.36l1.42 1.42 M1 12h2 M21 12h2 M4.22 19.78l1.42-1.42 M18.36 5.64l1.42-1.42",
        "display": "M2 4h20v12H2z M8 21h8 M12 16v5",
        "mic": "M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z M19 10v2a7 7 0 0 1-14 0v-2 M12 19v4 M8 23h8",
        "battery": "M3 7h14a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z M23 13v-2",
        "bolt": "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
        "leaf": "M11 20A7 7 0 0 1 4 13C4 7 9 4 20 3c0 9-2 17-9 17z M4 21c2-6 6-9 11-11",
        "scale": "M12 3v18 M5 7h14 M5 7l-3 7a3.5 3.5 0 0 0 6 0L5 7z M19 7l-3 7a3.5 3.5 0 0 0 6 0l-3-7z M8 21h8",
        "coffee": "M18 8h1a4 4 0 0 1 0 8h-1 M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z M6 1v3 M10 1v3 M14 1v3",
        "lock": "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z M7 11V7a5 5 0 0 1 10 0v4",
        "unlock": "M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z M7 11V7a5 5 0 0 1 9.9-1",
        "cloud": "M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z",
        "rain": "M16 13v8 M8 13v8 M12 15v8 M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25",
        "layers": "M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5",
        "left": "M15 18l-6-6 6-6",
        "right": "M9 18l6-6-6-6",
        "check": "M20 6L9 17l-5-5",
        "record": "M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 2a10 10 0 1 0 0 20a10 10 0 1 0 0-20z",
        "camera": "M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z M12 9a4 4 0 1 0 0 8a4 4 0 1 0 0-8z",
        "power": "M18.36 6.64a9 9 0 1 1-12.73 0 M12 2v10"
    })
    Shape {
        width: 24; height: 24
        scale: icon.size / 24
        transformOrigin: Item.TopLeft
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            strokeColor: icon.color
            strokeWidth: icon.weight
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: icon.paths[icon.name] || "" }
        }
    }
    Behavior on color { ColorAnimation { duration: 110 } }
}
