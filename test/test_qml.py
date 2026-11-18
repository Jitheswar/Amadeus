#!/usr/bin/python3
"""Syntax-check every QML file with Qt 6 qmllint, when it is installed.

Quickshell type warnings do not fail this syntax check. Structured diagnostics
must still be readable, so a broken checker cannot silently report success.
Run by ./build.sh check.
"""
import json, re, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANDIDATES = ("qmllint6", "/usr/lib/qt6/bin/qmllint", "/usr/lib/qt6/bin/qmllint6", "qmllint")


def find_qmllint():
    for candidate in CANDIDATES:
        found = shutil.which(candidate)
        if not found:
            continue
        try:
            p = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if p.returncode == 0 and re.search(r"\bqmllint\s+6\.", p.stdout + p.stderr):
            return found
    return None


def diagnostics(result):
    try:
        data = json.loads(result.stdout)
        files = data["files"]
        if not isinstance(files, list) or len(files) != 1:
            raise ValueError("expected one file result")
        entry = files[0]
        warnings = entry["warnings"]
        if not isinstance(entry["success"], bool) or not isinstance(warnings, list):
            raise ValueError("invalid file result")
        if result.returncode and not warnings:
            raise ValueError("the checker failed without diagnostics")
        if not entry["success"] and not warnings:
            raise ValueError("the checker did not parse the file")
        problems = []
        for warning in warnings:
            if not isinstance(warning, dict) or not isinstance(warning.get("id"), str):
                raise ValueError("unrecognized diagnostic")
            # qmllint rejects an id on a grouped property (anchor { id: ... }); the QML engine
            # accepts it, and the desktop shell relies on it to name a popup's anchor.
            if warning["id"] == "syntax" and warning.get("message") != "id declarations are only allowed in objects":
                problems.append(f"line {warning.get('line', '?')}: {warning['message']}")
        return problems
    except (ValueError, KeyError, TypeError) as error:
        return [f"qmllint diagnostics could not be read: {error}"]


def main():
    qmllint = find_qmllint()
    if not qmllint:
        print("Qt 6 qmllint is not available; QML syntax not checked", file=sys.stderr)
        return 0
    ignored = {".git", "out", "pkg", "src"}
    files = [p for p in sorted(ROOT.rglob("*.qml")) if not ignored & set(p.relative_to(ROOT).parts)]
    problems = []
    for path in files:
        try:
            p = subprocess.run([qmllint, "--ignore-settings", "--json", "-", str(path)],
                               capture_output=True, text=True, timeout=60)
            errors = diagnostics(p)
        except subprocess.TimeoutExpired:
            # qmllint never finishes on a few large files; qmlformat still proves they parse.
            fmt = Path(qmllint).with_name("qmlformat")
            p = subprocess.run([str(fmt), str(path)], capture_output=True, text=True, timeout=60) if fmt.exists() else None
            errors = [] if p is not None and p.returncode == 0 else [f"does not parse: {(p.stderr if p else 'no qmlformat').strip()[:200]}"]
        except (OSError, subprocess.SubprocessError) as error:
            errors = [f"qmllint did not finish: {error}"]
        if errors:
            problems.append(f"{path.relative_to(ROOT)}: " + "; ".join(errors[:3]))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        print(f"{len(problems)} QML file(s) could not be syntax-checked", file=sys.stderr)
        return 1
    print(f"{len(files)} QML files parse", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
