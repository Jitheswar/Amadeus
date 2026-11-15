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



class PreferencesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(config, "CONFIG", Path(self.tmp.name) / "config")
        self.patch.start()
        config.ensure_dirs()
        from amadeus import preferences
        from amadeus.policy import Policy
        self.p, self.policy = preferences, Policy(config.load())

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def decide(self, mode, cap, risk, args=None, root_on=False):
        return self.p.decision(self.policy, mode, cap, risk, args or {}, root_on)[0]

    def test_model_and_effort_are_saved_validated_and_displayed(self):
        self.p.save("claude-cli", "opus", "high")
        info = {p["name"]: p for p in config.provider_info()["providers"]}
        self.assertEqual((info["claude-cli"]["model"], info["claude-cli"]["effort"]), ("opus", "high"))
        self.assertIn("xhigh", info["claude-cli"]["effort_levels"])
        self.assertEqual(config.load()["providers"]["claude-cli"]["type"], "claude-cli")
        for name, model, effort in (("claude-cli", "opus", "ludicrous"), ("claude-cli", "a\nb", ""), ("openrouter", "", "low"), ("missing", "x", "")):
            with self.assertRaises(ValueError):
                self.p.save(name, model, effort)

    def test_a_request_overrides_without_changing_what_is_saved(self):
        cfg = config.load()
        result, chosen = self.p.request_config(cfg, "codex-cli", {"model": "other", "effort": "low", "mode": "auto"})
        self.assertEqual(result["providers"]["codex-cli"]["model"], "other")
        self.assertEqual(chosen, {"model": "other", "effort": "low", "mode": "auto"})
        self.assertNotIn("model", cfg["providers"]["codex-cli"])
        self.assertEqual(self.p.request_config(cfg, "codex-cli", None, "sandbox")[1]["mode"], "sandbox")
        with self.assertRaises(ValueError):
            self.p.request_config(cfg, "codex-cli", {"policy": "allow"})

    def test_full_access_needs_confirmation_each_time_and_is_never_saved(self):
        cfg = config.load()
        for options in ({"mode": "full"}, {"mode": "full", "confirm_full_access": "yes"}):
            with self.assertRaises(ValueError):
                self.p.request_config(cfg, "claude-cli", options)
        self.assertEqual(self.p.request_config(cfg, "claude-cli", {"mode": "full", "confirm_full_access": True})[1]["mode"], "full")
        with self.assertRaises(ValueError):
            self.p.save_mode("full")
        self.p.save_mode("auto")
        self.assertEqual(config.provider_info()["mode"], "auto")
        self.assertEqual(self.p.saved_mode({"ai": {"mode": "full"}}), "ask")

    def test_ask_mode_is_the_configured_policy(self):
        self.assertEqual(self.decide("ask", "fs.write", "modify", {"path": "~/notes.txt"}), "ask")
        self.assertEqual(self.decide("ask", "desktop.control", "modify"), "allow")
        self.policy.grant_session("fs.write", "modify")
        self.assertEqual(self.decide("ask", "fs.write", "modify", {"path": "~/notes.txt"}), "allow")

    def test_sandbox_mode_reads_but_never_changes_the_host(self):
        self.assertEqual(self.decide("sandbox", "fs.read", "read", {"path": "~/notes.txt"}), "allow")
        self.assertEqual(self.decide("sandbox", "shell.sandbox", "read", {"command": "ls"}), "allow")
        for cap, risk, args in (("fs.write", "modify", {"path": "~/notes.txt"}), ("desktop.control", "modify", {}),
                                ("shell.host", "destructive", {"host": True}), ("pkg.manage", "privileged", {})):
            self.assertEqual(self.decide("sandbox", cap, risk, args, root_on=True), "deny", cap)
        self.assertEqual(self.decide("sandbox", "fs.read", "read", {"path": "~/.ssh/id_ed25519"}), "deny")

    def test_auto_mode_allows_only_reversible_user_changes(self):
        self.assertEqual(self.decide("auto", "fs.write", "modify", {"path": "~/notes.txt"}), "allow")
        self.assertEqual(self.decide("auto", "desktop.config", "modify"), "allow")
        for cap in ("net.manage", "sys.manage", "ai.configure", "tasks.manage", "app.grant", "screen.interact"):
            self.assertEqual(self.decide("auto", cap, "modify"), "ask", cap)

    def test_no_mode_skips_the_core_prompts(self):
        own = str(config.CONFIG / "config.toml")
        for mode in ("auto", "full"):
            self.assertEqual(self.decide(mode, "fs.write", "destructive", {"path": "~/notes.txt"}), "ask")
            self.assertEqual(self.decide(mode, "pkg.manage", "privileged", root_on=True), "ask")
            self.assertEqual(self.decide(mode, "pkg.manage", "privileged"), "deny")
            self.assertEqual(self.decide(mode, "screen.observe", "modify"), "ask")
            self.assertEqual(self.decide(mode, "screen.interact", "modify"), "ask")
            self.assertEqual(self.decide(mode, "fs.write", "modify", {"path": own}), "ask")
            self.assertEqual(self.decide(mode, "fs.write", "modify", {"path": "~/.ssh/config"}), "deny")
        self.assertEqual(self.decide("full", "net.manage", "modify"), "allow")
        self.policy.rules["net.manage"] = "deny"
        self.assertEqual(self.decide("full", "net.manage", "modify"), "deny")


class GuideTest(unittest.TestCase):
    """Topic guides are pulled on demand; what they name must exist."""
    def setUp(self):
        from amadeus import discover, tools
        tools.load_all()
        self.discover, self.tools = discover, tools
        self.root = Path(__file__).resolve().parent.parent.parent

    def test_every_guide_is_indexed_and_readable(self):
        guides = self.discover.guides()
        skill = (config.SHARE / "skill/amadeus/SKILL.md").read_text()
        self.assertGreaterEqual(len(guides), 5)
        for name, about in guides.items():
            self.assertIn(f"({name}.md)", skill)
            self.assertTrue(about)
            self.assertLess(len(self.discover.guide(name).splitlines()), 80, f"{name} is too long to pull up on demand")
            self.assertIn(name, self.tools.REGISTRY["system_guide"]["description"])
        self.assertEqual(self.tools.REGISTRY["system_guide"]["fn"]({}, None), guides)
        self.assertEqual(self.tools.REGISTRY["system_guide"]["fn"]({"topic": "theming"}, None), self.discover.guide("theming"))
        with self.assertRaises(self.tools.ToolError):
            self.tools.REGISTRY["system_guide"]["fn"]({"topic": "../../config"}, None)

    def test_guides_name_only_commands_and_tools_that_exist(self):
        import re
        from amadeus import cli
        commands = {p.name for p in (self.root / "desktop/bin").iterdir()}
        for name in self.discover.guides():
            text = self.discover.guide(name)
            for token in set(re.findall(r"`([a-z_-]+(?: [a-z]+)?)[^`]*`", text)):
                first = token.split()[0]
                if first.startswith("amadeus-"):
                    self.assertIn(first, commands, f"{name}.md names {first}")
                elif "_" in first and first.islower():
                    self.assertIn(first, self.tools.REGISTRY, f"{name}.md names tool {first}")
                elif first == "ama" and " " in token:
                    self.assertIn("ama " + token.split()[1], cli.HELP, f"{name}.md names `{token}`")
