# Changing the AI layer

Read `AGENTS.md` first. This area is the security boundary of the system; its rules are
not style.

`ai/` builds the `amadeus` package. `ai/amadeus/` is the daemon and its tools,
`ai/priv/` the root helper, `ai/shell/` the UI components and AI surfaces,
`ai/skill/` the guide shipped for agents on an installed system.

## Invariants

1. **One enforcement point.** Every action the AI takes, from any provider, the MCP
   bridge, a generated app or the command line, passes through the daemon's `execute`
   method in `ai/amadeus/daemon.py`: policy, then approval, then run, then audit. Never
   add a path that reaches a tool function without it.
2. **Standard library only.** No third-party Python packages. A system update must not
   be able to break the layer, and the code must stay small enough to audit.
3. **The daemon is never root.** Privileged work is a request to the helper in
   `ai/priv/`, which validates it again on its own side. The helper must stay able to
   refuse: do not move validation out of it.
4. **Root mode never persists.** Nothing may enable it at boot or keep it across a
   shutdown.
5. **Reads never prompt; destructive and privileged actions always do.** A tool declares
   its capability and risk truthfully. When risk depends on the arguments, pass a
   function. Do not lower a risk level to avoid a prompt.
6. **Undo and audit.** A tool that changes a file records it first (`remember` in
   `ai/amadeus/tools/files.py`). The audit log is hash-chained; never write to it except
   through `ai/amadeus/audit.py`.
7. **Generated apps are untrusted.** They run in the sandbox with only what their
   manifest declares. Never give an app a capability by default.
8. **Secrets** are read through the config module and are scrubbed from the audit log.
   Never log a request body that could hold one.

## Adding a tool

Register it with the `tool` decorator in `ai/amadeus/tools/__init__.py`, in the module
for its area. Give it the narrowest capability, an honest risk, and a description that
tells a model when to use it. If it introduces a capability, add the default to the
policy in `ai/amadeus/config.py` (ask, unless it only reads). Add a test.

## The agent skill

`ai/skill/` must never describe the system. It teaches how to discover it, and
`ai/amadeus/discover.py` builds the map by inspecting the machine. If you are tempted to
write a fact about the system into the skill, make the map report it instead.

## Checking your change

`./build.sh check` runs the unit tests in `ai/tests/`. They use the environment
overrides, so they never touch your own configuration. Changes to the helper, the
service or anything session-dependent also need the VM test.
