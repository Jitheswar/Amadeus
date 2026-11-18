# Amadeus OS

*El Psy Kongroo.*

Amadeus OS is a small, rolling Linux system with an AI assistant built in. The assistant
can look at your system, change settings with your permission, rearrange your desktop
and build small apps for you, each in its own sandbox. You don't need an AI account to
use the desktop, and you can install the whole system without an internet connection.

It runs on 64-bit Intel and AMD computers with Intel, AMD or NVIDIA graphics. The
installer works out what hardware you have and sets up the right drivers, firmware and
fixes from the USB stick itself. Run `amadeus-hardware` to see what it found.
The machine it is tested on by hand is a Dell G15 5530 (Core i5-13450HX, Intel UHD
graphics, RTX 3050 6 GB, 16 GB RAM, 1 TB NVMe).

> **Pre-release.** See [Testing status](#testing-status) for what has and hasn't been
> checked. Real hardware and live AI-provider sign-in have not been verified yet.

## What you get

| | |
|---|---|
| **Base** | Arch Linux with CachyOS's faster packages and kernel, an encrypted btrfs disk, systemd-boot and compressed swap in memory. Builds tuned for newer processors are used when your processor supports them. |
| **Desktop** | Hyprland, with one shell for the bar, menus, app launcher and notifications. Your own settings always win over the shipped ones. One theme file colours every app. |
| **Graphics** | Intel, AMD and NVIDIA, with the right drivers picked for your card. On laptops with two GPUs, the desktop runs on the power-saving one and games and heavy apps use the fast one. You can change this in **Setup → GPU**. |
| **Audio** | PipeWire for everything, including PulseAudio and JACK apps. |
| **Recovery** | A snapshot before every update, and a way back from the running system or from the USB stick. |
| **AI** | An assistant that asks before it changes anything, keeps a log, and can undo file changes. Use a subscription CLI, an API key or a local model, or none at all. |
| **Generated apps** | Small apps the assistant builds for you, each with only the permissions you grant. |

The package lists in [installer/](installer/) say exactly what gets installed. The
[architecture notes](docs/ARCHITECTURE.md) explain how the parts fit together, and the
[decisions](docs/DECISIONS.md) explain why things were chosen and what their limits are.

## Getting started

### 1. Get the image

Build it yourself (see [Building from source](#building-from-source)), then write it to a
USB stick. **This erases the stick.** Replace both placeholders with your ISO file and
your whole USB device:

```bash
sudo dd if=out/amadeus-os-YYYY.MM.DD-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

### 2. Try it

Boot from the stick in UEFI mode with Secure Boot turned off. **Try Amadeus OS** is
selected by default: it starts the full desktop from memory without touching your disk.
Nothing you do is kept after shutdown. To log back in after logging out, pick
**Amadeus** and press **Login**; there is no password. The live system uses Arch's
kernel, so hardware that works here might still behave differently once installed.

### 3. Install it

Choose **Install Amadeus OS**. The guided installer asks for your name, network, disk
and whether you want the optional extras. **Nothing is written to your disk until you
type its name** on the final summary screen.

On newer processors (Intel Haswell from 2013, AMD Zen, and later), the install needs no internet at
all: every driver for every supported computer is on the stick. Older processors need
a connection. AI tools, provider sign-in and later updates always need internet.

To install onto a USB drive you can carry between computers, run
`./build.sh usb /dev/sdX` from the source tree. It starts the installer in a virtual
machine that can only see that drive. Portable installs include every maker's graphics
drivers so they start on any computer.

### Logging in

The login screen lists the people on this computer. With one account it is
pre-selected and ready for your password; with several, the last one used is
selected. Lock, log out and log in again from the power menu.

## What's installed

Everything in the [desktop list](installer/packages.desktop) and
[app list](installer/packages.apps) is always installed, including btop and fastfetch.

The installer's **Optional extras** question only covers Brave Origin, LocalSend and
herdr. Brave Origin and LocalSend come from the CachyOS repositories
([extras list](installer/packages.extras)); herdr isn't in any repository, so it is
built from its publisher's release ([AUR list](installer/packages.aur)).

Steam (**Gaming**), Discord and Telegram (**Chat**) are in the Amadeus menu, from the
official Arch repositories. Claude Desktop is under **Install → AI** and Claude Code
under **Install → Harness**. None of these, and no AI coding tool, is installed for you.

GNOME Keyring isn't installed, so you won't get surprise password-store prompts. Apps
that need a Secret Service password store need one installed first.

## Using the desktop

**Super+Space** opens the Amadeus menu: **Apps, Learn, Appearance, Trigger, Setup,
Install, Remove, Update, About** and **System** (Super+Escape opens System directly).
Start typing to find any app or setting. Lists
of things to pick, like packages, only search their own entries. Arrow keys keep their
place while the mouse is still, and each result shows where it lives. To hide an app
from the list, add it to `~/.config/amadeus/launcher.hides`. The menu itself is one file,
`/usr/share/amadeus-os/menu.jsonc`; add, change or hide entries in
`~/.config/amadeus/menu.jsonc` using the same format.

**Super+K** (or `amadeus-keys --print`) lists every shortcut. The shipped shortcuts are
in the [desktop defaults](desktop/system/usr/share/amadeus/default/hypr/); your own go in
`~/.config/hypr/hyprland.lua`. Bar changes are kept in `~/.config/amadeus/bar.json`.

**Super+C** and **Super+V** copy and paste everywhere, terminals included.

- **Theme.** **Setup → Theme** (or `amadeus-theme`) recolours everything at once: the
  bar, panel, terminals, GTK apps, btop, window borders and the lock screen. A theme is
  one `colors.toml` file; add your own in `~/.config/amadeus/themes/NAME/`. Open
  terminals change colour in place.
- **Login screen.** **Setup → Login screen** (or `amadeus-login`) picks its theme
  separately. It asks for your password because the login screen belongs to the system.
- **Displays.** A new display gets a sensible scale for its size and resolution. Once
  you choose one in **Setup → Display**, your choice stays. Text size (in the display
  popover or **Setup**) changes the bar, apps and terminals together.
- **Default apps.** **Setup → Defaults** chooses your terminal, editor, AI coding tool
  and the assistant used in the side panel.
- **Graphics.** **Setup → GPU** (or `amadeus-gpu`) on a two-GPU laptop: *Automatic*
  (the default), *Dedicated for everything*, or *Integrated only* for the longest
  battery. Changes apply at your next login.
- **Power and administrator access.** Power profiles follow whether you're plugged in.
  The bar has a switch for passwordless administrator access; it is off by default,
  asks for your password to turn on, and always turns off at restart.

## Using the assistant

**Super+Z** opens the side panel; **Super+A** opens it about the window you're in.
You can also reach it with **Ctrl+Enter** in a menu, **Super+Alt+A** on selected
text, or **Scripts → Ask Amadeus** on files. These fill in the context; you still press
send.

Each request becomes a task. Tasks run side by side, show their steps, can be stopped,
and their file changes can be undone. **Super+Shift+Escape** stops all of them.
Stopping doesn't undo what's already done.

```bash
ama "why is the fan loud?"
ama "set up a workspace for writing"
ama "build me a habit tracker"
```

### How much it may do on its own

The row above the text box sets the **execution mode**:

- **Ask**: every change waits for your approval (as set in your policy file).
- **Sandbox**: it can look and run isolated commands, but cannot change anything.
- **Auto**: changes to your files and desktop that can be undone happen without asking.
- **Full access**: one request may change anything in your account without asking.
  It needs confirming every time and is never remembered.

Whatever the mode, it always asks before deleting data, using administrator rights,
looking at your screen or typing into apps, and it can never change its own
permissions. `ama mode` shows or sets the remembered mode.

### Bigger jobs: goals

For something that takes several steps, press **Goal** instead of Enter (or run
`ama goal "..."`). It keeps working in the background, one round at a time, and checks
its own result against the real system before calling it done. It comes back to you
when it needs a decision, was refused permission, or got stuck. Answer in **Tasks** or
with `ama goal answer`; stop it with `ama goal stop`. At most three goals run at once,
and goals never get full access.

### It notices things

When a service fails, a program crashes, the disk is over 90% full, or you haven't
updated in two weeks, a notification offers to look into it. It reads only local files
to notice these, and each is offered at most every six hours (three days for updates).
Set `notices = false` in the configuration to turn this off.

### Scheduled tasks

**Tasks** in the panel (or **Setup → Tasks**) runs work on a timer or when something
happens on the desktop. New tasks start switched off. They only run while you're logged
in, and they still ask before changing things unless you mark one **Unasked changes**,
which only you can do.

### Providers, models and memory

**Settings** in the panel picks a subscription, API key or local model, and the model
and reasoning effort for each. **Setup → Defaults → Agent** sets the default. Install a
missing CLI through **Install → Harness**, then sign in the way that provider asks.
Saved API keys are never shown again.

The assistant keeps up to 40 short notes between requests, in one plain file. It always
asks before saving one. `ama memory` lists them; `ama memory forget N` or
`ama memory clear` removes them.

The top-right AI control shows your default assistant and its subscription usage. It
only checks when you open it and never sends a model request to do so.

### Under the hood

Requests stay small: the model gets a short list of everyday tools and looks up others
when needed, and old output is trimmed from long conversations. The panel shows tokens
used and how much was reused from cache. `ama --help` explains the command line,
`ama discover` lists what's installed, `ama doctor` checks the system, and `ama guide`
lists the topic guides the assistant reads.

## Updates and recovery

Run **`amadeus-update`** as yourself. It asks for your password once, keeps the computer
awake, and saves everything it prints to `~/.local/state/amadeus/update.log`. In order, it:

1. checks there are 10 GB free, then trims old packages from the download cache;
2. takes a system snapshot;
3. picks fast mirrors when due and refreshes the package signing keys;
4. updates the system;
5. applies settings changes that came with the update (`amadeus-migrate`), once each;
6. removes packages nothing needs any more;
7. installs any drivers your hardware needs but doesn't have yet;
8. updates AUR apps and mise tools;
9. offers to restart if the kernel was updated.

`amadeus-update -y` does it all without questions. `amadeus-update firmware` updates
device firmware (BIOS, docks, drives) through fwupd.

The newest five snapshots are kept. **`amadeus-rollback`** takes you back to one, from
the running system or from the USB stick if the system won't start. Snapshots cover the
system, not your home folder, so keep your own backups. Installing or removing packages
by hand doesn't take a snapshot; the assistant's package changes do.

If you change hardware (a new graphics card, say), run `amadeus-hardware setup` and
restart.

When something stops working, **Update → Restart a part** (or `amadeus-restart audio`,
`wifi`, `bluetooth`, `trackpad`, `shell`…) brings it back without restarting the computer.
**Update → Reset settings** (`amadeus-reset`) puts the shipped settings back, keeping your
old files as backups, or reinstalls every package to repair damaged files.

To run your own scripts after an update, at login or when the theme changes, put them in
`~/.config/amadeus/hooks/` (see `amadeus-hook`). `amadeus-version` shows the release.

## Building from source

Everything builds in Docker and is tested in a QEMU/KVM virtual machine. Nothing is
installed on your computer.

```bash
./build.sh check     # quick checks, no container
./build.sh iso       # build the install image into out/
./build.sh test      # install it in a VM and run the self-test
./build.sh preview   # render the assistant panel and login screen to images in out/preview/
```

If an Arch package update gets ahead of CachyOS and the build stops with
"could not satisfy dependencies", build against an earlier day's Arch packages:
`ARCH_SNAPSHOT=YYYY-MM-DD ./build.sh iso`. This usually sorts itself out within a day
or two. The [build guide](agents/build-and-test.md) covers the checks and their logs.

Contributors should start with [AGENTS.md](AGENTS.md). Planned work is in the
[roadmap](docs/ROADMAP.md). The earlier pure-Arch version is kept under the `v0-arch` tag.

## Testing status

The most recent full virtual-machine run was the November 18 image built from
[b4e12a7](https://github.com/Jitheswar/Amadeus/commit/b4e12a7), before the hardware
detection, graphics and update changes of the same day. **Those changes are covered by
the quick checks only, and have not yet been through a VM install.**

That run booted the Try desktop, installed onto an encrypted disk with no internet, and
passed all 153 installed-system checks, including both ways of rolling back (from the
running system and from the USB stick). The installer refused invalid answers without
touching the target disk. Login, logout, menu navigation, theme changes, notices,
goals and the assistant's settings tools were exercised against a scripted local model.

Still to be checked:

- real hardware, including the GPU modes and their effect on battery life;
- hardware the developer doesn't own (AMD graphics, Macs, other laptop models);
- signing in to real AI providers and how well a real model works the tasks;
- a full system update on an installed machine;
- the guided installer clicked through by a person.

The VM has no NVIDIA card, battery or Wi-Fi, so it can't test those.
