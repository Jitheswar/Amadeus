-- The Amadeus assistant and what the system adds to the desktop around it.

-- Shortcuts and settings the assistant adds on your behalf (desktop_keybind, desktop_config).
require("default.hypr.require_optional").module("hypr.amadeus")

-- Approval prompts and the assistant's own windows float in the centre.
o.window({ class = "^org\\.quickshell$", title = "^Amadeus" }, { float = true, center = true })
