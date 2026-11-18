#!/usr/bin/python3
"""Exercise menu ranking and pointer movement in the real QML engine."""
import os, shutil, subprocess, sys
from pathlib import Path

runner = shutil.which("qmltestrunner") or "/usr/lib/qt6/bin/qmltestrunner"
if not Path(runner).exists():
    print("Qt Quick Test unavailable; menu interaction tests not run")
    sys.exit(0)
result = subprocess.run([runner, "-input", str(Path(__file__).parent / "qml"), "-o", "-,txt"],
                        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software"),
                        capture_output=True, text=True, timeout=45)
print(result.stdout.strip())
if result.returncode:
    print(result.stderr.strip(), file=sys.stderr)
sys.exit(result.returncode)
