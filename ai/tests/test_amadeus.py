"""Run with: python3 -m unittest discover -s tests -v
Uses throwaway directories; never touches the real config, apps or audit log."""
import json, os, socket, subprocess, sys, tempfile, threading, time, unittest
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
    def test_focused_window_is_mapped_for_the_panel(self):
        from amadeus.tools import desktop
        with mock.patch.object(desktop, "hj", return_value={"address": "0xabc", "class": "foot", "title": "t" * 200}):
            self.assertEqual(desktop.focused_window(), {"id": "0xabc", "app": "foot", "title": "t" * 120})
        with mock.patch.object(desktop, "hj", return_value={"address": "0x1"}):
            self.assertEqual(desktop.focused_window(), {"id": "0x1", "app": "", "title": ""})
        with mock.patch.object(desktop, "hj", return_value={}):
            self.assertIsNone(desktop.focused_window())


class AuditTest(unittest.TestCase):
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


QML = 'import QtQuick\nimport Quickshell\nimport "Amadeus"\nAppWindow { title: "t"; Txt { text: "%s" } }\n'


class AppsTest(unittest.TestCase):
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

    def test_broken_update_is_rejected_and_old_version_kept(self):
        apps.save("keep", "Keep", "", {"shell.qml": QML % "good"})
        with self.assertRaises(apps.AppError):
            apps.save("keep", files={"shell.qml": "import QtQuick\nItem { this is not qml"})
        self.assertIn("good", (apps.app_dir("keep") / "shell.qml").read_text())

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


class DaemonTest(unittest.TestCase):
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


class HelperTest(unittest.TestCase):
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
                 ("snapper", {"action": "undo", "frm": 5, "to": 2}), ("nope", {})]
        for op, args in cases:
            r = root.call(op, **args)
            self.assertFalse(r["ok"], (op, args, r))

    def test_socket_is_private(self):
        self.assertEqual(os.stat(os.environ["AMADEUS_PRIV_SOCK"]).st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
