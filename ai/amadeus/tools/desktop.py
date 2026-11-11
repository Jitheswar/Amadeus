"""Desktop control through the niri compositor: windows, workspaces, launching (with GPU
selection), shortcuts and rules, and the bar layout."""
import os, json, re, glob, shlex, subprocess, shutil
from pathlib import Path
from . import tool, sh, clip, ToolError
from .files import remember

NIRI_USER = Path.home() / ".config/niri"
MAIN = NIRI_USER / "config.kdl"
MANAGED = NIRI_USER / "amadeus.kdl"
NV_ENV = {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia", "__VK_LAYER_NV_optimus": "NVIDIA_only"}


def kstr(s):
    """A KDL string literal."""
    return json.dumps(str(s), ensure_ascii=False)


def niri_env():
    env = dict(os.environ)
    if not env.get("NIRI_SOCKET"):
        socks = sorted(glob.glob(os.path.join(env.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "niri.*.sock")), key=os.path.getmtime)
        if not socks:
            raise ToolError("the desktop compositor is not running")
        env["NIRI_SOCKET"] = socks[-1]
    return env


def niri(*args):
    p = subprocess.run(["niri", "msg", *args], capture_output=True, text=True, timeout=10, env=niri_env())
    if p.returncode:
        raise ToolError(f"niri: {(p.stderr or p.stdout).strip()[:500]}")
    return p.stdout


def nj(what):
    return json.loads(niri("--json", what))


def action(*args):
    niri("action", *[str(x) for x in args])


@tool("desktop_state", "Windows (id, app, title, workspace, floating, focused), workspaces and monitors. Windows are arranged in "
      "columns on a horizontal strip per workspace.", cap="desktop.read")
def desktop_state(a, ctx):
    spaces = nj("workspaces")
    name = {w["id"]: w.get("name") or str(w["idx"]) for w in spaces}
    wins = nj("windows")
    return {"windows": [{"id": w["id"], "app": w.get("app_id"), "title": (w.get("title") or "")[:80], "workspace": name.get(w.get("workspace_id")),
                         "floating": w.get("is_floating", False), "focused": w.get("is_focused", False), "pid": w.get("pid")} for w in wins],
            "workspaces": [{"index": w["idx"], "name": w.get("name"), "monitor": w.get("output"), "active": w.get("is_active"), "focused": w.get("is_focused")}
                           for w in sorted(spaces, key=lambda w: (w.get("output") or "", w["idx"]))],
            "monitors": [{"name": n, "mode": (lambda m: f"{m['width']}x{m['height']}@{round(m['refresh_rate'] / 1000)}" if m else None)(
                              o["modes"][o["current_mode"]] if o.get("current_mode") is not None else None),
                          "scale": (o.get("logical") or {}).get("scale")} for n, o in nj("outputs").items()]}


SIZE = re.compile(r"^[+-]?\d+(\.\d+)?%?$")
WINDOW_ACTIONS = {
    "focus": "focus-window", "close": "close-window", "float": "move-window-to-floating", "tile": "move-window-to-tiling",
    "fullscreen": "fullscreen-window", "center": "center-window",
}


@tool("desktop_window", "Act on a window (default: the focused one; pass id from desktop_state for another). Actions: focus, close, float, tile, "
      "fullscreen, maximize, center, move_to_workspace (workspace: index or name), width / height (size: '50%', '800', '+10%'), "
      "move (direction: left/right moves its column, up/down moves it within the column), stack (direction: left/right pulls it into the "
      "neighbouring column or pushes it out into its own).",
      {"action": {"type": "string", "enum": ["focus", "close", "float", "tile", "fullscreen", "maximize", "center", "move_to_workspace", "width", "height", "move", "stack"]},
       "id": {"type": "integer"}, "workspace": {"type": "string"}, "size": {"type": "string"},
       "direction": {"type": "string", "enum": ["left", "right", "up", "down"]}, "follow": {"type": "boolean"}},
      required=("action",), cap="desktop.control", risk=lambda a: "destructive" if a.get("action") == "close" else "modify")
def desktop_window(a, ctx):
    act, wid = a["action"], a.get("id")
    sel = ["--id", int(wid)] if wid is not None else []
    if act == "focus" and wid is None:
        raise ToolError("focus needs a window id")
    if act in WINDOW_ACTIONS:
        action(WINDOW_ACTIONS[act], *sel)
    elif act == "move_to_workspace":
        if not a.get("workspace"):
            raise ToolError("workspace is required")
        action("move-window-to-workspace", *(["--window-id", int(wid)] if wid is not None else []), "--focus", "true" if a.get("follow") else "false", a["workspace"])
    elif act in ("width", "height"):
        if not SIZE.match(a.get("size", "")):
            raise ToolError("size must look like 50%, 800, +10% or -100")
        action(f"set-window-{act}", *sel, a["size"])
    else:
        # These act on the focused window, so focus the target first.
        d = a.get("direction")
        if act != "maximize" and d is None:
            raise ToolError("direction is required")
        if wid is not None:
            action("focus-window", "--id", int(wid))
        if act == "maximize":
            action("maximize-column")
        elif act == "move":
            action({"left": "move-column-left", "right": "move-column-right", "up": "move-window-up", "down": "move-window-down"}[d])
        elif d in ("left", "right"):
            action(f"consume-or-expel-window-{d}")
        else:
            raise ToolError("stack takes left or right")
    return "done"


@tool("desktop_workspace", "Switch to a workspace by index or name.", {"workspace": {"type": "string"}}, required=("workspace",), cap="desktop.control", risk="modify")
def desktop_workspace(a, ctx):
    action("focus-workspace", a["workspace"])
    return "done"


def desktop_entries():
    out = {}
    dirs = [Path.home() / ".local/share/applications", Path("/usr/local/share/applications"), Path("/usr/share/applications")]
    for d in reversed(dirs):
        for f in d.glob("*.desktop"):
            e, sect = {"id": f.stem, "file": str(f)}, None
            for line in f.read_text(errors="replace").splitlines():
                if line.startswith("["):
                    sect = line
                elif sect == "[Desktop Entry]" and "=" in line:
                    k, v = line.split("=", 1)
                    if k in ("Name", "Exec", "Categories", "NoDisplay", "PrefersNonDefaultGPU", "X-KDE-RunOnDiscreteGpu", "Comment", "Terminal"):
                        e[k] = v
            if "Exec" in e and e.get("NoDisplay") != "true":
                out[f.stem] = e
    return out


def wants_dgpu(e):
    return e.get("PrefersNonDefaultGPU") == "true" or e.get("X-KDE-RunOnDiscreteGpu") == "true" or "Game" in e.get("Categories", "")


@tool("desktop_apps", "List installed desktop applications (id, name, whether it prefers the dedicated GPU). Optional name filter.", {"query": {"type": "string"}}, cap="desktop.read")
def desktop_apps(a, ctx):
    q = a.get("query", "").lower()
    return [{"id": e["id"], "name": e.get("Name"), "dedicated_gpu": wants_dgpu(e)} for e in desktop_entries().values()
            if q in e["id"].lower() or q in e.get("Name", "").lower()][:200]


def spawn(argv, env=None):
    """Start a program as the compositor's child, so it gets the session environment."""
    pre = ["env"] + [f"{k}={v}" for k, v in (env or {}).items()] if env else []
    action("spawn", "--", *pre, *argv)


@tool("desktop_launch", "Launch an installed application by desktop id or name, optionally with arguments (files, URLs). "
      "gpu: 'auto' uses the Intel GPU unless the app is a game or asks for the dedicated one; 'dedicated' forces NVIDIA; 'integrated' forces Intel.",
      {"app": {"type": "string"}, "args": {"type": "array", "items": {"type": "string"}}, "gpu": {"type": "string", "enum": ["auto", "integrated", "dedicated"]}},
      required=("app",), cap="apps.launch", risk="modify")
def desktop_launch(a, ctx):
    entries = desktop_entries()
    q = a["app"].lower()
    e = entries.get(a["app"]) or next((x for x in entries.values() if x["id"].lower() == q or x.get("Name", "").lower() == q), None) \
        or next((x for x in entries.values() if q in x["id"].lower() or q in x.get("Name", "").lower()), None)
    if not e:
        raise ToolError(f"no installed application matches {a['app']!r}; see desktop_apps")
    argv = [t for t in shlex.split(e["Exec"]) if not re.fullmatch(r"%[a-zA-Z]", t)] + list(a.get("args", []))
    if e.get("Terminal") == "true":
        argv = ["xdg-terminal-exec"] + argv if shutil.which("xdg-terminal-exec") else ["foot"] + argv
    gpu = a.get("gpu", "auto")
    dg = gpu == "dedicated" or (gpu == "auto" and wants_dgpu(e))
    spawn(argv, NV_ENV if dg else None)
    return f"launched {e.get('Name', e['id'])} on the {'NVIDIA' if dg else 'Intel'} GPU"


MODS = {"SUPER": "Mod", "MOD": "Mod", "WIN": "Mod", "CTRL": "Ctrl", "CONTROL": "Ctrl", "SHIFT": "Shift", "ALT": "Alt"}
KEY = re.compile(r"^[A-Za-z0-9_]+$")


def norm_keys(keys):
    """'SUPER + SHIFT + N' or 'Mod+Shift+N' -> 'Mod+Shift+N'."""
    parts = [p.strip() for p in re.split(r"\s*\+\s*", keys.strip()) if p.strip()]
    if not parts or not all(KEY.match(p) for p in parts):
        raise ToolError("keys must look like 'Mod+Shift+N'")
    *mods, key = parts
    out = []
    for m in mods:
        if m.upper() not in MODS:
            raise ToolError(f"unknown modifier {m!r}; use Mod, Ctrl, Shift, Alt")
        out.append(MODS[m.upper()])
    return "+".join(out + [key.upper() if len(key) == 1 else key])


def _managed_load():
    state = {"binds": {}, "extra": ""}
    if MANAGED.exists():
        m = re.search(r"^// state (.+)$", MANAGED.read_text(), re.M)
        if m:
            state.update(json.loads(m.group(1)))
    return state


def _managed_save(state):
    """Write the managed file only if the whole desktop configuration still validates with it."""
    lines = ["// Managed by Amadeus. Change it by asking, or with `ama`; this file is rewritten.",
             "// state " + json.dumps(state, ensure_ascii=False), ""]
    if state["binds"]:
        lines.append("binds {")
        for b in state["binds"].values():
            lines.append(f"    {b['keys']} hotkey-overlay-title={kstr(b['description'])} {{ spawn-sh {kstr(b['command'])}; }}")
        lines += ["}", ""]
    if state["extra"].strip():
        lines += [state["extra"].strip(), ""]
    new = "\n".join(lines)
    old = MANAGED.read_text() if MANAGED.exists() else None
    remember(MANAGED)
    NIRI_USER.mkdir(parents=True, exist_ok=True)
    MANAGED.write_text(new)
    if MAIN.exists() and shutil.which("niri"):
        p = subprocess.run(["niri", "validate", "-c", str(MAIN)], capture_output=True, text=True, timeout=10)
        if p.returncode:
            MANAGED.write_text(old) if old is not None else MANAGED.unlink()
            raise ToolError("the desktop rejected that configuration; nothing was changed.\n" + (p.stderr or p.stdout).strip()[-800:])


@tool("desktop_keybind", "Add, replace or remove a persistent keyboard shortcut that runs a shell command, e.g. keys 'Mod+Shift+N' "
      "(Mod is the Super key). Checked before it is applied, applied immediately, kept across reboots.",
      {"keys": {"type": "string"}, "description": {"type": "string"}, "command": {"type": "string"}, "remove": {"type": "boolean"}},
      required=("keys",), cap="desktop.config", risk="modify")
def desktop_keybind(a, ctx):
    state = _managed_load()
    keys = norm_keys(a["keys"])
    if a.get("remove"):
        state["binds"].pop(keys, None)
        _managed_save(state)
        return f"removed {keys}"
    if not a.get("command"):
        raise ToolError("command is required")
    state["binds"][keys] = {"keys": keys, "description": a.get("description", a["command"]), "command": a["command"]}
    _managed_save(state)
    return f"bound {keys}"


@tool("desktop_config", "Read or replace the free-form part of the desktop configuration that Amadeus manages, in niri's KDL format: "
      "window-rule, layout, output, input, animations, named workspaces. Omit kdl to read the current text. The whole configuration "
      "is validated first and a rejected change is not applied. It can define commands, so the user is always asked.",
      {"kdl": {"type": "string"}}, cap="desktop.config", risk=lambda a: "destructive" if "kdl" in a else "read")
def desktop_config(a, ctx):
    state = _managed_load()
    if "kdl" not in a:
        return {"kdl": state["extra"], "shortcuts": list(state["binds"].values())}
    state["extra"] = a["kdl"]
    _managed_save(state)
    return "applied"


BAR_FILE = Path.home() / ".config/amadeus/bar.json"
BAR_WIDGETS = ["workspaces", "title", "clock", "gpu", "network", "volume", "battery", "amadeus"]
BAR_DEFAULT = {"left": ["workspaces", "title"], "center": ["clock"], "right": ["gpu", "network", "volume", "battery", "amadeus"]}


@tool("desktop_bar", "Read or change the top bar layout. Pass left/center/right as lists of widget ids to rearrange, add or remove widgets; "
      "omit them to read the current layout. Widgets: " + ", ".join(BAR_WIDGETS) + ". The bar updates immediately.",
      {"left": {"type": "array", "items": {"type": "string"}}, "center": {"type": "array", "items": {"type": "string"}}, "right": {"type": "array", "items": {"type": "string"}}},
      cap="desktop.control", risk=lambda a: "modify" if any(k in a for k in ("left", "center", "right")) else "read")
def desktop_bar(a, ctx):
    try:
        cur = json.loads(BAR_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        cur = dict(BAR_DEFAULT)
    if not any(k in a for k in ("left", "center", "right")):
        return {"layout": cur, "available_widgets": BAR_WIDGETS}
    new = {k: list(a.get(k, cur.get(k, []))) for k in ("left", "center", "right")}
    bad = [w for sec in new.values() for w in sec if w not in BAR_WIDGETS]
    if bad:
        raise ToolError(f"unknown widgets {bad}; available: {BAR_WIDGETS}")
    remember(BAR_FILE)
    BAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    BAR_FILE.write_text(json.dumps(new, indent=2) + "\n")
    return {"layout": new}


@tool("desktop_notify", "Show a desktop notification.", {"title": {"type": "string"}, "body": {"type": "string"}}, required=("title",), cap="desktop.control", risk="read")
def desktop_notify(a, ctx):
    sh(["notify-send", "-a", "Amadeus", a["title"], a.get("body", "")])
    return "shown"


@tool("desktop_clipboard_set", "Put text on the clipboard.", {"text": {"type": "string"}}, required=("text",), cap="desktop.control", risk="modify")
def desktop_clipboard_set(a, ctx):
    sh(["wl-copy"], input=a["text"], check=True)
    return "copied"
