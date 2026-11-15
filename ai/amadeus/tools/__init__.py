"""Tool registry. A tool declares the capability it needs and how risky a given
call is; the daemon consults policy before running it."""
import subprocess

REGISTRY = {}


class ToolError(Exception):
    pass


def tool(name, desc, params=None, required=(), cap="sys.read", risk="read"):
    """risk may be a string or a function(args) -> string."""
    def deco(fn):
        REGISTRY[name] = {"name": name, "description": desc, "cap": cap, "risk": risk, "fn": fn,
                          "schema": {"type": "object", "properties": params or {}, "required": list(required)}}
        return fn
    return deco


def risk_of(t, args):
    return t["risk"](args) if callable(t["risk"]) else t["risk"]


def sh(argv, timeout=30, input=None, env=None, cwd=None, check=False, binary=False):
    try:
        p = subprocess.run(argv, capture_output=True, text=not binary, timeout=timeout, input=input, env=env, cwd=cwd)
    except FileNotFoundError:
        raise ToolError(f"{argv[0]} is not installed")
    except subprocess.TimeoutExpired:
        raise ToolError(f"{argv[0]} timed out after {timeout}s")
    if check and p.returncode:
        message = (p.stderr or p.stdout)
        if isinstance(message, bytes): message = message.decode(errors="replace")
        raise ToolError(message.strip()[:2000] or f"{argv[0]} failed ({p.returncode})")
    return p


def clip(s, n=12000):
    return s if len(s) <= n else s[:n] + f"\n...[truncated, {len(s)} chars total]"


def load_all():
    from . import system, files, shell, desktop, network, apps, controls, interaction, automations, notes  # noqa: F401
    return REGISTRY


# The tools a model is always shown. Everything else is found with tool_find and run with
# tool_call, so a request does not carry every definition and the list stays byte-stable
# for prompt caching. Keep this to what most requests need.
CORE = ("system_guide", "system_discover", "tool_find", "sys_status", "fs_list", "fs_read", "fs_search", "fs_write", "fs_edit",
        "shell_run", "os_menu", "desktop_settings", "desktop_launch", "memory_save", "goal_update")
TOOL_CALL = {"name": "tool_call", "description": "Run a tool that tool_find returned. It passes the same permission policy, approval and audit "
             "as a listed tool; args must follow that tool's schema.",
             "schema": {"type": "object", "properties": {"name": {"type": "string"}, "args": {"type": "object"}}, "required": ["name"]}}


def spec(t):
    return {"name": t["name"], "description": t["description"], "schema": t["schema"]}


def specs(everything=False):
    if everything:
        return [spec(t) for t in REGISTRY.values()]
    return [spec(REGISTRY[name]) for name in CORE if name in REGISTRY] + [TOOL_CALL]


def unwrap(name, args):
    """tool_call is only an envelope: policy, approval and audit see the tool inside it."""
    if name == "tool_call" and isinstance(args, dict):
        return args.get("name"), args.get("args") if isinstance(args.get("args"), dict) else {}
    return name, args
