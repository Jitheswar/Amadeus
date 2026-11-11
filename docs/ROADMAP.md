# Roadmap

## Done (0.1)
- Session daemon, policy engine, approvals (terminal, palette, desktop dialog), audit chain, undo journal
- Providers: Claude API, OpenAI-compatible, Claude subscription via MCP
- 39 OS tools; MCP server usable from Claude Code, Claude Desktop and other clients
- Generated-app framework: manifest, sandbox, component library, versioning, rollback, OS bridge
- Root mode helper (restricted and unrestricted, TTL, off at shutdown)
- `ama doctor`, test suite, PKGBUILD

## Not yet verified on this machine
- `codex-cli` provider: written to the documented CLI interface, but codex is not installed here
- API providers against live endpoints (tested against a local mock; no keys are configured)
- Root-mode operations as root (validation is tested unprivileged; needs `install.sh --system`)

## Next
1. Local model: ollama with a 4-bit 7B model fits the 6 GB card; wire it as the offline fallback
2. Context awareness: daemon subscribes to Hyprland events and offers workspace layouts per activity
3. Extending existing applications: per-app side panels attached to a window class
4. App bridge for `ai` permission with subscription providers
5. Streaming output in the palette for API providers
6. Snapshots in the boot menu
7. Offline install (packages on the ISO) and our own package repository for updates to `amadeus`
