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


def sh(argv, timeout=30, input=None, env=None, cwd=None, check=False):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, input=input, env=env, cwd=cwd)
    except FileNotFoundError:
        raise ToolError(f"{argv[0]} is not installed")
    except subprocess.TimeoutExpired:
        raise ToolError(f"{argv[0]} timed out after {timeout}s")
    if check and p.returncode:
        raise ToolError((p.stderr or p.stdout).strip()[:2000] or f"{argv[0]} failed ({p.returncode})")
    return p


def clip(s, n=12000):
    return s if len(s) <= n else s[:n] + f"\n...[truncated, {len(s)} chars total]"


def load_all():
    from . import system, files, shell, desktop, network, apps  # noqa: F401
    return REGISTRY


def specs():
    return [{"name": t["name"], "description": t["description"], "schema": t["schema"]} for t in REGISTRY.values()]
