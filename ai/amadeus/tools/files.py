"""Files. Every write keeps the previous version so `ama undo` can restore it."""
import os, json, shutil, time, fnmatch, threading
from pathlib import Path
from . import tool, sh, clip, ToolError
from .. import config
from ..policy import expand


def _journal():
    d = config.STATE / "undo"
    d.mkdir(parents=True, exist_ok=True)
    return d


current = threading.local()     # .session is set by the daemon around each tool call


def remember(path):
    """Save the current version of path before changing it."""
    path = Path(path)
    stamp = f"{time.time_ns()}"
    entry = {"path": str(path), "existed": path.exists(), "ts": time.time(), "session": getattr(current, "session", None)}
    if path.is_file():
        shutil.copy2(path, _journal() / f"{stamp}.bak")
    (_journal() / f"{stamp}.json").write_text(json.dumps(entry))
    old = sorted(_journal().glob("*.json"))[:-200]   # keep the last 200 changes
    for j in old:
        j.unlink(missing_ok=True)
        j.with_suffix(".bak").unlink(missing_ok=True)
    return stamp


def _restore(j):
    e = json.loads(j.read_text())
    bak = j.with_suffix(".bak")
    if bak.exists():
        shutil.copy2(bak, e["path"])
        bak.unlink()
        msg = f"restored {e['path']}"
    elif not e["existed"]:
        Path(e["path"]).unlink(missing_ok=True)
        msg = f"removed {e['path']} (it did not exist before)"
    else:
        msg = f"no saved copy for {e['path']}"
    j.unlink()
    return msg


def undo_last():
    entries = sorted(_journal().glob("*.json"))
    return _restore(entries[-1]) if entries else "nothing to undo"


def undo_session(session):
    """Put back every file one task changed, newest change first."""
    mine = [j for j in sorted(_journal().glob("*.json"), reverse=True) if json.loads(j.read_text()).get("session") == session]
    return [_restore(j) for j in mine]


def changed_by(session):
    return sum(1 for j in _journal().glob("*.json") if json.loads(j.read_text()).get("session") == session)


P = {"path": {"type": "string", "description": "absolute or ~ path"}}


@tool("fs_list", "List a directory.", {**P, "hidden": {"type": "boolean"}}, required=("path",), cap="fs.read")
def fs_list(a, ctx):
    p = expand(a["path"])
    rows = []
    for e in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        if e.name.startswith(".") and not a.get("hidden"):
            continue
        try:
            rows.append(f"{'d' if e.is_dir() else '-'} {e.stat().st_size:>12} {e.name}")
        except OSError:
            rows.append(f"? {'':>12} {e.name}")
    return clip("\n".join(rows[:500])) or "(empty)"


@tool("fs_read", "Read a text file. offset/limit are in lines.", {**P, "offset": {"type": "integer"}, "limit": {"type": "integer"}}, required=("path",), cap="fs.read")
def fs_read(a, ctx):
    p = expand(a["path"])
    if p.stat().st_size > 5_000_000:
        raise ToolError("file is larger than 5 MB; read a range with shell tools instead")
    lines = p.read_text(errors="replace").splitlines()
    o = int(a.get("offset", 0))
    return clip("\n".join(lines[o:o + int(a.get("limit", 400))]))


@tool("fs_search", "Find files by name pattern, or lines by content (regex), under a directory.",
      {**P, "name": {"type": "string", "description": "glob such as *.pdf"}, "content": {"type": "string", "description": "regex to search inside files"}},
      required=("path",), cap="fs.read")
def fs_search(a, ctx):
    p = str(expand(a["path"]))
    if a.get("content"):
        cmd = ["grep", "-rnI", "--max-count=5", "-E", a["content"], p]
        if a.get("name"):
            cmd.insert(1, f"--include={a['name']}")
        out = sh(cmd, timeout=60).stdout
    else:
        out = sh(["find", p, "-xdev", "-iname", a.get("name", "*"), "-not", "-path", "*/.git/*"], timeout=60).stdout
    keep = [l for l in out.splitlines() if not ctx.policy.path_denied(l.split(":")[0])]
    return clip("\n".join(keep[:300])) or "(no matches)"


@tool("fs_write", "Create or replace a file in the user's home. The previous version is kept for undo.",
      {**P, "content": {"type": "string"}}, required=("path", "content"), cap="fs.write", risk="modify")
def fs_write(a, ctx):
    p = expand(a["path"])
    if Path.home() not in p.parents:
        raise ToolError("fs_write only writes inside the home directory; use sys_config_write for system files")
    remember(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".amadeus-tmp")
    tmp.write_text(a["content"])
    os.replace(tmp, p)       # atomic
    return f"wrote {len(a['content'])} bytes to {p}"


@tool("fs_edit", "Replace one exact string in a file with another. The old string must occur exactly once.",
      {**P, "old": {"type": "string"}, "new": {"type": "string"}}, required=("path", "old", "new"), cap="fs.write", risk="modify")
def fs_edit(a, ctx):
    p = expand(a["path"])
    text = p.read_text()
    n = text.count(a["old"])
    if n != 1:
        raise ToolError(f"old string occurs {n} times; it must occur exactly once")
    return fs_write({"path": str(p), "content": text.replace(a["old"], a["new"])}, ctx)


@tool("fs_move", "Move or rename a file or directory.", {"src": {"type": "string"}, "dst": {"type": "string"}}, required=("src", "dst"),
      cap="fs.write", risk=lambda a: "destructive" if expand(a.get("dst", "/")).exists() else "modify")
def fs_move(a, ctx):
    shutil.move(str(expand(a["src"])), str(expand(a["dst"])))
    return "moved"


@tool("fs_trash", "Move a file or directory to the trash (recoverable).", P, required=("path",), cap="fs.write", risk="modify")
def fs_trash(a, ctx):
    sh(["gio", "trash", str(expand(a["path"]))], check=True)
    return "moved to trash"
