# Working on Amadeus OS

Instructions for anyone changing this repository: people and AI coding agents alike.
Read this file first. Then read the task guide for the area you are about to touch
**before** you edit anything in it. The guides are short and each one exists because
that area has rules you cannot infer from the code.

This file states rules and points at sources of truth. It does not restate what the
code says, so it stays true as the code changes. `./build.sh check` fails when a path,
guide or command named here no longer exists, or when a new area has no guide.

## Task guides

| If you touch | Read first | It covers |
|---|---|---|
| `installer/` | [agents/installer.md](agents/installer.md) | disk layout, package lists, what "minimal" means here |
| `desktop/` | [agents/desktop.md](agents/desktop.md) | compositor defaults, bar, system commands, the two-layer config rule |
| `ai/` | [agents/ai.md](agents/ai.md) | the single enforcement point, tools, policy, root helper, generated apps, the agent skill |
| `iso/`, `test/`, `build.sh` | [agents/build-and-test.md](agents/build-and-test.md) | container build, VM harness, self-test |
| `docs/`, `agents/`, `README.md`, this file | [agents/docs.md](agents/docs.md) | what goes where, how to keep it from going stale |

When a task spans areas, read each guide. For why a component was chosen, read
`docs/DECISIONS.md`; for how the parts fit, `docs/ARCHITECTURE.md`. Do not replace a
component chosen there without adding the evidence to that file in the same change.

## Documentation layout

| Audience | Lives in | Rule |
|---|---|---|
| Users | `README.md`, and each command's own `--help` and header comment | The manual for a command is the command. |
| AI agents on an installed system | `ai/skill/` and `ama discover` | Teaches discovery. Never describes the system. |
| Contributors | this file and `agents/` | Rules and procedures. No inventories. |
| Design record | `docs/` | Decisions with evidence, architecture, roadmap. |

Never copy a list that the repository can produce (packages, commands, tools, key
bindings) into prose. Point to the file or the command that produces it.

## Style

**Bash**
- `#!/bin/bash`. Line 2 is a comment saying what the program does in one sentence:
  `ama discover` shows that line to users and agents as the program's description.
- `set -euo pipefail` in anything that changes the system.
- Two-space indent. `[[ ]]`, not `[ ]`. Quote expansions unless word splitting is the point.
- Lower-case for locals, upper-case for settings a caller or answers file provides.
- Messages are for the user of the machine: say what happened and what to do, in plain
  words. A failed step names the way back.

**Python** (the AI layer)
- Standard library only. No third-party imports, ever: see [agents/ai.md](agents/ai.md).
- Small modules, plain functions, no frameworks.

**QML**: use the shared components in `ai/shell/components/`; colours and sizes come from
the theme component, never literals in an app.

**Everywhere**: no dead code, no speculative options, no comments that narrate the code.
A comment explains a reason that the code cannot.

## Command naming

- System commands are `amadeus-<what>`: `amadeus-update`, `amadeus-rollback`. They live
  in `desktop/bin/` (or `installer/` and `iso/live/` for the install medium).
- Everything about the AI layer is a subcommand of `ama`.
- No other names. A new verb for users is a new `amadeus-` command or `ama` subcommand,
  never a bare name that could collide with a package.

## Runtime environment

- The AI layer finds its files through `AMADEUS_CONFIG`, `AMADEUS_STATE`, `AMADEUS_DATA`,
  `AMADEUS_RUN`, `AMADEUS_SHARE` and `AMADEUS_PRIV_SOCK`, defaulting to the XDG
  locations. Tests rely on these overrides: never hard-code a path under a home directory.
- Code runs in three places that differ: the build container (no session, no GPU), the
  test VM (no NVIDIA card, no battery, no Wi-Fi), and the real machine. Anything that
  assumes hardware must check for it and carry on without it.
- The compositor socket may be absent (daemon started before the session). Look it up
  when needed; do not cache it at start.

## Platforms

One target: x86_64, the machine in `README.md`. Do not add support for hardware that
machine does not have. Hardware that is present only sometimes is detected, never
assumed:

- NVIDIA packages and settings apply only when the card is found at install time.
- Never run a tool that wakes the NVIDIA card (for example `nvidia-smi`) to read its
  state. Read sysfs.
- Nothing may select the NVIDIA card globally. Offload is per application.

## Privileged commands

- The AI daemon never runs as root and never calls `sudo`. Root actions go through the
  root helper in `ai/priv/`, which exists only while the user has root mode on.
- A user-facing command that needs root either re-runs itself through `sudo` at the top
  (so the user sees one password prompt and knows why) or refuses to run as root when it
  must build or download as the user. Follow the existing commands.
- Never add a passwordless sudo rule, a polkit rule that allows without asking, or a
  setuid file. The one exception is the user's own switch, `desktop/bin/amadeus-sudo`:
  it asks for the password to turn on, writes a single rule for that user, and a timed
  setting ends by itself and at restart. Nothing else may create such a rule, and
  nothing may turn that switch on for the user.
- **Never run the installer, a package manager, or any system-changing command on the
  machine you are developing on.** Everything is built and tested in the container and
  the VM. This is the project's hardest rule.

## Git

- One logical change per commit. A commit that needs "and" in its subject is two commits.
- Subject in the imperative, under 72 characters. The body says why, then what was
  verified and what was not ("checked in the container; not yet run in a VM").
- Commit and push each finished step; do not sit on work.
- Never commit build output (`out/`), secrets, or a file a build step generates.

## Helper commands

Use what exists before writing something new.

- `./build.sh` is the only entry point for building and testing. Read its header.
- In the installer, packages come from the lists in `installer/`; do not install a
  package from inside a script body.
- In the AI layer, run subprocesses through the registry's helper, record a file before
  changing it so it can be undone, and register every capability with the tool decorator.
  [agents/ai.md](agents/ai.md) names them.
- On an installed system, `ama discover` tells you what exists. Use it instead of guessing.

## Background work

Battery life and idle memory are requirements.

- No polling when an event exists. The bar follows the compositor's event stream; do the
  same for anything new.
- No new always-running process without a line in `docs/DECISIONS.md` saying what it
  costs and why that is worth it.
- The daemon does nothing while idle: no timers, no periodic checks.

## Tests

| When | Run |
|---|---|
| Before every commit | `./build.sh check` |
| You changed `installer/`, `iso/`, `desktop/`, a package list, or anything that runs at boot | `./build.sh iso` then `./build.sh test` |
| You added something a user can see or run | add a line to `test/selftest.sh` in the same change |

A change is not done until the check that covers it has run. If you could not run it,
say so in the commit body. Never weaken a check to make it pass.

## Refresh pattern

How a configuration change reaches a running system:

1. **Defaults ship in the package** under `/usr/share/amadeus-os/`. Updating the package
   updates them.
2. **The user's file includes the defaults** and adds overrides. Updates never rewrite a
   user's file.
3. **Changes apply live.** The compositor and the bar watch their files; the daemon
   reloads on `ama reload`. A change must never require logging out.
4. **Write, validate, keep or restore.** Anything that writes configuration validates
   the result as a whole and puts the previous content back if validation fails.

A new setting follows all four. If it cannot, it needs a reason in the commit.
