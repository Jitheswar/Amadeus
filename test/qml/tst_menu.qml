import QtQuick
import QtTest
import "../../desktop/shell" as Desktop
import "../../desktop/shell/MenuSearch.js" as Search

Item {
    id: surface
    width: 1000; height: 800
    Item { id: row; x: 20; y: 100 }
    Desktop.PointerMoveGate { id: gate; referenceItem: surface }
    TestCase {
        name: "MenuInteraction"
        when: windowShown
        function init() { gate.reset(); row.y = 100 }
        function test_stationary_pointer_after_keyboard_scroll() {
            verify(!gate.moved(row, {x: 30, y: 10}))
            verify(gate.moved(row, {x: 35, y: 10}))
            gate.reset() // An arrow key moved the selected row.
            verify(!gate.moved(row, {x: 35, y: 10}))
            row.y = 66 // Scrolling brings another delegate beneath the same screen position.
            verify(!gate.moved(row, {x: 35, y: 44}))
            verify(gate.moved(row, {x: 38, y: 44})) // Actual mouse movement resumes hover.
        }
        function test_slow_pointer_movement_accumulates() {
            verify(!gate.moved(row, {x: 30, y: 10}))
            verify(!gate.moved(row, {x: 30.5, y: 10}))
            verify(gate.moved(row, {x: 31.5, y: 10}))
        }
        function test_ranking_and_breadcrumbs() {
            const entries = [
                { id: "menu:install:Terminal", label: "Terminal", keywords: "", path: "Amadeus › Install", kind: "Menu" },
                { id: "app:foot", label: "Foot Terminal", keywords: "terminal emulator", path: "Apps", kind: "Application" },
                { id: "setting:volume", label: "Sound settings", keywords: "audio volume microphone", path: "Amadeus › Setup", kind: "Setting" }
            ]
            let result = Search.rows([], entries, "terminal", "Amadeus")
            compare(result.lines[0], "Foot Terminal\t@global:app:foot")
            compare(result.info[result.lines[1]].path, "Amadeus › Install")
            result = Search.rows(["Sound settings"], entries, "sound", "Setup")
            compare(result.lines.length, 1)
            compare(result.lines[0], "Sound settings")
            compare(Search.rows([], entries, "microphone", "Chat").lines[0], "Sound settings\t@global:setting:volume")
        }
        function test_search_does_not_match_partial_description_noise() {
            const entry = {id: "x", label: "Files", description: "Manage documents", aliases: []}
            verify(!Search.matchesQuery(entry, "doc", true))
            verify(Search.matchesQuery(entry, "documents", true))
            verify(!Search.matchesQuery(entry, "files", false))
        }
    }
}
