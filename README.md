# Amadeus OS

A minimal, rolling Linux distribution in which the AI is part of the operating system:
it reads real system state, acts through permission-checked tools, rearranges the
desktop, and builds sandboxed applications on demand. The system underneath is complete
and works without any AI provider or network connection.

It is built for one machine: Core i5-13450HX, RTX 3050 6 GB with Intel UHD graphics,
16 GB RAM, 1 TB NVMe. Nothing is included for hardware that machine does not have.

> **Status: pre-release.** The ISO installs and passes its self-test in a virtual
> machine. It has not been installed on real hardware yet. See [Status](#status).

## What you get

| | |
|---|---|
| **Base** | Arch packages, rolling. Encrypted btrfs, systemd-boot, compressed swap in RAM. About 750 packages after install. |
| **Recovery** | A snapshot before and after every package change. `amadeus-rollback` returns the system to any of them, from the running system or from the USB stick when it no longer starts. |
| **Graphics** | Intel draws the desktop. The NVIDIA card is powered off until an application is sent to it; nothing forces it on. CUDA, Vulkan and video decode are available on both. |
| **AI layer** | One daemon through which every AI action passes: capability policy, approval for destructive actions, tamper-evident audit log, undo. Works with a Claude subscription or API key, OpenAI-compatible APIs, OpenRouter, Codex, and local models. |
| **Root mode** | The AI has no root access by default. `ama root on` grants it; it ends at shutdown at the latest and must be turned on again. |
| **Generated apps** | The AI writes small applications from a shared component library. Each runs in its own sandbox with only the permissions its manifest declares, and keeps a version history. |
| **Applications** | Steam, ProtonPlus, Brave Origin, Claude Desktop, Claude Code, Discord, Telegram, herdr, LocalSend, LibreOffice, mpv, plus a terminal, file manager, document viewer, image viewer and camera. Nothing else. |

Why each component was chosen, and over what: [docs/DECISIONS.md](docs/DECISIONS.md).
How the pieces fit: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Using it

```
ama "why is the fan loud?"          inspects the system, then answers or fixes it
ama "set up a workspace for writing"  arranges windows, panels and shortcuts
ama "build me a habit tracker"      generates a sandboxed application
SUPER+Z                             the same, from anywhere on the desktop
```

| | |
|---|---|
| `ama status` | provider, root mode, machine state |
| `ama provider` · `use NAME` · `key NAME` | list providers, switch, store an API key |
| `ama root on [--ttl MIN] [--full]` · `ama root off` | allow system changes for a while |
| `ama app list` · `run` · `history` · `rollback` · `remove` | generated applications |
| `ama audit` · `ama audit verify` · `ama undo` | what the AI did, proof the log is intact, undo the last file change |
| `ama doctor` | check drivers, GPU, sandbox, providers and applications |
| `amadeus-update` | update the system and the applications from outside the Arch repositories |
| `amadeus-rollback` | list snapshots, or go back to one |

## Build

Everything is built and tested inside a container. Nothing is installed on the machine
doing the build. Requirements: Docker and KVM.

```
./build.sh iso     build out/amadeus-os-<date>-x86_64.iso
./build.sh test    install it in a VM, boot the result, run the self-test and both rollback paths
```

## Install

1. Write the ISO to a USB stick:
   `sudo dd if=out/amadeus-os-*.iso of=/dev/sdX bs=4M status=progress oflag=sync`
2. Boot it (UEFI, Secure Boot off) and connect to the network.
3. Run `amadeus-install`. It asks for the disk, a user name and a password, then
   **erases that disk**. Packages are downloaded during the install.

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
| Verified in a VM (tag `v0-arch`, the earlier Hyprland desktop) | UEFI boot, unattended encrypted install, first boot into the desktop, snapshots, sandbox, policy, audit log; 35 of 35 checks |
| Built and checked in the build container, not yet run in a VM | The niri desktop (configuration validates; the AI's config tool rejects a bad change and keeps the old one), `amadeus-rollback`, `amadeus-update`, the six applications built from publisher releases |
| Decided, not yet built | Launcher and notifications inside the shell (fuzzel and mako are used today) |
| Never tested | Real hardware: the NVIDIA power path, Wi-Fi, suspend, the interactive installer |

Next steps are in [docs/ROADMAP.md](docs/ROADMAP.md).
