"""Dynamic application framework.

An app is a directory of QML built from the shared component library, plus a
manifest that declares everything it may touch. Apps run under bubblewrap with
exactly those grants; with an empty manifest an app can draw a window and keep
private data, nothing else. Each app is a git repository, so an update is a
small commit and any version can be restored."""
import json, os, re, shutil, subprocess, tomllib, time
from pathlib import Path
from . import config
from .sandbox import bwrap

ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
FILE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,80}\.(qml|js|json|txt|md|svg)$")
COMPONENTS = config.SHARE / "shell" / "components"
EMPTY = {"network": False, "nvidia": False, "ai": False, "files": [], "tools": []}


class AppError(Exception):
    pass


def app_dir(app_id):
    if not ID_RE.match(app_id or ""):
        raise AppError("app id must be lowercase letters, digits and dashes")
    return config.APPS / app_id


def _git(d, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="Amadeus", GIT_AUTHOR_EMAIL="amadeus@localhost",
               GIT_COMMITTER_NAME="Amadeus", GIT_COMMITTER_EMAIL="amadeus@localhost")
    return subprocess.run(["git", "-C", str(d), "-c", "commit.gpgsign=false", *args], capture_output=True, text=True, env=env)


def normalise(perms):
    p = dict(EMPTY, **(perms or {}))
    unknown = set(p) - set(EMPTY)
    if unknown:
        raise AppError(f"unknown permissions: {sorted(unknown)}")
    files = []
    for f in p["files"]:
        if f.get("mode", "ro") not in ("ro", "rw") or not f.get("path"):
            raise AppError("files entries need a path and mode ro|rw")
        files.append({"path": f["path"], "mode": f.get("mode", "ro")})
    return {"network": bool(p["network"]), "nvidia": bool(p["nvidia"]), "ai": bool(p["ai"]), "files": files, "tools": sorted(set(p["tools"]))}


def exceeds(new, old):
    """True if `new` grants anything `old` did not. Used to decide whether to ask."""
    if (new["network"] and not old["network"]) or (new["nvidia"] and not old["nvidia"]) or (new["ai"] and not old["ai"]):
        return True
    if set(new["tools"]) - set(old["tools"]):
        return True
    have = {(f["path"], f["mode"]) for f in old["files"]} | {(f["path"], "ro") for f in old["files"] if f["mode"] == "rw"}
    return any((f["path"], f["mode"]) not in have for f in new["files"])


def manifest(app_id):
    f = app_dir(app_id) / "manifest.json"
    if not f.exists():
        raise AppError(f"no app named {app_id}")
    return json.loads(f.read_text())


def list_apps():
    out = []
    for d in sorted(config.APPS.glob("*/manifest.json")):
        m = json.loads(d.read_text())
        out.append({"id": m["id"], "name": m["name"], "description": m.get("description", ""), "version": m["version"], "permissions": m["permissions"]})
    return out


def _write_files(d, files):
    for rel, content in files.items():
        if not FILE_RE.match(rel) or ".." in rel or rel.startswith(("Amadeus/", "data/", ".git")) or rel == "manifest.json":
            raise AppError(f"file name not allowed: {rel}")
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            p.unlink(missing_ok=True)
        else:
            p.write_text(content)


def lint(d):
    """Static check so a broken update is rejected before it replaces a working app."""
    if not (d / "shell.qml").exists():
        return "shell.qml (the entry point) is missing"
    qmllint = shutil.which("qmllint6") or shutil.which("qmllint") or "/usr/lib/qt6/bin/qmllint"
    if not os.path.exists(qmllint):
        return ""
    problems = []
    for f in d.rglob("*.qml"):
        if "Amadeus" in f.relative_to(d).parts:
            continue
        p = subprocess.run([qmllint, str(f)], capture_output=True, text=True)
        lines = (p.stdout + p.stderr).splitlines()
        errs = [l.split(": ", 1)[-1] for l in lines if l.rstrip().endswith("[syntax]")]
        if errs:
            problems.append(f"{f.name}: " + "; ".join(errs[:3]))
    return "\n".join(problems)


def save(app_id, name=None, description=None, files=None, permissions=None, note=""):
    """Create an app or apply an incremental update. Returns the manifest."""
    d = app_dir(app_id)
    new = not d.exists()
    if new:
        if not name or not files or "shell.qml" not in files:
            raise AppError("a new app needs a name and a shell.qml file")
        (d / "Amadeus").mkdir(parents=True)      # mount point for the component library
        (d / "data").mkdir()
        (d / ".gitignore").write_text("data/\nAmadeus/\n")
        _git(d, "init", "-q", "-b", "main")
        m = {"id": app_id, "name": name, "description": description or "", "version": 0, "permissions": dict(EMPTY)}
    else:
        m = manifest(app_id)
    try:
        _write_files(d, files or {})
        problems = lint(d)
        if problems:
            raise AppError("QML does not parse:\n" + problems)
    except AppError:
        if new:
            shutil.rmtree(d)
        else:
            _git(d, "checkout", "-q", "--", ".")
            _git(d, "clean", "-qfd")
        raise
    m.update(name=name or m["name"], description=description if description is not None else m["description"], version=m["version"] + 1)
    if permissions is not None:
        m["permissions"] = normalise(permissions)
    (d / "manifest.json").write_text(json.dumps(m, indent=2) + "\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", f"v{m['version']}: {note or ('create' if new else 'update')}")
    _desktop_entry(m)
    return m


def history(app_id):
    return _git(app_dir(app_id), "log", "--format=%h %ad %s", "--date=short", "-n", "30").stdout.splitlines()


def rollback(app_id, version=None):
    d = app_dir(app_id)
    m = manifest(app_id)
    target = int(version) if version else m["version"] - 1
    log = _git(d, "log", "--format=%H %s").stdout.splitlines()
    commit = next((l.split()[0] for l in log if l.split()[1] == f"v{target}:"), None)
    if not commit:
        raise AppError(f"no version {target}")
    _git(d, "checkout", "-q", commit, "--", ".")
    old = manifest(app_id)
    old["version"] = m["version"] + 1          # history only moves forward
    (d / "manifest.json").write_text(json.dumps(old, indent=2) + "\n")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", f"v{old['version']}: restore v{target}")
    return old


def remove(app_id):
    d = app_dir(app_id)
    if not d.exists():
        raise AppError(f"no app named {app_id}")
    trash = config.STATE / "removed-apps" / f"{app_id}-{int(time.time())}"
    trash.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(trash))
    (Path.home() / f".local/share/applications/amadeus-{app_id}.desktop").unlink(missing_ok=True)
    return str(trash)


def _desktop_entry(m):
    if os.environ.get("AMADEUS_DATA"):      # test and development runs stay out of the real launcher
        return
    f = Path.home() / f".local/share/applications/amadeus-{m['id']}.desktop"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"[Desktop Entry]\nType=Application\nName={m['name']}\nComment={m['description']}\n"
                 f"Exec=ama app run {m['id']}\nIcon=applications-other\nCategories=Utility;Amadeus;\n")


def theme_env():
    env = {}
    f = config.CONFIG / "theme.toml"
    f = f if f.exists() else None
    try:
        c = tomllib.loads(f.read_text()) if f else {}
        pairs = {"AMA_BG": "background", "AMA_FG": "foreground", "AMA_ACCENT": "accent", "AMA_GOOD": "color2", "AMA_WARN": "color3", "AMA_BAD": "color1"}
        env = {k: c[v] for k, v in pairs.items() if isinstance(c.get(v), str)}
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return env


def command(app_id, sock_path=None):
    """The exact sandboxed command line for an app; this is the whole trust boundary."""
    d = app_dir(app_id)
    perms = manifest(app_id)["permissions"]
    env = theme_env()
    ro = [d, COMPONENTS]
    rw = [d / "data"]
    for f in perms["files"]:
        (rw if f["mode"] == "rw" else ro).append(os.path.expanduser(f["path"]))
    argv = bwrap(["quickshell", "-p", str(d / "shell.qml")], ro=ro, rw=rw, net=perms["network"], gui=True, nvidia=perms["nvidia"], cwd=d, env=env)
    # Overlay the component library at <app>/Amadeus and the bridge socket.
    i = argv.index("--")
    extra = ["--ro-bind", str(COMPONENTS), str(d / "Amadeus"), "--setenv", "AMADEUS_APP_DATA", str(d / "data")]
    if sock_path:
        inside = f"{os.environ.get('XDG_RUNTIME_DIR', '/tmp')}/amadeus-app.sock"
        extra += ["--ro-bind", str(sock_path), inside, "--setenv", "AMADEUS_APP_SOCK", inside]
    return argv[:i] + extra + argv[i:]
