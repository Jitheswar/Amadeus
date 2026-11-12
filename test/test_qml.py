#!/usr/bin/python3
"""Syntax-check every QML file with qmllint, when it is installed.

qmllint reports a real syntax error with a [syntax] line. Other warnings need the
Quickshell types, which qmllint does not load outside a session, so only syntax is
treated as a failure. Run by ./build.sh check."""
import shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ("qmllint", "qmllint6", "/usr/lib/qt6/bin/qmllint", "/usr/lib/qt6/bin/qmllint6")


def find_qmllint():
    for candidate in CANDIDATES:
        found = shutil.which(candidate)
        if found:
            return found
        if Path(candidate).is_file():
            return candidate
    return None


def main():
    qmllint = find_qmllint()
    if not qmllint:
        print("qmllint is not installed; QML syntax not checked", file=sys.stderr)
        return 0
    files = sorted(ROOT.rglob("*.qml"))
    problems = []
    for path in files:
        p = subprocess.run([qmllint, str(path)], capture_output=True, text=True, timeout=30)
        syntax = [line for line in (p.stdout + p.stderr).splitlines() if "[syntax]" in line]
        if syntax:
            problems.append(f"{path.relative_to(ROOT)}: " + "; ".join(syntax[:3]))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print(f"{len(problems)} QML file(s) do not parse", file=sys.stderr)
        return 1
    print(f"{len(files)} QML files parse", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
