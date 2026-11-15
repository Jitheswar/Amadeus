# Changing documentation and these guides

Read `AGENTS.md` first, section "Documentation layout".

## What goes where

- `README.md`: what the system is, how to build and install it, and an honest account
  of verification. Update that account when the evidence changes.
- `docs/DECISIONS.md`: one entry per choice: what, over what, and the evidence. A change
  of component edits its entry; it does not append a contradiction.
- `docs/ARCHITECTURE.md`: how the parts work together. No file inventories.
- `docs/ROADMAP.md`: done, in progress, next, not verified.
- `AGENTS.md` and `agents/`: rules for contributors.

## Keeping it true

- **State rules, point at facts.** A rule ("validate before applying") stays true. A
  fact ("there are 39 tools") goes stale; let a command report it.
- **Name a path only when the reader must open it**, and write it in backticks from the
  repository root. `./build.sh check` verifies every such path exists.
- **A new top-level directory needs a row** in the task-guide table and, if it has rules
  of its own, a guide. The check fails without the row.
- **Claims of verification are dated by the commit.** Write what was tested and where
  (container, VM, real machine). Never write "works" for something that has not run.
  Name the runtime baseline when a later documentation-only commit reports existing
  results. A prose refresh needs the fast checks, not a claim that the VM was rerun.
- **Review related audiences together.** Behavior changes can affect the README,
  architecture, decision record, roadmap, contributor rules and installed-agent skill.
  Keep a correct shared pointer such as `CLAUDE.md` instead of duplicating its target.
- **Separate intent from evidence.** Do not present hardware power behavior, provider
  authentication or performance estimates as tested facts. Historical packaging
  rationale is not a claim about a vendor's current distribution channels.
- Plain words. Write for someone reading this for the first time.
- The official line of the distribution is "El Psy Kongroo". It appears at the top of
  `README.md`, on the login screen, and where the installer greets and finishes. Keep it
  exactly as written; do not translate, restyle or explain it.
