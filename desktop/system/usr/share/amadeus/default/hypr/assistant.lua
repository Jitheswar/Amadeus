-- The Amadeus assistant and what the system adds to the desktop around it.

-- The side panel, and asking about what is on screen. Super+A stays "select all", like the
-- rest of the universal copy, paste and select shortcuts.
o.bind("SUPER + Z", "Amadeus panel", "ama panel")
o.bind("SUPER + SHIFT + Z", "Ask Amadeus about this window", "ama panel window")
o.bind("SUPER + ALT + A", "Ask Amadeus about selected text", "ama panel selection")
o.bind("SUPER + SHIFT + ESCAPE", "Stop all Amadeus tasks", "ama stop")

-- Approval prompts and the assistant's own windows float in the centre.
o.window({ class = "^org\\.quickshell$", title = "^Amadeus" }, { float = true, center = true })

hl.on("hyprland.start", function()
  -- Audio fixes this computer's hardware needs (ASUS mixer, AMD microphones, Dell XPS speaker
  -- tuning). Once per user: it needs the audio server, so it cannot run at install.
  hl.exec_cmd("amadeus-hardware user --once")
end)
