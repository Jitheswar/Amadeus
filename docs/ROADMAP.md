# Roadmap

The [README](../README.md#verification) records the verification baseline. Package,
command, provider and shortcut inventories belong to their source files and live
discovery output rather than this roadmap.

## Implemented

- A user-session AI daemon with policy checks, approval, audit and file undo; a separate
  transient root helper; and sandboxed, versioned generated applications.
- Subscription, API and local-model selection, saved panel-agent defaults, temporary
  overrides, and on-demand usage controls. Terminal harness installation and defaults
  remain independent user choices.
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

The runtime identified in the README passed 117 installed-system VM checks: 102 on first
boot, eight after rollback from the running system, and seven after rollback from the ISO. The Try-session
checks, fast checks and QML syntax checks also passed; rendered previews were inspected.
The VM installation had no internet access. AI requests used a scripted local model.

The package-index regression was reproduced with an old index and a newer detached
signature: installation-time freshness could retain the old data. The shared seeder
passed a conditional-HTTP regression and a real signed-metadata refresh check, followed
by the full VM suite. Signature verification remained enabled.

## Next validation

1. Install on the target machine and measure NVIDIA runtime power-down, PRIME offload,
   Dynamic Boost, Wi-Fi, Bluetooth, battery use and suspend/resume.
2. Exercise live subscription sign-in and API endpoints, including cancellation, approvals
   and quota collection. The VM results do not establish vendor-account compatibility.
3. Test full system updates and mirror changes in the VM, plus structured root-mode
   actions beyond the existing refusal and helper checks.
4. Walk through the guided installer and desktop controls by hand. The automated installer
   test uses the backend; preview images do not verify real compositor motion.

## Planned work

- Snapshot selection from the boot menu.
- An explicit offline local-model fallback suited to the target machine's memory.
- Richer workspace suggestions built on the opt-in desktop-event task system.
- Side panels attached to existing applications and a visible mark on windows the AI
  is working with.

These are planned features, not behavior supplied by the current image.
