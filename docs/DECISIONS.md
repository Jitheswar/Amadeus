# Decisions

Every choice below was made against the requirements, starting from nothing: not from
what any existing machine or distribution happens to run. Each entry names what was
picked, what it was picked over, and the evidence. Where a choice is not yet implemented
in the tree, it says so.

## Base system: Arch, through the CachyOS repositories

Amadeus OS is an Arch system that takes its packages from the CachyOS repositories
first and the Arch repositories second.

| Candidate | For | Against |
|---|---|---|
| **Arch packages, CachyOS builds first** | Everything Arch offers (rolling, every required application has a maintained package, standard filesystem layout so vendor binaries run unmodified), plus the same packages rebuilt for newer processors (x86-64-v3, which this CPU supports) and a kernel tuned for desktop responsiveness with a matching prebuilt NVIDIA module. | A second set of repositories to trust, and their own build of the package manager comes with them. |
| Plain Arch | One upstream. | Generic builds; the stock kernel. |
| NixOS (unstable) | Atomic system generations and rollback in the boot menu: the best fit for an AI that changes the system. | Checked on 2026-11-11: Brave was removed from nixpkgs for lack of maintainers, and Claude Desktop is not packaged. A browser whose security updates depend on us is not acceptable. |
| openSUSE Tumbleweed / Aeon | Rolling with tested snapshots and transactional updates. | Claude Desktop ships only as a `.deb`; several other required applications need repackaging. |
| Fedora Atomic, Debian, Ubuntu | Stable. | Not rolling. |
| Void, Gentoo | Minimal. | Few of the required applications; no systemd (Void). |

What to expect from the CachyOS builds, stated plainly: they are the same software as
Arch's, compiled with newer instructions and link-time optimisation. The gain is a few
percent in most programs and more in some. They are not more thoroughly tested than
Arch's and track Arch closely, so they are not a stability measure. Stability here
comes from what is below, as before:

- a btrfs snapshot before every update (`amadeus-update`), the newest five kept; installing
  or removing a single package takes none, so the list stays short and meaningful
- a copy of `/boot` inside each snapshot, so a snapshot carries its matching kernel
- `amadeus-rollback`, from the running system or from the installer medium
- AI changes go through one enforcement point with an undo journal and an audit log

The installer uses the processor-specific repositories only when the processor can run
them, and falls back to the generic CachyOS and Arch repositories otherwise. Their
signing key and mirror lists are fetched over HTTPS when the ISO is built and shipped
on it.

## Kernel, boot, storage

- **Kernel: `linux-cachyos`**, the kernel CachyOS recommends by default: built with
  Clang and link-time optimisation, profiled, 1000 Hz, with their scheduler tuning for
  desktop responsiveness. Whatever scheduler that default uses is the one used here; no
  alternative scheduler is layered on top. Over Arch's `linux` (generic build) and over
  the other CachyOS variants (LTS, hardened, server and real-time builds answer needs
  this machine does not have).
- **System tuning: `cachyos-settings`** (their sysctl values, I/O scheduler rules and
  related defaults) and `ananicy-cpp` with their rule set, which lowers the priority of
  background work so the foreground stays responsive. That is one more always-running
  process; it idles at a few MB.
- **Boot loader: systemd-boot.** Already part of systemd; nothing extra to maintain.
  Over GRUB (large, slow, fragile config generation) and limine.
- **Filesystem: btrfs on LUKS2**, subvolumes `@ @home @log @pkg`, zstd compression.
  Snapshots are the recovery mechanism, so the filesystem must provide them; over ext4
  (no snapshots) and ZFS (out-of-tree module on a rolling kernel).
- **Swap: zram**, no swap partition. 16 GB of RAM with compressed swap in memory beats
  writing to the SSD. The cost: hibernation is not available, so the system menu does
  not offer it.

## Graphics

- **Intel renders the desktop; NVIDIA is off until asked for.** `nvidia-open` (the RTX
  3050 is supported by the open module) with runtime power management `0x02`, so the
  card is fully powered down when idle. Applications are offloaded one at a time
  (`amadeus-gpu-run`, or the AI decides per application). Nothing sets NVIDIA globally.
- **Driver package: `linux-cachyos-nvidia-open`**, for the card in this machine
  (GA107BM, `10de:25ec`, Ampere): the open kernel module is NVIDIA's supported path for
  this generation, and this package is that module prebuilt for the `linux-cachyos`
  kernel and versioned in lockstep with it and with `nvidia-utils`, so there is no DKMS
  compile and no window where kernel and module disagree. CachyOS carries a newer driver
  branch than Arch. The GPU firmware ships in `nvidia-utils`; `linux-firmware-nvidia` is only for
  nouveau and is not installed. `lib32-nvidia-utils` is there for Proton.
- **Dynamic Boost on (`nvidia-powerd`).** The laptop firmware reports it as supported. It
  is the one GPU daemon worth running: under load it shifts power budget from the CPU
  to the GPU, which is where games on this machine are limited.
- **CUDA is installed on demand**, not preinstalled: the toolkit is 5 GB.
- Left at the driver default, to be tried on the real machine: S0ix video-memory
  self-refresh (`NVreg_EnableS0ixPowerManagement`). The platform supports it and only
  offers s2idle sleep, but if deep idle is not reached it costs battery during sleep.
- **The user can choose, in Setup > GPU**: automatic (the default above), NVIDIA for
  everything (the compositor renders on NVIDIA and the Intel GPU only passes frames to
  the built-in screen; most performance, most power, the card never sleeps), or Intel
  only (nothing is sent to NVIDIA, so it stays asleep). The choice is written to the
  session environment and takes effect at the next login, because the compositor picks
  its GPU when it starts. udev gives the two cards stable names for this.
- No GPU switching daemon (optimus-manager, envycontrol, supergfxctl): PRIME render
  offload in the kernel and driver already does this without a background service.
- Video decode: `intel-media-driver` (VA-API) on Intel; `libva-nvidia-driver` when an
  application runs on NVIDIA.

## Compositor: Hyprland

The compositor is what the AI rearranges, so the deciding questions are: can a bad
change break the session, and does the interface stay the same across updates?

| Candidate | For | Against |
|---|---|---|
| **Hyprland** | The owner's choice, and the most runtime control: every setting, rule and shortcut can be changed live from its Lua configuration and its IPC. Special workspaces give a true scratchpad that floats over everything. Smooth, configurable animation. Every shortcut can carry a description, which Super+K reads live. | Replaced its configuration language within the past year; on a rolling distribution such a change lands on the user. |
| niri | Validates a config before applying it; windows never resize each other. | No overlay scratchpad; the owner prefers Hyprland. Used here for a few days before this decision and replaced. |
| Sway | The most proven Wayland compositor; complete, stable IPC. | Manual tiling tree is easy to scramble; no animation or rounding without a fork. |
| KDE Plasma, GNOME, COSMIC | Complete desktops. | Not minimal; the shell cannot be reshaped as data. |

The risk is handled the same way for every writer of configuration: the user's file
includes the shipped defaults, anything Amadeus writes goes into its own file, and every
change is checked with `Hyprland --verify-config` against the whole configuration before
it is kept, then applied with a reload. A rejected change leaves the old one in place.

## Capture: screenshots and recording

- **Screenshots** freeze the screen (hyprpicker), then one gesture chooses: drag for an
  area, click a window for that window, click empty space for the whole screen (slurp
  with the windows and screens offered as targets). The image is saved, copied to the
  clipboard, and announced with Open and Edit (satty for annotating).
- **Recording** uses gpu-screen-recorder: the Intel GPU encodes, the processor takes over
  where it cannot, and it captures the computer's sound and the microphone separately or
  mixed. Over wf-recorder (encodes on the processor; one audio source). A red mark in the
  bar shows while recording and stops it when clicked; the saved notification carries a
  frame from the video.

## Installation

The USB stick starts a guided installer by itself (gum, styled with the system palette):
keyboard, internet (optional), name and password, computer name, time zone, disk,
encryption, applications, then a summary. Nothing is written until the disk's name is
typed at the summary. It hands its answers to the same `amadeus-install` that the
unattended VM test drives, so the tested path and the guided path are one path.

**Everything the installation needs is on the ISO.** When the ISO is built, a fresh empty
package database stands in for the new system and every package pacman would download to
install the package lists and the bundled applications is collected, checked against its
signature, and stored on the ISO as a repository. The installer uses it and needs no
network; the internet is needed afterwards only for updates and for what is set up per
user (Claude Code and other harnesses, through mise). The cost is size: the ISO grows by
the size of those packages. The collected packages are the x86-64-v3 builds, which this
machine runs; a processor without v3 installs from the internet as before. The VM test
installs with its network cut off, so the offline path is the tested one.

## Desktop shell and generated applications: Quickshell (QML)

One toolkit for the bar, launcher, notifications, AI surfaces and generated apps.

- Over **web views** (models write HTML best, but 100–150 MB per window and a second
  toolkit for the shell).
- Over **AGS/Astal** (a JavaScript runtime per shell) and **EWW** (too limited).
- QML is declarative, reloads live, and a window costs about 40 MB.
- The weakness, that models write QML less reliably than HTML, is handled by a small
  component library, a lint pass before a new version replaces the working one, and
  per-app version history.

The launcher, every menu and notifications are part of the shell rather than separate
programs: one picker draws all lists (applications, the Amadeus menu, packages with a
details pane), so there is one look and two fewer packages. Applications from the AUR
are built by `amadeus-aur`, a short script, instead of a third-party helper such as yay:
it shows where a recipe downloads from and asks before building, because AUR recipes
are written by users and are the least trusted software on the system.

## Look and motion

Amadeus OS has its own visual identity, defined once in `desktop/theme/theme.json` and
read by the shell, the Amadeus panel and every generated app.

- **Palette: warm black with one amber accent.** Near-black surfaces with a slight warm
  tint, off-white text, and a single amber accent (with a deeper orange for gradients),
  after the glow of a nixie tube. One accent colour means anything amber is either
  focused or the AI; nothing else competes for the eye. Over the cool blue, green and
  purple palettes most Linux desktops ship, which this would otherwise be mistaken for.
- **Type: Inter for the interface, JetBrains Mono for code**, set system-wide, so
  applications match the shell.
- **Shape: floating, rounded surfaces** (bar, panel, picker, notifications) on a
  background the shell draws itself: no wallpaper image and no wallpaper program.
- **Motion: short and decisive.** Three durations (110, 180, 260 ms) and one easing
  curve that arrives fast and settles gently. Window movement uses critically damped
  curves that arrive fast and settle without overshoot, so windows never bounce. Opening and closing are a single
  motion driven by one value, so a surface can be interrupted halfway and reverse.
  Nothing animates for longer than a quarter of a second, and nothing animates that
  does not explain where something came from or went.
- **No blur or transparency effects.** The compositor does not provide them, and they
  cost battery on the integrated GPU for no gain in legibility.
- GTK applications are told to use dark mode, the same accent and the same fonts through
  system defaults; a user's own settings still win.

## AI coding harnesses: mise

Claude Code, Codex, opencode, Antigravity CLI and the like are installed per user
through mise, not as system packages.

- They release several times a week; mise installs the publisher's build directly and
  `mise upgrade` moves them all at once, with no recipe in between to wait for.
- They live in the user's home, so installing or updating one needs no administrator
  password and cannot break the system.
- One tool covers all of them, and the same menu reaches anything else mise can install.
- The list offered in the menu is a short file of names; only names mise's registry
  still knows are shown, and the program each one provides is asked from mise, so no
  command names or sources are written down in this repository.

Over AUR packages (a second maintainer between the publisher and the user, root to
install), npm installed globally (needs a system Node and root) and each tool's own
installer script (a different updater per tool).

## The bar and its controls

- **Icons are drawn, not installed.** One family of line icons on a 24-unit grid lives in
  `desktop/shell/Icon.qml` as vector paths (shapes after Feather Icons, MIT). They are
  sharp at any size, take the theme's colours, and a new icon is one more path in the
  same style. Over an icon font (a package, fixed weights, glyph numbers nobody can
  read) and over an icon theme (mixed styles from many hands).
- **Controls follow events.** Battery, power profile, audio, Bluetooth, the tray and
  stay-awake come from the shell toolkit's own bindings to the system services; Wi-Fi is
  re-read only when NetworkManager reports a change. The exceptions are the weather
  (every 30 minutes) and two sysfs reads every 30 seconds for the NVIDIA power state.
- **Power follows the cable**: performance when plugged in, balanced on battery, battery
  saver under 20%. A choice made by hand holds until the cable or that threshold changes.
- **Weather** asks wttr.in, which places you by network address. Removing `weather` from
  the bar layout stops the requests.
- **Administrator access without a password is a visible switch**, never a default. It
  costs one password prompt to turn on, shows in the bar while on, and a timed setting
  cannot outlive a restart. While it is on, the AI's host shell could also use it; that
  tool still asks for approval per command under the default policy.

## Where software comes from

In this order, and the install catalogue encodes it per entry:

1. **The system repositories**, when the software is there.
2. **An AUR recipe that downloads the publisher's own release**, when it is not. The
   recipe's sources are shown and the user is asked before anything is built.
3. **mise**, for AI coding harnesses and language toolchains, which belong to the user
   and change too often for packages.

An entry lists its sources best first and the first that still exists is used, so the
catalogue keeps working when a package moves into or out of the repositories.

Two small background helpers were added with the shortcuts: a clipboard watcher (cliphist,
a few MB, idle until something is copied) for clipboard history, and nothing for copy and
paste themselves, which send the standard keys to the focused window on demand.

## Defaults: terminal, editor, harness

The user's choice of terminal, editor and harness is one small file, read by three
wrappers: `amadeus-terminal`, `amadeus-editor` and `amadeus-harness run`. Every shortcut,
menu, `EDITOR`, and "open with" for text files points at a wrapper, never at a program,
so changing a default takes effect everywhere at once without logging out.

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
| Lock and idle | swaylock, swayidle | Compositor-independent |
| Audio | PipeWire + WirePlumber | Required by screen sharing and Bluetooth audio |
| Power | power-profiles-daemon + thermald | Uses the Intel driver's own hints; over TLP, which fights it |
