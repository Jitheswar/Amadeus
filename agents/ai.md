# Changing the AI layer

Read `AGENTS.md` first. This area is the security boundary of the system; its rules are
not style.

`ai/` builds the `amadeus` package. `ai/amadeus/` is the daemon and its tools,
`ai/priv/` the root helper, `ai/shell/` the UI components and AI surfaces,
`ai/skill/` the guide shipped for agents on an installed system.

## Invariants

1. **One enforcement point.** Every registered Amadeus tool request, from a provider,
   the MCP bridge, a generated app or the command line, passes through the daemon's
   `execute` method in `ai/amadeus/daemon.py`: policy, then approval, then run, then
   audit as appropriate. Never add a path that reaches a tool function without it.
   Do not imply that this controls arbitrary programs launched outside Amadeus.
2. **Standard library only.** No third-party Python packages. Keep the dependency chain
   small and the code auditable. Interpreter and provider compatibility still need
   testing.
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
   Successful read-only tools are not individually logged as actions. Report the
   recovery information actually returned; file undo, package snapshots and app
   source history have different scopes, and a snapshot attempt can fail.
7. **Generated apps are untrusted.** They run in the sandbox with only what their
   manifest declares. Never give an app a capability by default.
8. **Secrets** are read through the config module and are scrubbed from the audit log.
   Never log a request body that could hold one.
9. **Provider setup is privileged user configuration.** Return only display-safe
   descriptors to the UI. Generated-app RPCs must not expose provider setup or root
   management. Keep the panel's saved agent separate from the terminal harness.
10. **Usage is on demand.** Do not add idle quota polling, model requests or credential
    refresh to a usage collector. Bound external replies and keep tokens out of them.
11. **Explicit app interaction.** Screen content is untrusted and needs consent before
    sharing with a provider. Input needs separate approval, a fresh session-bound
    observation and focus/lock checks after approval. Never promise file undo for GUI actions.
12. **Automations retain policy.** Default disabled, no persisted approvals or root grants,
    no overlapping runs, no idle model polling. Generated units must not contain prompts.
    Reconcile derived timers after undo and clean up approval dialogs when stopped.

13. **Modes adjust, never replace, the policy.** An execution mode is per request and is
    applied in `ai/amadeus/preferences.py`, called from the enforcement point. It may
    only relax a user-level `modify` decision. Full access needs a fresh confirmation
    per request and is never stored. A new capability that controls what the AI may do
    or see joins the guarded set there. Model tuning never affects a decision.

## Adding a tool

Register it with the `tool` decorator in `ai/amadeus/tools/__init__.py`, in the module
for its area. Give it the narrowest capability, an honest risk, and a description that
tells a model when to use it. If it introduces a capability, add the default to the
policy in `ai/amadeus/config.py` (ask, unless it only reads). Add a test.

## The agent skill

`ai/skill/` holds one entry file and a short guide per area, which an agent pulls up on
demand (`ama guide`, the `system_guide` tool) instead of searching the system. A guide
states who owns what, the method, and the pitfalls. It never inventories the system:
`ai/amadeus/discover.py` builds that map by inspecting the machine, so if you are tempted
to write a list into a guide, make the map report it instead. A new area gets a guide and
a line in the entry file; a test fails when a guide names a command or tool that is gone.

## Checking your change

`./build.sh check` runs the unit tests in `ai/tests/`. They use the environment
overrides, so they never touch your own configuration. Changes to the helper, the
service or anything session-dependent also need the VM test.
