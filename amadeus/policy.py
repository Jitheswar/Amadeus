"""Capability policy. Every tool call is (capability, risk, args) -> allow | ask | deny.

risk levels:
  read         observes state
  modify       changes user-level state, reversible
  destructive  loses data or is hard to undo  -> always asks, never remembered
  privileged   needs root                     -> needs root mode on AND approval
"""
import os
from pathlib import Path


def expand(p):
    return Path(os.path.expanduser(str(p))).resolve()


def _under(path, roots):
    path = expand(path)
    for r in roots:
        r = expand(r)
        if path == r or r in path.parents:
            return True
    return False


class Policy:
    def __init__(self, cfg):
        pol = dict(cfg.get("policy", {}))
        paths = pol.pop("paths", {})
        self.rules = pol
        self.deny_paths = paths.get("deny", [])
        self.free_paths = paths.get("free", [])
        self.session_grants = set()   # capabilities the user chose "always" for; dies with the daemon

    def path_denied(self, path):
        return _under(path, self.deny_paths)

    def decide(self, cap, risk, args=None, root_on=False):
        """Return (decision, reason)."""
        args = args or {}
        for key in ("path", "src", "dst"):
            if key in args and self.path_denied(args[key]):
                return "deny", f"{args[key]} is in a protected location"
        rule = self.rules.get(cap, "ask")
        if rule == "deny":
            return "deny", f"policy denies {cap}"
        if risk == "privileged" and not root_on:
            return "deny", "this needs root mode, which is off (the user enables it with `ama root on`)"
        if risk in ("destructive", "privileged"):
            return "ask", f"{risk} action"
        if risk == "read":
            return "allow", "read-only"
        if cap == "fs.write" and "path" in args and _under(args["path"], self.free_paths):
            return "allow", "inside the free workspace"
        if rule == "allow" or cap in self.session_grants:
            return "allow", "policy"
        return "ask", f"policy asks for {cap}"

    def grant_session(self, cap, risk):
        if risk not in ("destructive", "privileged"):
            self.session_grants.add(cap)
