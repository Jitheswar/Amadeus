"""Run with: python3 -m unittest discover -s tests -v
Uses throwaway directories; never touches the real config, apps or audit log."""
import json, os, subprocess, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

TMP = tempfile.mkdtemp(prefix="amadeus-test-")
for k in ("CONFIG", "STATE", "DATA", "RUN"):
    os.environ[f"AMADEUS_{k}"] = f"{TMP}/{k.lower()}"
os.environ["AMADEUS_PRIV_SOCK"] = f"{TMP}/priv.sock"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from amadeus import config, audit, policy, apps, sandbox, agent, providers, root, tools as T   # noqa: E402
from amadeus.daemon import Daemon                                                              # noqa: E402

config.ensure_dirs()


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.p = policy.Policy(config.load())

    def test_reads_allowed_writes_ask(self):
        self.assertEqual(self.p.decide("fs.read", "read", {"path": "~/notes.txt"})[0], "allow")
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/notes.txt"})[0], "ask")

    def test_protected_paths_denied_even_for_reads(self):
        for path in ("~/.ssh/id_ed25519", "~/.gnupg/x", "~/.config/amadeus/secrets/anthropic", "~/.claude/settings.json"):
            self.assertEqual(self.p.decide("fs.read", "read", {"path": path})[0], "deny", path)

    def test_symlink_and_dotdot_cannot_escape_protection(self):
        self.assertEqual(self.p.decide("fs.read", "read", {"path": "~/Documents/../.ssh/config"})[0], "deny")

    def test_privileged_needs_root_mode_then_still_asks(self):
        self.assertEqual(self.p.decide("pkg.manage", "privileged", {}, root_on=False)[0], "deny")
        self.assertEqual(self.p.decide("pkg.manage", "privileged", {}, root_on=True)[0], "ask")

    def test_destructive_always_asks_and_is_never_remembered(self):
        self.p.grant_session("desktop.control", "destructive")
        self.assertEqual(self.p.decide("desktop.control", "destructive", {})[0], "ask")

    def test_session_grant_applies_to_modify(self):
        self.p.grant_session("fs.write", "modify")
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/a"})[0], "allow")
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/.ssh/a"})[0], "deny")

    def test_reads_never_prompt_unless_denied(self):
        self.assertEqual(self.p.decide("sys.manage", "read", {})[0], "allow")
        self.p.rules["sys.manage"] = "deny"
        self.assertEqual(self.p.decide("sys.manage", "read", {})[0], "deny")

    def test_free_workspace(self):
        self.assertEqual(self.p.decide("fs.write", "modify", {"path": "~/.local/share/amadeus/workspace/x"})[0], "allow")


class DesktopTest(unittest.TestCase):
    def test_old_bar_layout_retains_the_display_control_without_a_write(self):
        from amadeus.tools import desktop
        f = Path(TMP) / "old-bar.json"
        original = '{"left": [], "center": [], "right": ["brightness", "volume"]}'
        f.write_text(original)
        with mock.patch.object(desktop, "BAR_FILE", f):
            state = desktop.desktop_bar({}, None)
        self.assertEqual(state["layout"]["right"], ["display", "volume"])
        self.assertEqual(f.read_text(), original)

    def test_focused_window_is_mapped_for_the_panel(self):
        from amadeus.tools import desktop
        with mock.patch.object(desktop, "hj", return_value={"address": "0xabc", "class": "foot", "title": "t" * 200}):
            self.assertEqual(desktop.focused_window(), {"id": "0xabc", "app": "foot", "title": "t" * 120})
        with mock.patch.object(desktop, "hj", return_value={"address": "0x1"}):
            self.assertEqual(desktop.focused_window(), {"id": "0x1", "app": "", "title": ""})
        with mock.patch.object(desktop, "hj", return_value={}):
            self.assertIsNone(desktop.focused_window())


class AuditTest(unittest.TestCase):
    def test_scalar_json_is_reported_as_a_corrupt_record(self):
        f = config.STATE / "audit.jsonl"
        for value in (None, True, 42, "text", [1, 2], {}):
            with self.subTest(value=value):
                f.unlink(missing_ok=True)
                audit.record("action", tool="a")
                with f.open("a") as out:
                    out.write(json.dumps(value) + "\n")
                self.assertEqual(audit.verify(), (False, 2, 2))
        f.unlink()

    def test_chain_detects_tampering_and_redacts_secrets(self):
        f = config.STATE / "audit.jsonl"
        f.unlink(missing_ok=True)
        audit.record("action", tool="a", args={"api_key": "sk-secret", "path": "/x"})
        audit.record("action", tool="b")
        audit.record("action", tool="c")
        self.assertEqual(audit.verify()[:2], (True, 3))
        self.assertNotIn("sk-secret", f.read_text())
        lines = f.read_text().splitlines()
        lines[1] = lines[1].replace('"b"', '"x"')
        f.write_text("\n".join(lines) + "\n")
        ok, _, bad = audit.verify()
        self.assertFalse(ok)
        self.assertEqual(bad, 2)
        f.unlink()

    def test_large_record_does_not_break_the_chain(self):
        f = config.STATE / "audit.jsonl"
        f.unlink(missing_ok=True)
        big = audit.record("action", tool="big", args={"files": [{"path": "x" * 2000} for _ in range(40)]})
        self.assertGreater(len(json.dumps(big)), 65536)
        nxt = audit.record("action", tool="after")
        self.assertEqual(nxt["prev"], big["hash"])
        self.assertEqual(audit.verify()[:2], (True, 2))
    def test_read_skips_malformed_records(self):
        f = config.STATE / "audit.jsonl"
        f.unlink(missing_ok=True)
        audit.record("action", tool="a")
        with open(f, "a") as fh:
            fh.write("not json\n")
            fh.write("[1, 2]\n")
            fh.write('{"no": "ts"}\n')
        recs = audit.read(10)
        self.assertEqual([r["tool"] for r in recs], ["a"])
        self.assertEqual(audit.read(0), [])
    def test_malformed_line_is_reported_not_raised(self):
        f = config.STATE / "audit.jsonl"
        f.unlink(missing_ok=True)
        audit.record("action", tool="a")
        f.write_text(f.read_text() + "not json\n")
        self.assertEqual(audit.verify(), (False, 2, 2))
    def test_log_is_private_even_if_it_already_existed(self):
        f = config.STATE / "audit.jsonl"
        f.unlink(missing_ok=True)
        f.write_text("")
        f.chmod(0o644)
        audit.record("action", tool="a")
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        f.unlink()


QML = 'import QtQuick\nimport Quickshell\nimport "Amadeus"\nAppWindow { title: "t"; Txt { text: "%s" } }\n'


class AppsTest(unittest.TestCase):
    def test_git_failure_restores_the_committed_version(self):
        real_git = apps._git
        for command in ("add", "commit"):
            app_id = "fail-" + command
            apps.save(app_id, "Fail", "", {"shell.qml": QML % "old"})
            def failing_git(d, *args):
                if args[0] == command:
                    return subprocess.CompletedProcess(args, 1, "", "simulated git failure")
                return real_git(d, *args)
            with mock.patch.object(apps, "_git", side_effect=failing_git):
                with self.assertRaisesRegex(apps.AppError, "simulated git failure"):
                    apps.save(app_id, files={"shell.qml": QML % "new", "extra.js": "var x = 1"})
            d = apps.app_dir(app_id)
            self.assertEqual(apps.manifest(app_id)["version"], 1)
            self.assertIn("old", (d / "shell.qml").read_text())
            self.assertFalse((d / "extra.js").exists())
            self.assertEqual(real_git(d, "status", "--porcelain").stdout, "")
            self.assertEqual(len(apps.history(app_id)), 1)

    def test_rollback_removes_the_destination_of_a_rename(self):
        apps.save("rename", "Rename", "", {"shell.qml": QML % "one", "old.js": "var a = 1\n"})
        apps.save("rename", files={"old.js": None, "new.js": "var a = 1\n"})
        apps.rollback("rename")
        d = apps.app_dir("rename")
        self.assertTrue((d / "old.js").exists())
        self.assertFalse((d / "new.js").exists())

    def test_lifecycle_update_rollback(self):
        m = apps.save("demo", "Demo", "d", {"shell.qml": QML % "one"})
        self.assertEqual((m["version"], m["permissions"]), (1, apps.normalise(None)))
        m = apps.save("demo", files={"extra.js": "var a = 1\n"}, note="add helper")
        self.assertEqual(m["version"], 2)
        self.assertIn("one", (apps.app_dir("demo") / "shell.qml").read_text())      # untouched file survives
        apps.save("demo", files={"shell.qml": QML % "two"})
        m = apps.rollback("demo")
        self.assertEqual(m["version"], 4)
        self.assertIn("one", (apps.app_dir("demo") / "shell.qml").read_text())
        self.assertEqual(len(apps.history("demo")), 4)

    def test_app_name_cannot_inject_desktop_entry_fields(self):
        apps.save("inject", "Evil\nExec=touch /tmp/pwned", "d", {"shell.qml": QML % "x"})
        with tempfile.TemporaryDirectory(prefix="amadeus-home-") as tmp:
            home = Path(tmp)
            env = {k: v for k, v in os.environ.items() if k != "AMADEUS_DATA"}
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(apps.Path, "home", return_value=home):
                apps._desktop_entry(apps.manifest("inject"))
            text = (home / ".local/share/applications/amadeus-inject.desktop").read_text()
        self.assertEqual([l for l in text.splitlines() if l.startswith("Exec=")], ["Exec=ama app run inject"])
        self.assertIn("Name=Evil Exec=touch /tmp/pwned", text)
    def test_rollback_removes_files_added_later(self):
        apps.save("roll", "Roll", "", {"shell.qml": QML % "one"})
        apps.save("roll", files={"extra.js": "var a = 1\n"})
        m = apps.rollback("roll")
        self.assertEqual(m["version"], 3)
        self.assertIn("one", (apps.app_dir("roll") / "shell.qml").read_text())
        self.assertFalse((apps.app_dir("roll") / "extra.js").exists())

    def test_broken_update_is_rejected_and_old_version_kept(self):
        apps.save("keep", "Keep", "", {"shell.qml": QML % "good"})
        with self.assertRaises(apps.AppError):
            apps.save("keep", files={"shell.qml": "import QtQuick\nItem { this is not qml"})
        self.assertIn("good", (apps.app_dir("keep") / "shell.qml").read_text())

    def test_failed_new_app_leaves_nothing(self):
        with self.assertRaises(AttributeError):
            apps.save("txnew", "Tx", "", "shell.qml")
        self.assertFalse(apps.app_dir("txnew").exists())

    def test_failed_update_keeps_the_previous_version(self):
        apps.save("tx", "Tx", "", {"shell.qml": QML % "one"})
        with self.assertRaises(AttributeError):
            apps.save("tx", files="shell.qml")
        self.assertIn("one", (apps.app_dir("tx") / "shell.qml").read_text())
        self.assertEqual(apps.manifest("tx")["version"], 1)

    def test_file_names_cannot_escape(self):
        for bad in ("../evil.qml", "/etc/x.qml", "manifest.json", "Amadeus/Theme.qml", ".git/config", "a.sh"):
            with self.assertRaises(apps.AppError, msg=bad):
                apps.save("esc", "Esc", "", {"shell.qml": QML % "x", bad: "x"})
            self.assertFalse(apps.app_dir("esc").exists())

    def test_permission_escalation_detection(self):
        none = apps.normalise(None)
        self.assertFalse(apps.exceeds(none, none))
        self.assertTrue(apps.exceeds(apps.normalise({"network": True}), none))
        self.assertTrue(apps.exceeds(apps.normalise({"tools": ["sys_status"]}), none))
        rw = apps.normalise({"files": [{"path": "~/Documents", "mode": "rw"}]})
        ro = apps.normalise({"files": [{"path": "~/Documents", "mode": "ro"}]})
        self.assertTrue(apps.exceeds(rw, ro))
        self.assertFalse(apps.exceeds(ro, rw))
        with self.assertRaises(apps.AppError):
            apps.normalise({"root": True})

    def test_sandbox_command_reflects_manifest(self):
        apps.save("net0", "N", "", {"shell.qml": QML % "x"})
        cmd = apps.command("net0")
        self.assertIn("--unshare-all", cmd)
        self.assertNotIn("--share-net", cmd)
        self.assertFalse(any("nvidia" in c for c in cmd))
        apps.save("net1", "N", "", {"shell.qml": QML % "x"}, {"network": True, "files": [{"path": TMP, "mode": "ro"}]})
        cmd = apps.command("net1")
        self.assertIn("--share-net", cmd)
        i = cmd.index(TMP)
        self.assertEqual(cmd[i - 1], "--ro-bind")


class DesktopConfigTest(unittest.TestCase):
    def test_failed_verifier_restores_the_managed_file(self):
        from amadeus.tools import desktop
        d = Path(TMP) / "hypr-config"
        d.mkdir(parents=True, exist_ok=True)
        managed, main = d / "amadeus.lua", d / "hyprland.lua"
        managed.write_text("-- old\n")
        main.write_text("-- main\n")
        with mock.patch.object(desktop, "MANAGED", managed), \
             mock.patch.object(desktop, "HYPR_USER", d), \
             mock.patch.object(desktop, "MAIN", main), \
             mock.patch.object(desktop.shutil, "which", return_value="/usr/bin/Hyprland"), \
             mock.patch.object(desktop.subprocess, "run", side_effect=subprocess.TimeoutExpired("Hyprland", 20)):
            with self.assertRaises(desktop.ToolError):
                desktop._managed_save({"binds": {}, "extra": "-- new\n"})
        self.assertEqual(managed.read_text(), "-- old\n")


class SandboxTest(unittest.TestCase):
    def run_in(self, script, **kw):
        return subprocess.run(sandbox.bwrap(["bash", "-c", script], **kw), capture_output=True, text=True, timeout=30)

    def test_isolation(self):
        secret = Path.home() / ".amadeus-sandbox-probe"
        secret.write_text("x")
        try:
            p = self.run_in(f"test -e {secret} && echo LEAK; touch /usr/probe 2>/dev/null && echo WRITABLE; "
                            "ls /run/user/*/bus 2>/dev/null && echo DBUS; cat /proc/1/comm")
            self.assertNotIn("LEAK", p.stdout)
            self.assertNotIn("WRITABLE", p.stdout)
            self.assertNotIn("DBUS", p.stdout)
            self.assertIn("bwrap", p.stdout)        # own PID namespace
        finally:
            secret.unlink()

    def test_no_network_by_default(self):
        p = self.run_in("ls /sys/class/net 2>/dev/null; cat /proc/net/dev | tail -n +3 | cut -d: -f1")
        self.assertEqual([l.strip() for l in p.stdout.split() if l.strip() != "lo"], [])

    def test_granted_dir_is_writable(self):
        d = Path(TMP) / "grant"
        self.run_in(f"echo hi > {d}/f", rw=[d])
        self.assertEqual((d / "f").read_text(), "hi\n")


class Mock(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        Mock.seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        had_result = any(m["role"] == "tool" or (isinstance(m.get("content"), list) and any(b.get("type") == "tool_result" for b in m["content"])) for m in body["messages"])
        if self.path == "/v1/messages":
            rep = ({"stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}]} if had_result else
                   {"stop_reason": "tool_use", "content": [{"type": "thinking", "thinking": "", "signature": "sig"},
                                                           {"type": "tool_use", "id": "tu_1", "name": "echo", "input": {"v": 7}}]})
        else:
            rep = ({"choices": [{"message": {"content": "done"}}]} if had_result else
                   {"choices": [{"message": {"content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "echo", "arguments": '{"v": 7}'}}]}}]})
        data = json.dumps(rep).encode()
        self.send_response(200)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class ProviderTest(unittest.TestCase):
    def test_retry_after_invalid_numbers_use_backoff(self):
        from amadeus.providers.http import _retry_delay
        for value in ("inf", "-inf", "nan", "not a date", ""):
            self.assertEqual(_retry_delay(value, 2), 4)
        self.assertEqual(_retry_delay("0.25", 2), 0.25)
        self.assertEqual(_retry_delay("-1", 2), 0)

    def test_claude_error_reads_a_bounded_stderr_tail(self):
        from amadeus.providers.cli import ClaudeCLI
        from amadeus.providers import ProviderError
        fake = Path(TMP) / "fake-claude-error"
        fake.write_text("#!/usr/bin/env python3\nimport sys\nsys.stderr.write('x' * 200000 + 'tail-error')\nsys.exit(1)\n")
        fake.chmod(0o755)
        with self.assertRaises(ProviderError) as error:
            ClaudeCLI("claude-cli", {"command": str(fake)}).run("s", [{"role": "user", "text": "hi"}], "s", lambda *a: None)
        self.assertTrue(str(error.exception).endswith("tail-error"))
        self.assertLess(len(str(error.exception)), 550)

    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Mock)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def loop(self, prov):
        Mock.seen.clear()
        calls = []
        hist = [{"role": "user", "text": "go"}]
        T.REGISTRY.setdefault("echo", {"name": "echo", "description": "echo", "schema": {"type": "object", "properties": {}, "required": []}, "cap": "sys.read", "risk": "read", "fn": None})
        text = agent.run_chat(prov, hist, lambda n, a: (calls.append((n, a)) or "7", False), lambda *a: None)
        self.assertEqual((text, calls), ("done", [("echo", {"v": 7})]))
        return Mock.seen

    def test_anthropic_tool_loop(self):
        os.environ["T_KEY"] = "k"
        from amadeus.providers.anthropic import Anthropic
        seen = self.loop(Anthropic("anthropic", {"base_url": self.url, "key_env": "T_KEY", "model": "claude-opus-5-5"}))
        path, headers, body = seen[1]
        self.assertEqual(headers["x-api-key"], "k")
        self.assertEqual(body["thinking"], {"type": "adaptive"})
        self.assertNotIn("fallbacks", body)                                   # only sent to the official endpoint
        self.assertEqual(body["messages"][1]["content"][0]["type"], "thinking")   # thinking replayed unchanged
        self.assertEqual(body["messages"][2]["content"][0], {"type": "tool_result", "tool_use_id": "tu_1", "content": "7", "is_error": False})

    def test_truncated_tool_call_is_not_replayed(self):
        os.environ["T_KEY"] = "k"
        from amadeus.providers.anthropic import Anthropic
        p = Anthropic("anthropic", {"key_env": "T_KEY"})
        reply = {"stop_reason": "max_tokens", "content": [
            {"type": "text", "text": "partial"},
            {"type": "tool_use", "id": "tu_1", "name": "echo", "input": {}}]}
        with mock.patch("amadeus.providers.anthropic.post_json", return_value=reply):
            turn = p.chat("s", [{"role": "user", "text": "go"}], [])
        self.assertEqual(turn["calls"], [])
        self.assertEqual([b["type"] for b in turn["raw"]], ["text"])
        hist = [{"role": "user", "text": "go"},
                {"role": "assistant", "text": turn["text"], "calls": turn["calls"], "raw": turn["raw"], "raw_from": "anthropic"}]
        self.assertEqual([b["type"] for b in p._messages(hist)[1]["content"]], ["text"])

    def test_openai_compatible_tool_loop(self):
        from amadeus.providers.openai import OpenAICompat
        seen = self.loop(OpenAICompat("local", {"base_url": self.url + "/v1", "model": "m"}))
        body = seen[1][2]
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][-1], {"role": "tool", "tool_call_id": "c1", "content": "7"})

    def test_switching_provider_mid_conversation(self):
        from amadeus.providers.anthropic import Anthropic
        from amadeus.providers.openai import OpenAICompat
        hist = [{"role": "user", "text": "hi"},
                {"role": "assistant", "text": "", "calls": [{"id": "x", "name": "echo", "args": {}}], "raw": [{"type": "thinking", "thinking": "", "signature": "s"}], "raw_from": "anthropic"},
                {"role": "tool", "results": [{"id": "x", "name": "echo", "content": "ok"}]}]
        other = Anthropic("other", {"base_url": self.url})._messages(hist)
        self.assertEqual(other[1]["content"][0]["type"], "tool_use")           # foreign thinking blocks are not replayed
        self.assertEqual(OpenAICompat("o", {"model": "m"})._messages(hist)[1]["tool_calls"][0]["id"], "x")

    def test_missing_key_is_a_clear_error(self):
        from amadeus.providers.anthropic import Anthropic
        with self.assertRaises(providers.ProviderError):
            Anthropic("nokey", {"key_env": "AMADEUS_NO_SUCH_KEY"}).chat("s", [{"role": "user", "text": "x"}], [])

    def test_claude_cli_does_not_deadlock_on_stderr(self):
        """Claude Code can log more than a pipe buffer to stderr. If it is not drained
        while stdout is read, the child blocks and the provider never returns."""
        fake = Path(TMP) / "fake-claude"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json, sys\n"
            "sys.stderr.write('x' * 200000)\n"
            "sys.stderr.flush()\n"
            "print(json.dumps({'type': 'result', 'result': 'done'}))\n"
        )
        fake.chmod(0o755)
        code = ("import sys\n"
                f"sys.path.insert(0, {str(ROOT)!r})\n"
                "from amadeus.providers.cli import ClaudeCLI\n"
                f"print(ClaudeCLI('claude-cli', {{'command': {str(fake)!r}}}).run("
                "'s', [{'role': 'user', 'text': 'hi'}], 'sess', lambda *a: None))\n")
        p = T.sh([sys.executable, "-c", code], timeout=15, env=dict(os.environ, PYTHONPATH=str(ROOT)))
        self.assertEqual(p.returncode, 0, p.stderr[-1000:])
        self.assertEqual(p.stdout.strip(), "done")


class CliTest(unittest.TestCase):
    def test_permission_failure_keeps_the_previous_secret(self):
        from amadeus import cli
        f = config.CONFIG / "secrets" / "keep-provider"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("keep-this-secret")
        with mock.patch("getpass.getpass", return_value="replacement"), mock.patch("os.fchmod", side_effect=PermissionError("not owner")):
            with self.assertRaises(PermissionError):
                cli.provider_cmd(None, ["key", "keep-provider"])
        self.assertEqual(f.read_text(), "keep-this-secret")
        f.unlink()

    def test_secret_file_is_private_even_if_it_already_existed(self):
        from amadeus import cli
        f = config.CONFIG / "secrets" / "test-provider"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("old")
        f.chmod(0o644)
        with mock.patch("getpass.getpass", return_value="new-key"), mock.patch("builtins.print"):
            cli.provider_cmd(None, ["key", "test-provider"])
        self.assertEqual(f.stat().st_mode & 0o777, 0o600)
        self.assertEqual(f.read_text(), "new-key")
        f.unlink()
    def test_retry_after_http_date_is_understood(self):
        from amadeus.providers.http import post_json
        hits = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers.get("content-length", 0)))
                hits.append(1)
                if len(hits) == 1:
                    self.send_response(429)
                    self.send_header("retry-after", "Wed, 21 Oct 2015 07:28:00 GMT")
                    self.send_header("content-length", "0")
                    self.end_headers()
                else:
                    data = b'{"ok": true}'
                    self.send_response(200)
                    self.send_header("content-length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            self.assertEqual(post_json(f"http://127.0.0.1:{srv.server_port}/x", {}, {}), {"ok": True})
        finally:
            srv.shutdown()
            srv.server_close()
        self.assertEqual(len(hits), 2)


class DaemonTest(unittest.TestCase):
    def test_an_active_session_rejects_a_second_request(self):
        d = Daemon()
        entered, release = threading.Event(), threading.Event()
        errors = []
        class Blocking:
            kind = "agent"
            def run(self, *args):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("test did not release the provider")
                return "done"
        def first():
            try:
                d.ask(mock.Mock(), 1, "first", session="shared")
            except Exception as error:
                errors.append(error)
        with mock.patch("amadeus.daemon.providers.make", return_value=Blocking()):
            thread = threading.Thread(target=first)
            thread.start()
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(RuntimeError, "still running"):
                    d.ask(mock.Mock(), 2, "second", session="shared")
            finally:
                release.set()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual([m["text"] for m in d.sessions["shared"]["history"]], ["first", "done"])
        self.assertFalse(d.sessions["shared"]["running"])

    def test_session_reservation_is_protected_by_the_daemon_lock(self):
        d = Daemon()
        class Guarded(dict):
            def get(inner, key, *args):
                if key == "running":
                    self.assertTrue(d.lock.locked())
                return super().get(key, *args)
        d.sessions["locked"] = Guarded(history=[], conn=None, cancel=threading.Event(), proc=None)
        with mock.patch("amadeus.daemon.providers.make", side_effect=RuntimeError("unavailable")):
            with self.assertRaisesRegex(RuntimeError, "unavailable"):
                d.ask(mock.Mock(), 1, "hello", session="locked")
        self.assertEqual(d.sessions["locked"]["history"], [])


    def test_a_request_mode_reaches_its_tool_calls_and_ends_with_it(self):
        d = Daemon()
        asked, seen = [], {}
        d.ask_user = lambda *a: (asked.append(a[2]) or "no")
        target = Path.home() / ".amadeus-test-mode"
        class Agent:
            kind = "agent"
            def run(self, system, history, session, emit):
                seen["mode"] = d.sessions[session]["mode"]
                seen["result"] = d.execute("fs_write", {"path": str(target), "content": "x"}, session=session)
                return "done"
        def made(name, cfg):
            seen["effort"] = cfg["providers"][name].get("effort")
            return Agent()
        with mock.patch("amadeus.daemon.providers.make", side_effect=made):
            with self.assertRaisesRegex(ValueError, "explicit confirmation"):
                d.ask(mock.Mock(), 1, "write", session="modes", options={"mode": "full"})
            self.assertNotIn("modes", d.sessions)
            d.ask(mock.Mock(), 1, "write", session="modes", options={"mode": "sandbox", "effort": "high"})
            self.assertEqual((seen["mode"], seen["effort"], seen["result"][1], asked), ("sandbox", "high", True, []))
            d.ask(mock.Mock(), 1, "write", session="modes", options={"mode": "full", "confirm_full_access": True})
            self.assertEqual((seen["mode"], seen["result"][1], asked), ("full", False, []))
            d.ask(mock.Mock(), 1, "write", session="modes")
            self.assertEqual((seen["mode"], seen["result"][1], asked), ("ask", True, ["fs_write"]))
        self.assertNotIn("mode", d.sessions["modes"])
        self.assertNotIn("effort", d.cfg["providers"][d.cfg["ai"]["provider"]])
        target.unlink(missing_ok=True)

    def test_unexpected_cli_failure_preserves_its_request(self):
        d = Daemon()
        provider = mock.Mock(kind="agent")
        provider.run.side_effect = OSError("output stream failed after tools ran")
        with mock.patch("amadeus.daemon.providers.make", return_value=provider):
            with self.assertRaises(OSError):
                d.ask(mock.Mock(), 1, "keep my request", session="cli-partial")
        self.assertEqual(d.sessions["cli-partial"]["history"][0]["text"], "keep my request")
        self.assertFalse(d.sessions["cli-partial"]["running"])

    @classmethod
    def setUpClass(cls):
        cls.d = Daemon()
        cls.asked = []
        cls.answer = "no"
        cls.d.ask_user = lambda *a: (cls.asked.append(a[2]) or cls.answer)

    def test_unknown_tool_and_bad_args(self):
        self.assertTrue(self.d.execute("nope", {})[1])
        self.assertTrue(self.d.execute("fs_read", {})[1])
        self.assertTrue(self.d.execute("fs_read", "x")[1])

    def test_failed_audit_does_not_wedge_the_session(self):
        d = Daemon()
        with mock.patch("amadeus.daemon.audit.record", side_effect=OSError("disk full")) as record:
            with self.assertRaises(OSError):
                d.ask(mock.Mock(), 1, "hello", session="s-audit")
        record.assert_called_once_with("request", session="s-audit", provider=d.cfg["ai"]["provider"], prompt="hello", model="", effort="", mode="ask")
        self.assertFalse(d.sessions["s-audit"]["running"])
        self.assertEqual(d.sessions["s-audit"]["history"], [])

    def test_denied_write_does_not_happen(self):
        target = Path.home() / ".amadeus-test-write"
        DaemonTest.answer = "no"
        out, err = self.d.execute("fs_write", {"path": str(target), "content": "x"})
        self.assertTrue(err)
        self.assertFalse(target.exists())

    def test_approved_write_then_undo(self):
        from amadeus.tools import files
        target = Path.home() / ".amadeus-test-write2"
        target.write_text("before")
        try:
            DaemonTest.answer = "yes"
            self.assertFalse(self.d.execute("fs_write", {"path": str(target), "content": "after"})[1])
            self.assertEqual(target.read_text(), "after")
            files.undo_last()
            self.assertEqual(target.read_text(), "before")
        finally:
            target.unlink(missing_ok=True)

    def test_host_shell_always_asks_sandbox_does_not(self):
        DaemonTest.asked.clear()
        DaemonTest.answer = "no"
        self.assertTrue(self.d.execute("shell_run", {"command": "true", "host": True})[1])
        self.assertEqual(DaemonTest.asked, ["shell_run"])
        out, err = self.d.execute("shell_run", {"command": "echo sandboxed"})
        self.assertIn("sandboxed", out)
        self.assertEqual(len(DaemonTest.asked), 1)

    def test_privileged_tools_refused_while_root_mode_off(self):
        self.assertFalse(root.enabled())
        for name, args in (("pkg_manage", {"action": "install", "packages": ["x"]}), ("sys_root_exec", {"argv": ["id"]}),
                           ("sys_config_write", {"path": "/etc/x", "content": ""}), ("sys_service_control", {"unit": "sshd", "action": "start", "scope": "system"})):
            out, err = self.d.execute(name, args)
            self.assertTrue(err and "root mode" in out, name)

    def test_app_can_only_call_declared_tools(self):
        out, err = self.d.execute("fs_read", {"path": "/etc/hostname"}, origin="app:x", allowed={"sys_status"})
        self.assertTrue(err)
        self.assertFalse(self.d.execute("sys_status", {}, origin="app:x", allowed={"sys_status"})[1])

    def test_app_run_log_is_private(self):
        apps.save("logapp", "Log", "", {"shell.qml": QML % "x"})
        log = config.STATE / "app-logapp.log"
        log.write_text("old")
        log.chmod(0o644)
        old = os.umask(0o022)
        try:
            with mock.patch("amadeus.daemon.subprocess.Popen"):
                self.d.run_app("logapp")
        finally:
            os.umask(old)
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)
        self.assertEqual(log.read_text(), "")
    def test_failed_provider_turn_does_not_poison_history(self):
        from amadeus import providers

        class Flaky:
            kind = "chat"
            name = "flaky"

            def __init__(self):
                self.turns = 0

            def chat(self, system, history, tools):
                self.turns += 1
                if self.turns == 1:
                    return {"text": "", "calls": [{"id": "c1", "name": "sys_status", "args": {}}], "raw": None, "stop": "tools"}
                raise providers.ProviderError("upstream failed")

        class Conn:
            def event(self, *a):
                pass

        with mock.patch("amadeus.daemon.providers.make", return_value=Flaky()):
            with self.assertRaises(RuntimeError):
                self.d.ask(Conn(), "r1", "do it", session="failed-turn")
        self.assertEqual(self.d.sessions["failed-turn"]["history"], [])
        self.assertFalse(self.d.sessions["failed-turn"]["running"])


class TaskTest(unittest.TestCase):
    """Whole-task undo and stopping, as the side panel uses them."""
    def test_undo_restores_everything_one_task_changed(self):
        from amadeus.tools import files as F
        a, b, other = (Path(TMP) / n for n in ("task-a.txt", "task-b.txt", "task-other.txt"))
        a.write_text("a0"); other.write_text("o0")
        F.current.session = "task1"
        F.remember(a); a.write_text("a1")
        F.remember(b); b.write_text("b-new")
        F.remember(a); a.write_text("a2")
        F.current.session = "task2"
        F.remember(other); other.write_text("o1")
        self.assertEqual(F.changed_by("task1"), 3)
        self.assertEqual(len(F.undo_session("task1")), 3)
        self.assertEqual(a.read_text(), "a0")
        self.assertFalse(b.exists())
        self.assertEqual(other.read_text(), "o1")          # another task's change is untouched
        self.assertEqual(F.changed_by("task1"), 0)
        F.current.session = None

    def test_stopped_task_runs_no_more_tools(self):
        import threading
        from amadeus.daemon import Daemon
        d = Daemon()
        d.sessions["s1"] = {"history": [], "conn": None, "cancel": threading.Event(), "proc": None, "running": True}
        self.assertFalse(d.execute("sys_status", {}, session="s1")[1])
        self.assertTrue(d.stop("s1"))
        out, err = d.execute("sys_status", {}, session="s1")
        self.assertTrue(err)
        self.assertIn("stopped", out)
        self.assertFalse(d.stop("nope"))


class SystemToolTest(unittest.TestCase):
    def test_valid_prefixes_reach_the_same_helper_boundary(self):
        from amadeus.tools import system
        with mock.patch.object(system.root, "call") as call:
            for unit in (":demo.service", r"\x2edemo.service"):
                system.sys_service_control({"action": "start", "unit": unit, "scope": "system"}, None)
                call.assert_called_with("systemctl", action="start", unit=unit)
            for pkg in ("_demo", "+demo", "@demo"):
                system.pkg_manage({"action": "install", "packages": [pkg]}, None)
                call.assert_called_with("pacman", action="install", packages=[pkg])

    def test_option_like_names_are_refused(self):
        from amadeus.tools import system
        self.assertTrue(system.UNIT_RE.match("getty@tty1.service"))
        self.assertTrue(system.PKG_RE.match("lib32-glibc"))
        for unit in ("--now", "-H", ".service"):
            with self.assertRaises(T.ToolError, msg=unit):
                system.sys_service_control({"action": "start", "unit": unit, "scope": "user"}, None)
        for pkg in ("-Syu", "--overwrite=*", ".hidden"):
            with self.assertRaises(T.ToolError, msg=pkg):
                system.pkg_manage({"action": "install", "packages": [pkg]}, None)
        with self.assertRaises(T.ToolError):
            system.sys_service_control({"action": "--now", "unit": "demo.service", "scope": "user"}, None)
        with self.assertRaises(T.ToolError):
            system.sys_service_control({"action": "start", "unit": "demo.service", "scope": "bogus"}, None)
        with self.assertRaises(T.ToolError):
            system.pkg_manage({"action": "install", "packages": "htop"}, None)


class HelperTest(unittest.TestCase):
    def test_names_are_validated_before_any_command_runs(self):
        source = (ROOT / "priv/amadeus-priv").read_text().rsplit("\nmain()", 1)[0]
        ns = {"__name__": "helper_validation"}
        with mock.patch.object(sys, "argv", ["amadeus-priv", "--uid", str(os.getuid())]):
            exec(compile(source, "amadeus-priv", "exec"), ns)
        runner = mock.Mock(return_value=(0, ""))
        ns["run"] = runner
        for unit in ("--now", "-H", ".service", "ok.service\n"):
            with self.assertRaises(ValueError):
                ns["op_systemctl"]({"action": "start", "unit": unit})
        for pkgs in (["-Syu"], ["--overwrite=*"], [".hidden"], ["ok\n"], "htop", [None]):
            with self.assertRaises(ValueError):
                ns["op_pacman"]({"action": "install", "packages": pkgs})
        runner.assert_not_called()
        for unit in (":demo.service", r"\x2edemo.service", "getty@tty1.service"):
            ns["op_systemctl"]({"action": "start", "unit": unit})
            self.assertEqual(runner.call_args.args[0], ["systemctl", "start", unit])
        for pkg in ("_demo", "+demo", "@demo"):
            ns["op_pacman"]({"action": "install", "packages": [pkg]})
            self.assertIn(mock.call(["pacman", "-S", "--noconfirm", "--needed", pkg], 3600), runner.call_args_list)

    """The root helper, run unprivileged: validation must refuse before anything executes."""
    @classmethod
    def setUpClass(cls):
        cls.p = subprocess.Popen([str(ROOT / "priv/amadeus-priv"), "--uid", str(os.getuid()), "--socket", os.environ["AMADEUS_PRIV_SOCK"]], stderr=subprocess.DEVNULL)
        for _ in range(50):
            if root.enabled():
                break
            time.sleep(0.05)

    @classmethod
    def tearDownClass(cls):
        root.call("shutdown")
        cls.p.wait(5)

    def test_refusals(self):
        self.assertFalse(root.call("info")["full"])
        cases = [("exec", {"argv": ["id"]}), ("write_file", {"path": "/usr/bin/x", "content": ""}), ("write_file", {"path": "/etc/sudoers.d/x", "content": ""}),
                 ("write_file", {"path": "/etc/../root/x", "content": ""}), ("systemctl", {"action": "start", "unit": "a; rm -rf /"}),
                 ("systemctl", {"action": "mask", "unit": "x.service"}), ("systemctl", {"action": "stop", "unit": "amadeus-priv.service"}),
                 ("pacman", {"action": "install", "packages": ["--overwrite=*"]}), ("pacman", {"action": "install", "packages": []}),
                 ("pacman", {"action": "install", "packages": ["-Syu"]}), ("systemctl", {"action": "start", "unit": "--now"}),
                 ("snapper", {"action": "undo", "frm": 5, "to": 2}), ("nope", {})]
        for op, args in cases:
            r = root.call(op, **args)
            self.assertFalse(r["ok"], (op, args, r))

    def test_socket_is_private(self):
        self.assertEqual(os.stat(os.environ["AMADEUS_PRIV_SOCK"]).st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
