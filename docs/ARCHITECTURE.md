# Architecture

Why each component was chosen is in [DECISIONS.md](DECISIONS.md). This file describes how
the parts work together.

## Components

```
 palette (SUPER+Z)   ama CLI   Claude Code / Desktop / Codex      generated apps
        \              |              | MCP (ama mcp)                  | per-app socket,
         \             |              |                                | manifest tools only
          +------------+--------------+--------------------------------+
                                      |
                              amadeusd  (user service)
           providers ── agent loop ── Daemon.execute ── tools
                                      |   policy → approval → run → audit
                                      |
                    root mode off: stops here      root mode on: /run/amadeus/priv.sock
                                                   amadeus-priv (transient root unit)
```

`Daemon.execute` is the single enforcement point. Nothing reaches a tool except
through it, whichever model, client or app made the request.

### Providers

| type | covers | loop runs in |
|---|---|---|
| `anthropic` | Claude API | daemon |
| `openai` | OpenAI, OpenRouter, ollama, llama.cpp, any compatible endpoint | daemon |
| `claude-cli` | Claude subscription | Claude Code, tools via MCP |
| `codex-cli` | ChatGPT/Codex subscription | codex, tools via MCP |

History is kept in a neutral format, so `ama provider use` switches models even in
the middle of a conversation.

### Tools (39)

System state and processes, services, journal, packages, power profile, snapshots,
system config; files with undo; sandboxed and host shell; windows, workspaces,
launching with GPU selection, keybindings, bar/widgets/themes; network; app
build/update/run/rollback.

### Generated applications

An app is a directory under `~/.local/share/amadeus/apps/<id>`: QML sources, a
`manifest.json`, a private `data/` directory, and its own git history.

- **Declarative permissions:** `network`, `nvidia`, `ai`, `files` (path + ro/rw),
  `tools` (which OS tools the app may call). The sandbox command line is generated
  from the manifest and nothing else; `ama app command ID` prints it.
- **Empty manifest:** a window on the Intel GPU and its own data directory. No
  network, no home directory, no D-Bus, read-only system, private PID namespace.
- **Asking:** creating or updating an app with no new permissions does not prompt.
  Any widening of permissions is shown to the user first.
- **Incremental updates:** an update sends only changed files, is syntax-checked
  before it replaces the working version, and becomes a commit. `rollback` restores
  any earlier version.
- **OS access from inside:** the `Os` component speaks to a per-app socket. The
  daemon checks each call against the manifest, then against system policy; any
  call that changes state prompts even if policy would allow it for the user.

## Security model

| risk | meaning | handling |
|---|---|---|
| read | observes | allowed by policy, except protected paths |
| modify | reversible user-level change | policy: allow, ask, or deny; "always this session" possible |
| destructive | data loss or hard to undo; host shell; window-manager Lua | always asks, never remembered |
| privileged | needs root | refused unless root mode is on, then always asks |

- **Protected paths** (ssh and gpg keys, keyrings, provider credentials, the secrets
  directory) are denied even for reads, after resolving `..` and symlinks.
- **Root mode** is a transient systemd unit started through polkit authentication.
  It is never enabled, so it cannot exist after a shutdown; `--ttl` ends it sooner.
  The helper accepts one user id (SO_PEERCRED) and, unless started with `--full`,
  only validated operations: systemctl, pacman, snapper, writing files under `/etc`
  (login, sudo, PAM, ssh, fstab excluded). Arbitrary root commands need `--full`.
- **Transactions:** package changes are wrapped in a snapper pre/post pair and return
  the undo command. System files are backed up before replacement. User files the AI
  writes are journalled for `ama undo`, and written atomically.
- **Audit:** every action, denial and request is appended to a hash-chained log with
  secrets redacted. `ama audit verify` detects edits or deletions.
- **Injected instructions:** the model is told that tool output is data, but the real
  defence is structural: whatever text the model reads, it cannot destroy, escalate
  or leave the sandbox without a prompt that shows the user the exact action.
- **Unapproved by default:** prompts time out to "no"; closing the dialog, Enter and
  Escape all decline.

## Hardware

- The panel is wired to the Intel GPU; the compositor and ordinary apps render there.
- The RTX 3050 runtime-suspends when idle. Amadeus reads its state from sysfs and
  never calls `nvidia-smi` on a sleeping card, since that wakes it.
- `desktop_launch` selects the GPU per application: NVIDIA for games and apps that
  declare `PrefersNonDefaultGPU`, Intel otherwise, with an explicit override. No
  global variable forces NVIDIA.
- Video decode: Intel VA-API (`intel-media-driver`) for the desktop and browser;
  NVDEC through `libva-nvidia-driver` when an app runs on the NVIDIA card.
- Vulkan: Intel and NVIDIA ICDs, 64- and 32-bit, for Steam and Proton.
- CUDA is not preinstalled (about 5 GB). Install `cuda cudnn` when needed; sandboxes
  get the card with `nvidia: true`.
- Power: power-profiles-daemon and thermald, nothing overlapping.
