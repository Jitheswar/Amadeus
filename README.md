# Amadeus OS

*El Psy Kongroo.*

A minimal, rolling Linux distribution with an AI layer that can inspect the system,
use permission-checked tools, rearrange the desktop, and build sandboxed applications.
The desktop works without an AI account. The supported offline installation path
includes the packages needed to reach a usable system.

The target is a Core i5-13450HX laptop with Intel UHD graphics, an RTX 3050 6 GB,
16 GB RAM and a 1 TB NVMe drive.

> **Pre-release:** the current runtime passed 117 installed-system VM checks, including
> both rollback paths, plus the live-session checks. Real hardware and live provider
> authentication have not been verified. See [Verification](#verification).

## The system

| Area | Design |
|---|---|
| Base | Arch with CachyOS repositories first, a CachyOS kernel, encrypted btrfs, systemd-boot and zram. Processor-specific builds are selected when supported. |
| Desktop | Hyprland with one Quickshell shell for the bar, menus, launcher and notifications. Personal configuration overrides shipped defaults. |
| Graphics | Automatic mode uses Intel for the desktop and offloads suitable applications to NVIDIA. Other GPU modes are an explicit user choice and apply at the next login. Hardware power behavior still needs testing. |
| Recovery | A snapshot before a system update, a matching copy of the boot files, and rollback from the installed system or installer medium. AI package transactions have their own pre/post snapshots. |
| AI | A user-session daemon applies capability policy, approvals, audit logging and file undo to Amadeus tool requests. Subscription CLIs, APIs and compatible local servers are optional. |
| Generated apps | QML applications with explicit sandbox permissions, private data and source-version history. |

The package lists in [installer/](installer/) define what is installed. The
[architecture](docs/ARCHITECTURE.md) explains how the parts interact, and the
[decisions](docs/DECISIONS.md) explain the choices and their limits.

## Default apps and optional extras

The base desktop and default applications are installed whether the installer's
**Optional extras** answer is yes or no. This includes btop and fastfetch. The
[desktop list](installer/packages.desktop) and
[application list](installer/packages.apps) are the authoritative package sets.

The yes/no choice controls only Brave Origin, herdr and LocalSend, the
[optional publisher-app bundle](installer/packages.aur).
The installer names that bundle and shows its selection separately from base apps in
the final summary. Those releases are packaged through AUR recipes; they are separate
from the official repository packages.

Gaming and Chat are directly in the Amadeus menu. Steam is optional under **Gaming**;
Discord and Telegram are optional under **Chat**. Their catalogues use explicitly named
official Arch repositories. Claude Desktop is optional
under **Install → AI**; Claude Code is optional under the existing **Install → Harness**
menu. ProtonPlus and those clients are absent from the default package set, and no
coding harness is automatically installed.

GNOME Keyring is absent by default, so a fresh desktop has no automatically activated
GNOME password-store prompt. Apps that require Secret Service need an optional provider
before they can store credentials. Package-signing keys remain part of the system;
Amadeus API keys use its private secrets directory.

## Using the desktop

Open the Amadeus menu with **Super+Space**. Start typing an installed app or setting
name from a list to search across menus. A global result closes the current menu before
opening its destination. Free-text entry prompts continue to accept the text they ask
for. Apps respects desktop-entry visibility and hides dependency-owned helpers and
secondary launchers; settings remain available through search.

Use **Setup → Defaults** for application choices. The terminal, editor and terminal
harness use wrappers, so changing a default applies to shortcuts and menus that call
those wrappers. **Agent** is a separate choice for the right-side AI panel.

The display popover and Setup text-size control adjust shell and panel text, GTK
scaling and terminal configuration together. Existing terminals may need a new window.
Display resolution and scaling are separate from text size. The sound popover lists
ready device endpoints and omits application streams, monitors and virtual nodes.

The bar's controls open their corresponding settings. Power profiles follow cable and
battery state when those services are available. The passwordless-administrator switch
is off by default and requires authentication to enable; it is separate from AI root
mode. Its timed choices end automatically, and it never survives a restart.

For the current shortcuts and command descriptions, use **Super+K** or
`amadeus-keys --print`. The [desktop defaults](desktop/hypr/default.lua) define the
shipped bindings; the [bar layout](desktop/shell/bar.default.json) defines its initial
placement. Personal bar changes live in `~/.config/amadeus/bar.json`.

## Using Amadeus

**Super+Z** opens the right-side panel. **Super+A** opens it with the focused window as
context. Each request is a task: tasks can run in parallel, show their steps, be stopped,
and undo journalled file changes. Stopping a task does not undo completed actions.

Open **Settings** in the panel to select a subscription, API provider or local model.
**Setup → Defaults → Agent** saves the panel's default. A temporary panel selection
applies to the next request; **Use default** clears it. The terminal harness default is
independent. Install a missing CLI through **Install → Harness**, then use the provider's
sign-in flow. Provider definitions live in the [configuration module](ai/amadeus/config.py).

API setup accepts a model, server address and private key. Saved keys are not displayed
in the provider listing. A CLI being installed or configuration fields being present
is not proof that authentication or a model endpoint works.

The AI control at the top right shows the default agent and opens usage. It reads
subscription limits on demand and caches results briefly. It sends no model request
and does not refresh credentials. Recent Amadeus request counts are not a complete
history of every external agent. Providers without subscription limits show an
explanation rather than an invented quota.

```bash
ama "why is the fan loud?"
ama "set up a workspace for writing"
ama "build me a habit tracker"
```

Use `ama --help` for CLI usage, `ama discover` for the installed capabilities, and
`ama doctor` for diagnostics. On an installed system, `ama skill` prints the agent
management guide. That guide teaches discovery rather than storing a system inventory.

AI actions follow the configured policy. Destructive and privileged tools require
approval; structured privileged tools also require user-enabled root mode. An approved
host-shell command runs with the user's existing OS permissions, including any sudo
access the user enabled separately. File undo, app source rollback and system snapshot
rollback cover different kinds of changes.

## Build and validate

Use `build.sh` as the build/test entry point. Builds run in Docker and installation tests
run in QEMU/KVM. The tested setup uses the host Intel render node for VM graphics.
No build package is installed on the host.

```bash
./build.sh check
./build.sh iso
./build.sh preview
./build.sh test
```

The [build guide](agents/build-and-test.md) explains the checks and generated logs.
The script's header documents other modes. Build output belongs in `out/` and is not
committed.

## Try and install

Use the exact ISO filename generated in `out/`. Writing it to a USB drive erases that
USB drive immediately; it is separate from the installer's later disk confirmation.
Replace both placeholders with the intended ISO file and whole USB drive:

```bash
sudo dd if=out/amadeus-os-YYYY.MM.DD-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

Boot in UEFI mode with Secure Boot off. **Try Amadeus OS** is the default entry: it
starts a temporary desktop in memory without installing to an internal disk. Changes
are lost on shutdown. The live medium uses Arch's kernel, so its hardware behavior does
not establish that of the installed CachyOS kernel.

Choose **Install Amadeus OS** for the guided flow. It asks for identity, network and
storage choices, then the optional extras selection. Nothing is installed onto the
selected system disk until its name is typed at the final summary. The target machine's
x86-64-v3 installation works without internet; the generic-processor fallback needs a
connection. Harness downloads, provider sign-in and later updates need network access.

For a portable system on a USB drive, `./build.sh usb /dev/sdX` starts the guided installer
in a VM that sees the selected drive. That workflow unmounts the chosen USB on the host,
and the installer erases it after confirmation. Portable installs include the NVIDIA
driver and broader boot-image coverage; CPU-build compatibility still applies.

The medium seeds missing package indexes for offline browsing. Their first online sync
fetches current metadata instead of treating the copy time as freshness. Signature
verification remains enabled.

## Updates and recovery

Run `amadeus-update` as your user. It takes a system snapshot before updating, ranks
mirrors when due, and updates repository packages, AUR apps and mise-managed tools.
Number-based cleanup is configured to retain the newest five snapshots. The temporary
Try session takes no system snapshot because its changes disappear on restart.

Normal manual package installs and removals have no automatic snapshot hook. The AI's
structured package tool asks the root helper to create a pre/post pair and reports the
available recovery information. Inspect current snapshots before relying on a particular
recovery point. A system-root snapshot does not back up the separate home subvolume.

Use `amadeus-rollback` to inspect recovery choices. It can select a system snapshot from
the running installation or the installer medium. Journalled file undo and generated-app
source rollback do not replace a backup of personal data.

## Verification

Runtime [cab3010](https://github.com/Jitheswar/Amadeus/commit/cab3010864cdbc7bea2d2d9179630cd92465f793),
with results recorded in [82c2880](https://github.com/Jitheswar/Amadeus/commit/82c28800a98b0e6cdbcf1a4f14bff7fa3b8e74d5),
passed **117 installed-system checks**: 102 on first boot,
eight after rollback from the running system, and seven after rollback from the ISO.
The live-session test, fast checks, QML syntax checks and headless previews also passed.
This includes offline encrypted installation, package-index refresh, optional app and
keyring defaults, cross-menu search, text sizing, agent defaults, usage controls, and AI
requests against a scripted local model.

Real hardware, live subscription/API authentication, manual guided-installer interaction,
full system updates and the explicit GPU modes still need validation. The VM has no
NVIDIA card, battery or Wi-Fi adapter. Preview images check rendering rather than real
compositor motion.

Contributors should start with [AGENTS.md](AGENTS.md). Planned work and remaining
validation are tracked in the [roadmap](docs/ROADMAP.md). The earlier Arch version is
preserved under the `v0-arch` tag.
