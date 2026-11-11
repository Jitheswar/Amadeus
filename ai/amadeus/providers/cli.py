"""Subscription logins. These CLIs are agents themselves, so instead of driving
them turn by turn we hand them the OS tools over MCP (`ama mcp`) with their own
built-in tools switched off. Every action still passes Amadeus policy and audit."""
import json, os, shutil, subprocess, sys, tempfile
from .. import config
from . import ProviderError

AMA = [sys.executable, "-m", "amadeus.cli"]


def _transcript(history):
    lines = []
    for m in history[:-1]:
        if m["role"] in ("user", "assistant") and m.get("text"):
            lines.append(f"{m['role'].upper()}: {m['text']}")
    prior = ("Conversation so far:\n" + "\n".join(lines[-20:]) + "\n\n") if lines else ""
    return prior + history[-1]["text"]


def _env(session):
    e = dict(os.environ, AMADEUS_SESSION=session, PYTHONPATH=str(config.SHARE))
    e.pop("CLAUDECODE", None)
    return e


class ClaudeCLI:
    kind = "agent"

    def __init__(self, name, pcfg):
        self.name, self.cfg = name, pcfg
        self.model = pcfg.get("model", "")

    def run(self, system, history, session, emit):
        exe = shutil.which(self.cfg.get("command", "claude"))
        if not exe:
            raise ProviderError("claude CLI not found. Install Claude Code and log in.")
        mcp = {"mcpServers": {"amadeus": {"command": AMA[0], "args": AMA[1:] + ["mcp"],
                                           "env": {"AMADEUS_SESSION": session, "PYTHONPATH": str(config.SHARE)}}}}
        with tempfile.NamedTemporaryFile("w", suffix=".json", dir=config.RUN, delete=False) as f:
            json.dump(mcp, f)
        cmd = [exe, "-p", _transcript(history), "--output-format", "stream-json", "--verbose",
               "--mcp-config", f.name, "--strict-mcp-config", "--tools", "",
               "--allowedTools", "mcp__amadeus", "--system-prompt", system,
               "--no-session-persistence", "--setting-sources", ""]
        if self.model:
            cmd += ["--model", self.model]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 env=_env(session), cwd=config.WORKSPACE, stdin=subprocess.DEVNULL)
            emit("_proc", p)
            final, said = "", []
            for line in p.stdout:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("type") == "assistant":
                    for b in ev.get("message", {}).get("content", []):
                        if b.get("type") == "text" and b.get("text"):
                            said.append(b["text"])
                            emit("text", {"text": b["text"]})
                elif ev.get("type") == "result":
                    final = ev.get("result") or ""
                    if ev.get("is_error"):
                        raise ProviderError(f"claude: {final[:500]}")
            p.wait()
            if p.returncode and not (final or said):
                raise ProviderError(f"claude exited {p.returncode}: {p.stderr.read()[-500:]}")
            return final or "\n".join(said)
        finally:
            os.unlink(f.name)


class CodexCLI:
    kind = "agent"

    def __init__(self, name, pcfg):
        self.name, self.cfg = name, pcfg
        self.model = pcfg.get("model", "")

    def run(self, system, history, session, emit):
        exe = shutil.which(self.cfg.get("command", "codex"))
        if not exe:
            raise ProviderError("codex CLI not found. Install it and run `codex login`.")
        out = tempfile.NamedTemporaryFile("r", suffix=".txt", dir=config.RUN, delete=False)
        cmd = [exe, "exec", "--skip-git-repo-check", "--sandbox", "read-only",
               "-c", f"mcp_servers.amadeus.command={json.dumps(AMA[0])}",
               "-c", f"mcp_servers.amadeus.args={json.dumps(AMA[1:] + ['mcp'])}",
               "-c", f"mcp_servers.amadeus.env={{AMADEUS_SESSION={json.dumps(session)},PYTHONPATH={json.dumps(str(config.SHARE))}}}",
               "--output-last-message", out.name]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(system + "\n\n" + _transcript(history))
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, env=_env(session), cwd=config.WORKSPACE, stdin=subprocess.DEVNULL)
            text = out.read().strip()
            if p.returncode and not text:
                raise ProviderError(f"codex exited {p.returncode}: {p.stderr[-500:]}")
            emit("text", {"text": text})
            return text
        finally:
            out.close()
            os.unlink(out.name)
