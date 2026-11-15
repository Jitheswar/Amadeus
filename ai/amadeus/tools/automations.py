"""User-visible automations, never a route around tool permissions."""
from . import tool, ToolError
from .. import tasks


@tool("task_manage", "List, save, enable/disable or remove an Amadeus task. Tasks are disabled unless enabled=true is explicit. "
      "A timer uses a systemd calendar expression; an event is app-focused, battery-low, network-changed, "
      "unit-failed (a service failed) or disk-low. match filters the app id, connection, unit or mount name. A provider name is optional (empty uses the saved default). "
      "Every automated change still asks at execution time; root mode and approvals are never saved in a task.",
      {"action": {"type": "string", "enum": ["list", "save", "enable", "disable", "remove"]},
       "id": {"type": "string"}, "label": {"type": "string"}, "prompt": {"type": "string"},
       "trigger": {"type": "string", "enum": ["timer", "event"]}, "calendar": {"type": "string"},
       "event": {"type": "string", "enum": list(tasks.EVENTS)}, "match": {"type": "string"},
       "cooldown": {"type": "integer"}, "provider": {"type": "string"}, "enabled": {"type": "boolean"}},
      cap="tasks.manage", risk=lambda a: "read" if a.get("action", "list") == "list" else ("destructive" if a.get("action") == "remove" else "modify"))
def task_manage(a, ctx):
    action = a.get("action", "list")
    if action == "list": return tasks.listing()
    if action == "save": return tasks.save(a)
    if action in ("enable", "disable"):
        job = tasks.load(a.get("id")); job["enabled"] = action == "enable"
        return tasks.save(job)
    if action == "remove":
        with ctx.daemon.lock:
            if a.get("id") in getattr(ctx.daemon, "active_tasks", set()):
                raise ToolError("stop this running task before removing it")
            return tasks.remove(a.get("id"))
    raise ToolError("unknown task action")
