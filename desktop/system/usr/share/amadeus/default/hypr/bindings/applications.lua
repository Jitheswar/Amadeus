-- Essential application bindings.
o.bind("SUPER + RETURN", "Terminal", o.launch_terminal())
o.bind("SUPER + SHIFT + RETURN", "Browser", { amadeus = "browser" })
o.bind("SUPER + SHIFT + F", "File manager", { amadeus = "nautilus" })
o.bind("SUPER + ALT + SHIFT + F", "File manager (cwd)", { amadeus = "nautilus-cwd" })
o.bind("SUPER + SHIFT + B", "Browser", { amadeus = "browser" })
o.bind("SUPER + SHIFT + ALT + B", "Browser (private)", { amadeus = "browser --private" })
o.bind("SUPER + SHIFT + N", "Editor", { amadeus = "editor" })

