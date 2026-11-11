# Amadeus

An AI-native layer for a minimal Arch Linux system, built for one machine:
Dell laptop, Core i5-13450HX, RTX 3050 6 GB + Intel UHD, 16 GB RAM, 1 TB NVMe.

The AI is part of the operating system rather than a chat window beside it. It reads
real system state, acts through permission-checked tools, reshapes the desktop, and
builds sandboxed applications on demand. The base OS works unchanged without it.

```
ama "why is the fan loud?"                     # inspects, then answers or fixes
ama "put the weather widget after the clock"   # changes the bar
ama "build me a habit tracker"                 # generates a sandboxed app
SUPER+Z                                        # the same, from the desktop
```

## Install

```
./install.sh            # user level, no root: `ama`, session daemon, SUPER+Z palette
./install.sh --system   # also installs the pacman package with the root-mode helper
ama doctor              # verify drivers, GPU, sandbox, providers, applications
```

## Everyday commands

| | |
|---|---|
| `ama <request>` / `ama chat` | ask for something / interactive session |
| `ama status` | provider, root mode, machine state |
| `ama provider` · `ama provider use NAME` · `ama provider key NAME` | list, switch, store an API key |
| `ama root on [--ttl MIN] [--full]` · `ama root off` | let the AI make system changes, until shutdown at most |
| `ama app list` · `run` · `history` · `rollback` · `remove` | generated applications |
| `ama audit` · `ama audit verify` | what the AI did; check the log was not altered |
| `ama undo` | restore the last file the AI changed |

Configuration is one file, `~/.config/amadeus/config.toml`: providers and the
allow / ask / deny policy per capability.

## Layout

```
amadeus/            daemon, policy, audit, providers, tools, app framework (Python stdlib only)
shell/              palette, approval prompt, shared UI components (QML)
priv/               root-mode helper and polkit action
packaging/          PKGBUILD
system/             package set and hardware notes for a clean rebuild
tests/              python3 -m unittest discover -s tests
docs/               ARCHITECTURE.md, ROADMAP.md
```
