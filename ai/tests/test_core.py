#!/usr/bin/python3
"""Tests for the parts of the AI layer that the existing suite does not reach:
configuration, the sandbox command line, the agent loop, provider HTTP retries,
discovery, and the small CLI helpers. Run by ./build.sh check with the others."""
import json, os, stat, sys, tempfile, threading, time, unittest
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

if not os.environ.get("AMADEUS_CONFIG"):
    TMP = tempfile.mkdtemp(prefix="amadeus-core-test-")
    for key in ("CONFIG", "STATE", "DATA", "RUN"):
        os.environ[f"AMADEUS_{key}"] = f"{TMP}/{key.lower()}"
    os.environ["AMADEUS_PRIV_SOCK"] = f"{TMP}/priv.sock"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amadeus import config, policy, sandbox, agent, tools as T, cli, root, discover   # noqa: E402
from amadeus.providers import ProviderError                                                    # noqa: E402
from amadeus.providers import http as H                                                        # noqa: E402

config.ensure_dirs()


class ConfigTest(unittest.TestCase):
    def test_defaults_cover_the_layers(self):
        cfg = config.load()
        self.assertEqual(cfg["ai"]["provider"], "claude-cli")
        for name in ("claude-cli", "codex-cli", "anthropic", "openai", "openrouter", "local"):
            self.assertIn(name, cfg["providers"])
        self.assertEqual(cfg["policy"]["fs.write"], "ask")
        self.assertIn("~/.ssh", cfg["policy"]["paths"]["deny"])

    def test_user_config_merges_over_defaults(self):
        f = config.CONFIG / "config.toml"
        old = f.read_text() if f.exists() else None
        try:
            f.write_text('[ai]\nmax_steps = 7\n\n[providers.core-test]\ntype = "openai"\nmodel = "m"\n')
            cfg = config.load()
            self.assertEqual(cfg["ai"]["max_steps"], 7)
            self.assertIn("core-test", cfg["providers"])
            self.assertIn("claude-cli", cfg["providers"])
        finally:
            if old is None:
                f.unlink(missing_ok=True)
            else:
                f.write_text(old)

    def test_secret_precedence(self):
        pcfg = {"key_env": "AMADEUS_CORE_KEY"}
        os.environ["AMADEUS_CORE_KEY"] = "from-env"
        try:
            self.assertEqual(config.secret(pcfg, "core-key"), "from-env")
            secret_dir = config.CONFIG / "secrets"
            f = secret_dir / "core-key"
            f.write_text("from-file\n")
            os.environ.pop("AMADEUS_CORE_KEY")
            self.assertEqual(config.secret(pcfg, "core-key"), "from-file")
            self.assertEqual(config.secret({"key_cmd": "printf from-command"}, "other"), "from-command")
            self.assertEqual(config.secret({}, "missing"), "")
        finally:
            (config.CONFIG / "secrets/core-key").unlink(missing_ok=True)

    def test_private_directories_are_private(self):
        self.assertEqual(stat.S_IMODE(config.RUN.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((config.CONFIG / "secrets").stat().st_mode), 0o700)


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.p = policy.Policy(config.load())

    def test_protected_paths_are_denied_in_every_path_argument(self):
        for args in ({"path": "~/.ssh/id_ed25519"}, {"src": "~/.gnupg/a"}, {"dst": "~/.config/amadeus/secrets/key"}):
            self.assertEqual(self.p.decide("fs.write", "modify", args)[0], "deny", args)

    def test_free_workspace_is_allowed_but_elsewhere_is_asked(self):
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/.local/share/amadeus/workspace/a"})[0], "allow")
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/notes.txt"})[0], "ask")

    def test_reads_are_allowed_unless_the_policy_denies_them(self):
        self.assertEqual(self.p.decide("fs.read", "read", {"path": "~/notes.txt"})[0], "allow")
        self.p.rules["fs.read"] = "deny"
        self.assertEqual(self.p.decide("fs.read", "read", {"path": "~/notes.txt"})[0], "deny")

    def test_privileged_and_destructive_still_ask(self):
        self.assertEqual(self.p.decide("pkg.manage", "privileged", {})[0], "deny")
        self.assertEqual(self.p.decide("pkg.manage", "privileged", {}, root_on=True)[0], "ask")
        self.p.grant_session("desktop.control", "destructive")
        self.assertEqual(self.p.decide("desktop.control", "destructive", {})[0], "ask")

    def test_a_session_grant_does_not_cover_protected_paths(self):
        self.p.grant_session("fs.write", "modify")
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/.ssh/a"})[0], "deny")


class FilesTest(unittest.TestCase):
    def setUp(self):
        from amadeus.tools import files
        self.files = files
        self.old_session = getattr(files.current, "session", None)
        self.session = f"core-test-{os.getpid()}-{time.time_ns()}"
        files.current.session = self.session
        self.created = []

    def tearDown(self):
        self.files.current.session = self.old_session
        for p in self.created:
            Path(p).unlink(missing_ok=True)

    def home_file(self, name):
        p = Path.home() / f".amadeus-core-{name}-{os.getpid()}-{time.time_ns()}"
        self.created.append(p)
        return p

    def test_write_then_undo_restores_an_existing_file(self):
        p = self.home_file("existing")
        p.write_text("before")
        self.files.fs_write({"path": str(p), "content": "after"}, None)
        self.assertEqual(p.read_text(), "after")
        self.files.undo_session(self.session)
        self.assertEqual(p.read_text(), "before")

    def test_write_then_undo_removes_a_new_file(self):
        p = self.home_file("new")
        self.files.fs_write({"path": str(p), "content": "new"}, None)
        self.assertTrue(p.exists())
        self.files.undo_session(self.session)
        self.assertFalse(p.exists())

    def test_edit_requires_one_match_and_can_be_undone(self):
        p = self.home_file("edit")
        p.write_text("one and two\n")
        self.files.fs_edit({"path": str(p), "old": "two", "new": "three"}, None)
        self.assertEqual(p.read_text(), "one and three\n")
        with self.assertRaises(self.files.ToolError):
            self.files.fs_edit({"path": str(p), "old": "e", "new": "E"}, None)
        self.files.undo_session(self.session)
        self.assertEqual(p.read_text(), "one and two\n")

    def test_write_outside_home_is_refused(self):
        p = Path(tempfile.mkdtemp()) / "outside"
        with self.assertRaises(self.files.ToolError):
            self.files.fs_write({"path": str(p), "content": "x"}, None)
        self.assertFalse(p.exists())

    def test_two_changes_to_one_file_undo_to_the_original(self):
        p = self.home_file("twice")
        p.write_text("zero")
        self.files.fs_write({"path": str(p), "content": "one"}, None)
        self.files.fs_write({"path": str(p), "content": "two"}, None)
        self.assertEqual(self.files.changed_by(self.session), 2)
        self.files.undo_session(self.session)
        self.assertEqual(p.read_text(), "zero")
        self.assertEqual(self.files.changed_by(self.session), 0)


class SandboxTest(unittest.TestCase):
    def test_defaults_are_isolated(self):
        argv = sandbox.bwrap(["true"])
        self.assertIn("--unshare-all", argv)
        self.assertNotIn("--share-net", argv)
        self.assertIn("--tmpfs", argv)
        self.assertEqual(argv[-2:], ["--", "true"])
        self.assertIn("--clearenv", argv)

    def test_network_is_a_grant(self):
        self.assertIn("--share-net", sandbox.bwrap(["true"], net=True))

    def test_read_only_and_read_write_bindings(self):
        d = Path(tempfile.mkdtemp())
        argv = sandbox.bwrap(["true"], ro=[d], rw=[d])
        self.assertEqual(argv[argv.index(str(d), argv.index("--ro-bind")) - 1], "--ro-bind")
        self.assertEqual(argv[argv.index(str(d), argv.index("--bind")) - 1], "--bind")
        missing = d / "missing"
        self.assertNotIn(str(missing), sandbox.bwrap(["true"], ro=[missing]))

    def test_environment_and_working_directory(self):
        argv = sandbox.bwrap(["true"], env={"AMA_TEST": "yes"}, cwd="/tmp")
        self.assertIn("AMA_TEST", argv)
        self.assertIn("yes", argv)
        self.assertEqual(argv[argv.index("--chdir") + 1], "/tmp")

    def test_gui_gets_the_wayland_socket(self):
        old = sandbox.XRD
        old_display = os.environ.get("WAYLAND_DISPLAY")
        d = Path(tempfile.mkdtemp())
        (d / "wayland-9").touch()
        sandbox.XRD = str(d)
        os.environ["WAYLAND_DISPLAY"] = "wayland-9"
        try:
            argv = sandbox.bwrap(["true"], gui=True)
            self.assertIn(str(d / "wayland-9"), argv)
            self.assertIn("WAYLAND_DISPLAY", argv)
            self.assertIn("QT_QPA_PLATFORM", argv)
        finally:
            sandbox.XRD = old
            if old_display is None:
                os.environ.pop("WAYLAND_DISPLAY", None)
            else:
                os.environ["WAYLAND_DISPLAY"] = old_display


class FakeProvider:
    kind = "chat"

    def __init__(self, turns):
        self.name = "fake"
        self.turns = list(turns)
        self.calls = 0

    def chat(self, system, history, tools):
        self.calls += 1
        return self.turns.pop(0)


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        T.REGISTRY.setdefault("core_probe", {"name": "core_probe", "description": "probe",
                                             "schema": {"type": "object", "properties": {}, "required": []},
                                             "cap": "sys.read", "risk": "read", "fn": None})

    def test_render(self):
        self.assertEqual(agent.render("text"), "text")
        self.assertEqual(json.loads(agent.render({"a": 1})), {"a": 1})

    def test_text_only_turn(self):
        events = []
        p = FakeProvider([{"text": "hello", "calls": [], "raw": None, "stop": "end"}])
        history = [{"role": "user", "text": "hi"}]
        self.assertEqual(agent.run_chat(p, history, lambda n, a: ("", False), lambda k, d: events.append(k)), "hello")
        self.assertEqual(events, ["text"])
        self.assertEqual(p.calls, 1)

    def test_tool_results_go_back_into_history(self):
        p = FakeProvider([{"text": "", "calls": [{"id": "1", "name": "core_probe", "args": {}}], "raw": None, "stop": "tools"},
                          {"text": "done", "calls": [], "raw": None, "stop": "end"}])
        executed, events = [], []
        history = [{"role": "user", "text": "go"}]
        text = agent.run_chat(p, history, lambda n, a: (executed.append(n) or "ok", False), lambda k, d: events.append(k))
        self.assertEqual((text, executed), ("done", ["core_probe"]))
        self.assertEqual(history[-2]["results"][0]["content"], "ok")
        self.assertEqual(history[-3]["calls"][0]["name"], "core_probe")

    def test_a_stopped_task_runs_no_model_turn(self):
        p = FakeProvider([{"text": "should not be used", "calls": [], "raw": None, "stop": "end"}])
        self.assertEqual(agent.run_chat(p, [], lambda n, a: ("", False), lambda k, d: None, stopped=lambda: True), "[stopped]")
        self.assertEqual(p.calls, 0)

    def test_step_budget_stops_a_loop_that_never_finishes(self):
        turn = {"text": "", "calls": [{"id": "1", "name": "core_probe", "args": {}}], "raw": None, "stop": "tools"}
        p = FakeProvider([dict(turn) for _ in range(10)])
        events = []
        text = agent.run_chat(p, [], lambda n, a: ("", False), lambda k, d: events.append(k), max_steps=2)
        self.assertEqual(text, "[stopped: step budget reached]")
        self.assertEqual(p.calls, 2)
        self.assertIn("text", events)

    def test_system_prompt_points_at_discovery(self):
        prompt = agent.system_prompt()
        self.assertIn("system_discover", prompt)
        self.assertIn("Hyprland", prompt)


class HttpTest(unittest.TestCase):
    class Server(BaseHTTPRequestHandler):
        counts = Counter()

        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("content-length", "0")))
            HttpTest.Server.counts[self.path] += 1
            if self.path == "/retry" and HttpTest.Server.counts[self.path] < 3:
                code, body = 500, b"try again"
            elif self.path == "/bad":
                code, body = 404, b"not here"
            else:
                code, body = 200, json.dumps({"ok": True}).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), cls.Server)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.old_sleep = H.time.sleep
        H.time.sleep = lambda seconds: None

    @classmethod
    def tearDownClass(cls):
        H.time.sleep = cls.old_sleep
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.Server.counts.clear()

    def test_a_server_error_is_retried(self):
        self.assertEqual(H.post_json(self.url + "/retry", {"a": 1}, {}), {"ok": True})
        self.assertEqual(self.Server.counts["/retry"], 3)

    def test_a_client_error_is_not_retried(self):
        with self.assertRaises(ProviderError) as e:
            H.post_json(self.url + "/bad", {}, {})
        self.assertIn("HTTP 404", str(e.exception))
        self.assertEqual(self.Server.counts["/bad"], 1)

    def test_an_unreachable_server_is_a_clear_error(self):
        with self.assertRaises(ProviderError) as e:
            H.post_json("http://127.0.0.1:1/none", {}, {}, retries=0)
        self.assertIn("cannot reach", str(e.exception))


class DiscoverTest(unittest.TestCase):
    def test_the_map_comes_from_the_package_database_and_the_tool_table(self):
        d = Path(tempfile.mkdtemp())
        tool = d / "usr/bin/core-tool"
        tool.parent.mkdir(parents=True)
        tool.write_text("#!/bin/bash\n# Does a core thing.\necho\n")
        pacman = d / "pacman"
        pacman.write_text(f"""#!/bin/bash
case "$1" in
  -Qlq) echo {tool} ; echo /usr/share/amadeus-os/theme.json ;;
  -Q) echo "$2 0.1.0" ;;
esac
""")
        pacman.chmod(0o755)
        old_path = os.environ["PATH"]
        os.environ["PATH"] = f"{d}:{old_path}"
        try:
            m = discover.build()
        finally:
            os.environ["PATH"] = old_path
        self.assertIn("/usr/share/amadeus-os/theme.json", m["defaults_shipped_with_the_system"])
        self.assertEqual(m["system"]["packages"]["amadeus"], "0.1.0")
        self.assertIn("tools", m)
        self.assertTrue(any(t["name"] == "sys_status" for t in m["tools"]))
        self.assertIn("policy", m)
        self.assertIn("explore_further", m)


class DaemonRulesTest(unittest.TestCase):
    def test_an_apps_change_is_asked_even_when_policy_allows_it(self):
        from amadeus.daemon import Daemon
        d = Daemon()
        asked = []
        d.ask_user = lambda *a: (asked.append(a[2]) or "no")
        out, err = d.execute("desktop_clipboard_set", {"text": "x"}, session="core-app", origin="app:test",
                             allowed={"desktop_clipboard_set"})
        self.assertTrue(err)
        self.assertIn("declined", out)
        self.assertEqual(asked, ["desktop_clipboard_set"])

    def test_reload_keeps_session_grants(self):
        from amadeus.daemon import Daemon
        d = Daemon()
        d.policy.grant_session("fs.write", "modify")
        d.reload()
        self.assertIn("fs.write", d.policy.session_grants)


class CliTest(unittest.TestCase):
    def test_short(self):
        self.assertEqual(cli.short({"a": 1}), '{"a": 1}')
        self.assertTrue(cli.short("x" * 200, 20).endswith("…"))

    def test_help_names_the_ways_in(self):
        for text in ("ama status", "ama discover", "ama panel", "daemon | mcp", "ama root on"):
            self.assertIn(text, cli.HELP)


class RootGuardTest(unittest.TestCase):
    def test_no_socket_means_off(self):
        old = config.PRIV_SOCK
        config.PRIV_SOCK = Path(tempfile.mkdtemp()) / "missing.sock"
        try:
            self.assertFalse(root.enabled())
            r = root.call("info")
            self.assertFalse(r["ok"])
            self.assertIn("root mode is off", r["error"])
        finally:
            config.PRIV_SOCK = old


if __name__ == "__main__":
    unittest.main(verbosity=2)
