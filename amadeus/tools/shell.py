"""Command execution. Sandboxed by default; the host shell always asks."""
import os
from . import tool, sh, clip
from .. import config
from ..sandbox import bwrap


@tool("shell_run", "Run a shell command. By default it runs in a sandbox: read-only system, no network, no home directory, "
      "and a persistent scratch workspace as the working directory. Set host=true to run on the real system as the user "
      "(the user is asked every time). Set network=true if the sandboxed command needs the internet.",
      {"command": {"type": "string"}, "host": {"type": "boolean"}, "network": {"type": "boolean"}, "timeout": {"type": "integer"},
       "nvidia": {"type": "boolean", "description": "give the sandbox the NVIDIA GPU (CUDA)"}},
      required=("command",), cap=None, risk=lambda a: "destructive" if a.get("host") else "read")
def shell_run(a, ctx):
    t = min(int(a.get("timeout", 120)), 1800)
    if a.get("host"):
        p = sh(["bash", "-c", a["command"]], timeout=t, cwd=os.path.expanduser("~"))
    else:
        argv = bwrap(["bash", "-c", a["command"]], rw=[config.WORKSPACE], net=bool(a.get("network")),
                     nvidia=bool(a.get("nvidia")), cwd=config.WORKSPACE)
        p = sh(argv, timeout=t)
    return clip(f"exit {p.returncode}\n{p.stdout}" + (f"\n[stderr]\n{p.stderr}" if p.stderr.strip() else ""))


# The capability depends on where it runs.
from . import REGISTRY
REGISTRY["shell_run"]["cap"] = lambda a: "shell.host" if a.get("host") else "shell.sandbox"
