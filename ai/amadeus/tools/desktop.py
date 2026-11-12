"""Desktop control through the Hyprland compositor: windows, workspaces, launching (with GPU
selection), shortcuts and rules, and the bar layout."""
import os, json, re, glob, shlex, subprocess, shutil
from pathlib import Path
from . import tool, sh, clip, ToolError
from .files import remember

HYPR_USER = Path.home() / ".config/hypr"
MAIN = HYPR_USER / "hyprland.lua"
MANAGED = HYPR_USER / "amadeus.lua"
NV_ENV = {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia", "__VK_LAYER_NV_optimus": "NVIDIA_only"}


def lstr(s):
    """A Lua string literal."""
    return json.dumps(str(s), ensure_ascii=False)


def hypr_env():
    """The running compositor's instance, looked up now: the daemon may have started before the session."""
    env = dict(os.environ)
    if not env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        run = env.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        found = sorted(glob.glob(os.path.join(run, "hypr", "*", ".socket.sock")), key=os.path.getmtime)
        if not found:
            raise ToolError("the desktop compositor is not running")
        env["HYPRLAND_INSTANCE_SIGNATURE"] = os.path.basename(os.path.dirname(found[-1]))
    return env


def hyprctl(*args):
    p = subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=10, env=hypr_env())
    out = (p.stdout + p.stderr).strip()
    if p.returncode or out.lower().startswith(("error", "invalid", "unknown")):
        raise ToolError(f"hyprland: {out[:500]}")
    return p.stdout


def hj(what):
    return json.loads(hyprctl("-j", what) or "null")


def dispatch(expr):
    """Run one Hyprland dispatcher, written in its Lua form: hl.dsp...."""
    return hyprctl("dispatch", expr)


@tool("desktop_state", "Windows (address, app, title, workspace, floating, focused), workspaces and monitors.", cap="desktop.read")
def desktop_state(a, ctx):
    active = (hj("activewindow") or {}).get("address")
    return {"windows": [{"address": c["address"], "app": c["class"], "title": c["title"][:80], "workspace": c["workspace"]["name"],
                         "floating": c["floating"], "focused": c["address"] == active, "pid": c["pid"]} for c in hj("clients")],
            "workspaces": [{"id": w["id"], "name": w["name"], "windows": w["windows"], "monitor": w["monitor"]} for w in hj("workspaces")],
            "active_workspace": (hj("activeworkspace") or {}).get("name"),
            "monitors": [{"name": m["name"], "mode": f"{m['width']}x{m['height']}@{round(m['refreshRate'])}", "scale": m["scale"]} for m in hj("monitors")]}


ADDR = re.compile(r"^0x[0-9a-f]+$")


@tool("desktop_window", "Act on a window (default: the focused one; pass address from desktop_state for another). Actions: focus, close, "
      "float, tile, fullscreen, maximize, center, move_to_workspace (workspace), resize (width, height in pixels), move (x, y in pixels).",
      {"action": {"type": "string", "enum": ["focus", "close", "float", "tile", "fullscreen", "maximize", "center", "move_to_workspace", "resize", "move"]},
       "address": {"type": "string"}, "workspace": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"},
       "width": {"type": "integer"}, "height": {"type": "integer"}, "follow": {"type": "boolean"}},
      required=("action",), cap="desktop.control", risk=lambda a: "destructive" if a.get("action") == "close" else "modify")
def desktop_window(a, ctx):
    w = ""
    if a.get("address"):
        if not ADDR.match(a["address"]):
            raise ToolError("address must look like 0x55c3...")
        w = f'window = "address:{a["address"]}"'
    t = lambda *parts: "{ " + ", ".join(p for p in parts if p) + " }"
    act = a["action"]
    if act == "move_to_workspace" and not a.get("workspace"):
        raise ToolError("workspace is required")
    if act in ("resize", "move") and not all(k in a for k in (("width", "height") if act == "resize" else ("x", "y"))):
        raise ToolError("resize needs width and height; move needs x and y")
    dispatch({
        "focus": lambda: f"hl.dsp.focus({t(w)})",
        "close": lambda: f"hl.dsp.window.close({t(w)})",
        "float": lambda: f"hl.dsp.window.float({t('action = \"on\"', w)})",
        "tile": lambda: f"hl.dsp.window.float({t('action = \"off\"', w)})",
        "fullscreen": lambda: f"hl.dsp.window.fullscreen({t('mode = \"fullscreen\"', 'action = \"toggle\"', w)})",
        "maximize": lambda: f"hl.dsp.window.fullscreen({t('mode = \"maximized\"', 'action = \"toggle\"', w)})",
        "center": lambda: f"hl.dsp.window.center({t(w)})",
        "move_to_workspace": lambda: f"hl.dsp.window.move({t('workspace = ' + lstr(a['workspace']), 'follow = ' + ('true' if a.get('follow') else 'false'), w)})",
        "resize": lambda: f"hl.dsp.window.resize({t('x = %d' % a['width'], 'y = %d' % a['height'], w)})",
        "move": lambda: f"hl.dsp.window.move({t('x = %d' % a['x'], 'y = %d' % a['y'], w)})",
    }[act]())
    return "done"


@tool("desktop_workspace", "Switch to a workspace by number or name.", {"workspace": {"type": "string"}}, required=("workspace",), cap="desktop.control", risk="modify")
def desktop_workspace(a, ctx):
    dispatch(f"hl.dsp.focus({{ workspace = {lstr(a['workspace'])} }})")
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
    """Start a program through the compositor, so it gets the session environment."""
    pre = ["env"] + [f"{k}={v}" for k, v in (env or {}).items()] if env else []
    dispatch(f"hl.dsp.exec_cmd({lstr(shlex.join(pre + argv))})")


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
        argv = (["amadeus-terminal", "-e"] if shutil.which("amadeus-terminal") else ["foot", "-e"]) + argv
    gpu = a.get("gpu", "auto")
    mode_file = Path.home() / ".config/amadeus/gpu"
    mode = mode_file.read_text().strip() if mode_file.exists() else "auto"     # the user's choice in Setup > GPU
    dg = gpu == "dedicated" or (gpu == "auto" and mode == "auto" and wants_dgpu(e))
    spawn(argv, NV_ENV if dg else None)
    return f"launched {e.get('Name', e['id'])} on the {'NVIDIA' if dg else 'Intel'} GPU"



MODS = {"SUPER": "SUPER", "MOD": "SUPER", "WIN": "SUPER", "CTRL": "CTRL", "CONTROL": "CTRL", "SHIFT": "SHIFT", "ALT": "ALT"}
KEY = re.compile(r"^[A-Za-z0-9_]+$")


def norm_keys(keys):
    """'super+shift+n' or 'SUPER + SHIFT + N' -> 'SUPER + SHIFT + N'."""
    parts = [p.strip() for p in re.split(r"\s*\+\s*", keys.strip()) if p.strip()]
    if not parts or not all(KEY.match(p) for p in parts):
        raise ToolError("keys must look like 'SUPER + SHIFT + N'")
    *mods, key = parts
    out = []
    for m in mods:
        if m.upper() not in MODS:
            raise ToolError(f"unknown modifier {m!r}; use SUPER, CTRL, SHIFT, ALT")
        out.append(MODS[m.upper()])
    return " + ".join(out + [key.upper() if len(key) == 1 else key])


def _managed_load():
    state = {"binds": {}, "extra": ""}
    if MANAGED.exists():
        m = re.search(r"^-- state (.+)$", MANAGED.read_text(), re.M)
        if m:
            state.update(json.loads(m.group(1)))
    return state


def _managed_save(state):
    """Write the managed file only if the whole desktop configuration still loads with it, then apply it."""
    lines = ["-- Managed by Amadeus. Change it by asking, or with `ama`; this file is rewritten.",
             "-- state " + json.dumps(state, ensure_ascii=False), ""]
    for b in state["binds"].values():
        lines.append(f"o.bind({lstr(b['keys'])}, {lstr(b['description'])}, {lstr(b['command'])})")
    if state["extra"].strip():
        lines += ["", state["extra"].strip()]
    new = "\n".join(lines) + "\n"
    old = MANAGED.read_text() if MANAGED.exists() else None
    remember(MANAGED)
    HYPR_USER.mkdir(parents=True, exist_ok=True)
    MANAGED.write_text(new)
    if MAIN.exists() and shutil.which("Hyprland"):
        p = subprocess.run(["Hyprland", "--verify-config", "--config", str(MAIN)], capture_output=True, text=True, timeout=20)
        if "config ok" not in (p.stdout + p.stderr):
            MANAGED.write_text(old) if old is not None else MANAGED.unlink()
            raise ToolError("the desktop rejected that configuration; nothing was changed.\n" + (p.stdout + p.stderr).strip()[-800:])
    try:
        hyprctl("reload")
    except ToolError:
        pass        # not in a session: the change applies at the next login


@tool("desktop_keybind", "Add, replace or remove a persistent keyboard shortcut that runs a shell command, e.g. keys 'SUPER + SHIFT + N'. "
      "Checked before it is applied, applied immediately, kept across reboots.",
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


@tool("desktop_config", "Read or replace the free-form part of the desktop configuration that Amadeus manages, written in Hyprland's Lua "
      "API (hl.config, hl.window_rule, hl.monitor, hl.animation, o.window). Omit lua to read the current text. The whole configuration is "
      "checked first and a rejected change is not applied. It can run commands, so the user is always asked.",
      {"lua": {"type": "string"}}, cap="desktop.config", risk=lambda a: "destructive" if "lua" in a else "read")
def desktop_config(a, ctx):
    state = _managed_load()
    if "lua" not in a:
        return {"lua": state["extra"], "shortcuts": list(state["binds"].values())}
    state["extra"] = a["lua"]
    _managed_save(state)
    return "applied"


BAR_FILE = Path.home() / ".config/amadeus/bar.json"
BAR_WIDGETS = ["workspaces", "title", "record", "sudo", "awake", "clock", "weather", "gpu", "tray", "bluetooth", "network", "volume", "brightness", "battery", "power", "amadeus"]
BAR_DEFAULT = {"left": ["workspaces", "title"], "center": ["sudo", "awake", "clock", "weather"],
               "right": ["record", "gpu", "tray", "bluetooth", "network", "volume", "brightness", "battery", "power", "amadeus"]}


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
