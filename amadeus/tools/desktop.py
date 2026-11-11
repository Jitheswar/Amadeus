"""Desktop control: windows, workspaces, launching (with GPU selection), keybindings,
bar/panels/widgets/themes through the shell's own command set."""
import os, json, re, glob, shlex, subprocess, shutil
from pathlib import Path
from . import tool, sh, clip, ToolError
from .files import remember

HYPR_USER = Path.home() / ".config/hypr"
MANAGED = HYPR_USER / "amadeus.lua"
NV_ENV = {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia", "__VK_LAYER_NV_optimus": "NVIDIA_only"}


def lstr(s):
    return json.dumps(str(s), ensure_ascii=False)


def hj(what):
    p = sh(["hyprctl", "-j", what], timeout=10, check=True)
    return json.loads(p.stdout)


def lua(code):
    p = sh(["hyprctl", "eval", code], timeout=10)
    out = (p.stdout + p.stderr).strip()
    if p.returncode or "error" in out.lower()[:40]:
        raise ToolError(f"hyprland: {out[:500]}")
    return out


def dispatch(expr):
    return lua(f"hl.dispatch({expr})")


@tool("desktop_state", "Windows (address, class, title, workspace, floating, size), workspaces, monitors and the focused window.", cap="desktop.read")
def desktop_state(a, ctx):
    wins = [{"address": c["address"], "class": c["class"], "title": c["title"][:80], "workspace": c["workspace"]["name"],
             "floating": c["floating"], "fullscreen": c.get("fullscreen"), "at": c["at"], "size": c["size"], "pid": c["pid"]} for c in hj("clients")]
    act = hj("activewindow") or {}
    return {"windows": wins, "focused": act.get("address"),
            "workspaces": [{"id": w["id"], "name": w["name"], "windows": w["windows"], "monitor": w["monitor"]} for w in hj("workspaces")],
            "active_workspace": hj("activeworkspace").get("name"),
            "monitors": [{"name": m["name"], "res": f"{m['width']}x{m['height']}@{round(m['refreshRate'])}", "scale": m["scale"]} for m in hj("monitors")]}


ADDR = re.compile(r"^0x[0-9a-f]+$")


@tool("desktop_window", "Act on a window (default: the focused one). Actions: focus, close, float, tile, fullscreen, maximize, center, "
      "move_to_workspace (workspace), resize (width,height in px), move (x,y in px).",
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
    j = lambda *parts: "{ " + ", ".join(p for p in parts if p) + " }"
    act = a["action"]
    expr = {
        "focus": lambda: f"hl.dsp.focus({j(w)})",
        "close": lambda: f"hl.dsp.window.close({j(w)})",
        "float": lambda: f"hl.dsp.window.float({j('action = \"on\"', w)})",
        "tile": lambda: f"hl.dsp.window.float({j('action = \"off\"', w)})",
        "fullscreen": lambda: f"hl.dsp.window.fullscreen({j('mode = \"fullscreen\"', 'action = \"toggle\"', w)})",
        "maximize": lambda: f"hl.dsp.window.fullscreen({j('mode = \"maximized\"', 'action = \"toggle\"', w)})",
        "center": lambda: f"hl.dsp.window.center({j(w)})",
        "move_to_workspace": lambda: f"hl.dsp.window.move({j('workspace = ' + lstr(a['workspace']), 'follow = ' + ('true' if a.get('follow') else 'false'), w)})",
        "resize": lambda: f"hl.dsp.window.resize({j('x = %d' % a['width'], 'y = %d' % a['height'], w)})",
        "move": lambda: f"hl.dsp.window.move({j('x = %d' % a['x'], 'y = %d' % a['y'], w)})",
    }[act]()
    dispatch(expr)
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
    full = dict(os.environ, **(env or {}))
    wrap = ["uwsm", "app", "--"] if shutil.which("uwsm") else []
    subprocess.Popen(wrap + argv, env=full, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


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


def _managed_load():
    binds = {}
    if MANAGED.exists():
        for line in MANAGED.read_text().splitlines():
            m = re.match(r"^-- bind (.+)$", line)
            if m:
                b = json.loads(m.group(1))
                binds[b["keys"]] = b
    return binds


def _managed_save(binds):
    remember(MANAGED)
    lines = ["-- Managed by Amadeus. Change it by asking, or with `ama`; this file is rewritten.", ""]
    for b in binds.values():
        lines += [f"-- bind {json.dumps(b)}", f"o.bind({lstr(b['keys'])}, {lstr(b['description'])}, {lstr(b['command'])})", ""]
    MANAGED.write_text("\n".join(lines))
    main = HYPR_USER / "hyprland.lua"
    if main.exists() and "amadeus.lua" not in main.read_text():
        remember(main)
        with open(main, "a") as f:
            f.write('\n-- Shortcuts and rules added by Amadeus.\ndofile(os.getenv("HOME") .. "/.config/hypr/amadeus.lua")\n')


@tool("desktop_keybind", "Add, replace or remove a persistent keyboard shortcut that runs a command, e.g. keys 'SUPER + SHIFT + N'. "
      "Applied immediately and kept across reboots.",
      {"keys": {"type": "string"}, "description": {"type": "string"}, "command": {"type": "string"}, "remove": {"type": "boolean"}},
      required=("keys",), cap="desktop.config", risk="modify")
def desktop_keybind(a, ctx):
    binds = _managed_load()
    keys = a["keys"].upper()
    if a.get("remove"):
        binds.pop(keys, None)
        _managed_save(binds)
        lua(f"hl.unbind({lstr(keys)})")
        return f"removed {keys}"
    if not a.get("command"):
        raise ToolError("command is required")
    binds[keys] = {"keys": keys, "description": a.get("description", a["command"]), "command": a["command"]}
    _managed_save(binds)
    try:
        lua(f"hl.unbind({lstr(keys)})")
    except ToolError:
        pass
    lua(f"o.bind({lstr(keys)}, {lstr(binds[keys]['description'])}, {lstr(a['command'])})")
    return f"bound {keys}"


@tool("desktop_lua", "Run Lua in the window manager (Hyprland `hl.*` API) for anything the other desktop tools do not cover: "
      "window rules, layouts, animations, config values. This can run arbitrary commands, so the user is always asked.",
      {"code": {"type": "string"}}, required=("code",), cap="desktop.config", risk="destructive")
def desktop_lua(a, ctx):
    return lua(a["code"]) or "ok"


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
