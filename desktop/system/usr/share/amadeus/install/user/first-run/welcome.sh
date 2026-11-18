# The catalog entry holds a real newline, not a literal \n: the card renders the
# body as it arrives, and elides past three lines.
amadeus-notification-send -u critical -g  "$(amadeus-i18n firstRun.keybindingsTitle)" \
  "$(amadeus-i18n firstRun.keybindingsBody)" \
  --exec amadeus-menu-keybindings
