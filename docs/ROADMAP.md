# Roadmap

## Done
- AI layer: session daemon, capability policy, approvals, hash-chained audit log, undo journal
- Providers: Claude API, OpenAI-compatible (OpenAI, OpenRouter, local), Claude subscription and Codex through MCP
- Generated-app framework: manifest, sandbox, component library, lint, version history
- Root mode: separate root helper, restricted or unrestricted, time limit, gone at shutdown
- Installer: encrypted btrfs, snapshots on every package change, NVIDIA only when present
- ISO build and VM test harness, both in a container
- Applications outside the Arch repositories built from publisher releases; no third-party repository

## In progress
1. Desktop on niri: compositor defaults, the AI's desktop tools, AI-managed include file
2. Launcher and notifications inside the shell; one entry point for applications and the AI
3. VM run of `amadeus-rollback` (running system and ISO) and `amadeus-update`

## Next
4. First install on the real machine: NVIDIA power-down, PRIME offload, Wi-Fi, suspend
5. Snapshots selectable in the boot menu
6. Local model as the offline fallback (a 4-bit 7B model fits the 6 GB card)
7. Context awareness: the daemon follows compositor events and offers workspace layouts per activity
8. Extending existing applications: side panels attached to an application's windows
9. Offline install (all packages on the ISO)

## Not yet verified
- Anything on real hardware
- API providers against live endpoints (tested against a local mock)
- Root-mode operations as root
