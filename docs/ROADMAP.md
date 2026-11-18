# Roadmap

The [README](../README.md#verification) records the verification baseline. Package,
command, provider and shortcut inventories belong to their source files and live
discovery output rather than this roadmap.

## Implemented

- A user-session AI daemon with policy checks, approval, audit and file undo; a separate
  transient root helper; and sandboxed, versioned generated applications.
- Subscription, API and local-model selection, saved panel-agent defaults, temporary
  overrides, per-provider model and effort, provider-independent execution modes, and
  on-demand usage controls. Terminal harness installation and defaults
  remain independent user choices.
- One theme file rendered for every application, a selectable login-screen theme, live
  recolouring of open terminals, and display scale and text size chosen from the panel.
- Topic guides an agent pulls up per area, alongside live discovery.
- Requests that carry a short fixed tool list with the rest found on demand, a cacheable
  prompt, bounded history, token reporting and a small user-editable memory.
- Goals worked in the background in rounds, checked before they count as done, resumed
  after a restart and handed back when they need a decision.
- Notices for failed services, crashed programs, a nearly full disk and overdue updates,
  offered as one-click requests, and
  a per-task grant for unasked reversible changes that only the user can set.
- A Hyprland desktop with a shared shell, cross-menu app/settings search, filtered app
  and audio-device lists, unified text sizing, capture tools and configurable defaults.
- A graphical login with account preselection, a profile dropdown when needed, and
  password-free graphical return to the Try session after logout.
- Native settings and app interaction, context handoff from menus/settings/selection/Files,
  visible working state and global stop, plus opt-in scheduled and desktop-event tasks.
- Guided and unattended installation, a temporary Try session, an optional extras choice,
  signed offline packages for the target CPU, and package-index snapshots that refresh
  correctly on the first network sync.
- An opt-in policy for gaming/chat clients and coding harnesses, plus a default desktop
  without automatic GNOME Keyring activation.
- Update snapshots, boot-file recovery and rollback from the running system or installer
  medium. Ordinary manual package changes do not create automatic snapshots.
- Container builds, fast checks, headless previews and a full VM install/recovery harness.

## Verified baseline

The runtime identified in the README passed 153 installed-system VM checks: 138 on first
boot, 8 after rollback from the running system, and 7 after rollback from the ISO.
The Try-session checks, fast checks and QML checks also passed; rendered previews were
inspected. The VM installation had no internet access. AI requests used a scripted model.
The new native checks exercise real compositor focus and NetworkManager profile changes,
plus timers, screen sharing, guarded keyboard input and settings undo. Login tests cover
password entry, rejection and both graphical session round trips.

The package-index regression was reproduced with an old index and a newer detached
signature: installation-time freshness could retain the old data. The shared seeder
passed a conditional-HTTP regression and a real signed-metadata refresh check, followed
by the full VM suite. Signature verification remained enabled.

## Next validation

The steps for the first run on the target machine are written out in
[HARDWARE-TEST.md](HARDWARE-TEST.md), for the user and an AI agent to work through there.

0. On the target machine, try the copy and paste shortcuts by hand, the automatic display
   choice, theme changes across real applications, and the themed login screen.
1. Install on the target machine and measure NVIDIA runtime power-down, PRIME offload,
   Dynamic Boost, Wi-Fi, Bluetooth, battery use and suspend/resume, and confirm the
   touchpad binds at boot (`hyprctl devices` lists a touchpad, not a PS/2 mouse).
1a. Install on machines other than the reference laptop: AMD graphics, a pre-Turing
   NVIDIA card, and any of the models with fixes in `amadeus-hardware`.
2. Exercise live subscription sign-in and API endpoints, including cancellation, approvals
   and quota collection. The VM results do not establish vendor-account compatibility.
3. Run `./build.sh test` on the image with hardware detection, the generalised GPU modes
   and the new update pipeline (cache pruning, migrations, orphans, drivers). Then test
   full system updates and mirror changes in the VM, plus structured root-mode
   actions beyond the existing refusal and helper checks.
4. Walk through the guided installer and desktop controls by hand. The automated installer
   test uses the backend; preview images do not verify real compositor motion. Include the
   multi-profile chooser and accessibility actions in several native applications.

## Planned work

- One undo for everything a goal changed, and a visible mark on windows a goal is using.
- Noticing a boot that needed a rollback, which needs a marker the rollback tool does not yet leave.
- Snapshot selection from the boot menu.
- An explicit offline local-model fallback suited to the target machine's memory.
- Richer workspace suggestions built on the opt-in desktop-event task system.
- Side panels attached to existing applications and a visible mark on windows the AI
  is working with.

These are planned features, not behavior supplied by the current image.
