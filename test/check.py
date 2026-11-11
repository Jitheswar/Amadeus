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

# 5. Unit tests.
p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd="ai", capture_output=True, text=True)
print(p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "no test output")
if p.returncode:
    bad("unit tests failed:\n" + p.stderr[-2000:])

print(f"\n{'FAILED: ' + str(len(fails)) + ' problem(s)' if fails else 'All checks passed.'}")
sys.exit(1 if fails else 0)
