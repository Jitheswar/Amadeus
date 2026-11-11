# Decisions

Every choice below was made against the requirements, starting from nothing: not from
what any existing machine or distribution happens to run. Each entry names what was
picked, what it was picked over, and the evidence. Where a choice is not yet implemented
in the tree, it says so.

## Base system: Arch Linux packages

| Candidate | For | Against |
|---|---|---|
| **Arch** | Rolling. Every required application has a maintained package built from the publisher's own release. Standard filesystem layout, so vendor binaries (Steam, Proton builds, CUDA wheels, Claude Desktop) run unmodified. Mature ISO tooling. | Updates are not atomic by themselves. |
| NixOS (unstable) | Atomic system generations, rollback in the boot menu, the whole system is one declarative file: the best fit for an AI that changes the system. | Checked on 2026-11-11: Brave was removed from nixpkgs for lack of maintainers, and Claude Desktop is not packaged. Both would become our own derivations of auto-updating proprietary binaries on a non-standard filesystem layout; a browser whose security updates depend on us is not acceptable. CUDA development outside Nix shells is awkward. |
| openSUSE Tumbleweed / Aeon | Rolling with tested snapshots and transactional updates. | Claude Desktop ships only as a `.deb`; ProtonPlus, herdr and Brave Origin need repackaging too. |
| Fedora Atomic, Debian, Ubuntu | Stable. | Not rolling. |
| Void, Gentoo | Minimal. | Few of the required applications; no systemd (Void). |

Arch wins on the requirement that outranks the others in daily use: the listed
applications and the gaming stack work from maintained packages. What NixOS does
better, atomic change and rollback, is built on top instead:

- btrfs snapshots before and after every package change (snapper, snap-pac)
- a copy of `/boot` inside each snapshot, so a snapshot carries its matching kernel
- `amadeus-rollback`, from the running system or from the installer medium
- AI changes go through one enforcement point with an undo journal and an audit log

No other distribution's repositories or tooling are used. Applications outside the Arch
repositories are built from their AUR recipes (each downloads the publisher's release)
into the repository on the ISO; `amadeus-update` keeps them current.

## Kernel, boot, storage

- **Kernel: Arch `linux`.** Tracks upstream closely, which is what a 13th-gen hybrid
  CPU (P and E cores) and the NVIDIA open module want. Over `linux-lts` (older scheduler
  work for hybrid cores) and `linux-zen` (no measurable benefit for this workload).
- **Boot loader: systemd-boot.** Already part of systemd; nothing extra to maintain.
  Over GRUB (large, slow, fragile config generation) and limine.
- **Filesystem: btrfs on LUKS2**, subvolumes `@ @home @log @pkg`, zstd compression.
  Snapshots are the recovery mechanism, so the filesystem must provide them; over ext4
  (no snapshots) and ZFS (out-of-tree module on a rolling kernel).
- **Swap: zram**, no swap partition. 16 GB of RAM with compressed swap in memory beats
  writing to the SSD.

## Graphics

- **Intel renders the desktop; NVIDIA is off until asked for.** `nvidia-open` (the RTX
  3050 is supported by the open module) with runtime power management `0x02`, so the
  card is fully powered down when idle. Applications are offloaded one at a time
  (`gpu-run`, or the AI decides per application). Nothing sets NVIDIA globally.
- **Driver package: `nvidia-open`**, rechecked against the card (GA107BM, `10de:25ec`,
  Ampere) and driver branch 615: the open kernel module is NVIDIA's supported path for
  this generation, it is prebuilt for the `linux` kernel and versioned in lockstep with
  `nvidia-utils`, so there is no DKMS compile and no window where kernel and module
  disagree. The GPU firmware ships in `nvidia-utils`; `linux-firmware-nvidia` is only for
  nouveau and is not installed. `lib32-nvidia-utils` is there for Proton.
- **Dynamic Boost on (`nvidia-powerd`).** The laptop firmware reports it as supported. It
  is the one GPU daemon worth running: under load it shifts power budget from the CPU
  to the GPU, which is where games on this machine are limited.
- **CUDA is installed on demand**, not preinstalled: the toolkit is 5 GB.
- Left at the driver default, to be tried on the real machine: S0ix video-memory
  self-refresh (`NVreg_EnableS0ixPowerManagement`). The platform supports it and only
  offers s2idle sleep, but if deep idle is not reached it costs battery during sleep.
- No GPU switching daemon (optimus-manager, envycontrol, supergfxctl): PRIME render
  offload in the kernel and driver already does this without a background service.
- Video decode: `intel-media-driver` (VA-API) on Intel; `libva-nvidia-driver` when an
  application runs on NVIDIA.

## Compositor: niri *(decided; the tree still ships the earlier Hyprland config)*

The compositor is what the AI rearranges, so the deciding questions are: can a bad
change break the session, and does the interface stay the same across updates?

| Candidate | For | Against |
|---|---|---|
| **niri** | Config is validated before it is applied and reloaded live; a bad file leaves the running config in place, and `niri validate` checks one in advance. Includes (25.11+) let AI-managed settings live in their own file. Versioned JSON IPC with an event stream. Opening a window never resizes the others, so arranged workspaces stay arranged. Built-in overview, screenshots and Xwayland integration, so fewer packages. | Younger than Sway. No tearing support yet. |
| Sway | The most proven Wayland compositor; complete, stable IPC. | Manual tiling tree is easy to scramble; no animation or rounding without a fork. |
| Hyprland | Most runtime control. | Replaced its entire configuration language within the past year; on a rolling distribution every such change lands on the user. |
| KDE Plasma, GNOME, COSMIC | Complete desktops. | Not minimal; the shell cannot be reshaped as data. |

## Desktop shell and generated applications: Quickshell (QML)

One toolkit for the bar, launcher, notifications, AI surfaces and generated apps.

- Over **web views** (models write HTML best, but 100–150 MB per window and a second
  toolkit for the shell).
- Over **AGS/Astal** (a JavaScript runtime per shell) and **EWW** (too limited).
- QML is declarative, reloads live, and a window costs about 40 MB.
- The weakness, that models write QML less reliably than HTML, is handled by a small
  component library, a lint pass before a new version replaces the working one, and
  per-app version history.

The launcher and notifications are part of the shell rather than separate programs
*(planned; fuzzel and mako are used today)*.

## AI layer: Python standard library

A daemon in the user session with no third-party packages, so a system update cannot
break it and the enforcement code stays small enough to read in one sitting. Over Rust
or Go: nothing here is performance-critical, and fast iteration matters more. Root
actions never run in the daemon: they go to a separate root helper that exists only
while root mode is on and is gone at shutdown.

## Applications

| Need | Choice | Why |
|---|---|---|
| Terminal | foot | Wayland-native, starts instantly, a few MB of memory |
| File manager | Nautilus | It is already required as the file chooser for the desktop portal that provides screen sharing, so it adds nothing |
| Document viewer | Papers | Maintained GTK4 successor to Evince |
| Image viewer | imv | Tiny, keyboard-driven, Wayland-native |
| Camera | Snapshot | Uses PipeWire/libcamera; the older choices (Cheese, guvcview) do not |
| Login | greetd + tuigreet | No display-manager stack |
| Lock and idle | swaylock, swayidle *(planned; hyprlock and hypridle today)* | Compositor-independent |
| Audio | PipeWire + WirePlumber | Required by screen sharing and Bluetooth audio |
| Power | power-profiles-daemon + thermald | Uses the Intel driver's own hints; over TLP, which fights it |
