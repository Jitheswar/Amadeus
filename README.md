# Amadeus OS

*El Psy Kongroo.*

A minimal, rolling Linux distribution in which the AI is part of the operating system:
it reads real system state, acts through permission-checked tools, rearranges the
desktop, and builds sandboxed applications on demand. The system underneath is complete
and works without any AI provider or network connection.

It is built for one machine: Core i5-13450HX, RTX 3050 6 GB with Intel UHD graphics,
16 GB RAM, 1 TB NVMe. Nothing is included for hardware that machine does not have.

> **Status: pre-release.** The ISO installs, boots and rolls back in a virtual machine,
> passing every check. It has not been installed on real hardware yet. See [Status](#status).

## What you get

| | |
|---|---|
| **Base** | Arch, with packages from the CachyOS repositories (built for newer processors) and the `linux-cachyos` kernel. Rolling. Encrypted btrfs, systemd-boot, compressed swap in RAM. About 750 packages after install. |
| **Recovery** | A snapshot before and after every package change. `amadeus-rollback` returns the system to any of them, from the running system or from the USB stick when it no longer starts. |
| **Graphics** | Intel draws the desktop. The NVIDIA card is powered off until an application is sent to it; nothing forces it on. CUDA, Vulkan and video decode are available on both. |
| **AI layer** | One daemon through which every AI action passes: capability policy, approval for destructive actions, tamper-evident audit log, undo. Works with a Claude subscription or API key, OpenAI-compatible APIs, OpenRouter, Codex, and local models. |
| **Root mode** | The AI has no root access by default. `ama root on` grants it; it ends at shutdown at the latest and must be turned on again. |
| **Generated apps** | The AI writes small applications from a shared component library. Each runs in its own sandbox with only the permissions its manifest declares, and keeps a version history. |
| **Desktop** | Hyprland, with a bar, launcher, menus and notifications drawn by the system's own shell; a scratchpad that floats over everything; screenshots and screen recording built in. |
| **Look** | Its own identity: warm black with a single amber accent, floating rounded surfaces, and short, decisive motion. One theme file drives the shell, the panel and every generated app. |
| **Applications** | Steam, ProtonPlus, Brave Origin, Claude Desktop, Claude Code (through mise, like every AI coding harness), Discord, Telegram, herdr, LocalSend, LibreOffice, mpv, plus a terminal, file manager, document viewer, image viewer and camera. Nothing else. |

### For AI agents

The system ships a skill that teaches any agent (Claude Code picks it up automatically;
`ama skill` prints it for others) to configure and manage it. The skill contains no
description of the system. It tells the agent to run `ama discover`, which builds a map
by inspecting the machine at that moment, and then how to dig further by asking the
system itself. Documentation written into a skill goes stale; a system that describes
itself cannot.

Why each component was chosen, and over what: [docs/DECISIONS.md](docs/DECISIONS.md).
How the pieces fit: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Using it

```
ama "why is the fan loud?"          inspects the system, then answers or fixes it
ama "set up a workspace for writing"  arranges windows, panels and shortcuts
ama "build me a habit tracker"      generates a sandboxed application
```

**The Amadeus panel** (Super+Z) docks to the right edge of the screen and stays there
while you work. Each request is a task: tasks run side by side, each can show its steps,
be stopped, and have everything it changed undone together. **Super+A** opens the panel
pointed at the window you are looking at, so "summarise this" or "make this half width"
means that window.


| | |
|---|---|
| `ama status` | provider, root mode, machine state |
| `ama provider` · `use NAME` · `key NAME` | list providers, switch, store an API key |
| `ama root on [--ttl MIN] [--full]` · `ama root off` | allow system changes for a while |
| `ama app list` · `run` · `history` · `rollback` · `remove` | generated applications |
| `ama audit` · `ama audit verify` · `ama undo` | what the AI did, proof the log is intact, undo the last file change |
| `ama doctor` | check drivers, GPU, sandbox, providers and applications |
| `ama discover` | a live map of the system: commands, files, tools, permissions |
| `Super+K` | every keyboard shortcut and system command, searchable |
| `Super+Space` | the Amadeus menu: Apps, Trigger, Install, Remove, Update, Setup, System, About |
| `Super+Shift+Enter` | your default AI coding harness, in a terminal |
| `Super+C` · `Super+V` · `Super+Ctrl+V` | copy and paste that work the same everywhere, terminals included · clipboard history |
| `Super+S` · `Super+Alt+S` | show or hide the scratchpad over everything · send the focused window to it |
| `Print` | screenshot: the screen freezes; drag an area, click a window, or click empty space for the whole screen. Saved and copied. |
| `Alt+Print` | record the screen (no sound, the computer's sound, or that and the microphone), or stop recording. A red mark in the bar also stops it. |
| `Super+Escape` | lock, suspend, hibernate, log out, restart, shut down |
| `Super+Z` · `Super+A` | the Amadeus panel · the panel, about the focused window |
| `amadeus-update` | update the system and the applications from the AUR |
| `amadeus-aur` | look up, review, build and install applications from the AUR |
| `amadeus-harness` | install, remove, update and run AI coding harnesses (Claude Code, Codex, opencode, Antigravity CLI and others) through mise |
| `amadeus-default` | show or set your default terminal, editor and harness |
| `amadeus-rollback` | list snapshots, or go back to one |

### The bar

| | |
|---|---|
| Left | Workspaces, and the title of the focused window. |
| Centre | Administrator-without-password switch (15 minutes, 30 minutes, 1 hour, or until turned off), stay-awake switch, the day and 12-hour time (click for a calendar), the weather. |
| Right | Applications running in the background, Bluetooth, Wi-Fi, volume, brightness, battery, and the Amadeus button. Each opens a small panel: devices and networks to connect to, sliders, and the power mode. |

Power mode follows the cable: performance when plugged in, balanced on battery, battery
saver under 20%. The layout is a file (`~/.config/amadeus/bar.json`); ask Amadeus to
rearrange it, or edit it.

### The Amadeus menu

| | |
|---|---|
| **Install** | Terminals, browsers, editors, AI desktop apps, development tools, AI coding harnesses, web apps, any package, anything from the AUR. Each list shows details beside it and marks what is installed. Software comes from the system repositories when it is there, and from an AUR recipe of the publisher's own build only when it is not. |
| **Remove** | Packages, harnesses and tools, web apps. |
| **Update** | Everything, or only what mise manages. |
| **Trigger** | Capture: screenshot, and the three kinds of screen recording. |
| **Setup** | Display resolution and scaling, text size, defaults (terminal, editor, harness, browser, and what opens each kind of file), and Config, which opens any of the system's configuration files in your editor. |
| **System** | Lock, suspend, hibernate, log out, restart, shut down. |
| **About** | The facts about this machine. |

## Build

Everything is built and tested inside a container. Nothing is installed on the machine
doing the build. Requirements: Docker and KVM.

```
./build.sh iso     build out/amadeus-os-<date>-x86_64.iso
./build.sh test    install it in a VM, boot the result, run the self-test and both rollback paths
./build.sh preview draw the shell and the panel headless; pictures land in out/preview/
```

## Install

1. Write the ISO to a USB stick:
   `sudo dd if=out/amadeus-os-*.iso of=/dev/sdX bs=4M status=progress oflag=sync`
2. Boot it (UEFI, Secure Boot off). The guided installer starts by itself: keyboard,
   Wi-Fi if there is no cable, your name and password, time zone, disk, encryption,
   applications, then a summary.
3. Nothing is written until you type the disk's name at the summary. Then it installs,
   which takes about ten minutes and downloads packages, and offers to restart.

## Repository

```
installer/   amadeus-install and the package lists: this is the definition of the system
desktop/     the amadeus-desktop package: compositor defaults, bar, system tools
ai/          the amadeus package: daemon, policy, providers, tools, app framework, UI components
iso/         live-medium additions and the ISO build
test/        VM harness: install, first boot, rollback from the system, rollback from the ISO
docs/        decisions, architecture, roadmap
build.sh     entry point
```

## Status

| | |
|---|---|
| Verified in a VM (72 checks, all passing) | UEFI boot and unattended encrypted install; first boot into the desktop (on niri at the time; Hyprland since); snapshots; sandbox, policy and audit log; AI requests end to end with a scripted model (tool run, approval, denial, opening an application, stop, undo of a whole task, two tasks in parallel, audit trail); the Amadeus panel opening and reaching the daemon; the Amadeus menu; Super+K; the agent skill and `ama discover`; the six applications from publisher releases; rollback from the running system, and rollback from the ISO, each followed by a clean boot |
| Built, checked in the VM self-test but not yet passed | Everything since the last full pass: Hyprland, the bar's switches and drop-downs, the install catalogue, capture, the CachyOS base |
| Not yet exercised | A real model driving the system (the VM has no provider login, so the model is scripted); clicking through the panel and bar by hand; the guided installer's screens and its Wi-Fi step (the VM test uses the unattended path behind it); `amadeus-update` |
| Decided, not yet built | A mark on windows the AI is working in |
| Never tested | Real hardware: the NVIDIA driver and power path, Dynamic Boost, Wi-Fi, suspend |

The earlier Arch + Hyprland version is kept under the tag `v0-arch`.

Next steps are in [docs/ROADMAP.md](docs/ROADMAP.md).
