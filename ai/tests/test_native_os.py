"""Native control, visual boundaries and automation tests, entirely in throwaway state."""
import base64, json, os, struct, sys, tempfile, threading, time, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from amadeus import config, attachments, tasks, tools, policy
from amadeus.daemon import Daemon, Ctx
from amadeus.tools import controls, interaction, files
from amadeus.providers.openai import OpenAICompat
from amadeus.providers.anthropic import Anthropic


class NativeOS(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="amadeus-native-")
        self.root = Path(self.temp.name)
        self.patches = [mock.patch.object(config, k, self.root / k.lower()) for k in ("CONFIG", "STATE", "DATA", "RUN")]
        for patch in self.patches: patch.start()
        self.env = mock.patch.dict(os.environ, XDG_CONFIG_HOME=str(self.root / "user-config"))
        self.env.start()
        config.ensure_dirs()
        self.daemon = Daemon()
        self.ctx = Ctx(self.daemon, "test-native", "ai")
        self.calls = []
        self.command = mock.patch.object(tasks, "sh", side_effect=self.fake_command)
        self.command.start()
        self.locked = mock.patch.object(interaction, "locked", return_value=False)
        self.locked.start()

    def tearDown(self):
        self.locked.stop(); self.command.stop(); self.env.stop()
        for patch in reversed(self.patches): patch.stop()
        self.temp.cleanup()

    def fake_command(self, argv, **kwargs):
        self.calls.append(argv)
        return SimpleNamespace(stdout="ok", stderr="", returncode=0)

    def test_read_only_controls_do_not_gain_write_permission(self):
        with mock.patch.object(controls, "sh", side_effect=self.fake_command):
            self.daemon.policy.rules["desktop.config"] = "deny"
            out, failed = self.daemon.execute("desktop_settings", {"area":"brightness", "action":"set", "value":60})
            self.assertTrue(failed); self.assertEqual(self.calls, [])
            out, failed = self.daemon.execute("desktop_settings", {"area":"brightness"})
            self.assertFalse(failed)
            self.assertEqual(self.calls, [["brightnessctl", "-m"]])

    def test_bad_settings_are_rejected_before_any_write_command(self):
        with mock.patch.object(controls, "sh", side_effect=self.fake_command):
            for args in ({"area":"brightness", "action":"set", "value":0},
                         {"area":"gpu", "action":"set", "value":"nvidia; id"},
                         {"area":"audio", "action":"set", "key":"mute", "value":"false"}):
                with self.assertRaises(tools.ToolError): controls.desktop_settings(args, self.ctx)
            self.assertFalse(any("set" in call for call in self.calls))

    def test_protected_symlink_cannot_be_read_as_a_theme(self):
        secret = config.CONFIG / "secrets" / "private"
        secret.write_text('{"token":"do not expose"}')
        theme = self.root / "user-config/amadeus/theme.json"
        theme.parent.mkdir(parents=True); theme.symlink_to(secret)
        with self.assertRaises(tools.ToolError): controls.desktop_settings({"area":"theme"}, self.ctx)

    def test_screen_pixels_are_not_returned_as_plain_tool_text(self):
        image = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"private-pixels").decode()
        content = json.dumps({"observation":"o", "image":{"mime":"image/png", "data":image}})
        text, native = attachments.split_result("desktop_observe", content)
        self.assertNotIn(image, text)
        self.assertEqual(native["data"], image)
        self.assertEqual(attachments.mcp_content("desktop_observe", content)[1]["type"], "image")
        history = [{"role":"tool", "results":[{"id":"c", "name":"desktop_observe", "content":content}]}]
        msgs = OpenAICompat("x", {"model":"m"})._messages(history)
        self.assertEqual(msgs[-1]["content"][1]["type"], "image_url")
        claude = Anthropic("x", {})._messages(history)
        self.assertEqual(claude[0]["content"][0]["content"][1]["type"], "image")
        self.assertEqual(attachments.split_result("fs_read", content), (content, None))

    def test_focus_change_after_approval_prevents_all_input(self):
        self.daemon.observations = {"o": {"at":time.monotonic(), "session":"test-native", "window":"0x123", "nodes":[]}}
        with mock.patch.object(interaction, "hj", return_value={"address":"0x456"}), mock.patch.object(interaction, "sh") as command:
            with self.assertRaises(tools.ToolError): interaction.desktop_interact({"observation":"o", "steps":[{"type":"type", "text":"hello"}]}, self.ctx)
            command.assert_not_called()

    def test_whole_input_batch_is_validated_before_first_keystroke(self):
        self.daemon.observations = {"o": {"at":time.monotonic(), "session":"test-native", "window":"0x123", "nodes":[]}}
        with mock.patch.object(interaction, "hj", return_value={"address":"0x123"}), mock.patch.object(interaction, "sh") as command:
            with self.assertRaises(tools.ToolError): interaction.desktop_interact({"observation":"o", "steps":[{"type":"type", "text":"hello"}, {"type":"key", "key":"Return; exec"}]}, self.ctx)
            command.assert_not_called()

    def test_observation_is_private_to_a_task_and_expires(self):
        self.daemon.observations = {"o": {"at":time.monotonic()-91, "session":"test-native", "window":"0x123"}}
        with self.assertRaises(tools.ToolError): interaction.snapshot(self.ctx, "o")
        self.daemon.observations["o"].update(at=time.monotonic(), session="another-task")
        with self.assertRaises(tools.ToolError): interaction.snapshot(self.ctx, "o")

    def test_observation_pixels_are_not_stored_in_the_audit(self):
        from amadeus import audit
        self.daemon.ask_user = lambda *args: "yes"
        with mock.patch.dict(tools.REGISTRY["desktop_observe"], fn=lambda a,c:{"image":{"data":"private-pixels"}}):
            self.daemon.execute("desktop_observe", {}, session="test-native")
        self.assertNotIn("private-pixels", json.dumps(audit.read(20)))

    def test_disabled_task_has_no_model_run_and_no_prompt_in_unit(self):
        job = tasks.save({"id":"daily-report", "label":"Report", "prompt":"private task text", "calendar":"daily"})
        self.assertFalse(job["enabled"])
        self.assertNotIn("private task text", tasks.units(job["id"])[0].read_text())
        with mock.patch.object(self.daemon, "ask") as ask:
            with self.assertRaises(tools.ToolError): tasks.run(self.daemon, SimpleNamespace(interactive=False), "r", job["id"])
            ask.assert_not_called()
        self.assertEqual(tasks.task_path(job["id"]).stat().st_mode & 0o777, 0o600)

    def test_event_tasks_publish_only_enabled_event_names(self):
        job = {"id":"focus-helper", "label":"Help", "prompt":"Summarise state", "trigger":"event", "event":"app-focused"}
        tasks.save(job)
        self.assertEqual(json.loads((config.CONFIG/"automation-events.json").read_text()), [])
        tasks.save(dict(job, enabled=True))
        self.assertEqual(json.loads((config.CONFIG/"automation-events.json").read_text()), ["app-focused"])
        tasks.remove(job["id"])
        self.assertTrue((config.STATE/"removed-tasks/focus-helper.json").exists())
        self.assertEqual(json.loads((config.CONFIG/"automation-events.json").read_text()), [])

    def test_automation_does_not_inherit_a_write_session_grant(self):
        self.daemon.policy.rules["desktop.control"] = "allow"
        self.daemon.policy.grant_session("desktop.control", "modify")
        self.daemon.ask_user = mock.Mock(return_value="no")
        with mock.patch.dict(tools.REGISTRY["desktop_clipboard_set"], fn=mock.Mock()) as registry:
            out, failed = self.daemon.execute("desktop_clipboard_set", {"text":"x"}, origin="automation:job")
            self.assertTrue(failed)
            self.daemon.ask_user.assert_called_once()
            tools.REGISTRY["desktop_clipboard_set"]["fn"].assert_not_called()

    def test_task_calendar_cannot_inject_another_unit_directive(self):
        with self.assertRaises(tools.ToolError): tasks.save({"id":"bad-task", "prompt":"x", "calendar":"daily\nExecStart=/bin/false"})
        self.assertFalse(tasks.task_path("bad-task").exists())

    def test_failed_timer_enable_restores_previous_job_and_units(self):
        old = tasks.save({"id":"rollback-job", "prompt":"old", "calendar":"daily"})
        before = [p.read_bytes() for p in (tasks.task_path(old["id"]), *tasks.units(old["id"]))]
        def fail_enable(argv, **kwargs):
            self.calls.append(argv)
            if "enable" in argv and kwargs.get("check"): raise tools.ToolError("enable failed")
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        with mock.patch.object(tasks, "sh", side_effect=fail_enable):
            with self.assertRaises(tools.ToolError): tasks.save(dict(old, prompt="changed", enabled=True))
        self.assertEqual(before, [p.read_bytes() for p in (tasks.task_path(old["id"]), *tasks.units(old["id"]))])

    def test_undo_disables_timer_and_removes_derived_units(self):
        files.current.session = "task-undo"
        tasks.save({"id":"undo-job", "prompt":"x", "calendar":"daily", "enabled":True})
        files.undo_session("task-undo")
        self.assertFalse(tasks.task_path("undo-job").exists())
        self.assertTrue(all(not p.exists() for p in tasks.units("undo-job")))
        self.assertIn(["systemctl", "--user", "disable", "--now", "amadeus-task-undo-job.timer"], self.calls)

    def test_event_cooldown_prevents_duplicate_model_requests(self):
        tasks.save({"id":"event-job", "prompt":"x", "trigger":"event", "event":"app-focused", "enabled":True})
        conn = SimpleNamespace(interactive=False)
        with mock.patch.object(self.daemon, "ask", return_value={"text":"done"}) as ask:
            tasks.event(self.daemon, conn, "r", "app-focused", {"app":"foot"})
            tasks.event(self.daemon, conn, "r", "app-focused", {"app":"foot"})
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(ask.call_args.kwargs["origin"], "automation:event-job")

    def test_stop_declines_pending_approvals_and_terminates_the_dialog(self):
        self.daemon.sessions["running"] = {"running":True, "cancel":threading.Event()}
        dialog = mock.Mock(); dialog.poll.return_value = None
        pending = {"session":"running", "event":threading.Event(), "dialog":dialog}
        self.daemon.pending["approval"] = pending
        self.assertTrue(self.daemon.stop("running"))
        self.assertEqual(pending["decision"], "no")
        self.assertTrue(pending["event"].is_set())
        dialog.terminate.assert_called_once()

    def test_lock_prevents_screen_capture(self):
        with mock.patch.object(interaction, "locked", return_value=True), mock.patch.object(interaction, "sh") as command:
            with self.assertRaises(tools.ToolError): interaction.desktop_observe({}, self.ctx)
            command.assert_not_called()

    def test_text_undo_restores_exact_gtk_factor_and_absent_theme(self):
        files.current.session = "text-undo"
        def response(argv, **kwargs):
            return SimpleNamespace(stdout="1.2727" if argv[0] == "gsettings" else "14 px", stderr="", returncode=0)
        with mock.patch.object(controls, "sh", side_effect=response):
            controls.desktop_settings({"area":"text", "action":"set", "value":16}, self.ctx)
        with mock.patch.object(files, "sh", side_effect=self.fake_command):
            files.undo_session("text-undo")
        self.assertIn(["gsettings", "set", "org.gnome.desktop.interface", "text-scaling-factor", "1.2727"], self.calls)
        self.assertFalse((self.root/"user-config/amadeus/theme.json").exists())
