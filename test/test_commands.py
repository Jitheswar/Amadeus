#!/usr/bin/python3
"""Behaviour tests for the desktop commands. Run by ./build.sh check.

Every external program these commands talk to is a stand-in: nothing here starts a
session, changes a package, asks for a password or touches the user's own files.
The commands are run from the repository, in a throwaway HOME, with a PATH whose
first entry holds the stand-ins and whose result is checked."""
import json, os, re, shlex, shutil, subprocess, tempfile, time, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "desktop/bin"

# Programs that could change the machine. They are always replaced, so a test that
# accidentally reaches one records a call instead of doing something.
DANGEROUS = ("sudo", "pkexec", "systemctl", "pacman", "pacman-key", "snapper", "reboot", "poweroff",
             "shutdown", "uwsm", "notify-send", "quickshell", "curl")


def desktop_exec(value):
    """Parse an Exec value the way a desktop launcher does: quotes, backslash escapes,
    %% for a literal percent, and field codes removed. Returns the argument list."""
    args, cur, quoted, i = [], "", False, 0
    while i < len(value):
        c = value[i]
        if c == '"':
            quoted = not quoted
        elif c == "\\" and i + 1 < len(value):
            i += 1
            cur += value[i]
        elif c == "%" and i + 1 < len(value):
            code = value[i + 1]
            if code == "%":
                cur += "%"
            elif code in "fFuUdDnNick":
                pass
            else:
                pass          # an unknown field code is dropped, as launchers do
            i += 1
        elif c.isspace() and not quoted:
            if cur:
                args.append(cur)
                cur = ""
        else:
            cur += c
        i += 1
    if cur:
        args.append(cur)
    return args


class Commands(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="amadeus-commands-"))
        self.home, self.config, self.data = self.tmp / "home", self.tmp / "config", self.tmp / "home/.local/share"
        self.state, self.run_dir, self.bin = self.tmp / "state", self.tmp / "run", self.tmp / "bin"
        for d in (self.home, self.config, self.data, self.state, self.bin, self.run_dir):
            d.mkdir(parents=True)
        os.chmod(self.run_dir, 0o700)
        self.calls = self.tmp / "calls.log"
        self.calls.write_text("")
        self.env = {
            "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.config), "XDG_DATA_HOME": str(self.data),
            "XDG_STATE_HOME": str(self.state), "XDG_RUNTIME_DIR": str(self.run_dir),
            "PATH": f"{self.bin}:{BIN}:{ROOT / 'ai/bin'}:/usr/bin:/bin", "LANG": "C.UTF-8",
            "AMADEUS_TEST_CALLS": str(self.calls),
        }
        for name in DANGEROUS:
            self.stub(name, rc=1 if name in ("quickshell", "curl") else 0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- stand-ins ---------------------------------------------------------
    def stub(self, name, body="", rc=0, output=""):
        """A stand-in for one program. It records its arguments, prints `output`,
        runs `body` and exits with `rc`."""
        path = self.bin / name
        show = f"printf '%s' {shlex.quote(output)}" if output else ""
        path.write_text(f"""#!/bin/bash
printf '%s' {shlex.quote(name)} >> "$AMADEUS_TEST_CALLS"
for a in "$@"; do printf '\\t%s' "$a" >> "$AMADEUS_TEST_CALLS"; done
printf '\\n' >> "$AMADEUS_TEST_CALLS"
{show}
{body}
exit {rc}
""")
        path.chmod(0o755)

    def run_cmd(self, *argv, env=None, timeout=30, input=None):
        script = BIN / argv[0]
        return subprocess.run([str(script), *map(str, argv[1:])], capture_output=True, text=True,
                              env=dict(self.env, **(env or {})), cwd=self.tmp, timeout=timeout, input=input)

    def picker(self, *answers, rc=0):
        """A picker that answers each call in turn; the caller sees one line per call."""
        state = self.tmp / "picker.answers"
        cases = "\n".join(f"  {i}) printf '%s\\n' {shlex.quote(a)} ;;" for i, a in enumerate(answers, 1))
        self.stub("amadeus-pick", rc=rc, body=f"""n=$(cat {state} 2>/dev/null || echo 0); n=$((n + 1)); echo $n >{state}
cat >/dev/null
case $n in
{cases}
  *) exit 1 ;;
esac""")

    def stop_stray_recorder(self, pidfile):
        try:
            os.kill(int(pidfile.read_text()), 9)
        except (OSError, ValueError):
            pass

    def wait_for(self, name, count=1, timeout=3):
        """The launcher starts applications detached; give the stand-in time to run."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(self.calls_of(name)) >= count:
                return
            time.sleep(0.02)
        self.fail(f"{name} was not started")

    def calls_of(self, name):
        out = []
        for line in self.calls.read_text().splitlines():
            fields = line.split("\t")
            if fields[0] == name:
                out.append(fields[1:])
        return out

    def write_defaults(self, **values):
        f = self.config / "amadeus/defaults"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("".join(f"{k.upper()}={v}\n" for k, v in values.items()))

    def write_entry(self, app_id, **fields):
        d = self.home / ".local/share/applications"
        d.mkdir(parents=True, exist_ok=True)
        lines = ["[Desktop Entry]", "Type=Application", f"Name={fields.pop('Name', app_id)}"]
        for k, v in fields.items():
            lines.append(f"{k}={v}")
        (d / f"{app_id}.desktop").write_text("\n".join(lines) + "\n")

    def assert_ok(self, p):
        self.assertEqual(p.returncode, 0, f"exit {p.returncode}\nstdout: {p.stdout}\nstderr: {p.stderr}")

    # ---- defaults, terminal and editor -------------------------------------
    def test_defaults_work_before_a_file_exists(self):
        """A fresh user has no defaults file yet; asking what the defaults are must work."""
        self.assertEqual(self.run_cmd("amadeus-default", "terminal").stdout.strip(), "foot")
        self.assertEqual(self.run_cmd("amadeus-default", "editor").stdout.strip(), "nano")
        self.assertEqual(self.run_cmd("amadeus-default", "harness").stdout.strip(), "")
        shown = self.run_cmd("amadeus-default")
        self.assert_ok(shown)
        self.assertIn("terminal  foot", shown.stdout)
        self.assertIn("harness   (not set)", shown.stdout)

    def test_defaults_list_choices_and_set(self):
        self.write_entry("myterm", Name="My Term", Exec="myterm", Categories="TerminalEmulator;")
        self.stub("nvim")
        choices = self.run_cmd("amadeus-default", "terminal", "--choices")
        self.assert_ok(choices)
        self.assertIn("myterm", choices.stdout.splitlines())
        self.assert_ok(self.run_cmd("amadeus-default", "terminal", "myterm"))
        self.assertEqual((self.config / "amadeus/defaults").read_text(), "TERMINAL=myterm\n")
        self.assertEqual(self.run_cmd("amadeus-default", "terminal").stdout.strip(), "myterm")

        self.assertIn("nvim", self.run_cmd("amadeus-default", "editor", "--choices").stdout.splitlines())
        self.assert_ok(self.run_cmd("amadeus-default", "editor", "nvim"))
        self.assertEqual(set((self.config / "amadeus/defaults").read_text().splitlines()),
                         {"EDITOR=nvim", "TERMINAL=myterm"})

        before = (self.config / "amadeus/defaults").read_text()
        refused = self.run_cmd("amadeus-default", "terminal", "no-such-terminal")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("is not an installed terminal", refused.stdout)
        self.assertEqual((self.config / "amadeus/defaults").read_text(), before)

    def test_terminal_uses_the_chosen_one(self):
        self.write_defaults(TERMINAL="foot")
        self.stub("foot")
        self.assert_ok(self.run_cmd("amadeus-terminal", "--title", "Test title", "-e", "echo", "hello"))
        self.assertEqual(self.calls_of("foot"), [["--title", "Test title", "-e", "echo", "hello"]])
        self.write_defaults(TERMINAL="myterm")
        self.stub("myterm")
        self.assert_ok(self.run_cmd("amadeus-terminal", "-e", "true"))
        self.assertEqual(self.calls_of("myterm"), [["-e", "true"]])

    def test_editor_opens_in_the_terminal_when_it_lives_there(self):
        self.write_defaults(TERMINAL="myterm", EDITOR="nvim")
        self.stub("myterm")
        self.stub("nvim")
        self.assert_ok(self.run_cmd("amadeus-editor", "notes.txt"))
        self.assertEqual(self.calls_of("myterm"), [["-e", "nvim", "notes.txt"]])
        self.write_defaults(TERMINAL="myterm", EDITOR="code")
        self.stub("code")
        self.assert_ok(self.run_cmd("amadeus-editor", "notes.txt"))
        self.assertEqual(self.calls_of("code"), [["notes.txt"]])

    # ---- web apps -----------------------------------------------------------
    def test_web_app_list_works_with_none_installed(self):
        p = self.run_cmd("amadeus-webapp", "list")
        self.assert_ok(p)
        self.assertEqual(p.stdout, "")

    def test_web_app_is_added_listed_launched_and_removed(self):
        self.assert_ok(self.run_cmd("amadeus-webapp", "install", "My App", "https://example.org"))
        f = self.data / "applications/amadeus-webapp-my-app.desktop"
        text = f.read_text()
        self.assertIn("Name=My App", text)
        self.assertIn("X-Amadeus-WebApp=true", text)
        self.assertEqual(self.run_cmd("amadeus-webapp", "list").stdout, "My App\thttps://example.org\n")
        self.assertIn("My App", self.run_cmd("amadeus-launcher", "--print").stdout)
        self.assert_ok(self.run_cmd("amadeus-webapp", "remove", "My App"))
        self.assertFalse(f.exists())
        self.assertEqual(self.run_cmd("amadeus-webapp", "list").stdout, "")

    def test_web_app_address_survives_the_desktop_entry(self):
        """A URL with % in it is common (%20 for a space); the launcher must receive it unchanged."""
        url = "https://example.org/a%20b?q=100%25"
        self.assert_ok(self.run_cmd("amadeus-webapp", "install", "Percent", url))
        exec_line = next(l for l in (self.data / "applications/amadeus-webapp-percent.desktop").read_text().splitlines()
                         if l.startswith("Exec="))
        argv = desktop_exec(exec_line[len("Exec="):])
        self.assertEqual(argv, ["amadeus-webapp", "launch", url])

        # The same path a click takes: the default browser says it can show a site as an app.
        self.stub("xdg-settings", output="test-browser.desktop")
        self.write_entry("test-browser", Name="Test Browser", Exec="test-browser")
        self.stub("test-browser", output="Chromium 120")
        self.assert_ok(self.run_cmd(argv[0], *argv[1:]))
        self.assertEqual(self.calls_of("test-browser")[-1], [f"--app={url}"])

    def test_web_app_refuses_a_name_with_a_line_break(self):
        p = self.run_cmd("amadeus-webapp", "install", "Two\nLines", "https://example.org")
        self.assertEqual(p.returncode, 1)
        self.assertIn("line break", p.stdout)
        self.assertEqual(list((self.data / "applications").glob("*.desktop")), [])

    # ---- launcher -----------------------------------------------------------
    def test_launcher_starts_an_entry_with_a_missing_working_directory(self):
        self.write_entry("mine", Name="Mine", Exec="mineapp %U", Path="/nonexistent/directory")
        self.assertIn("Mine\tmine", self.run_cmd("amadeus-launcher", "--print").stdout)
        self.stub("amadeus-pick", output="Mine\tmine", body="cat >/dev/null")
        self.stub("mineapp")
        self.assert_ok(self.run_cmd("amadeus-launcher"))
        self.wait_for("mineapp")
        self.assertEqual(self.calls_of("mineapp")[0], [])

    def test_launcher_puts_a_terminal_application_in_a_terminal(self):
        self.write_entry("termapp", Name="Term App", Exec="termapp", Terminal="true")
        self.stub("amadeus-pick", output="Term App\ttermapp", body="cat >/dev/null")
        self.stub("amadeus-terminal")
        self.stub("termapp")
        self.assert_ok(self.run_cmd("amadeus-launcher"))
        self.wait_for("amadeus-terminal")
        self.assertEqual(self.calls_of("amadeus-terminal")[0], ["-e", "termapp"])

    def test_launcher_hides_entries_that_ask_to_be_hidden(self):
        self.write_entry("visible", Name="Visible", Exec="visible")
        self.write_entry("hidden", Name="Hidden", Exec="hidden", NoDisplay="true")
        listed = self.run_cmd("amadeus-launcher", "--print").stdout
        self.assertIn("Visible\tvisible", listed)
        self.assertNotIn("Hidden", listed)

    # ---- install catalogue --------------------------------------------------
    def test_catalog_says_so_when_it_is_not_installed(self):
        p = self.run_cmd("amadeus-catalog", env={"AMADEUS_CATALOG": str(self.tmp / "missing")})
        self.assertEqual(p.returncode, 1)
        self.assertIn("No install catalogue", p.stderr)

    def test_catalog_resolves_sources_and_installs_through_stand_ins(self):
        cat = self.tmp / "catalog"
        cat.mkdir()
        (cat / "terminal.list").write_text(
            "# Title\tsources\n"
            "Foot\tpacman:foot\n"
            "Kitty\tpacman:missing aur:kitty-git\n"
            "Tool\tmise:opencode\n")
        self.stub("pacman", body="""case "$1 $2" in
  "-Si foot") exit 0 ;;
  "-Si missing") exit 1 ;;
  "-Q foot") exit 0 ;;
  "-Q kitty-git"|"-Q opencode") exit 1 ;;
  *) exit 0 ;;
esac""")
        self.stub("amadeus-aur", body="""case "$1" in
  list) echo kitty-git ;;
  install) exit 0 ;;
  *) exit 0 ;;
esac""")
        self.stub("mise", body="""case "$1" in
  registry) exit 0 ;;
  ls) exit 1 ;;
  *) exit 0 ;;
esac""")
        self.stub("amadeus-harness")
        env = {"AMADEUS_CATALOG": str(cat)}
        self.assertEqual(self.run_cmd("amadeus-catalog", env=env).stdout, "terminal\n")
        listed = self.run_cmd("amadeus-catalog", "terminal", env=env)
        self.assert_ok(listed)
        self.assertIn("Foot  (installed)\tpacman:foot", listed.stdout)
        self.assertIn("Kitty\taur:kitty-git", listed.stdout)
        self.assertIn("Tool\tmise:opencode", listed.stdout)
        self.assertIn("terminal", self.run_cmd("amadeus-catalog", "nope", env=env).stdout)

        p = self.run_cmd("amadeus-catalog", "install", "Foot\tpacman:foot", "Kitty\taur:kitty-git",
                         "Tool\tmise:opencode", env=env)
        self.assert_ok(p)
        # The package manager is reached through sudo; the stand-in proves the command
        # without running it. The other two sources are called directly.
        self.assertEqual(self.calls_of("sudo"), [["pacman", "-S", "--needed", "--", "foot"]])
        self.assertEqual(self.calls_of("amadeus-aur")[-1], ["install", "kitty-git"])
        self.assertEqual(self.calls_of("amadeus-harness"), [["install", "opencode"]])

    # ---- shortcuts ----------------------------------------------------------
    def test_keys_are_read_from_the_configuration_file(self):
        config = self.tmp / "hyprland.lua"
        config.write_text('o.bind("SUPER + SHIFT + T", "Test shortcut", "echo test")\n'
                          'o.bind("SUPER + K", "Shortcuts and commands", "amadeus-keys")\n')
        out = self.run_cmd("amadeus-keys", "--print", env={"AMADEUS_HYPR_CONFIG": str(config)})
        self.assert_ok(out)
        self.assertRegex(out.stdout, r"(?m)^Super \+ Shift \+ T +Test shortcut$")
        self.assertRegex(out.stdout, r"(?m)^Super \+ K +Shortcuts and commands$")

    def test_keys_print_without_a_configuration(self):
        out = self.run_cmd("amadeus-keys", "--print", env={"AMADEUS_HYPR_CONFIG": str(self.tmp / "none.lua")})
        self.assert_ok(out)

    # ---- harnesses ----------------------------------------------------------
    def test_harness_list_install_run_and_remove(self):
        tool_bin = self.tmp / "installs/claude/2.1/bin"
        tool_bin.mkdir(parents=True)
        claude = tool_bin / "claude"
        claude.write_text(f"#!/bin/bash\necho claude \"$@\"\n")
        claude.chmod(0o755)
        self.stub("mise", body="""case "$1" in
  registry) printf 'claude    aqua:anthropics/claude-code\\nopencode  npm:opencode-ai\\n' ;;
  ls) [[ "$2" == --global ]] && printf 'claude 2.1.0\\n' ;;
  bin-paths) echo "$AMADEUS_TEST_TOOL_BIN" ;;
  latest) echo 2.2.0 ;;
  *) exit 0 ;;
esac""")
        self.env["AMADEUS_TEST_TOOL_BIN"] = str(tool_bin)
        harnesses = self.tmp / "harnesses.list"
        harnesses.write_text("claude\tClaude Code\nopencode\topencode\n")
        env = {"AMADEUS_HARNESS_LIST": str(harnesses)}

        listed = self.run_cmd("amadeus-harness", "list", env=env)
        self.assert_ok(listed)
        self.assertIn("Claude Code  (installed)\tclaude", listed.stdout)
        self.assertIn("opencode\topencode", listed.stdout)
        self.assertEqual(self.run_cmd("amadeus-harness", "installed", env=env).stdout, "claude\n")
        info = self.run_cmd("amadeus-harness", "info", "claude", env=env)
        self.assertIn("Name        : Claude Code", info.stdout)
        self.assertIn("Installed   : 2.1.0", info.stdout)

        self.assert_ok(self.run_cmd("amadeus-harness", "install", "opencode", env=env))
        self.assertEqual(self.calls_of("mise")[-1], ["use", "--global", "opencode@latest"])
        self.assert_ok(self.run_cmd("amadeus-harness", "remove", "claude", env=env))
        self.assertEqual(self.calls_of("mise")[-2:], [["unuse", "--global", "claude"], ["uninstall", "--all", "claude"]])
        ran = self.run_cmd("amadeus-harness", "run", "claude", "--version", env=env)
        self.assertIn("claude --version", ran.stdout)

    # ---- Wi-Fi --------------------------------------------------------------
    def test_wifi_lists_and_connects(self):
        self.stub("nmcli", body="""case "$*" in
  "-t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list --rescan auto")
      printf '*:Home:82:WPA2\\n:Office:44:WPA2\\n:Home:30:WPA2\\n:Open:70:\\n' ;;
  "-t -f NAME connection show") printf 'Home\\n' ;;
  "connect Home") exit 0 ;;
  "radio wifi") echo enabled ;;
  "-t -f SSID,SECURITY device wifi list") printf 'Home:WPA2\\nOffice:WPA2\\nOpen:\\n' ;;
  "device wifi connect Open") exit 0 ;;
  "device wifi connect Office password secret") exit 0 ;;
  *) exit 0 ;;
esac""")
        listed = self.run_cmd("amadeus-wifi", "list")
        self.assert_ok(listed)
        self.assertEqual(listed.stdout.count("Home"), 1)
        self.assertEqual(self.run_cmd("amadeus-wifi", "state").stdout.strip(), "enabled")
        self.assert_ok(self.run_cmd("amadeus-wifi", "on"))
        self.assertEqual(self.calls_of("nmcli")[-1], ["radio", "wifi", "on"])
        self.assert_ok(self.run_cmd("amadeus-wifi", "connect", "Home"))
        self.assertEqual(self.calls_of("nmcli")[-1], ["connection", "up", "id", "Home"])
        # An open network needs no password and is joined directly.
        self.assert_ok(self.run_cmd("amadeus-wifi", "connect", "Open"))
        self.assertEqual(self.calls_of("nmcli")[-1], ["device", "wifi", "connect", "Open"])
        # A secured network not saved before asks for the password (here, a stand-in answer).
        self.stub("amadeus-pick", output="secret", rc=2, body="cat >/dev/null")
        self.assert_ok(self.run_cmd("amadeus-wifi", "connect", "Office"))
        self.assertEqual(self.calls_of("nmcli")[-1], ["device", "wifi", "connect", "Office", "password", "secret"])

    # ---- power menu ---------------------------------------------------------
    def test_power_menu_offers_what_the_machine_can_do(self):
        self.stub("busctl", output='s "yes"')
        self.stub("amadeus-pick", output="Suspend", body="cat >/dev/null")
        self.stub("systemctl")
        self.stub("swaylock")
        self.assert_ok(self.run_cmd("amadeus-power-menu"))
        self.assertEqual(self.calls_of("systemctl"), [["suspend"]])

        self.stub("amadeus-pick", output="Hibernate", body="cat >/dev/null")
        self.assert_ok(self.run_cmd("amadeus-power-menu"))
        self.assertEqual(self.calls_of("systemctl")[-1], ["hibernate"])

    def test_power_menu_does_not_offer_hibernate_when_it_cannot(self):
        self.stub("busctl", output='s "no"')
        self.stub("amadeus-pick", output="Lock", body="cat >/dev/null")
        self.stub("swaylock")
        sent = self.tmp / "picker.in"
        self.stub("amadeus-pick", body=f'cat >{sent}')
        self.assert_ok(self.run_cmd("amadeus-power-menu"))
        self.assertNotIn("Hibernate", sent.read_text())

    # ---- the menu builds commands without running them ----------------------
    def test_menu_routes_to_commands(self):
        self.stub("amadeus-terminal")
        self.stub("fastfetch", output="Amadeus OS")
        self.assert_ok(self.run_cmd("amadeus-menu", "about"))
        self.assertEqual(self.calls_of("amadeus-terminal")[0][0], "--title")
        self.stub("amadeus-power-menu")
        self.assert_ok(self.run_cmd("amadeus-menu", "system"))
        self.assertEqual(self.calls_of("amadeus-power-menu"), [[]])
        self.stub("amadeus-pick", output="Harnesses and tools only", body="cat >/dev/null")
        self.assert_ok(self.run_cmd("amadeus-menu", "update"))
        self.assertIn("amadeus-harness update", self.calls_of("amadeus-terminal")[-1][-1])

    # ---- the picker itself and the menu that drives it -----------------------
    def test_pick_passes_the_list_through_the_shell_and_prints_the_choice(self):
        seen = self.tmp / "pick"
        self.stub("quickshell", body=f"""cp "$8" {seen}.in
printf '%s' "${{10}}" > {seen}.options
( sleep 0.05; printf 'ok\\nbeta\\n' > "$9" ) &""")
        p = self.run_cmd("amadeus-pick", "--multi", "--preview", 'printf %s "$1"', "--hint", "more", "Pick one",
                         input="alpha\nbeta\n")
        self.assert_ok(p)
        self.assertEqual(p.stdout, "beta\n")
        self.assertEqual(Path(str(seen) + ".in").read_text(), "alpha\nbeta\n")
        options = json.loads(Path(str(seen) + ".options").read_text())
        self.assertEqual(options, {"multi": True, "allowNew": False, "preview": 'printf %s "$1"',
                                    "preview2": "", "hint": "more", "newLabel": ""})

    def test_pick_returns_new_text_and_cancel(self):
        self.stub("quickshell", body="""( sleep 0.05; printf 'new\\ntyped text\\n' > "$9" ) &""")
        p = self.run_cmd("amadeus-pick", "--new", "Name", input="")
        self.assertEqual((p.returncode, p.stdout), (2, "typed text\n"))
        self.stub("quickshell", body="""( sleep 0.05; printf 'cancel\\n' > "$9" ) &""")
        p = self.run_cmd("amadeus-pick", "Choose", input="")
        self.assertEqual((p.returncode, p.stdout), (1, ""))

    def test_pick_says_so_when_the_shell_is_not_running(self):
        self.stub("quickshell", rc=1)
        p = self.run_cmd("amadeus-pick", "Choose", input="")
        self.assertEqual(p.returncode, 1)
        self.assertIn("desktop shell is not running", p.stderr)

    def test_menu_routes_capture_to_the_screenshot_tool(self):
        self.picker("Capture", "Screenshot\tarea")
        self.stub("amadeus-screenshot")
        p = self.run_cmd("amadeus-menu", "trigger")
        self.assert_ok(p)
        self.assertEqual(self.calls_of("amadeus-screenshot"), [["area"]])

    def test_menu_builds_a_remove_command_without_running_it(self):
        self.picker("Packages", "htop")
        self.stub("pacman", body="[[ $1 == -Qqe ]] && printf 'htop\\n'")
        self.stub("amadeus-terminal")
        p = self.run_cmd("amadeus-menu", "remove")
        self.assert_ok(p)
        self.assertIn("sudo pacman -Rns -- htop", " ".join(self.calls_of("amadeus-terminal")[-1]))
        self.assertEqual(self.calls_of("sudo"), [])

    def test_menu_routes_to_display_setup(self):
        self.picker("Display")
        self.stub("amadeus-display")
        p = self.run_cmd("amadeus-menu", "setup")
        self.assert_ok(p)
        self.assertEqual(self.calls_of("amadeus-display"), [[]])

    # ---- capture, display and small helpers ---------------------------------
    def hyprctl_json(self, monitors=None, clients=None, active=None):
        """One stand-in for hyprctl, answering the queries these commands make."""
        monitors = monitors or [{"name": "eDP-1", "focused": True, "x": 0, "y": 0, "width": 1920, "height": 1080,
                                 "scale": 1.0, "transform": 0, "refreshRate": 60.0,
                                 "activeWorkspace": {"id": 1}, "availableModes": ["1920x1080@60.00Hz", "1280x720@60.00Hz"]}]
        clients = clients or []
        self.stub("hyprctl", body=f"""case "$*" in
  "-j monitors") cat <<'JSON'
{json.dumps(monitors)}
JSON
    ;;
  "-j clients") cat <<'JSON'
{json.dumps(clients)}
JSON
    ;;
  "-j activewindow") cat <<'JSON'
{json.dumps(active or {})}
JSON
    ;;
  *) exit 0 ;;
esac""")

    def test_area_returns_a_drag_a_window_and_the_screen(self):
        self.hyprctl_json(clients=[
            {"at": [100, 100], "size": [400, 300], "workspace": {"id": 1}, "hidden": False},
            {"at": [600, 100], "size": [800, 600], "workspace": {"id": 1}, "hidden": False}])
        self.stub("slurp", body='cat >/dev/null; [[ ${SLURP_EXIT:-0} != 0 ]] && exit 1; printf "%s\\n" "$SLURP"')
        drag = self.run_cmd("amadeus-area", env={"SLURP": "10,20 300x200"})
        self.assertEqual(drag.stdout.strip(), "10,20 300x200")          # a drag is used as drawn
        window = self.run_cmd("amadeus-area", env={"SLURP": "150,150 0x0"})
        self.assertEqual(window.stdout.strip(), "100,100 400x300")      # a click is the window under it
        empty = self.run_cmd("amadeus-area", env={"SLURP": "1500,900 0x0"})
        self.assertEqual(empty.stdout.strip(), "0,0 1920x1080")         # a click on nothing is the screen
        cancelled = self.run_cmd("amadeus-area", env={"SLURP": "", "SLURP_EXIT": "1"})
        self.assertEqual(cancelled.returncode, 1)
        self.assertEqual(cancelled.stdout, "")

    def test_area_freezes_and_releases_the_screen(self):
        self.hyprctl_json()
        self.stub("slurp", body="cat >/dev/null; echo '0,0 10x10'")
        self.stub("hyprpicker", body="exec sleep 30")
        p = self.run_cmd("amadeus-area", "--freeze")
        self.assert_ok(p)
        self.assertIn("-r", self.calls_of("hyprpicker")[0])
        self.assertIn("-z", self.calls_of("hyprpicker")[0])

    def test_display_writes_and_checks_the_setting(self):
        self.hyprctl_json()
        answers = self.tmp / "display.answers"
        self.stub("amadeus-pick", body=f"""n=$(cat {answers} 2>/dev/null || echo 0); n=$((n + 1)); echo $n >{answers}
cat >/dev/null
[[ $n == 1 ]] && echo Resolution || echo '1920x1080@60.00'""")
        self.stub("Hyprland", output="config ok")
        self.stub("notify-send")
        hyprland = self.config / "hypr/hyprland.lua"
        hyprland.parent.mkdir(parents=True)
        hyprland.write_text("-- config\n")
        self.assert_ok(self.run_cmd("amadeus-display"))
        written = (self.config / "hypr/display.lua").read_text()
        self.assertIn('hl.monitor({ output = "eDP-1", mode = "1920x1080@60.00", position = "auto", scale = 1.0 })', written)
        self.assertEqual(self.calls_of("hyprctl")[-1], ["reload"])

    def test_display_puts_the_old_file_back_when_the_desktop_rejects_it(self):
        self.hyprctl_json()
        answers = self.tmp / "display.answers"
        self.stub("amadeus-pick", body=f"""n=$(cat {answers} 2>/dev/null || echo 0); n=$((n + 1)); echo $n >{answers}
cat >/dev/null
[[ $n == 1 ]] && echo Scale || echo 1.25""")
        self.stub("Hyprland", output="config error")
        self.stub("notify-send")
        hyprland = self.config / "hypr/hyprland.lua"
        hyprland.parent.mkdir(parents=True)
        hyprland.write_text("-- config\n")
        display = self.config / "hypr/display.lua"
        display.write_text("-- old setting\n")
        p = self.run_cmd("amadeus-display")
        self.assertEqual(p.returncode, 1)
        self.assertEqual(display.read_text(), "-- old setting\n")
        self.assertIn("Display setting not applied", " ".join(self.calls_of("notify-send")[-1]))

    def test_display_text_size(self):
        self.stub("gsettings", output="1.0")
        self.assertEqual(self.run_cmd("amadeus-display", "text").stdout.strip(), "100%")
        set_size = self.run_cmd("amadeus-display", "text", "125%")
        self.assert_ok(set_size)
        self.assertEqual(self.calls_of("gsettings")[-1],
                         ["set", "org.gnome.desktop.interface", "text-scaling-factor", "1.25"])

    def test_screenshot_screen_is_saved_and_copied(self):
        self.hyprctl_json()
        self.stub("xdg-user-dir", output=str(self.home / "Pictures"))
        self.stub("grim", body=': >"$3"')
        self.stub("wl-copy", body="cat >/dev/null")
        self.stub("notify-send")
        p = self.run_cmd("amadeus-screenshot", "screen")
        self.assert_ok(p)
        shots = list((self.home / "Pictures/Screenshots").glob("screenshot-*.png"))
        self.assertEqual(len(shots), 1)
        self.assertIn("--type", self.calls_of("wl-copy")[0])
        self.assertTrue(any("Screenshot copied" in c for c in self.calls_of("notify-send")))

    def test_recording_starts_by_name_and_stops_cleanly(self):
        self.hyprctl_json()
        self.stub("amadeus-area", output="0,0 1920x1080")
        self.stub("xdg-user-dir", output=str(self.home / "Videos"))
        # A background job in a non-interactive shell ignores SIGINT, so this stand-in stops
        # by itself shortly after starting; stop still has to clean up after it.
        self.stub("gpu-screen-recorder", body="""out=""
while [[ $# -gt 0 ]]; do [[ $1 == -o ]] && out=$2; shift; done
: >"$out"
sleep 0.5""")
        self.stub("ffprobe", output="3.5")
        self.stub("ffmpeg")
        self.stub("notify-send")
        started = self.run_cmd("amadeus-record", "screen")
        self.assert_ok(started)
        pidfile = self.run_dir / "amadeus-record.pid"
        for _ in range(100):
            if pidfile.exists():
                break
            time.sleep(0.02)
        self.assertTrue(pidfile.exists())
        self.addCleanup(lambda: self.stop_stray_recorder(pidfile))
        recorder = self.calls_of("gpu-screen-recorder")[0]
        self.assertIn("eDP-1", recorder)                    # the whole screen is recorded by monitor name
        self.assertIn("-f", recorder)
        self.assert_ok(self.run_cmd("amadeus-record", "stop"))
        self.assertFalse(pidfile.exists())
        files = list((self.home / "Videos").glob("screenrecording-*.mp4"))
        self.assertEqual(len(files), 1)

    def test_gpu_run_sets_the_offload_variables(self):
        self.stub("probe", output="", body='printf "%s|%s|%s\n" "$__NV_PRIME_RENDER_OFFLOAD" "$__GLX_VENDOR_LIBRARY_NAME" "$__VK_LAYER_NV_optimus"')
        p = self.run_cmd("amadeus-gpu-run", "probe")
        self.assert_ok(p)
        self.assertEqual(p.stdout.strip(), "1|nvidia|NVIDIA_only")

    def test_clipboard_history_and_clear(self):
        clip = self.tmp / "clipboard"
        self.stub("cliphist", body=f"""case "$1" in
  list) printf '1\tone\n2\ttwo\n' ;;
  decode) cat >{clip} ;;
  wipe) touch {self.tmp}/wiped ;;
esac""")
        self.stub("amadeus-pick", output="2\ttwo", body="cat >/dev/null")
        self.stub("wl-copy", body="cat >/dev/null")
        self.assert_ok(self.run_cmd("amadeus-clipboard"))
        self.assertEqual(clip.read_text(), "2\ttwo")
        self.assertEqual(self.calls_of("wl-copy"), [[]])
        self.assert_ok(self.run_cmd("amadeus-clipboard", "clear"))
        self.assertTrue((self.tmp / "wiped").exists())

    def test_menu_builds_an_install_command_without_running_it(self):
        answers = self.tmp / "picker.count"
        self.stub("amadeus-pick", body=f"""n=$(cat {answers} 2>/dev/null || echo 0); n=$((n + 1)); echo $n >{answers}
cat >/dev/null
[[ $n == 1 ]] && echo Packages || echo htop""")
        self.stub("pacman", body="""[[ $1 == -Slq ]] && printf 'htop\\nvim\\n'""")
        self.stub("amadeus-terminal")
        self.stub("sudo")
        self.assert_ok(self.run_cmd("amadeus-menu", "install"))
        command = " ".join(self.calls_of("amadeus-terminal")[-1])
        self.assertIn("sudo pacman -S --needed -- htop", command)
        self.assertEqual(self.calls_of("sudo"), [])   # only handed to a terminal, never run here


if __name__ == "__main__":
    unittest.main(verbosity=2)
