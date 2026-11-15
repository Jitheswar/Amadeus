"""Native desktop controls use the same commands and state as the human interface."""
import json, os, re
from pathlib import Path
from . import tool, sh, ToolError
from . import desktop, files
from .. import config

AREAS = ("text", "gpu", "scale", "brightness", "audio", "defaults", "agent", "theme", "stay_awake")


def setting_risk(a):
    return "read" if a.get("action", "get") == "get" else "modify"


def setting_cap(a):
    if a.get("action", "get") == "get": return "desktop.read"
    return "ai.configure" if a.get("area") == "agent" else "desktop.config"


def remember(ctx, path, recovery=None):
    if ctx.policy.path_denied(str(path)): raise ToolError("that setting points to a protected path")
    files.remember(path, recovery=recovery)


def checked(argv):
    p = sh(argv, check=True)
    return p.stdout.strip()


def number(value, low, high):
    if isinstance(value, bool): raise ToolError("a number is required")
    try: value = float(value)
    except (TypeError, ValueError): raise ToolError("a number is required")
    if not low <= value <= high: raise ToolError(f"value must be between {low} and {high}")
    return format(value, "g")


def audio_devices():
    nodes = json.loads(checked(["pw-dump"]))
    out = []
    for node in nodes:
        info = node.get("info") or {}
        props = info.get("props") or {}
        kind = {"Audio/Sink": "sink", "Audio/Source": "source"}.get(props.get("media.class"))
        name = str(props.get("node.name", ""))
        if not kind or props.get("node.virtual") in (True, "true") or props.get("device.class") == "monitor" or name.endswith(".monitor") or info.get("state") == "error": continue
        out.append({"id": node["id"], "name": props.get("node.description", name), "kind": kind})
    return out


@tool("os_menu", "Search all installed applications and native Amadeus menu/settings routes. With id, open that route; "
      "this opens its UI rather than silently performing an install or system action.",
      {"query": {"type": "string"}, "id": {"type": "string"}}, cap=lambda a: ("apps.launch" if str(a.get("id", "")).startswith("app:") else "desktop.control") if a.get("id") else "desktop.read",
      risk=lambda a: "modify" if a.get("id") else "read")
def os_menu(a, ctx):
    entries = json.loads(checked(["amadeus-search", "--index"]))
    if a.get("id"):
        if a["id"] not in {e["id"] for e in entries}: raise ToolError("that route is not available")
        return checked(["amadeus-search", "--run", a["id"]]) or "Opened the requested control."
    words = str(a.get("query", "")).casefold().split()
    return [e for e in entries if all(w in (e["label"] + " " + e.get("keywords", "") + " " + e.get("path", "")).casefold() for w in words)][:80]


@tool("desktop_settings", "Inspect or change native settings without navigating menus: text size, GPU mode, focused-monitor scale, "
      "brightness, audio, defaults, panel agent, theme or stay-awake. Use get before set; results report the previous setting. "
      "GPU changes need another login; no logout is performed. Audio target is sink/source, key is volume/mute/device. "
      "Defaults key is terminal/editor/harness or a file type from get; omit key to discover choices. Theme value is a JSON object of palette, font and timing overrides.",
      {"area": {"type": "string", "enum": list(AREAS)}, "action": {"type": "string", "enum": ["get", "set"]},
       "key": {"type": "string"}, "value": {}, "target": {"type": "string", "enum": ["sink", "source"]}},
      required=("area",), cap=setting_cap, risk=setting_risk)
def desktop_settings(a, ctx):
    area, action = a["area"], a.get("action", "get")
    if area not in AREAS or action not in ("get", "set"): raise ToolError("unknown setting or action")
    value, key = a.get("value"), a.get("key", "")
    root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    if action == "set" and "value" not in a: raise ToolError("value is required to change a setting")
    if area == "agent":
        before = config.load()["ai"]["provider"]
        if action == "set":
            if not isinstance(value, str): raise ToolError("provider name must be text")
            remember(ctx, config.CONFIG / "config.toml")
            config.set_default_provider(value); ctx.daemon.reload()
        return {"value": config.load()["ai"]["provider"], "previous": before}
    if area == "theme":
        path = root / "amadeus/theme.json"
        if ctx.policy.path_denied(str(path)): raise ToolError("that setting points to a protected path")
        before = json.loads(path.read_text()) if path.exists() else {}
        if action == "set":
            if not isinstance(value, dict): raise ToolError("theme value must be an object")
            palette = json.loads((config.SHARE.parent / "amadeus-os/theme.json").read_text())
            for k, v in value.items():
                if k not in palette: raise ToolError(f"unknown theme field: {k}")
                if k in ("font", "mono"):
                    if not isinstance(v, str) or not 1 <= len(v) <= 100 or any(ord(c) < 32 for c in v): raise ToolError("invalid font")
                elif isinstance(palette[k], str):
                    if not isinstance(v, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", v): raise ToolError("colours must be #RRGGBB")
                else:
                    number(v, 9 if k == "font_size" else 0, 20 if k == "font_size" else 1000)
            if "font_size" in value:
                raise ToolError("use the text setting to keep shell, GTK and terminal sizes consistent")
            remember(ctx, path)
            config._atomic_config(path, json.dumps(dict(before, **value), indent=2))
        return {"value": json.loads(path.read_text()) if path.exists() else {}, "previous": before, "undo": "journalled file change"}
    if area == "stay_awake":
        cmd = ["quickshell", "ipc", "-p", "/usr/share/amadeus-os/shell", "call", "shell"]
        before = json.loads(checked(cmd + ["state"]))["awake"]
        if action == "set":
            if not isinstance(value, bool): raise ToolError("stay_awake requires true or false")
            checked(cmd + ["awake", str(value).lower()])
        return {"value": before if action == "get" else value, "previous": before}
    if area == "audio":
        target = a.get("target", "sink")
        if target not in ("sink", "source"): raise ToolError("audio target must be sink or source")
        node = "@DEFAULT_AUDIO_SINK@" if target == "sink" else "@DEFAULT_AUDIO_SOURCE@"
        before = checked(["wpctl", "get-volume", node])
        if action == "set":
            if key == "volume": argv = ["wpctl", "set-volume", node, number(value, 0, 1.5)]
            elif key == "mute":
                if not isinstance(value, bool): raise ToolError("mute requires true or false")
                argv = ["wpctl", "set-mute", node, "1" if value else "0"]
            elif key == "device":
                if not isinstance(value, int) or isinstance(value, bool) or value <= 0: raise ToolError("device must be a positive PipeWire node id")
                if value not in {d["id"] for d in audio_devices() if d["kind"] == target}:
                    raise ToolError("select a ready audio device of the requested type")
                argv = ["wpctl", "set-default", str(value)]
            else: raise ToolError("audio key must be volume, mute or device")
            checked(argv)
        return {"value": checked(["wpctl", "get-volume", node]), "previous": before, "devices": audio_devices()}
    if area == "defaults":
        types = {name.lower(): mime for line in checked(["amadeus-menu", "--default-types"]).splitlines() if "\t" in line for name, mime in [line.split("\t", 1)]}
        if not key and action == "get":
            return {"wrappers": checked(["amadeus-default"]), "file_types": types}
        if key in types:
            mime_types = types[key].split()
            before = checked(["xdg-mime", "query", "default", mime_types[0]])
            apps = json.loads(checked(["amadeus-launcher", "--json"]))
            choices = [{"id": e["id"] + ".desktop", "name": e["label"]} for e in apps if mime_types[0] in e.get("mimeTypes", [])]
            if action == "set":
                if value not in {e["id"] for e in choices}: raise ToolError("choose a desktop id from the installed handlers")
                remember(ctx, root / "mimeapps.list")
                checked(["xdg-mime", "default", value, *mime_types])
                if key == "browser": checked(["xdg-settings", "set", "default-web-browser", value])
            return {"value": checked(["xdg-mime", "query", "default", mime_types[0]]), "previous": before, "choices": choices}
        if key not in ("terminal", "editor", "harness"): raise ToolError("unknown default; get without key to discover choices")
        before = checked(["amadeus-default", key])
        if action == "set":
            if not isinstance(value, str) or not value or value.startswith("-"): raise ToolError("invalid default name")
            remember(ctx, root / "amadeus/defaults")
            checked(["amadeus-default", key, value])
        return {"value": checked(["amadeus-default", key]), "previous": before,
                "choices": checked(["amadeus-default", key, "--choices"])}
    commands = {"text": ["amadeus-display", "text"], "gpu": ["amadeus-gpu"],
                "scale": ["amadeus-display", "scale"], "brightness": ["brightnessctl", "-m"]}
    before = checked(commands[area])
    if action == "set":
        if area == "text":
            val = number(value, 9, 20)
            if not float(val).is_integer(): raise ToolError("text size must be a whole number")
            factor = checked(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"])
            for rel in ("amadeus/theme.json", "foot/foot.ini", "kitty/kitty.conf", "alacritty/alacritty.toml", "ghostty/config"):
                remember(ctx, root / rel, recovery={"kind": "text", "factor": factor} if rel == "amadeus/theme.json" else None)
            argv = commands[area] + [val]
        elif area == "gpu":
            if value not in ("auto", "intel", "nvidia"): raise ToolError("GPU mode must be auto, intel or nvidia")
            for rel in ("amadeus/gpu", "uwsm/env-hyprland"): remember(ctx, root / rel)
            argv = ["amadeus-gpu", "set", value]
        elif area == "scale":
            remember(ctx, root / "hypr/display.lua")
            argv = commands[area] + [number(value, 0.5, 3)]
        else: argv = ["brightnessctl", "set", number(value, 1, 100) + "%"]
        result = checked(argv)
    else: result = before
    return {"value": result, "previous": before, "next_login": area == "gpu" and action == "set"}


@tool("bluetooth_control", "List Bluetooth devices or connect/disconnect/trust/remove one by its address. "
      "Pairing that needs a PIN stays in the user's Bluetooth UI.",
      {"action": {"type": "string", "enum": ["devices", "connect", "disconnect", "trust", "remove"]}, "address": {"type": "string"}},
      cap=lambda a: "net.read" if a.get("action", "devices") == "devices" else "net.manage",
      risk=lambda a: "read" if a.get("action", "devices") == "devices" else ("destructive" if a.get("action") == "remove" else "modify"))
def bluetooth_control(a, ctx):
    action = a.get("action", "devices")
    if action not in ("devices", "connect", "disconnect", "trust", "remove"): raise ToolError("unknown Bluetooth action")
    argv = ["bluetoothctl", "--timeout", "15", action]
    if action != "devices":
        address = a.get("address", "")
        if not isinstance(address, str) or not re.fullmatch(r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", address): raise ToolError("a Bluetooth device address is required")
        argv.append(address)
    return checked(argv)
