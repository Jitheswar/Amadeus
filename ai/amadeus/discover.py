"""A live map of this system, built by looking at it. Nothing here is a stored description:
commands, files, tools and settings are read from the installed packages and the running
configuration each time, so the map cannot go out of date."""
import json, os, subprocess, sys
from pathlib import Path
from . import config, __version__

PACKAGES = ("amadeus", "amadeus-desktop")


def _run(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _purpose(path):
    """A program's own description: the first comment after the interpreter line, or its module docstring."""
    try:
        lines = Path(path).read_text(errors="replace").splitlines()[1:12]
    except OSError:
        return ""
    for line in lines:
        s = line.strip()
        if s.startswith("#") and len(s) > 2 and not s.startswith("#!"):
            return s.lstrip("# ").rstrip()
        if s.startswith('"""'):
            return s.strip('"').strip()
    return ""


def _os_release():
    try:
        return dict(l.split("=", 1) for l in Path("/etc/os-release").read_text().splitlines() if "=" in l)
    except OSError:
        return {}


def build():
    from . import tools
    from .tools import system, files, shell, desktop, network, apps  # noqa: F401  (registers the tools)
    owned = {p: [f for f in _run(["pacman", "-Qlq", p]).splitlines() if not f.endswith("/")] for p in PACKAGES}
    files_all = [f for fs in owned.values() for f in fs]
    cfg = config.load()
    user_files = [config.CONFIG / "config.toml", config.CONFIG / "bar.json", config.CONFIG / "theme.json",
                  Path.home() / ".config/niri/config.kdl", Path.home() / ".config/niri/amadeus.kdl"]
    osr = _os_release()
    return {
        "system": {"name": osr.get("PRETTY_NAME", "").strip('"'), "kernel": os.uname().release, "amadeus": __version__,
                   "packages": {p: (_run(["pacman", "-Q", p]).split() or [None, None])[1] for p in PACKAGES}},
        "commands": {os.path.basename(f): _purpose(f) for f in sorted(files_all) if f.startswith("/usr/bin/")},
        "defaults_shipped_with_the_system": sorted(f for f in files_all if f.startswith(("/usr/share/amadeus-os/", "/etc/skel/")))[:60],
        "your_configuration": {str(f): ("present" if f.exists() else "not created yet") for f in user_files},
        "state": {"audit_log_and_undo": str(config.STATE), "generated_apps": str(config.APPS), "daemon_socket": str(config.SOCK)},
        "ai": {"provider": cfg["ai"]["provider"], "providers": sorted(cfg["providers"])},
        "policy": {k: v for k, v in cfg.get("policy", {}).items() if isinstance(v, str)},
        "tools": [{"name": t["name"], "capability": "depends on arguments" if callable(t["cap"]) else t["cap"], "risk": "depends on arguments" if callable(t["risk"]) else t["risk"],
                   "does": t["description"]} for t in tools.REGISTRY.values()],
        "explore_further": {
            "every file a package installed": "pacman -Qlq amadeus amadeus-desktop",
            "what a command does": "<command> --help, or read it: these are short scripts",
            "packages installed on purpose": "pacman -Qqe",
            "the desktop right now": "niri msg --json windows | workspaces | outputs",
            "every desktop action and setting": "niri msg action --help; niri validate checks a config",
            "what the AI has done": "ama audit; ama audit verify",
            "snapshots": "amadeus-rollback",
            "health": "ama doctor",
        },
    }


def main(argv):
    m = build()
    if "--json" in argv:
        return print(json.dumps(m, indent=2))
    for section, body in m.items():
        print(f"\n{section.replace('_', ' ').upper()}")
        if section == "tools":
            for t in body:
                print(f"  {t['name']:<22} {t['capability']:<16} {t['risk']:<20} {t['does'][:80]}")
        elif isinstance(body, dict):
            for k, v in body.items():
                print(f"  {k:<34} {v if not isinstance(v, (dict, list)) else json.dumps(v)}")
        else:
            for v in body:
                print(f"  {v}")
