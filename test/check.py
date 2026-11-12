#!/usr/bin/python3
"""Fast checks that need no container: syntax, unit tests, and that the contributor
guides still match the repository. Run with ./build.sh check before every commit."""
import os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
fails = []
files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True, check=True).stdout.split()
files = [f for f in files if Path(f).exists()]


def bad(msg):
    fails.append(msg)
    print(f"FAIL  {msg}")


def shebang(f):
    try:
        return open(f, errors="replace").readline()
    except OSError:
        return ""


# 1. Syntax.
scripts = [f for f in files if re.match(r"#!.*\b(ba)?sh\b", shebang(f))]
for f in scripts:
    p = subprocess.run(["bash", "-n", f], capture_output=True, text=True)
    if p.returncode:
        bad(f"{f}: {p.stderr.strip()}")
for f in files:
    if f.endswith(".py") or "python" in shebang(f):
        try:
            compile(Path(f).read_text(), f, "exec")
        except SyntaxError as e:
            bad(f"{f}: {e}")

# 2. Every program describes itself on line 2 (ama discover shows that line).
for f in scripts:
    second = (open(f, errors="replace").read().splitlines() + ["", ""])[1]
    if not re.match(r"#\s*\S.{15,}", second):
        bad(f"{f}: line 2 must be a comment saying what the program does")

# 3. Command naming.
for d in ("desktop/bin", "iso/live"):
    for f in files:
        if f.startswith(d + "/") and re.match(r"#!", shebang(f)) and not Path(f).name.startswith("amadeus-"):
            bad(f"{f}: system commands are named amadeus-<what>")

# 4. The guides match the repository.
guides = ["AGENTS.md"] + sorted(f for f in files if f.startswith("agents/") and f.endswith(".md"))
main = Path("AGENTS.md").read_text()
top = sorted({f.split("/")[0] for f in files} - {".gitignore", "CLAUDE.md"})
for g in guides[1:]:
    if f"({g})" not in main:
        bad(f"{g} is not linked from AGENTS.md")
for entry in top:
    name = entry + "/" if Path(entry).is_dir() else entry
    if f"`{name}`" not in main and entry != "AGENTS.md":
        bad(f"AGENTS.md has no task-guide row for `{name}`")
for g in guides + ["README.md"] + sorted(f for f in files if f.startswith("docs/")):
    text = Path(g).read_text()
    for link in re.findall(r"\]\(([^)#]+)\)", text):
        if not link.startswith("http") and not (Path(g).parent / link).exists():
            bad(f"{g}: link to missing file {link}")
    for ref in re.findall(r"`([A-Za-z0-9_.][A-Za-z0-9_./-]*)`", text):
        first = ref.split("/")[0]
        if ("/" in ref or ref in top) and first in top and not Path(ref).exists():
            bad(f"{g}: names `{ref}`, which does not exist")

# 5. One palette. Files that cannot read the theme file must only use its colours.
import json
palette = {v.lstrip("#").lower() for v in json.loads(Path("desktop/theme/theme.json").read_text()).values() if isinstance(v, str) and v.startswith("#")}
for f, pattern in (("desktop/hypr/default.lua", r'rgba?\(([0-9a-fA-F]{6})'), ("desktop/skel/.config/swaylock/config", r"=([0-9a-fA-F]{6})\b"),
                   ("desktop/skel/.config/foot/foot.ini", r"^(?:background|foreground|selection-\w+)=([0-9a-fA-F]{6})"),
                   ("ai/shell/components/Theme.qml", r'"#([0-9a-fA-F]{6})"'), ("desktop/shell/shell.qml", r'"#([0-9a-fA-F]{6})"')):
    for c in set(re.findall(pattern, Path(f).read_text(), re.M)):
        if c.lower() not in palette | {"000000"}:
            bad(f"{f}: colour #{c} is not in desktop/theme/theme.json")

# 5b. The shortcut list reads the shipped desktop defaults.
p = subprocess.run([sys.executable, "desktop/bin/amadeus-keys", "--print"], capture_output=True, text=True,
                   env=dict(os.environ, AMADEUS_HYPR_CONFIG="desktop/hypr/default.lua"))
keys = p.stdout.splitlines()
if p.returncode or len(keys) < 30 or not any(l.startswith("Super + K ") for l in keys) or not any("Terminal" in l for l in keys):
    bad("desktop/bin/amadeus-keys did not list the shipped shortcuts:\n" + (p.stderr or p.stdout)[-600:])

# 6. Unit tests.
p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd="ai", capture_output=True, text=True)
print(p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "no test output")
if p.returncode:
    bad("unit tests failed:\n" + p.stderr[-2000:])

# 7. The desktop commands, run against stand-in programs in a throwaway home.
p = subprocess.run([sys.executable, "test/test_commands.py"], capture_output=True, text=True)
print(p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "no command test output")
if p.returncode:
    bad("desktop command tests failed:\n" + p.stderr[-2500:])

print(f"\n{'FAILED: ' + str(len(fails)) + ' problem(s)' if fails else 'All checks passed.'}")
sys.exit(1 if fails else 0)
