"""Provider selection, private setup and display-only usage regressions."""
import json, os, tempfile, unittest
from pathlib import Path
from unittest import mock
from amadeus import config
from amadeus.providers.cli import AntigravityCLI


class ProviderSettingsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.patch = mock.patch.object(config, "CONFIG", self.root / "config")
        self.patch.start()
        config.ensure_dirs()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_default_changes_only_the_ai_section(self):
        path = config.CONFIG / "config.toml"
        path.write_text('[policy]\nprovider="leave this alone"\n[ai]\nprovider="claude-cli"\n')
        config.set_default_provider("codex-cli")
        data = config.load()
        self.assertEqual(data["ai"]["provider"], "codex-cli")
        self.assertEqual(data["policy"]["provider"], "leave this alone")

    def test_api_key_is_private_and_never_in_display_info(self):
        config.save_provider("my-api", {"type": "openai", "model": "test-model", "base_url": "https://api.example.org/v1"}, "test-private-key")
        path = config.CONFIG / "secrets/my-api"
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn("test-private-key", json.dumps(config.provider_info()))
        self.assertNotIn("test-private-key", (config.CONFIG / "config.toml").read_text())
        config.save_provider("my-api", {"type": "openai", "model": "changed-model"})
        self.assertEqual(path.read_text(), "test-private-key")

    def test_new_and_legacy_policies_protect_agent_credentials(self):
        from amadeus.policy import Policy
        policy = Policy({"policy": {"paths": {"deny": []}}})
        self.assertTrue(policy.path_denied(config.CONFIG / "secrets/my-api"))
        self.assertTrue(policy.path_denied(Path.home() / ".gemini/antigravity-cli/antigravity-oauth-token"))

    def test_invalid_provider_settings_leave_the_file_unchanged(self):
        path = config.CONFIG / "config.toml"
        old = path.read_bytes()
        for name, values in (("../escape", {"type": "openai", "model": "m"}),
                             ("safe", {"type": "openai", "model": ""}),
                             ("safe", {"type": "openai", "model": "m", "base_url": "file:///etc/passwd"})):
            with self.assertRaises(ValueError):
                config.save_provider(name, values, "not-saved")
            self.assertEqual(path.read_bytes(), old)

    def test_antigravity_uses_only_the_amadeus_mcp_bridge(self):
        script = self.root / "agy"
        captured = self.root / "captured.json"
        script.write_text('#!/usr/bin/python3\nimport json,sys,pathlib\na=sys.argv[1:]\ns=json.loads(a[a.index("--settings")+1])\nm=json.loads(pathlib.Path(".agents/mcp_config.json").read_text())\npathlib.Path('+repr(str(captured))+').write_text(json.dumps({"settings":s,"mcp":m,"args":a}))\nprint(json.dumps({"status":"SUCCESS","response":"hello"}))\n')
        script.chmod(0o755)
        emitted = []
        result = AntigravityCLI("antigravity-cli", {"command": str(script)}).run("system", [{"role": "user", "text": "hi"}], "s", lambda *event: emitted.append(event))
        self.assertEqual(result, "hello")
        data = json.loads(captured.read_text())
        self.assertEqual(data["settings"]["permissions"]["allow"], ["mcp(amadeus/*)"])
        self.assertIn("command(*)", data["settings"]["permissions"]["deny"])
        self.assertIn("write_file(*)", data["settings"]["permissions"]["deny"])
        self.assertEqual(data["mcp"]["mcpServers"]["amadeus"]["env"]["AMADEUS_SESSION"], "s")
        self.assertNotIn("--dangerously-skip-permissions", data["args"])
        self.assertTrue(any(e[0] == "_proc" for e in emitted))

