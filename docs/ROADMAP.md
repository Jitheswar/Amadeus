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
- Install catalogue: terminals, browsers, editors, AI desktop apps and development tools, each from the system repositories first and an AUR recipe of the publisher's build otherwise; web apps
- Amadeus menu: Setup (display, text size, defaults, config), System, About
- Shortcuts: universal copy and paste, clipboard history, scratchpad, screenshots, move window to workspace
- AI coding harnesses through mise (install, remove, update, run); defaults for terminal, editor and harness
- Own visual identity and motion system from one theme file; headless preview of the shell
- Launcher, menus and notifications drawn by the shell; text in the launcher that matches no application goes to Amadeus
- Install menu for Arch packages and the AUR with a details pane; `amadeus-aur` with recipe review
- Shortcut and command list (Super+K), read from the live configuration
- Amadeus menu (Super+Space): Apps, Install, Remove, Update, Defaults
- Desktop on niri: defaults, bar driven by the compositor's event stream, AI-managed include file that is validated before it is applied
- Applications outside the Arch repositories built from publisher releases; no third-party repository

## In progress
1. `amadeus-update` in the VM; a real model driving the installed system

## Next
2. First install on the real machine: NVIDIA power-down, PRIME offload, Wi-Fi, suspend
3. Snapshots selectable in the boot menu
4. Local model as the offline fallback (a 4-bit 7B model fits the 6 GB card)
5. Context awareness: the daemon follows compositor events and offers workspace layouts per activity
6. Extending existing applications: side panels attached to an application's windows
7. Offline install (all packages on the ISO)

## Not yet verified
- Anything on real hardware
- API providers against live endpoints (tested against a local mock)
- Root-mode operations as root
