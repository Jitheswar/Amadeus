---
name: amadeus
description: Configure and manage an Amadeus OS system. Use when asked to change, inspect, fix, install, remove, update or roll back anything on this machine: desktop, shortcuts, panels, windows, packages, services, GPU, AI providers, permissions, generated apps, snapshots. Triggers: Amadeus, ama, Hyprland, desktop, keybinding, bar, widget, workspace, install, update, rollback, snapshot, root mode, provider, NVIDIA.
---

# Managing an Amadeus OS system

This skill does not describe the system. It tells you how to find out what the system
is, because the system changes with every update and anything written here would go
stale. **Look first, every time. Do not rely on what you remember about Amadeus, Hyprland,
or Arch from training or from an earlier session.**

## 1. Get the map

```
ama discover          # human-readable
ama discover --json   # for parsing
```

It is built by inspecting the machine at the moment you run it: installed versions,
every command the system ships with its own one-line purpose, where the shipped defaults
live, which of the user's configuration files exist, the AI tools with the capability
each needs, and the current permission policy. If you are connected to the `amadeus`
MCP server, the `system_discover` tool returns the same map.

If `ama` is missing, this is not an Amadeus system; stop and say so.

## 2. Go deeper by asking the system, not by guessing

| To learn | Ask |
|---|---|
| What a command does and accepts | `<command> --help`, or read it: `ama discover` lists them and most are short scripts |
| Every file a package owns | `pacman -Qlq <package>` |
| Which package owns a file | `pacman -Qo <path>` |
| What is installed on purpose | `pacman -Qqe` |
| What the desktop is doing now | `hyprctl -j clients`, `workspaces`, `monitors`, `activewindow` |
| Every shortcut and what it does | `hyprctl -j binds` (each carries a description) |
| Whether a desktop config loads | `Hyprland --verify-config --config <file>` |
| What a service is and does | `systemctl cat <unit>`, `systemctl status <unit>` (add `--user` for session units) |
| What happened | `journalctl -b -p warning`, `ama audit` |
| Whether the machine is healthy | `ama doctor` |

Read the shipped default before changing behaviour: it is the real, current example of
the syntax. Its location is in the map under "defaults shipped with the system".

## 3. Rules that do not change

These are properties of the design, not details that drift.

1. **Two layers.** Files under `/usr` and `/etc/skel` belong to the system and are
   replaced on update. Never edit them. The user's files in their home directory
   include the defaults and override them. The map shows which user files exist.
2. **Prefer the system's own tools to editing files.** When the map lists a tool or
   command for the job (shortcuts, bar layout, default applications, providers), use
   it: those paths validate the change, record it in the audit log, and can undo it.
3. **Validate before you apply.** For the desktop, run `Hyprland --verify-config`. A rejected
   config must not be left in place. For anything else, find the checker the same way
   you found the command.
4. **System changes are snapshotted and reversible.** Package changes take a snapshot
   before and after. Find the way back with `amadeus-rollback` before you make a risky
   change, and tell the user which snapshot is the safe point.
5. **You do not have root unless the user turned it on.** `ama status` shows root mode.
   If a change needs it and it is off, say what you need and stop. Only the user turns
   it on; do not look for another route to root.
6. **A permission denial is an answer.** Do not retry through a different tool, a
   shell, or a script to get the same effect.
7. **Do not wake the NVIDIA GPU to look at it.** Read its state from the map or
   `ama status`. Run a program on it only when that program benefits.
8. **Destructive means ask.** Deleting files, removing packages, rolling back, changing
   disk or boot configuration: confirm with the user first, naming exactly what goes.

## 4. Working method

1. Run `ama discover`. Find the command, tool or file that owns what you were asked about.
2. Read its current state and the shipped default.
3. Make the smallest change in the user's layer, through a system tool when one exists.
4. Validate, then check the result by observing the system, not by assuming.
5. Say what changed, where, and how to undo it.

If the map and this skill disagree, the map is right: it is the system describing
itself, and this file may be older than the system it is installed on.
