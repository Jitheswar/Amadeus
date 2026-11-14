"""Subscription logins. These CLIs are agents themselves, so instead of driving
them turn by turn we hand them the OS tools over MCP (`ama mcp`) with their own
built-in tools switched off. Every action still passes Amadeus policy and audit."""
import json, os, shutil, subprocess, sys, tempfile
from .. import config
from . import ProviderError

AMA = [sys.executable, "-m", "amadeus.cli"]


def find_cli(command):
    """Resolve installed mise binaries without invoking a downloading shim."""
    from pathlib import Path
    from ..tools import sh
    found = shutil.which(command)
    if not found:
        return None
    path = Path(found)
    if path.is_symlink() and path.resolve().name == "mise":
        try:
            result = sh(["mise", "which", path.name], env=dict(os.environ, MISE_OFFLINE="1"), timeout=5)
            resolved = result.stdout.strip()
            return resolved if result.returncode == 0 and Path(resolved).is_file() else None
        except Exception:
            return None
    return found


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
        exe = find_cli(self.cfg.get("command", "claude"))
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
        err = tempfile.TemporaryFile("w+b", dir=config.RUN)
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, text=True,
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
                err.seek(0, os.SEEK_END)
                err.seek(max(0, err.tell() - 2000))
                detail = err.read(2000).decode("utf-8", errors="replace")[-500:]
                raise ProviderError(f"claude exited {p.returncode}: {detail}")
            return final or "\n".join(said)
        finally:
            err.close()
            os.unlink(f.name)


class CodexCLI:
    kind = "agent"

    def __init__(self, name, pcfg):
        self.name, self.cfg = name, pcfg
        self.model = pcfg.get("model", "")

    def run(self, system, history, session, emit):
        exe = find_cli(self.cfg.get("command", "codex"))
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


class AntigravityCLI:
    """Official agy headless mode, with native actions denied and Amadeus MCP allowed."""
    kind = "agent"

    def __init__(self, name, pcfg):
        self.name, self.cfg = name, pcfg

    def run(self, system, history, session, emit):
        from pathlib import Path
        exe = find_cli(self.cfg.get("command", "agy"))
        if not exe:
            raise ProviderError("Antigravity CLI not found. Install it from Install > Harness and sign in with agy.")
        with tempfile.TemporaryDirectory(prefix="agy-", dir=config.RUN) as directory:
            root = Path(directory)
            (root / ".agents").mkdir()
            mcp = {"mcpServers": {"amadeus": {"command": AMA[0], "args": AMA[1:] + ["mcp"],
                    "env": {"AMADEUS_SESSION": session, "PYTHONPATH": str(config.SHARE)}}}}
            (root / ".agents/mcp_config.json").write_text(json.dumps(mcp))
            permissions = {"agentMode": "", "toolPermission": "request-review", "permissions": {
                "deny": ["command(*)", "read_file(*)", "write_file(*)", "read_url(*)", "execute_url(*)"],
                "allow": ["mcp(amadeus/*)"], "ask": []}}
            prompt = system + "\nUse only the amadeus MCP tools for system actions.\n\n" + _transcript(history)
            command = [exe, "-p", prompt, "--output-format", "json", "--disable-slash-commands", "--settings", json.dumps(permissions)]
            if self.cfg.get("model"):
                command += ["--model", self.cfg["model"]]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       env=_env(session), cwd=root, stdin=subprocess.DEVNULL)
            emit("_proc", process)
            try:
                out, err = process.communicate()
                try:
                    result = json.loads(out)
                except json.JSONDecodeError:
                    raise ProviderError("Antigravity returned an unreadable response")
                if not isinstance(result, dict):
                    raise ProviderError("Antigravity returned an invalid response")
                if process.returncode or result.get("status") != "SUCCESS":
                    raise ProviderError("Antigravity: " + str(result.get("error") or err or "request failed")[-500:])
                text = str(result.get("response") or "")
                emit("text", {"text": text})
                return text
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                process.stdout.close()
                process.stderr.close()
