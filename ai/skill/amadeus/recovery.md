# Recovery: undo, snapshots, rollback

Read this before a risky change and whenever something has gone wrong.

## Three mechanisms, three scopes

| Mechanism | Covers | How |
|---|---|---|
| File undo | Files the AI changed through its file tools | `ama undo`, or Undo on the task in the panel |
| System snapshots | The system root, not the home directory | `sys_snapshot`; `amadeus-rollback` to choose one |
| App history | A generated app's source | `app_rollback` |

Nothing here is a backup of personal data. Say so when it matters.

## Before risk

1. Find out which mechanism covers what you are about to change.
2. For system changes, list snapshots and make sure a recent one exists; create one
   with a description if not. This needs root mode.
3. Name a safe point to the user only after confirming it exists.

## After a failure

- Desktop does not load a change: restore the previous file, then verify the config.
- A package change broke something: compare the snapshot pair the package tool
  reported, and offer `amadeus-rollback`. Rolling back is destructive: confirm first.
- The system does not boot: `amadeus-rollback` also runs from the install medium.
- Actions on an application's window have no undo. Do not promise one.

Read `journalctl -b -p warning` and `ama audit` to learn what happened before
proposing a fix.
