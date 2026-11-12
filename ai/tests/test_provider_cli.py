#!/usr/bin/python3
"""The subscription providers, driven by a stand-in CLI.

Claude Code and Codex run their own agent loop; these tests check the way the
daemon starts them, what reaches the model, and how their output comes back.
No subscription, network or real CLI is used."""
import os, sys, tempfile, unittest
from pathlib import Path

if not os.environ.get("AMADEUS_CONFIG"):
    TMP = tempfile.mkdtemp(prefix="amadeus-cli-test-")
    for key in ("CONFIG", "STATE", "DATA", "RUN"):
        os.environ[f"AMADEUS_{key}"] = f"{TMP}/{key.lower()}"
    os.environ["AMADEUS_PRIV_SOCK"] = f"{TMP}/priv.sock"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amadeus import config                                    # noqa: E402
from amadeus.providers import ProviderError                  # noqa: E402
from amadeus.providers.cli import ClaudeCLI, CodexCLI, _transcript   # noqa: E402

config.ensure_dirs()


class SubscriptionProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="amadeus-cli-case-"))
        self.saved = {k: os.environ.get(k) for k in ("CLAUDE_ARGS", "CODEX_ARGS", "CLAUDECODE")}

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def script(self, name, body):
        path = self.tmp / name
        path.write_text("#!/bin/bash\n" + body)
        path.chmod(0o755)
        return path

    @staticmethod
    def arguments(path):
        return path.read_text().rstrip("\x1e").split("\x1e")

    def test_claude_transcript_and_arguments(self):
        args = self.tmp / "claude.args"
        session = self.tmp / "claude.session"
        environ = self.tmp / "claude.env"
        fake = self.script("claude", f"""printf '%s\\036' "$@" > {args}
printf '%s' "$AMADEUS_SESSION" > {session}
printf 'CLAUDECODE=%s' "${{CLAUDECODE:-}}" > {environ}
printf '%s\\n' '{{"type":"assistant","message":{{"content":[{{"type":"text","text":"hello from claude"}}]}}}}'
printf '%s\\n' '{{"type":"result","result":"done","is_error":false}}'
""")
        os.environ["CLAUDE_ARGS"] = str(args)
        os.environ["CLAUDECODE"] = "should-not-reach-the-child"
        emitted = []
        history = [{"role": "user", "text": "earlier question"}, {"role": "assistant", "text": "earlier answer"},
                   {"role": "user", "text": "current request"}]
        provider = ClaudeCLI("claude-cli", {"command": str(fake), "model": "a-model"})
        result = provider.run("system rules", history, "session-42", lambda kind, data: emitted.append((kind, data)))

        self.assertEqual(result, "done")
        self.assertIn(("text", {"text": "hello from claude"}), emitted)
        self.assertEqual(session.read_text(), "session-42")
        self.assertEqual(environ.read_text(), "CLAUDECODE=")
        argv = self.arguments(args)
        self.assertEqual(argv[0], "-p")
        self.assertIn("earlier question", argv[1])
        self.assertIn("current request", argv[1])
        self.assertIn("--output-format", argv)
        self.assertIn("stream-json", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertIn("--allowedTools", argv)
        self.assertEqual(argv[argv.index("--allowedTools") + 1], "mcp__amadeus")
        self.assertEqual(argv[argv.index("--tools") + 1], "")
        self.assertEqual(argv[argv.index("--model") + 1], "a-model")
        self.assertEqual(argv[argv.index("--system-prompt") + 1], "system rules")

    def test_claude_error_result_is_a_provider_error(self):
        fake = self.script("claude", """printf '%s\\n' '{"type":"result","result":"the model refused","is_error":true}'
""")
        provider = ClaudeCLI("claude-cli", {"command": str(fake)})
        with self.assertRaises(ProviderError) as error:
            provider.run("system", [{"role": "user", "text": "hi"}], "s", lambda *a: None)
        self.assertIn("the model refused", str(error.exception))

    def test_claude_missing_binary_is_a_clear_error(self):
        provider = ClaudeCLI("claude-cli", {"command": str(self.tmp / "not-there")})
        with self.assertRaises(ProviderError) as error:
            provider.run("system", [{"role": "user", "text": "hi"}], "s", lambda *a: None)
        self.assertIn("not found", str(error.exception))

    def test_codex_transcript_and_output(self):
        args = self.tmp / "codex.args"
        environ = self.tmp / "codex.env"
        fake = self.script("codex", f"""out=""
while [[ $# -gt 0 ]]; do
  printf '%s\\036' "$1" >> {args}
  [[ $1 == --output-last-message ]] && out=$2
  shift
done
printf '%s' "$AMADEUS_SESSION" > {environ}
printf 'codex answer\\n' > "$out"
""")
        os.environ["CODEX_ARGS"] = str(args)
        emitted = []
        provider = CodexCLI("codex-cli", {"command": str(fake)})
        result = provider.run("system rules", [{"role": "user", "text": "do it"}], "session-7",
                              lambda kind, data: emitted.append((kind, data)))
        self.assertEqual(result, "codex answer")
        self.assertIn(("text", {"text": "codex answer"}), emitted)
        self.assertEqual(environ.read_text(), "session-7")
        argv = self.arguments(args)
        self.assertEqual(argv[0], "exec")
        self.assertIn("--skip-git-repo-check", argv)
        self.assertIn("read-only", argv)
        self.assertIn("mcp_servers.amadeus.command", " ".join(argv))
        self.assertTrue(any("system rules" in a and "do it" in a for a in argv))

    def test_codex_missing_binary_is_a_clear_error(self):
        provider = CodexCLI("codex-cli", {"command": str(self.tmp / "not-there")})
        with self.assertRaises(ProviderError) as error:
            provider.run("system", [{"role": "user", "text": "hi"}], "s", lambda *a: None)
        self.assertIn("not found", str(error.exception))

    def test_transcript_keeps_the_recent_conversation_and_the_last_request(self):
        history = [{"role": "user", "text": "one"}, {"role": "assistant", "text": "two"},
                   {"role": "user", "text": "three"}]
        text = _transcript(history)
        self.assertIn("USER: one", text)
        self.assertIn("ASSISTANT: two", text)
        self.assertTrue(text.endswith("three"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
