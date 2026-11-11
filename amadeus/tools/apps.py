"""Tools that let the AI build, change and run applications."""
from . import tool, ToolError
from .. import apps

GUIDE = """Apps are QML run by Quickshell in a sandbox. Entry point: shell.qml. Start it with
  import QtQuick
  import Quickshell
  import "Amadeus"
and use AppWindow { title: "..." ... } as the root. Build the interface from the shared components
(AppWindow, Card, Txt{dim,mono,title}, Btn{text,primary,onClicked}, Field{text,placeholder,onAccepted},
Stat{label,value,tone}, Meter{label,value 0..1,caption}) and the Theme singleton (Theme.bg, fg, accent,
good, warn, bad, surface, raised, line, dim, gap, radius, size, font, mono) so every app matches the desktop.
Use QtQuick positioners/Layouts for structure. To reach the system, declare tools in permissions.tools and use
  Os { id: os }  ...  os.call("sys_status", {}, r => { if (r.ok) use(r.result) })
Persistent private data: files under Quickshell.env("AMADEUS_APP_DATA") via FileView (Quickshell.Io).
Permissions: {network: bool, nvidia: bool, ai: bool, files: [{path, mode: ro|rw}], tools: [tool names]}.
Request the least that works; anything beyond an empty set is shown to the user for approval."""

PERM = {"type": "object", "description": "declarative permissions; omit for none"}
FILES = {"type": "object", "description": "map of relative file name -> full content; null deletes a file", "additionalProperties": {"type": ["string", "null"]}}


def _risk_create(a):
    want = apps.normalise(a.get("permissions"))
    try:
        have = apps.manifest(a.get("id", ""))["permissions"]
    except apps.AppError:
        have = apps.EMPTY
    return "privileged-grant" if apps.exceeds(want, have) and a.get("permissions") is not None else "modify"


@tool("app_guide", "How to write an Amadeus app: structure, component library, OS bridge, permissions. Read this before app_save.", cap="app.build")
def app_guide(a, ctx):
    return GUIDE


@tool("app_save", "Create a new app, or update an existing one by sending only the files that change. "
      "The result is linted, versioned, and added to the launcher.",
      {"id": {"type": "string"}, "name": {"type": "string"}, "description": {"type": "string"}, "files": FILES, "permissions": PERM,
       "note": {"type": "string", "description": "one line describing this change"}},
      required=("id",), cap=lambda a: "app.grant" if _risk_create(a) == "privileged-grant" else "app.build",
      risk=lambda a: "destructive" if _risk_create(a) == "privileged-grant" else "modify")
def app_save(a, ctx):
    try:
        m = apps.save(a["id"], a.get("name"), a.get("description"), a.get("files"), a.get("permissions"), a.get("note", ""))
    except apps.AppError as e:
        raise ToolError(str(e))
    return {"saved": m["id"], "version": m["version"], "permissions": m["permissions"]}


@tool("app_list", "List generated apps with their permissions.", cap="app.build")
def app_list(a, ctx):
    return apps.list_apps()


@tool("app_read", "Read an app's manifest, history and source files, to modify or extend it.", {"id": {"type": "string"}}, required=("id",), cap="app.build")
def app_read(a, ctx):
    try:
        d = apps.app_dir(a["id"])
        m = apps.manifest(a["id"])
    except apps.AppError as e:
        raise ToolError(str(e))
    files = {str(f.relative_to(d)): f.read_text() for f in sorted(d.rglob("*"))
             if f.is_file() and not {".git", "data", "Amadeus"} & set(f.relative_to(d).parts) and f.suffix in (".qml", ".js", ".json", ".txt", ".md")}
    return {"manifest": m, "history": apps.history(a["id"]), "files": files}


@tool("app_run", "Open a generated app in its sandbox.", {"id": {"type": "string"}}, required=("id",), cap="apps.launch", risk="modify")
def app_run(a, ctx):
    try:
        return ctx.daemon.run_app(a["id"])
    except apps.AppError as e:
        raise ToolError(str(e))


@tool("app_rollback", "Restore an earlier version of an app (default: the previous one).", {"id": {"type": "string"}, "version": {"type": "integer"}},
      required=("id",), cap="app.build", risk="modify")
def app_rollback(a, ctx):
    try:
        m = apps.rollback(a["id"], a.get("version"))
    except apps.AppError as e:
        raise ToolError(str(e))
    return {"restored": m["id"], "version": m["version"]}


@tool("app_remove", "Remove a generated app (kept in a recovery folder).", {"id": {"type": "string"}}, required=("id",), cap="app.build", risk="destructive")
def app_remove(a, ctx):
    try:
        return f"removed; recoverable at {apps.remove(a['id'])}"
    except apps.AppError as e:
        raise ToolError(str(e))
