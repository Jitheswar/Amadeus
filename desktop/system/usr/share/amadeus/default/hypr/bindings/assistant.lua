-- The assistant's side panel, and asking about what is on screen. Super+A stays "select all",
-- like the rest of the universal copy, paste and select shortcuts.
o.bind("SUPER + Z", "Amadeus panel", "ama panel")
o.bind("SUPER + SHIFT + Z", "Ask Amadeus about this window", "ama panel window")
o.bind("SUPER + ALT + A", "Ask Amadeus about selected text", "ama panel selection")
o.bind("SUPER + SHIFT + ESCAPE", "Stop all Amadeus tasks", "ama stop")
