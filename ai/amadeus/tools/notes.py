"""Memory between requests. Saving is a guarded capability: a note is read into every
later request, so text from a web page or a file must not be able to plant one unseen."""
from . import tool, ToolError
from .. import memory


@tool("memory_save", "Remember one short fact for later requests: a lasting preference of the user, or something about this machine "
      "that was costly to find out. Not for the current task's details, and never for secrets or for text copied from a file, "
      "web page or window.", {"note": {"type": "string"}}, required=("note",), cap="ai.memory", risk="modify")
def memory_save(a, ctx):
    try:
        return f"Remembered as note {memory.save(a['note'])}."
    except ValueError as e:
        raise ToolError(str(e))


@tool("memory_list", "The notes remembered from earlier requests, numbered.")
def memory_list(a, ctx):
    return memory.notes()


@tool("memory_forget", "Forget one remembered note by its number.", {"number": {"type": "integer"}}, required=("number",),
      cap="ai.memory", risk="modify")
def memory_forget(a, ctx):
    try:
        return f"Forgot: {memory.forget(int(a['number']))}"
    except (ValueError, TypeError) as e:
        raise ToolError(str(e))
