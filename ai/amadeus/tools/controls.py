"""Native desktop controls use the same commands and state as the human interface."""
import json, os, re
from pathlib import Path
from . import tool, sh, ToolError
from . import files
from .. import config

AREAS = ("text", "gpu", "scale", "brightness", "audio", "defaults", "agent", "theme", "stay_awake")
# Applications chosen by the desktop system's own default commands (amadeus-default-KEY).
DEFAULT_APPS = ("terminal", "editor", "browser", "agent")
# Kinds of file or link, and the types that decide which application opens them.
FILE_TYPES = {"files": "inode/directory", "images": "image/png image/jpeg image/webp image/gif",
              "video": "video/mp4 video/x-matroska video/webm", "music": "audio/mpeg audio/flac audio/ogg",
              "documents": "application/pdf", "mail": "x-scheme-handler/mailto"}


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
      "Defaults key is terminal/editor/browser/agent or a file type from get; omit key to discover choices. Theme value is a theme name from its choices.",
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
        before = checked(["amadeus-theme-current"])
        choices = checked(["amadeus-theme-list"]).splitlines()
        if action == "set":
            if value not in choices: raise ToolError("choose a theme name from choices")
            checked(["amadeus-theme-set", value])
        return {"value": checked(["amadeus-theme-current"]), "previous": before, "choices": choices}
    if area == "stay_awake":
        before = checked(["amadeus-toggle-idle", "status"])
        if action == "set":
            if not isinstance(value, bool): raise ToolError("stay_awake requires true or false")
            checked(["amadeus-toggle-idle", "stay-awake" if value else "allow-idle"])
        return {"value": checked(["amadeus-toggle-idle", "status"]), "previous": before}
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
        if not key and action == "get":
            return {"apps": {k: checked([f"amadeus-default-{k}"]) for k in DEFAULT_APPS}, "file_types": FILE_TYPES}
        if key in FILE_TYPES:
            mime_types = FILE_TYPES[key].split()
            before = checked(["xdg-mime", "query", "default", mime_types[0]])
            apps = json.loads(checked(["amadeus-launcher", "--json"]))
            choices = [{"id": e["id"] + ".desktop", "name": e["label"]} for e in apps if mime_types[0] in e.get("mimeTypes", [])]
            if action == "set":
                if value not in {e["id"] for e in choices}: raise ToolError("choose a desktop id from the installed handlers")
                remember(ctx, root / "mimeapps.list")
                checked(["xdg-mime", "default", value, *mime_types])
            return {"value": checked(["xdg-mime", "query", "default", mime_types[0]]), "previous": before, "choices": choices}
        key = "agent" if key == "harness" else key
        if key not in DEFAULT_APPS: raise ToolError("unknown default; get without key to discover choices")
        before = checked([f"amadeus-default-{key}"])
        if action == "set":
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.+-]+", value): raise ToolError("invalid default name")
            checked([f"amadeus-default-{key}", value])
        return {"value": checked([f"amadeus-default-{key}"]), "previous": before}
    commands = {"text": ["amadeus-display-text-size"], "gpu": ["amadeus-gpu"],
                "scale": ["amadeus-hyprland-monitor-scaling"], "brightness": ["amadeus-brightness-display", "--no-osd"]}
    before = checked(commands[area])
    if action == "set":
        if area == "text":
            val = number(value, 9, 20)
            if not float(val).is_integer(): raise ToolError("text size must be a whole number")
            argv = commands[area] + [val]
        elif area == "gpu":
            if value not in ("auto", "integrated", "dedicated", "intel", "nvidia"): raise ToolError("GPU mode must be auto, integrated or dedicated")
            for rel in ("amadeus/gpu", "uwsm/env-hyprland"): remember(ctx, root / rel)
            argv = ["amadeus-gpu", "set", value]
        elif area == "scale":
            argv = commands[area] + [number(value, 0.5, 3)]
        else: argv = commands[area] + [number(value, 1, 100) + "%"]
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
