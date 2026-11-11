# Roadmap

## Done
- AI layer: session daemon, capability policy, approvals, hash-chained audit log, undo journal
- Providers: Claude API, OpenAI-compatible (OpenAI, OpenRouter, local), Claude subscription and Codex through MCP
- Generated-app framework: manifest, sandbox, component library, lint, version history
- Root mode: separate root helper, restricted or unrestricted, time limit, gone at shutdown
- Installer: encrypted btrfs, snapshots on every package change, NVIDIA only when present
- ISO build and VM test harness, both in a container
- Built-in agent skill and `ama discover`: agents learn the system by inspecting it, not from stored documentation
- Amadeus menu (Super+Space): Apps, Install, Remove, Update, Defaults
- Desktop on niri: defaults, bar driven by the compositor's event stream, AI-managed include file that is validated before it is applied
- Applications outside the Arch repositories built from publisher releases; no third-party repository

## In progress
1. VM run of the niri desktop, `amadeus-rollback` (running system and ISO) and `amadeus-update`
2. Launcher and notifications inside the shell; one entry point for applications and the AI

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
