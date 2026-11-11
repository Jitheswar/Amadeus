"""Networking through NetworkManager."""
from . import tool, sh, clip, ToolError


@tool("net_status", "Connectivity, active connections, addresses, and optionally nearby Wi-Fi networks.", {"wifi_scan": {"type": "boolean"}}, cap="net.read")
def net_status(a, ctx):
    out = {"general": sh(["nmcli", "-t", "general", "status"]).stdout.strip(),
           "devices": sh(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"]).stdout.splitlines(),
           "addresses": sh(["ip", "-brief", "addr"]).stdout.splitlines()}
    if a.get("wifi_scan"):
        out["wifi"] = sh(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"], timeout=30).stdout.splitlines()[:25]
    return out


@tool("net_control", "Change networking: wifi on/off, connect to a saved or open network by name (up), disconnect (down). "
      "Passwords are never handled here; new secured networks are joined by the user.",
      {"action": {"type": "string", "enum": ["wifi_on", "wifi_off", "up", "down"]}, "name": {"type": "string"}},
      required=("action",), cap="net.manage", risk="modify")
def net_control(a, ctx):
    act = a["action"]
    if act in ("wifi_on", "wifi_off"):
        cmd = ["nmcli", "radio", "wifi", "on" if act == "wifi_on" else "off"]
    else:
        if not a.get("name"):
            raise ToolError("name is required")
        cmd = ["nmcli", "connection", act, a["name"]]
    p = sh(cmd, timeout=45)
    return (p.stdout + p.stderr).strip() or "done"
