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
| NixOS (unstable) | Atomic system generations and rollback in the boot menu: the best fit for an AI that changes the system. | The initial packaging evaluation favored the existing pacman/vendor-release workflow. This is a historical choice, not a claim about current optional-app availability. |
| openSUSE Tumbleweed / Aeon | Rolling with tested snapshots and transactional updates. | The initial vendor-app packaging workflow would need additional ownership in another package ecosystem. |
| Fedora Atomic, Debian, Ubuntu | Stable. | Not rolling. |
| Void, Gentoo | Minimal. | Few of the required applications; no systemd (Void). |

The selected CachyOS builds target newer CPU instructions where supported. This
project has not measured a performance gain or established greater stability than
Arch. Recovery and validation are separate requirements:

- a btrfs snapshot before every update (`amadeus-update`), the newest five kept; installing
  or removing a package manually has no automatic snapshot hook. Structured AI package
  transactions separately attempt pre/post snapshots and report the resulting recovery data
- a copy of `/boot` inside each snapshot, so a snapshot carries its matching kernel
- `amadeus-rollback`, from the running system or from the installer medium
- AI changes go through one enforcement point with an undo journal and an audit log

The installer uses the processor-specific repositories only when the processor can run
them, and falls back to the generic CachyOS and Arch repositories otherwise. Their
signing key and mirror lists are fetched over HTTPS when the ISO is built and shipped
on it.

## Kernel, boot, storage

- **Kernel: `linux-cachyos`**, the selected CachyOS desktop kernel family. Its upstream
  build configuration and scheduler can change; Amadeus does not layer another scheduler on top or claim
  benchmarked gains. Over Arch's `linux` (generic build) and over
  the other CachyOS variants (LTS, hardened, server and real-time builds answer needs
  this machine does not have).
- **System tuning: `cachyos-settings`** (their sysctl values, I/O scheduler rules and
  related defaults) and `ananicy-cpp` with their rule set, which lowers the priority of
  background work so the foreground stays responsive. That is one more always-running
  process; its actual idle memory and responsiveness benefit need measurement.
- **Boot loader: systemd-boot.** Already part of systemd; nothing extra to maintain.
  Over GRUB (large, slow, fragile config generation) and limine.
- **Filesystem: btrfs on LUKS2**, subvolumes `@ @home @log @pkg`, zstd compression.
  Snapshots are the recovery mechanism, so the filesystem must provide them; over ext4
  (no snapshots) and ZFS (out-of-tree module on a rolling kernel).
- **Swap: zram**, no swap partition. Compressed memory-backed swap avoids a dedicated
  disk swap partition. The shipped layout does not configure hibernation; the menu
  offers it only when logind reports it available.

## Graphics

- **Automatic mode renders on Intel and offloads applications to NVIDIA.** The selected
  open module uses runtime power management `0x02`, aiming to let the card suspend
  when idle. Actual power behavior remains unverified on hardware. Applications are
  offloaded one at a time (`amadeus-gpu-run`, or the AI decides per application).
  Only an explicit user-selected GPU mode may select NVIDIA globally.
- **Driver package: `linux-cachyos-nvidia-open`**, for the card in this machine
  (GA107BM, `10de:25ec`, Ampere): the open kernel module is NVIDIA's supported path for
  this generation at the initial driver evaluation. This package provides it prebuilt
  for the `linux-cachyos` kernel family, avoiding a local DKMS build. Package
  compatibility and the actual driver/power path still need target-machine validation.
  The proprietary-driver firmware comes with `nvidia-utils`; the image excludes the
  separate nouveau firmware package. `lib32-nvidia-utils` supports optional Proton use.
- **Dynamic Boost on (`nvidia-powerd`).** It is enabled when NVIDIA is provisioned to
  support firmware-controlled power allocation under load. Its benefit and battery cost
  need real-machine measurement.
- **CUDA is optional**, with its packages defined separately from the base image.
- Left at the driver default, to be tried on the real machine: S0ix video-memory
  self-refresh (`NVreg_EnableS0ixPowerManagement`). The actual suspend path, memory
  retention and battery cost need hardware testing.
- **The user can choose, in Setup > GPU**: automatic (the default above), NVIDIA for
  everything (the compositor renders on NVIDIA), or Intel only (desktop launches
  do not offload to NVIDIA). Actual display routing and power consumption must be
  measured on the machine. The choice is written to the
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
encryption, optional extras, then a summary. Base apps install regardless of the
extras answer. Nothing is written until the disk's name is
typed at the summary. It hands its answers to the same `amadeus-install` that the
unattended VM test drives, so the tested path and the guided path are one path.

**Everything the installation needs is on the ISO.** When the ISO is built, a fresh empty
package database stands in for the new system and every package pacman would download to
install the package lists and the bundled applications is collected, checked against its
signature, and stored on the ISO as a repository. On the target x86-64-v3 CPU, the
installer uses it without a network; updates, optional downloads and provider sign-in
need a connection later. The tradeoff is size: the ISO grows by
the size of those packages. The collected packages are the x86-64-v3 builds, which this
machine runs; a processor without v3 installs from the internet as before. The VM test
installs with its network cut off, so the offline path is the tested one.

**Trying without installing.** The ISO's default boot entry starts the desktop from the
stick: a temporary user, logged straight in, with every change kept in memory, so nothing
is written to any disk. It adds the desktop packages to the live medium (about a
gigabyte) and runs Arch's kernel, which the live medium boots, not CachyOS's: enough to
judge the hardware and the desktop, not the kernel tuning. The install entry is the
second one in the menu. The try session fetches the repository package lists once the
network comes up, so the Install menu and the catalogue show what can be added; it
installs nothing by itself. Missing lists are seeded from the medium for offline
browsing, then marked due for the first online refresh.

**Mirrors are chosen for quality first, then speed.** The first `amadeus-update` ranks
the official mirrors once: the Arch list from the Mirror Status data (fully synced, HTTPS,
synced in the last 12 hours, the twenty best-scored servers), then a measured download
speed from this connection; the CachyOS list is its own official mirrorlist, ranked by
fetching a package database from each entry. Country is not a filter: a nearby mirror is
not automatically good, and the speed test measures the path that a download will use.
The previous lists are kept, the new ones are checked with `pacman -Syy`, and a failure
puts the previous lists back. It is repeated after a month, or when a package replaces a
list. Cost: about half a minute on the first update, once a month; no timer and no
background service.

## Desktop shell and generated applications: Quickshell (QML)

One toolkit for the bar, launcher, notifications, AI surfaces and generated apps.

- Over **web views** (a second application runtime and toolkit would be needed for the shell).
- Over **AGS/Astal** (a JavaScript runtime per shell) and **EWW** (too limited).
- QML is declarative and supports shared components. Memory and responsiveness need
  measurement for each actual surface.
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
  curve that arrives fast and settles gently. Window movement uses compositor animation
  curves intended to settle without overshoot. Opening and closing are a single
  motion driven by one value, so a surface can be interrupted halfway and reverse.
  Motion should explain a transition and remain short. The theme is authoritative for
  shell timing; compositor animation settings are maintained separately.
- **No blur or transparency effects.** They are disabled by the shipped compositor
  configuration to avoid additional rendering work. This is a default choice rather
  than a compositor limitation.
- GTK applications are told to use dark mode, the same accent and the same fonts through
  system defaults; a user's own settings still win.

## AI coding harnesses: mise

Claude Code, Codex, opencode, Antigravity CLI and the like are installed per user
through mise, not as system packages.

- They release several times a week; mise installs the publisher's build directly and
  `mise upgrade` moves them all at once, with no recipe in between to wait for.
- They live in the user's home, so installing or updating one needs no administrator
  password. They still execute with the user's permissions and require trust in the publisher.
- One tool covers all of them, and the same menu reaches anything else mise can install.
- The list offered in the menu is a short file of names; only names mise's registry
  still knows are shown, and the program each one provides is asked from mise, rather than duplicating that executable mapping in menu code.

Over AUR packages (a second maintainer between the publisher and the user, root to
install), system-wide npm installs (shared ownership and a separate runtime/update path) and each tool's own
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
`amadeus-aur` refuses a name the system repositories already carry, so the order holds
even when a package is asked for by name rather than chosen from the catalogue.

Gaming and chat clients are opt-in through the Amadeus menu. Their catalogue entries
name the official Arch repository explicitly, so those installs use its signed packages.

Clipboard history uses separate `wl-paste` watchers for text and images, with cliphist
storing changes on demand. Copy and paste bindings send their keys on demand and do
not require their own persistent process.

## Defaults: terminal, editor, harness

The user's choice of terminal, editor and harness is one small file, read by three
wrappers: `amadeus-terminal`, `amadeus-editor` and `amadeus-harness run`. Every shortcut,
menu, `EDITOR`, and "open with" for text files points at a wrapper, never at a program,
so changing a default takes effect everywhere at once without logging out.

## AI layer: Python standard library

A daemon in the user session using only the Python standard library, reducing dependency
churn and keeping the enforcement code small enough to review. Interpreter, service and
provider changes can still require compatibility fixes. Over Rust
or Go: nothing here is performance-critical, and fast iteration matters more. Root
actions never run in the daemon: they go to a separate root helper that exists only
while root mode is on and is gone at shutdown.

## Applications

| Need | Choice | Why |
|---|---|---|
| Terminal | foot | Wayland-native, starts instantly, a few MB of memory |
| File manager | Nautilus | Provides the Files app and directory handling in the GTK desktop |
| Document viewer | Papers | Maintained GTK4 successor to Evince |
| Image viewer | imv | Tiny, keyboard-driven, Wayland-native |
| Camera | Snapshot | Uses PipeWire/libcamera; the older choices (Cheese, guvcview) do not |
| Login | greetd + tuigreet | No display-manager stack |
| Lock and idle | swaylock, swayidle | Compositor-independent |
| Audio | PipeWire + WirePlumber | Required by screen sharing and Bluetooth audio |
| Power | power-profiles-daemon + thermald | Uses the Intel driver's own hints; over TLP, which fights it |

## AI agent selection

Defaults > Agent controls the right-side Amadeus panel. A request can override
that default without changing it. Subscription CLIs keep their own login; API
keys stay in the private secrets directory and never enter the provider listing.
The Antigravity adapter uses its official headless CLI and workspace MCP setup,
with native shell, file and browser operations denied; system actions still go
through the daemon's policy and audit boundary.

## Unified text size

One text-size setting follows Omarchy's approach: live shell and panel sizing,
GTK scaling quantized to whole font points, and terminal configuration together.
The default remains Amadeus's 14px shell / 11pt terminal size. A terminal that
cannot reload its configuration takes the size in a new window.

## Search across menus

The picker indexes installed applications and Amadeus settings once per opening,
then searches that index locally. A global selection cancels its original menu
before launching its action, so a settings or application ID cannot be mistaken
for a package, display mode or another local menu choice. The application list
respects desktop visibility and package ownership; settings stay discoverable in
search while dependency helpers and secondary backend launchers stay out of Apps.

## On-demand AI usage

The usage view follows Omarchy's native collector sources: Claude OAuth usage,
Codex app-server rate limits, and Antigravity's quota summary. It runs only when
opened or explicitly refreshed, caches quota results for a minute, bounds replies,
and never sends credentials to the UI or follows authenticated redirects. API
providers without subscription limits say so rather than showing invented meters.

## Desktop credential storage

GNOME Keyring is not installed by default. Automatic Secret Service activation on
a fresh desktop can otherwise ask the user to create or unlock a separate keyring.
Users who want a desktop keyring can install a Secret Service provider from the
package menu. Applications that require Secret Service need a provider before
they can store credentials. Existing keyring files are not removed. Amadeus API keys
continue to use its private, permission-restricted secrets directory. Repository signing
keys are independent and remain required.

## Package index snapshots from the install medium

The medium seeds missing package indexes for offline catalogue browsing. A seeded
index is marked as due for refresh rather than given its copy time: HTTP conditional
requests must not keep an old database while downloading a newer detached signature.
Seeding publishes each file atomically and never replaces an existing index. The try
session and installed-system setup use the same helper; signature verification stays
with pacman when the first online sync downloads current metadata.

## Image filesystem boundary

The SquashFS build is restricted to the root filesystem. A temporary system mount
that survives build-tool cleanup must remain an empty mount directory in the image.
This avoids reading host sysfs data or other mounted pseudo-filesystems into the ISO.
The mounted-filesystem fixture and final archive inspection verified that behavior.
