# Amadeus OS

*El Psy Kongroo.*

A minimal, rolling Linux distribution with an AI layer that can inspect the system,
use permission-checked tools, rearrange the desktop, and build sandboxed applications.
The desktop works without an AI account. The supported offline installation path
includes the packages needed to reach a usable system.

Amadeus OS runs on x86_64 computers with Intel, AMD or NVIDIA graphics. The installer
detects the hardware and installs its drivers, firmware and model-specific fixes from the
install medium, without a connection (`amadeus-hardware` shows what it found). The reference machine, tested by hand, is a
Core i5-13450HX laptop with Intel UHD graphics, an RTX 3050 6 GB, 16 GB RAM and a 1 TB
NVMe drive.

> **Pre-release:** the November 18 image passed 153 installed-system VM checks, including
> both rollback paths, plus the live-session checks. Real hardware and live provider
> authentication have not been verified. See [Verification](#verification).

## The system

| Area | Design |
|---|---|
| Base | Arch with CachyOS repositories first, a CachyOS kernel, encrypted btrfs, systemd-boot and zram. Processor-specific builds are selected when supported. |
| Desktop | Hyprland with one Quickshell shell for the bar, menus, launcher and notifications. Personal configuration overrides shipped defaults. One theme file colours every application, and display scale and text size start from the panel's size. |
| Graphics | Intel, AMD and NVIDIA. With two GPUs, automatic mode draws the desktop on the integrated one and offloads suitable applications to the dedicated one. Other GPU modes are an explicit user choice and apply at the next login. Hardware power behavior still needs testing. |
| Recovery | A snapshot before a system update, a matching copy of the boot files, and rollback from the installed system or installer medium. AI package transactions have their own pre/post snapshots. |
| AI | A user-session daemon applies capability policy, approvals, audit logging and file undo to Amadeus tool requests. Requests carry a short tool list and a small memory; failed services and a full disk are noticed and offered. Subscription CLIs, APIs and compatible local servers are optional. |
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
optional extras bundle. Brave Origin and LocalSend come from the CachyOS repositories
([extras list](installer/packages.extras)); herdr, which no repository carries, is
packaged from its publisher's release through an AUR recipe
([AUR list](installer/packages.aur)). The installer names that bundle and shows its
selection separately from base apps in the final summary.

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
name in a navigation menu to search across menus. Lists of things to choose, such as
packages to install or remove, search only their own entries. Matching, app ranking and pointer handoff
show result paths shown under their names.
Arrow keys keep the selection while the pointer is stationary. A global result closes
the current menu before opening its destination. Free-text entry prompts continue to accept the text they ask
for. Apps respects desktop-entry visibility and hides dependency-owned helpers and
secondary launchers; settings remain available through search. The shipped
[hide list](desktop/shell/launcher.hides) names further helper entries; add your own in
`~/.config/amadeus/launcher.hides`. A personal desktop entry is always shown.

**Setup → Theme** (or `amadeus-theme`) changes the look of the whole system from one
file: the shell, the panel, terminals, GTK applications, btop, window borders and the
lock screen. A theme is a single `colors.toml`; put your own in
`~/.config/amadeus/themes/NAME/`. Applications installed later start out themed, and a
configuration file you already own is left alone. Open terminal windows are recoloured
in place, without interrupting what runs in them.

At the start of a session, a display you have not set up yourself gets a scale chosen
from its resolution and physical size, and the text size is raised slightly where that
scale leaves things small. A display that does not report its size keeps scale 1. Any
choice you make in **Setup → Display** stays and is never replaced.

**Setup → Login screen** (or `amadeus-login`) chooses which theme styles the login
screen, independently of the desktop. It asks for your password because the login screen
belongs to the system; `amadeus-login reset` returns to the shipped look.

**Super+C** and **Super+V** copy and paste in every application, terminals and the
Amadeus panel included. Text in the panel can be selected with the pointer, and each
answer has a **Copy** button.

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
and undo journalled file changes. Stopping a task does not undo completed actions or
instantly interrupt a provider request or OS command already in progress.
**Super+Shift+Escape** stops all Amadeus tasks and dismisses their pending approvals. The bar shows a working count while
requests are active.

The same AI panel is reachable from desktop settings, **Ctrl+Enter** in a menu,
**Super+Alt+A** for selected text, and **Scripts → Ask Amadeus** in Files for selected
paths. These shortcuts prepare context for your request; they do not submit it automatically.
Native setting tools share the desktop's own commands. Screen observation and app input
are explicit permission requests; observation sends the focused application's image to
the selected provider, so image reasoning needs a vision-capable model. Input uses a recent
observation and checks the window again after approval. Completed GUI actions have no
automatic file undo.

For work that takes more than one request, type it and press **Goal** instead of Enter
(or run `ama goal "..."`). Amadeus then carries it on in the background, a round at a
time, under the execution mode you had selected. Each round starts fresh from a short
list of progress notes rather than a growing conversation. When it reports the goal
finished, one more round checks the result against the real system before the goal
counts as done. It comes back to you when only you can decide something, when a
permission was denied, after eight rounds without finishing, or when a round fails
twice; answer in **Tasks** or with `ama goal answer`. A goal survives a restart, and
`ama goal stop` ends it. Full access is never available to a goal, and at most three
run at once. Changes a goal made to files can be undone with `ama undo` one at a time;
there is no single undo for a whole goal yet.

Amadeus also notices some things by itself. When a service fails, a program crashes, a
disk passes 90% full, or the system has gone two weeks without a full update, a
notification offers to look into it; clicking it hands the panel a request that
runs under your execution mode and approvals like any other. The same thing is not
offered again for six hours (three days for the update reminder), and `notices = false` in the configuration turns this off.
Failures and crashes are reported by systemd as they happen. Disk space, services that
failed before you logged in and the date of the last update are read once an hour and
shortly after login, from local files only: nothing contacts the network to check.

A task can be marked **Unasked changes** in its card (or with `ama task auto ID on`).
That task may then change your files and desktop without asking, as Auto mode does.
Everything else still asks, and editing what the task does or when it runs turns the
mark off again. Only you can set it; Amadeus cannot grant it to itself.

Open **Tasks** in the panel or **Setup → Tasks** to create scheduled or desktop-event work.
New tasks are disabled until enabled. Each can use the default agent or a specific provider.
They run only while the user session and daemon are available; missed timer runs are not
replayed. Automated changes still ask for approval unless you marked that task as above. There is no continuous screen capture
or background model polling. Disabling stops future triggers; use Stop for an active run.
Task creation and configuration can be undone, which also reconciles their user timers.

Open **Settings** in the panel to select a subscription, API provider or local model.
**Setup → Defaults → Agent** saves the panel's default. A temporary panel selection
applies to the next request; **Use default** clears it. The terminal harness default is
independent. Install a missing CLI through **Install → Harness**, then use the provider's
sign-in flow. Provider definitions live in the [configuration module](ai/amadeus/config.py).

The same Settings view sets a provider's **model** and **reasoning effort**. **Save**
keeps them for that provider; **Use for next request** applies them once. The effort
levels offered are the ones that provider type accepts; a blank choice leaves the
provider's own default. `ama provider tune` does the same from a terminal.

Separately, the row above the request field chooses an **execution mode**, which
decides how much a request may do without asking. It does not depend on the provider:

- **Ask** follows your policy file: changes wait for approval.
- **Sandbox** reads and runs isolated commands; anything that would change the computer
  is refused.
- **Auto** runs reversible changes to your files and desktop unasked; everything else
  still follows your policy.
- **Full access** lets one request change anything in your account unasked. It needs a
  confirmation each time, applies to the next request only and is never saved.

No mode skips a policy denial, the prompt for deleting data, root mode and its prompt,
consent for screen observation and input, or changes to what the AI itself is allowed
to do. Scheduled tasks and generated apps never use a mode. Ask, Sandbox and Auto are
remembered; `ama mode` shows or sets the saved one.

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

Requests are kept small. A model is sent a short, fixed list of everyday tools and
looks the others up when it needs them; every tool still passes the same permission
check. The system prompt and tool list do not change between requests, so providers that
cache prompts reuse them. In a long conversation, old tool output and all but the newest
screenshot are dropped. The panel shows each task's token use and the share that was
reused, and `ama audit` records it. `context_chars` in the configuration sets the limit.

Amadeus remembers a short list of notes between requests: at most 40 single sentences,
in one plain file you can read and edit. `ama memory` lists them, and `ama memory forget N`
or `ama memory clear` removes them. Saving a note always asks you first, in every
execution mode, because a note is read into every later request.

Agents working on the system, Amadeus or a coding harness, start from a short entry
guide and pull up one topic guide per area on demand: `ama guide` lists them. The guides
give rules and method; `ama discover` reports what is actually installed.

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

If a CachyOS rebuild lags behind an exact-version dependency from Arch, you can select
a compatible Arch Linux Archive date for the build with
`ARCH_SNAPSHOT=YYYY-MM-DD ./build.sh iso`. CachyOS packages and AUR recipes still come
from their current repositories. Installed systems use rolling mirrors.

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

Lock, logout and login are available from the desktop's power controls. Login uses a
native graphical screen: one installed profile is preselected with password entry ready;
multiple profiles show a dropdown with the last-used profile selected. No username typing
is needed. Try starts automatically and returns to the graphical screen after logout;
select **Amadeus**, then **Login**, with no password. Normal installs use the password
chosen during setup. Profile selection never stores or bypasses a password.

Choose **Install Amadeus OS** for the guided flow. It asks for identity, network and
storage choices, then the optional extras selection. Nothing is installed onto the
selected system disk until its name is typed at the final summary. The target machine's
x86-64-v3 installation works without internet; the generic-processor fallback needs a
connection. Harness downloads, provider sign-in and later updates need network access.

For a portable system on a USB drive, `./build.sh usb /dev/sdX` starts the guided installer
in a VM that sees the selected drive. That workflow unmounts the chosen USB on the host,
and the installer erases it after confirmation. Portable installs include every
maker's graphics drivers and broader boot-image coverage; CPU-build compatibility still applies.

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

The November 18 image, built from [b4e12a7](https://github.com/Jitheswar/Amadeus/commit/b4e12a7), used the November 16 Arch repository snapshot. It booted
the Try desktop, installed onto an encrypted disk without internet access, and
passed all **153 installed-system checks**. The guest reported 138 passes on first
boot, 8 after rollback from the running system, and 7 after rescue from the ISO.
Both rollback tests booted the restored system. AI requests used a scripted local
model.

The tested ISO has SHA-256
`57a71bbbc78c5ee2b496d17893c14ce7a641878119dd7c650679cd105074d1fd`.
Three additional UEFI boots supplied invalid values for `EXTRAS`, `PORTABLE` and
`NVIDIA`, one per boot. Each run identified the invalid setting and preserved
the checksum of the entire target disk.
A separate UEFI test supplied an invalid encryption answer to the installer on
[de94bcb](https://github.com/Jitheswar/Amadeus/commit/de94bcb) and verified that the entire target disk retained its original checksum.
The earlier [24bc744 validation](https://github.com/Jitheswar/Amadeus/commit/24bc744)
also included inspected headless previews.

The VM exercised password-only profile entry, rejection of an incorrect password,
graphical logout/login in both sessions, and keyboard navigation with a stationary mouse.
Native AI checks covered setting changes and exact text-size undo, timer enable/disable,
disabled jobs, event cooldowns, a model run from a real app-focus event, NetworkManager
profile updates, screen-image delivery, approved keyboard input and return to idle.
This run added checks for list-only search, the Apps hide list, saved model and effort,
saved execution mode with full access refused outside the panel, a theme change reaching
the shell, lock screen and an open terminal, the login-screen theme publish and reset,
topic guides, and the automatic display step. The Try session was checked for the
power-profile command, Bluetooth activation, compressed swap, default applications and
the absence of a serial console argument.

Open-terminal recolouring was confirmed by asking a real terminal for its background
after a theme change. The copy and paste shortcuts were checked for their binding and
configuration, not by physical key presses. The virtual display reports no usable
physical size, so the automatic scale choice itself is covered by unit tests only. The
chosen login-screen theme was rendered and published in the VM but not looked at.
Execution modes are enforced in unit tests and their saved state in the VM; no live
provider ran under them.

The VM also failed a user and a system service on purpose and found both recorded as
notices, with a malformed unit name refused, and exercised on-demand tool lookup, the
call envelope and the memory commands. Nobody clicked a notice, so the path from the
notification to the panel is untested outside unit tests, as is a task marked for
unasked changes in a real session. Prompt-cache hits, token reporting and the size of
the saving have not been measured with a live provider.

A program was crashed on purpose and its notice recorded, and a goal ran end to end
against the scripted model: three rounds, done only after the checking round. The
overdue-update reminder and the pick-up of services that failed before login are covered
by unit tests; the VM only confirmed that a fresh install is not told to update. How
well a real model writes useful notes and judges its own finish is unknown.

Real hardware, live subscription/API authentication, manual guided-installer interaction,
full system updates and the explicit GPU modes still need validation. Multi-profile login
needs a manual walkthrough beyond the account-cache unit checks. Live vision reasoning
and accessibility actions across applications also need validation. The VM has no
NVIDIA card, battery or Wi-Fi adapter. Preview images check rendering rather than real
compositor motion.

Contributors should start with [AGENTS.md](AGENTS.md). Planned work and remaining
validation are tracked in the [roadmap](docs/ROADMAP.md). The earlier Arch version is
preserved under the `v0-arch` tag.
