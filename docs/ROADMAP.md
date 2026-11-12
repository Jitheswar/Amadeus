# Roadmap

## Done
- AI layer: session daemon, capability policy, approvals, hash-chained audit log, undo journal
- Providers: Claude API, OpenAI-compatible (OpenAI, OpenRouter, local), Claude subscription and Codex through MCP
- Generated-app framework: manifest, sandbox, component library, lint, version history
- Root mode: separate root helper, restricted or unrestricted, time limit, gone at shutdown
- Installer: encrypted btrfs, snapshots on every package change, NVIDIA only when present
- ISO build and VM test harness, both in a container; the full run passes: install, first boot, rollback from the system, rollback from the ISO
- Built-in agent skill and `ama discover`: agents learn the system by inspecting it, not from stored documentation
- End-to-end AI request test on the installed system with a scripted model
- Amadeus panel: docked, parallel tasks, show steps, stop, undo a whole task; ask about the focused window (Super+A)
- Setup > GPU: automatic, NVIDIA for everything, or Intel only
- CachyOS repositories, `linux-cachyos` kernel with its prebuilt NVIDIA module, `cachyos-settings`
- Bar with drawn icons and drop-down panels: calendar, power mode (automatic by cable and charge), Wi-Fi, Bluetooth, volume, brightness, background apps, stay awake, timed passwordless administrator access, weather
- Install catalogue: terminals, browsers, editors, AI desktop apps and development tools, each from the system repositories first and an AUR recipe of the publisher's build otherwise; web apps
- Amadeus menu: Setup (display, text size, defaults, config), System, About
- Shortcuts: universal copy and paste, clipboard history, overlay scratchpad, move window to workspace
- Capture: freeze-and-choose screenshots saved and copied; screen recording with no sound, the computer's sound, or both with the microphone; Trigger > Capture menu
- Guided installer that starts when the USB stick boots
- AI coding harnesses through mise (install, remove, update, run); defaults for terminal, editor and harness
- Own visual identity and motion system from one theme file; headless preview of the shell
- Launcher, menus and notifications drawn by the shell; text in the launcher that matches no application goes to Amadeus
- Install menu for Arch packages and the AUR with a details pane; `amadeus-aur` with recipe review
- Shortcut and command list (Super+K), read from the live configuration
- Amadeus menu (Super+Space): Apps, Install, Remove, Update, Defaults
- Desktop on Hyprland (moved from niri): defaults, bar driven by the compositor's events, AI-managed file checked with `Hyprland --verify-config` before it is kept
- Applications outside the Arch repositories built from publisher releases; no third-party repository

## In progress
1. A full VM pass of everything since the last one: Hyprland, the CachyOS base, the bar, the install catalogue, capture
2. `amadeus-update` in the VM; a real model driving the installed system

## Next
3. First install on the real machine: NVIDIA power-down, PRIME offload, Wi-Fi, suspend
4. Snapshots selectable in the boot menu
5. Local model as the offline fallback (a 4-bit 7B model fits the 6 GB card)
6. Context awareness: the daemon follows compositor events and offers workspace layouts per activity
7. Extending existing applications: side panels attached to an application's windows
8. Offline install (all packages on the ISO)

## Not yet verified
- Anything on real hardware
- API providers against live endpoints (tested against a local mock)
- Root-mode operations as root
