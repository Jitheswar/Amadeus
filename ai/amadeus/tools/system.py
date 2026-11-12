"""System state, services, packages, power, snapshots."""
import os, glob, json, re
from pathlib import Path
from . import tool, sh, clip, ToolError
from .. import root

NV = "/sys/bus/pci/devices/0000:01:00.0"


def _read(p, default=""):
    try:
        return Path(p).read_text().strip()
    except OSError:
        return default


def gpu_state():
    """dGPU state from sysfs only. nvidia-smi is avoided while the card sleeps,
    because querying it wakes the card and costs battery."""
    nv = None
    for d in glob.glob("/sys/bus/pci/devices/*/vendor"):
        dev = Path(d).parent
        if _read(d) == "0x10de" and _read(dev / "class").startswith("0x03"):
            nv = dev
    if not nv:
        return {"nvidia": "absent"}
    st = {"nvidia": _read(nv / "power/runtime_status"), "runtime_pm": _read(nv / "power/control")}
    if st["nvidia"] == "active":
        p = sh(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"], timeout=10)
        if p.returncode == 0:
            u, mu, mt, t, w = [x.strip() for x in p.stdout.strip().split(",")]
            st.update(util_pct=u, vram_used_mb=mu, vram_total_mb=mt, temp_c=t, watts=w)
            apps = sh(["nvidia-smi", "--query-compute-apps=pid,name,used_memory", "--format=csv,noheader"], timeout=10)
            st["using_it"] = apps.stdout.strip().splitlines()
    return st


def status():
    mem = {l.split(":")[0]: int(l.split()[1]) // 1024 for l in Path("/proc/meminfo").read_text().splitlines() if l.split(":")[0] in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")}
    st = os.statvfs("/")
    temps = {}
    for z in glob.glob("/sys/class/thermal/thermal_zone*"):
        t = _read(f"{z}/temp")
        if t.lstrip("-").isdigit():
            temps[_read(f"{z}/type")] = int(t) // 1000
    bat = {}
    for b in glob.glob("/sys/class/power_supply/BAT*"):
        bat = {"percent": _read(f"{b}/capacity"), "status": _read(f"{b}/status")}
        pw = _read(f"{b}/power_now")
        if pw.isdigit():
            bat["watts"] = round(int(pw) / 1e6, 1)
    failed = sh(["systemctl", "--failed", "--no-legend", "--plain"]).stdout.split("\n")
    ufailed = sh(["systemctl", "--user", "--failed", "--no-legend", "--plain"]).stdout.split("\n")
    return {
        "load": os.getloadavg(), "cpus": os.cpu_count(),
        "mem_mb": mem, "disk_root_gb": {"free": round(st.f_bavail * st.f_frsize / 2**30), "total": round(st.f_blocks * st.f_frsize / 2**30)},
        "temps_c": {k: v for k, v in temps.items() if k in ("x86_pkg_temp", "TCPU", "acpitz", "SEN1")} or temps,
        "battery": bat, "gpu": gpu_state(),
        "power_profile": sh(["powerprofilesctl", "get"]).stdout.strip(),
        "failed_units": [l.split()[0] for l in failed + ufailed if l.strip()],
        "root_mode": root.enabled(), "kernel": os.uname().release,
    }


@tool("system_discover", "A live map of this system, built by inspecting it now: installed versions, every shipped command with its purpose, "
      "where defaults and the user's configuration live, all tools with the capability each needs, and the permission policy. "
      "Call this first when asked to configure or manage the system.")
def system_discover(a, ctx):
    from .. import discover
    return discover.build()


@tool("sys_status", "Snapshot of the machine: load, memory, disk, temperatures, battery, GPU power state, power profile, failed services, whether root mode is on.")
def sys_status(a, ctx):
    return status()


@tool("sys_processes", "Top processes by cpu or memory.", {"by": {"type": "string", "enum": ["cpu", "mem"]}, "n": {"type": "integer"}})
def sys_processes(a, ctx):
    key = "-%mem" if a.get("by") == "mem" else "-%cpu"
    return sh(["ps", "-eo", "pid,user,%cpu,%mem,rss,comm", "--sort", key]).stdout.splitlines()[: int(a.get("n", 15)) + 1]


@tool("sys_services", "List services or show one unit's status. scope is 'user' or 'system'.",
      {"unit": {"type": "string"}, "scope": {"type": "string", "enum": ["user", "system"]}, "state": {"type": "string", "description": "filter, e.g. running, failed, enabled"}})
def sys_services(a, ctx):
    base = ["systemctl"] + (["--user"] if a.get("scope") == "user" else [])
    if a.get("unit"):
        return clip(sh(base + ["status", "--no-pager", "-n", "15", a["unit"]]).stdout)
    cmd = base + ["list-units", "--type=service", "--no-legend", "--plain", "--no-pager"]
    if a.get("state"):
        cmd += [f"--state={a['state']}"]
    return clip(sh(cmd).stdout)


UNIT_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_@.:\\-]*$")


@tool("sys_service_control", "Start, stop, restart, enable or disable a systemd unit. User units run directly; system units need root mode.",
      {"unit": {"type": "string"}, "action": {"type": "string", "enum": ["start", "stop", "restart", "enable", "disable", "reload"]},
       "scope": {"type": "string", "enum": ["user", "system"]}}, required=("unit", "action", "scope"),
      cap="sys.manage", risk=lambda a: "modify" if a.get("scope") == "user" else "privileged")
def sys_service_control(a, ctx):
    if a.get("action") not in ("start", "stop", "restart", "enable", "disable", "reload"):
        raise ToolError("invalid action")
    if a.get("scope") not in ("user", "system"):
        raise ToolError("invalid scope")
    unit = a.get("unit")
    if not isinstance(unit, str) or not UNIT_RE.match(unit):
        raise ToolError("invalid unit name")
    if a["scope"] == "user":
        p = sh(["systemctl", "--user", a["action"], unit], timeout=60, check=True)
        return p.stdout or "done"
    return root.call("systemctl", action=a["action"], unit=unit)


@tool("sys_journal", "Read the system journal. Filter by unit, priority (0-7) or a time such as '10 min ago'.",
      {"unit": {"type": "string"}, "lines": {"type": "integer"}, "priority": {"type": "string"}, "since": {"type": "string"},
       "scope": {"type": "string", "enum": ["user", "system"]}, "grep": {"type": "string"}})
def sys_journal(a, ctx):
    cmd = ["journalctl", "--no-pager", "-o", "short", "-n", str(min(int(a.get("lines", 80)), 500))]
    if a.get("scope") == "user":
        cmd.append("--user")
    for flag, key in (("-u", "unit"), ("-p", "priority"), ("-S", "since"), ("-g", "grep")):
        if a.get(key):
            cmd += [flag, str(a[key])]
    p = sh(cmd, timeout=40)
    return clip(p.stdout or p.stderr)


@tool("sys_packages", "Query packages: 'search' the repos, 'info' on one, 'installed' (optionally filtered), 'updates' pending, 'owner' of a file.",
      {"action": {"type": "string", "enum": ["search", "info", "installed", "updates", "owner"]}, "query": {"type": "string"}}, required=("action",))
def sys_packages(a, ctx):
    q = a.get("query", "")
    cmd = {"search": ["pacman", "-Ss", q], "info": ["pacman", "-Si", q] if sh(["pacman", "-Qi", q]).returncode else ["pacman", "-Qi", q],
           "installed": ["pacman", "-Qe"], "updates": ["checkupdates"], "owner": ["pacman", "-Qo", q]}[a["action"]]
    out = sh(cmd, timeout=120).stdout
    if a["action"] == "installed" and q:
        out = "\n".join(l for l in out.splitlines() if q in l)
    return clip(out) or "(nothing)"


PKG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9@._+-]*$")


@tool("pkg_manage", "Install, remove or upgrade packages with pacman. A btrfs snapshot is taken before and after, so the change can be rolled back. Needs root mode.",
      {"action": {"type": "string", "enum": ["install", "remove", "upgrade"]}, "packages": {"type": "array", "items": {"type": "string"}}},
      required=("action",), cap="pkg.manage", risk="privileged")
def pkg_manage(a, ctx):
    pk = a.get("packages", [])
    if not isinstance(pk, list) or any(not isinstance(p, str) or not PKG_RE.match(p) for p in pk):
        raise ToolError("invalid package name")
    return root.call("pacman", action=a["action"], packages=pk)


@tool("sys_power_profile", "Get or set the power profile (power-saver, balanced, performance).",
      {"set": {"type": "string", "enum": ["power-saver", "balanced", "performance"]}}, cap="sys.manage", risk=lambda a: "modify" if a.get("set") else "read")
def sys_power_profile(a, ctx):
    if a.get("set"):
        sh(["powerprofilesctl", "set", a["set"]], check=True)
    return sh(["powerprofilesctl", "get"]).stdout.strip()


@tool("sys_snapshot", "btrfs snapshots of the system: list, create (with a description), or undo the changes between two snapshot numbers. Needs root mode.",
      {"action": {"type": "string", "enum": ["list", "create", "undo"]}, "description": {"type": "string"}, "from": {"type": "integer"}, "to": {"type": "integer"}},
      required=("action",), cap="snapshot", risk=lambda a: "destructive" if a.get("action") == "undo" else "privileged")
def sys_snapshot(a, ctx):
    return root.call("snapper", action=a["action"], description=a.get("description", "amadeus"), frm=a.get("from"), to=a.get("to"))


@tool("sys_config_write", "Write a system configuration file under /etc. The old file is backed up first. Login, sudo, PAM, ssh and fstab files are refused unless root mode is unrestricted. Needs root mode.",
      {"path": {"type": "string"}, "content": {"type": "string"}}, required=("path", "content"), cap="sys.manage", risk="privileged")
def sys_config_write(a, ctx):
    return root.call("write_file", path=a["path"], content=a["content"])


@tool("sys_root_exec", "Run an arbitrary command as root. Only available when the user enabled *unrestricted* root mode; prefer the specific tools.",
      {"argv": {"type": "array", "items": {"type": "string"}}}, required=("argv",), cap="sys.manage", risk="privileged")
def sys_root_exec(a, ctx):
    return root.call("exec", argv=a["argv"])
