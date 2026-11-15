#!/usr/bin/python3
"""Build the login screen from the same palette and timings as the desktop."""
import json, subprocess, sys
from pathlib import Path
from xml.sax.saxutils import escape

theme = json.loads(Path(sys.argv[1]).read_text())
source, out = Path(__file__).parent, Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
for name in ("regreet.css", "background.svg"):
    text = (source / (name + ".in")).read_text()
    for key, value in theme.items():
        text = text.replace("@" + key + "@", escape(str(value)) if name.endswith(".svg") else str(value))
    (out / name).write_text(text)
subprocess.run(["rsvg-convert", str(out / "background.svg"), "-o", str(out / "background.png")], check=True)
for name, greeting in (("regreet", "Welcome back"), ("regreet-auto", "Welcome back"), ("try", "Try Amadeus OS\\nSelect Amadeus and Login · No password needed")):
    # TOML basic strings share JSON's escaping for these plain strings.
    (out / (name + ".toml")).write_text(('skip_selection = true\n' if name == 'regreet-auto' else 'skip_selection = false\n') + '''[GTK]
application_prefer_dark_theme = true
cursor_theme_name = "Adwaita"
icon_theme_name = "Adwaita"
theme_name = "Adwaita"
font_name = ''' + json.dumps(theme["font"] + " 12") + '''
[appearance]
greeting_msg = ''' + json.dumps(greeting.replace('\\n', '\n'), ensure_ascii=False) + '''
[widget.clock]
format = "%H:%M · %A, %d %B"
resolution = "1s"
[commands]
reboot = ["systemctl", "reboot"]
poweroff = ["systemctl", "poweroff"]
''')
