#!/usr/bin/python3
"""Behaviour tests for the desktop commands. Run by ./build.sh check.

Every external program these commands talk to is a stand-in: nothing here starts a
session, changes a package, asks for a password or touches the user's own files.
The commands are run from the repository, in a throwaway HOME, with a PATH whose
first entry holds the stand-ins and whose result is checked."""
import gzip, json, os, shlex, shutil, subprocess, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from unittest import mock

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
    def test_seeded_package_indexes_fetch_updated_data_instead_of_http_304(self):
        from functools import partial
        from email.utils import formatdate
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
        medium, target, remote = (self.tmp / x for x in ("medium", "sync", "remote"))
        medium.mkdir(); remote.mkdir()
        (medium / "extra.db").write_bytes(b"old database from the medium")
        (remote / "extra.db").write_bytes(b"new database matching the current signature")
        published = int(time.time()) - 3600
        os.utime(remote / "extra.db", (published, published))
        class Quiet(SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(remote)))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        url = f"http://127.0.0.1:{server.server_port}/extra.db"
        try:
            # The old copy-at-install-time behaviour incorrectly produces Not Modified.
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url, headers={"If-Modified-Since": formatdate(time.time(), usegmt=True)}), timeout=3)
            self.assertEqual(error.exception.code, 304)
            error.exception.close()
            result = subprocess.run([sys.executable, str(ROOT / "iso/live/amadeus-seed-package-lists"), str(medium), str(target)], capture_output=True, text=True)
            self.assert_ok(result)
            request = Request(url, headers={"If-Modified-Since": formatdate((target / "extra.db").stat().st_mtime, usegmt=True)})
            with urlopen(request, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), (remote / "extra.db").read_bytes())
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3)

    def test_seeding_keeps_existing_validated_package_indexes(self):
        medium, target = self.tmp / "medium", self.tmp / "sync"
        medium.mkdir(); target.mkdir()
        (medium / "extra.db").write_bytes(b"old snapshot")
        (target / "extra.db").write_bytes(b"already refreshed")
        (target / "extra.db.sig").write_bytes(b"matching signature")
        before = (target / "extra.db").stat().st_mtime_ns
        result = subprocess.run([sys.executable, str(ROOT / "iso/live/amadeus-seed-package-lists"), str(medium), str(target)], capture_output=True, text=True)
        self.assert_ok(result)
        self.assertEqual((target / "extra.db").read_bytes(), b"already refreshed")
        self.assertEqual((target / "extra.db.sig").read_bytes(), b"matching signature")
        self.assertEqual((target / "extra.db").stat().st_mtime_ns, before)
        self.assertEqual(list(target.glob(".amadeus-seed-*")), [])

    def test_launcher_hides_dependency_helpers_but_keeps_explicit_apps(self):
        ns = {"__name__": "launcher_validation"}
        exec(compile((BIN / "amadeus-launcher").read_text(), "launcher", "exec"), ns)
        user, system = self.tmp / "user-desktops", self.tmp / "system-desktops"
        user.mkdir(); system.mkdir()
        for name in ("helper", "wanted"):
            (system / (name + ".desktop")).write_text("[Desktop Entry]\nName=" + name + "\nExec=true\n")
        ns["DIRS"] = [user, system]
        self.stub("pacman", body=f'''case "$1" in
  -Qqe) printf 'wanted-package\n' ;;
  -Qo) printf '%s is owned by helper-package 1\n%s is owned by wanted-package 1\n' {system}/helper.desktop {system}/wanted.desktop ;;
esac''')
        with mock.patch.dict(os.environ, {"PATH": self.env["PATH"]}):
            self.assertEqual(set(ns["entries"]()), {"wanted"})
            (user / "helper.desktop").write_text("[Desktop Entry]\nName=My helper\nExec=true\n")
            self.assertEqual(set(ns["entries"]()), {"wanted", "helper"})

    def test_search_indexes_apps_and_every_menu_entry_without_running_them(self):
        self.stub("amadeus-launcher", output='[{"id":"files","label":"Files","keywords":"folders"}]')
        result = self.run_cmd("amadeus-search", "--index")
        self.assert_ok(result)
        data = {x["id"]: x for x in json.loads(result.stdout)}
        self.assertIn("files", data["app:files"]["keywords"])
        self.assertEqual(data["menu:appearance.theme"]["path"], "Amadeus › Appearance")
        self.assertIn("menu:update.hardware.audio", data)
        self.assertEqual(self.calls_of("sudo"), [])
        self.assertNotEqual(self.run_cmd("amadeus-search", "--run", "menu:not.an.entry").returncode, 0)

    def test_search_opens_a_menu_entry_in_the_menu(self):
        self.stub("amadeus-menu")
        self.assert_ok(self.run_cmd("amadeus-search", "--run", "menu:appearance.theme"))
        for _ in range(50):
            if self.calls_of("amadeus-menu"):
                break
            time.sleep(0.01)
        self.assertEqual(self.calls_of("amadeus-menu"), [["summon", "appearance.theme"]])

    def test_qualified_repository_packages_are_detected_as_installed(self):
        catalog = self.tmp / "qualified-catalog"
        catalog.mkdir()
        (catalog / "gaming.list").write_text("Steam\tpacman:multilib/steam\n")
        self.stub("pacman", body='case "$1" in -Sl) echo "multilib steam 1.0-1" ;; -Qq) echo steam ;; esac')
        result = self.run_cmd("amadeus-catalog", "gaming", env={"AMADEUS_CATALOG": str(catalog)})
        self.assert_ok(result)
        self.assertIn("Steam  (installed)\tpacman:multilib/steam", result.stdout)

    def test_launcher_hides_listed_helpers_but_not_personal_entries(self):
        ns = {"__name__": "launcher_validation"}
        exec(compile((BIN / "amadeus-launcher").read_text().rsplit("\nmain()", 1)[0], "amadeus-launcher", "exec"), ns)
        user, system = self.tmp / "user-apps", self.tmp / "system-apps"
        user.mkdir(); system.mkdir()
        shipped = ROOT / "desktop/launcher.hides"
        personal = self.tmp / "launcher.hides"
        personal.write_text("# mine\nnoisy.desktop\n")
        ns["DIRS"], ns["HIDES"] = [user, system], [shipped, personal]
        for name in ("uuctl", "lftp", "vim", "noisy", "org.gnome.Nautilus", "btop"):
            (system / (name + ".desktop")).write_text("[Desktop Entry]\nName=" + name + "\nExec=true\n")
        self.assertEqual(set(ns["entries"]()), {"org.gnome.Nautilus", "btop"})
        (user / "vim.desktop").write_text("[Desktop Entry]\nName=My Vim\nExec=true\n")
        self.assertIn("vim", ns["entries"]())

    def test_launcher_applies_user_precedence_before_eligibility(self):
        ns = {"__name__": "launcher_validation"}
        source = (BIN / "amadeus-launcher").read_text().rsplit("\nmain()", 1)[0]
        exec(compile(source, "amadeus-launcher", "exec"), ns)
        user, system = self.tmp / "user-apps", self.tmp / "system-apps"
        user.mkdir()
        system.mkdir()
        ns["DIRS"] = [user, system]
        (system / "same.desktop").write_text("[Desktop Entry]\nName=System\nExec=true\n")
        for field in ("TryExec=definitely-not-installed", "Hidden=true", "NoDisplay=true"):
            with self.subTest(field=field):
                (user / "same.desktop").write_text("[Desktop Entry]\nName=User\nExec=true\n" + field + "\n")
                self.assertNotIn("same", ns["entries"]())
        (user / "same.desktop").write_text("[Desktop Entry]\nName=User\nExec=true\n")
        self.assertEqual(ns["entries"]()["same"]["Name"], "User")

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
            "AMADEUS_MENU": str(ROOT / "desktop/menu/menu.jsonc"),
            "AMADEUS_TEST_CALLS": str(self.calls), "AMADEUS_TRY_MARKER": str(self.tmp / "not-a-live-session"),
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
# One write per call: stand-ins run side by side in pipelines, and separate
# writes to the shared log would interleave.
line={shlex.quote(name)}
for a in "$@"; do line+=$'\\t'"$a"; done
printf '%s\\n' "$line" >> "$AMADEUS_TEST_CALLS"
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
    # ---- web apps -----------------------------------------------------------
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

    def test_launcher_reports_a_program_that_is_gone(self):
        self.write_entry("gone", Name="Gone App", Exec="definitely-not-installed-app")
        self.stub("amadeus-pick", output="Gone App\tgone", body="cat >/dev/null")
        self.stub("notify-send")
        p = self.run_cmd("amadeus-launcher")
        self.assert_ok(p)
        self.assertNotIn("Traceback", p.stderr)
        self.assertIn("Could not open Gone App", " ".join(self.calls_of("notify-send")[-1]))
        self.assertIn("definitely-not-installed-app was not found", " ".join(self.calls_of("notify-send")[-1]))

    def test_launcher_hides_an_entry_whose_tryexec_is_missing(self):
        self.write_entry("try", Name="Try App", Exec="whatever", TryExec="definitely-not-installed")
        listed = self.run_cmd("amadeus-launcher", "--print").stdout
        self.assertNotIn("Try App", listed)

    def test_launcher_hides_entries_that_ask_to_be_hidden(self):
        self.write_entry("visible", Name="Visible", Exec="visible")
        self.write_entry("hidden", Name="Hidden", Exec="hidden", NoDisplay="true")
        listed = self.run_cmd("amadeus-launcher", "--print").stdout
        self.assertIn("Visible\tvisible", listed)
        self.assertNotIn("Hidden", listed)

    # ---- theme ----------------------------------------------------------------
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
        self.stub("pacman", body="""case "$1" in
  -Sl) echo "extra foot 1.0-1 [installed]" ;;
  -Qq) echo foot ;;
esac""")
        self.stub("amadeus-aur", body="""case "$1" in
  list) echo kitty-git ;;
esac""")
        self.stub("mise", body="""case "$1" in
  registry) echo "opencode  aqua:sst/opencode" ;;
esac""")
        self.stub("amadeus-harness")
        env = {"AMADEUS_CATALOG": str(cat)}
        self.assertEqual(self.run_cmd("amadeus-catalog", env=env).stdout, "terminal\n")
        listed = self.run_cmd("amadeus-catalog", "terminal", env=env)
        self.assert_ok(listed)
        self.assertIn("Foot  (installed)\tpacman:foot", listed.stdout)
        self.assertIn("Kitty  (AUR)\taur:kitty-git", listed.stdout)
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

    # ---- AUR -----------------------------------------------------------------
    def test_aur_info_and_recipe_come_from_the_aur(self):
        record = {"results": [{"Name": "demo", "Version": "1.2-3", "Description": "A demo", "URL": "https://example.org",
                               "Maintainer": "someone", "NumVotes": 7, "Popularity": 1.25, "LastModified": 0,
                               "OutOfDate": None, "Depends": ["libfoo"], "MakeDepends": ["cmake"]}]}
        self.stub("curl", body=f"""case "$*" in
  *rpc/v5/info*) cat <<'JSON'
{json.dumps(record)}
JSON
    ;;
  *cgit/aur.git/plain/PKGBUILD*) printf 'pkgname=demo\\n' ;;
esac""")
        info = self.run_cmd("amadeus-aur", "info", "demo")
        self.assert_ok(info)
        self.assertIn("Name           : demo", info.stdout)
        self.assertIn("Version        : 1.2-3", info.stdout)
        self.assertIn("Maintainer     : someone", info.stdout)
        self.assertIn("Needs          : libfoo", info.stdout)
        recipe = self.run_cmd("amadeus-aur", "recipe", "demo")
        self.assertEqual(recipe.stdout, "pkgname=demo\n")

    def test_aur_rpc_encodes_a_name_with_a_plus(self):
        """A + in a package name is a space in a raw query string; curl must encode it."""
        (self.bin / "curl").unlink(missing_ok=True)
        if shutil.which("curl", path=self.env["PATH"]) is None:
            self.skipTest("the real curl is needed for the local server")
        queries = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                queries.append(parse_qs(urlparse(self.path).query))
                body = json.dumps({"results": [{"Name": "libsigc++", "Version": "1.0", "Description": "",
                                                "URL": "", "Maintainer": "m", "NumVotes": 1, "Popularity": 0,
                                                "LastModified": 0, "OutOfDate": None, "Depends": [], "MakeDepends": []}]}).encode()
                self.send_response(200)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            p = self.run_cmd("amadeus-aur", "info", "libsigc++",
                             env={"AMADEUS_AUR": f"http://127.0.0.1:{server.server_port}"})
        finally:
            server.shutdown()
            server.server_close()
        self.assert_ok(p)
        self.assertEqual(queries[0]["arg[]"], ["libsigc++"])
        self.assertIn("Name           : libsigc++", p.stdout)

    def test_aur_recipe_encodes_a_name_with_a_plus(self):
        (self.bin / "curl").unlink(missing_ok=True)
        if shutil.which("curl", path=self.env["PATH"]) is None:
            self.skipTest("the real curl is needed for the local server")
        queries = []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                queries.append(parse_qs(urlparse(self.path).query))
                body = b"pkgname=libsigc++\n"
                self.send_response(200)
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            p = self.run_cmd("amadeus-aur", "recipe", "libsigc++",
                             env={"AMADEUS_AUR": f"http://127.0.0.1:{server.server_port}"})
        finally:
            server.shutdown()
            server.server_close()
        self.assert_ok(p)
        self.assertEqual(queries[0]["h"], ["libsigc++"])
        self.assertIn("pkgname=libsigc++", p.stdout)

    def test_aur_list_uses_and_refreshes_its_cache(self):
        cache = self.tmp / "cache/amadeus-aur"
        cache.mkdir(parents=True)
        (cache / "names").write_text("one\ntwo\n")
        env = {"XDG_CACHE_HOME": str(self.tmp / "cache")}
        listed = self.run_cmd("amadeus-aur", "list", env=env)
        self.assertEqual(listed.stdout, "one\ntwo\n")
        self.assertEqual(self.calls_of("curl"), [])
        old = time.time() - 3 * 24 * 60 * 60
        os.utime(cache / "names", (old, old))
        payload = self.tmp / "names.gz"
        with gzip.open(payload, "wb") as f:
            f.write(b"three\nfour\n")
        self.stub("curl", body=f"""case "$*" in
  *packages.gz*) cat {payload} ;;
esac""")
        refreshed = self.run_cmd("amadeus-aur", "list", env=env)
        self.assertEqual(refreshed.stdout, "three\nfour\n")

    def test_aur_install_builds_through_stand_ins_without_asking(self):
        body = "\n".join([
            'dest="${@: -1}"',
            'mkdir -p "$dest"',
            "printf 'pkgname = demo\\n' > \"$dest/PKGBUILD\"",
            "printf 'pkgname = demo\\n\\tpkgver = 1.2\\n' > \"$dest/.SRCINFO\"",
        ])
        self.stub("git", body=body)
        self.stub("pacman", body='case "$1 $2" in "-Si demo") exit 1 ;; *) exit 0 ;; esac')
        self.stub("makepkg")
        p = self.run_cmd("amadeus-aur", "install", "demo", env={"AMADEUS_AUR_YES": "1"})
        self.assert_ok(p)
        self.assertIn("git", " ".join(self.calls_of("git")[0]))
        self.assertEqual(self.calls_of("makepkg"), [["-sif", "--needed", "--noconfirm"]])

    def test_overlapping_aur_builds_have_independent_recipe_directories(self):
        from concurrent.futures import ThreadPoolExecutor
        cache = self.tmp / "cache/amadeus-aur"
        self.stub("pacman", rc=1)
        self.stub("git", body='''dest="${@: -1}"
mkdir "$dest" || exit 1
touch "$dest/PKGBUILD" "$dest/.SRCINFO"''')
        self.stub("makepkg", body='''touch "$SYNC/$RUN"
for ((i=0; i<100; i++)); do
  [[ -e $SYNC/one && -e $SYNC/two ]] && exit 0
  sleep 0.02
done
exit 1''')
        def install(run):
            return self.run_cmd("amadeus-aur", "install", "demo", env={
                "RUN": run, "SYNC": str(self.tmp), "XDG_CACHE_HOME": str(cache.parent),
                "AMADEUS_AUR_YES": "1"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(install, ("one", "two")):
                self.assert_ok(result)
        destinations = {call[-1] for call in self.calls_of("git")}
        self.assertEqual(len(destinations), 2)
        self.assertEqual(list(cache.iterdir()), [])

    def test_failed_shared_aur_dependency_skips_both_apps(self):
        self.stub("git", body='''dest="${@: -1}"
mkdir -p "$dest"
touch "$dest/PKGBUILD" "$dest/.SRCINFO"
case ${dest##*/} in
  first|second) echo "depends = shared" > "$dest/.SRCINFO" ;;
esac''')
        self.stub("pacman", rc=1)
        builds = self.tmp / "builds"
        self.stub("makepkg", body=f'basename "$PWD" >> {builds}; [[ ${{PWD##*/}} != shared ]] || exit 1')
        p = self.run_cmd("amadeus-aur", "install", "first", "second", "independent",
                         env={"AMADEUS_AUR_YES": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(builds.read_text().splitlines(), ["shared", "independent"])
        self.assertIn("second was skipped", p.stdout)

    def test_aur_install_shows_the_recipe_and_can_be_declined(self):
        body = "\n".join([
            'dest="${@: -1}"',
            'mkdir -p "$dest"',
            "printf 'pkgname = demo\\n' > \"$dest/PKGBUILD\"",
            "printf 'pkgname = demo\\n\\tsource = https://example.org/demo-1.2.tar.gz\\n' > \"$dest/.SRCINFO\"",
        ])
        self.stub("git", body=body)
        self.stub("pacman", body='case "$1 $2" in "-Si demo") exit 1 ;; *) exit 0 ;; esac')
        self.stub("makepkg")
        p = self.run_cmd("amadeus-aur", "install", "demo", input="n\n")
        self.assertEqual(p.returncode, 1)
        self.assertIn("Downloads from", p.stdout)
        self.assertIn("https://example.org/demo-1.2.tar.gz", p.stdout)
        self.assertEqual(self.calls_of("makepkg"), [])

    def test_aur_refuses_a_package_the_repositories_have(self):
        # The stub package manager answers "this is in a repository", as pacman does for foot.
        p = self.run_cmd("amadeus-aur", "install", "foot")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("system repositories", p.stdout)
        self.assertEqual(self.calls_of("git"), [])

    # ---- updating ------------------------------------------------------------
    UPDATE_ENV = {"AMADEUS_UPDATE_LOGGED": "1", "AMADEUS_UPDATE_AWAKE": "1", "AMADEUS_UPDATE_FORCE": "1"}

    def test_update_prunes_the_cache_then_snapshots_then_updates_keys_and_packages(self):
        self.stub("amadeus-aur")
        self.stub("amadeus-harness")
        self.stub("amadeus-mirrors")
        p = self.run_cmd("amadeus-update", "-y", env=self.UPDATE_ENV)
        self.assert_ok(p)
        self.assertIn("Snapshot taken", p.stdout)
        self.assertEqual([c[0] for c in self.calls_of("sudo")], ["true", "paccache", "snapper", "snapper", "amadeus-mirrors", "pacman", "pacman"])
        self.assertEqual(self.calls_of("sudo")[1], ["paccache", "-rk2"])
        self.assertEqual(self.calls_of("sudo")[5], ["pacman", "-Sy", "--needed", "--noconfirm", "archlinux-keyring", "cachyos-keyring"])
        self.assertEqual(self.calls_of("sudo")[-1], ["pacman", "-Su", "--noconfirm"])

    def test_update_removes_orphans_and_runs_new_migrations_once(self):
        for n in ("amadeus-aur", "amadeus-harness", "amadeus-mirrors"): self.stub(n)
        self.stub("pacman", body='[[ $1 == -Qtdq ]] && echo old-dep; true')
        migrations = self.tmp / "migrations"; migrations.mkdir()
        (migrations / "1.sh").write_text(f"# First change\necho ran >>{self.tmp}/ran\n")
        env = dict(self.UPDATE_ENV, AMADEUS_MIGRATIONS=str(migrations))
        self.assert_ok(self.run_cmd("amadeus-update", "-y", env=env))
        self.assertIn(["pacman", "-Rns", "--noconfirm", "old-dep"], self.calls_of("sudo"))
        self.assert_ok(self.run_cmd("amadeus-update", "-y", env=env))
        self.assertEqual((self.tmp / "ran").read_text(), "ran\n")
        self.assertNotEqual(self.run_cmd("amadeus-migrate", "--pending", env=env).returncode, 0)

    def test_unreachable_aur_reports_incomplete_update_and_runs_harness_stage(self):
        self.stub("pacman", output="demo\n")
        self.stub("curl", rc=22)
        self.stub("amadeus-harness")
        p = self.run_cmd("amadeus-update", "-y", env=self.UPDATE_ENV)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("applications from it were not checked", p.stderr)
        self.assertIn("Retry with amadeus-aur update", p.stderr)
        self.assertEqual(self.calls_of("amadeus-harness"), [["update"]])

    def test_update_in_the_try_session_skips_the_snapshot(self):
        marker = self.tmp / "try-session"
        marker.touch()
        self.stub("amadeus-aur")
        self.stub("amadeus-harness")
        self.stub("amadeus-mirrors")
        p = self.run_cmd("amadeus-update", "-y", env=dict(self.UPDATE_ENV, AMADEUS_TRY_MARKER=str(marker)))
        self.assert_ok(p)
        self.assertIn("Try session", p.stdout)
        self.assertNotIn("snapper", [c[0] for c in self.calls_of("sudo")])

    # ---- mirrors -------------------------------------------------------------
    def mirror_stubs(self, arch=("arch.example",)):
        d = self.tmp / "pacman.d"
        d.mkdir()
        self.env["AMADEUS_TEST_ARCH_MIRRORS"] = " ".join(arch)
        self.stub("reflector", body="""save=""; prev=""
for a in "$@"; do [[ $prev == --save ]] && save=$a; prev=$a; done
for host in $AMADEUS_TEST_ARCH_MIRRORS; do printf 'Server = https://%s/$repo/os/$arch\\n' "$host"; done > "$save"
""")
        self.stub("curl", body="""case "$*" in
  *archlinux.org/mirrors/status/json*) exit 0 ;;
  *time_connect*) case "${@: -1}" in
      *far.example*) printf '200\\t0.01\\t0.90\\t%s\\n' "${@: -1}" ;;
      *dead.example*) exit 7 ;;
      *) printf '200\\t0.01\\t0.02\\t%s\\n' "${@: -1}" ;;
    esac ;;
  *stale.example*) printf '0.05\\tMon, 02 Nov 2026 10:00:00 GMT' ;;
  *far.example*) printf '0.30\\tMon, 16 Nov 2026 10:00:00 GMT' ;;
  *cachyos*) printf '0.10\\tMon, 16 Nov 2026 09:00:00 GMT' ;;
  *) exit 0 ;;
esac
""")
        return d

    def test_mirrors_print_the_official_choice_without_changing(self):
        d = self.mirror_stubs()
        (d / "cachyos-v3-mirrorlist").write_text(
            "# official list\nServer = https://cachyos.example/$arch_v3/$repo\n")
        p = self.run_cmd("amadeus-mirrors", "--print", env={"AMADEUS_MIRROR_DIR": str(d)})
        self.assert_ok(p)
        self.assertIn("Server = https://arch.example/$repo/os/$arch", p.stdout)
        self.assertIn("Server = https://cachyos.example/$arch_v3/$repo", p.stdout)
        self.assertFalse((d / "mirrorlist").exists(), "printing must not write a mirror list")

    def test_mirrors_test_the_speed_of_the_nearest_not_the_best_scored(self):
        hosts = [f"m{i}.example" for i in range(4)] + ["far.example", "dead.example", "de.cdn.example", "us.cdn.example"]
        d = self.mirror_stubs(arch=hosts)
        self.assert_ok(self.run_cmd("amadeus-mirrors", "--print", env={"AMADEUS_MIRROR_DIR": str(d)}))
        survey, ranking = self.calls_of("reflector")
        self.assertNotIn("--sort", survey)
        self.assertNotIn("--score", ranking)
        pool = ranking[ranking.index("--include") + 1]
        self.assertTrue(pool.startswith("^(") and pool.endswith(r"far\.example/)"), pool)      # the slowest to connect comes last
        self.assertIn(r"https://m0\.example/", pool)
        self.assertNotIn("dead", pool)
        self.assertEqual(pool.count("cdn"), 1, "aliases of one network are one candidate")

    def test_mirrors_fall_back_to_the_status_score_when_probing_fails(self):
        d = self.mirror_stubs(arch=("dead.example",))
        self.assert_ok(self.run_cmd("amadeus-mirrors", "--print", env={"AMADEUS_MIRROR_DIR": str(d)}))
        self.assertIn("--score", self.calls_of("reflector")[-1])

    def test_mirrors_drop_a_stale_cachyos_mirror_and_put_the_fastest_first(self):
        d = self.mirror_stubs()
        (d / "cachyos-v3-mirrorlist").write_text("".join(
            f"Server = https://{h}/$arch_v3/$repo\n" for h in ("far.example", "stale.example", "cachyos.example")))
        p = self.run_cmd("amadeus-mirrors", "--print", env={"AMADEUS_MIRROR_DIR": str(d)})
        self.assert_ok(p)
        listed = [line for line in p.stdout.split("CachyOS:")[1].splitlines() if line]
        self.assertEqual(listed, ["Server = https://cachyos.example/$arch_v3/$repo", "Server = https://far.example/$arch_v3/$repo"])

    # ---- shortcuts ----------------------------------------------------------
    # ---- harnesses ----------------------------------------------------------
    def test_harness_list_install_run_and_remove(self):
        tool_bin = self.tmp / "installs/claude/2.1/bin"
        tool_bin.mkdir(parents=True)
        claude = tool_bin / "claude"
        claude.write_text("#!/bin/bash\necho claude \"$@\"\n")
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
    # ---- the System menu ---------------------------------------------------------
    # ---- the update command -------------------------------------------------
    def test_update_snapshot_is_numbered_and_tools_update_last(self):
        self.stub("amadeus-aur")
        self.stub("amadeus-harness")
        p = self.run_cmd("amadeus-update", "-y", env=self.UPDATE_ENV)
        self.assert_ok(p)
        sudo = self.calls_of("sudo")
        snap = next(c for c in sudo if c[0] == "snapper")
        self.assertEqual(snap[:7], ["snapper", "-c", "root", "create", "--cleanup-algorithm", "number", "--description"])
        self.assertTrue(snap[7].startswith("before update "))
        self.assertIn(["snapper", "-c", "root", "cleanup", "number"], sudo)
        names = [line.split("\t")[0] for line in self.calls.read_text().splitlines()]
        self.assertEqual(names[-2:], ["amadeus-aur", "amadeus-harness"])

    # ---- the menu builds commands without running them ----------------------
    # ---- the picker itself and the menu that drives it -----------------------
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

    def screenshot_stubs(self):
        self.stub("xdg-user-dir", output=str(self.home / "Pictures"))
        self.stub("grim", body=': >"$3"')
        self.stub("wl-copy", body="cat >/dev/null")
        self.stub("notify-send")

    def recorder_stub(self):
        # A background job in a non-interactive shell ignores SIGINT, so this stand-in
        # stops by itself shortly after starting.
        self.stub("gpu-screen-recorder", body="""out=""
while [[ $# -gt 0 ]]; do [[ $1 == -o ]] && out=$2; shift; done
: >"$out"
sleep 0.5""")

    def monitor(self, name, width, height, mm_w, mm_h, scale=1.0, focused=True):
        return {"name": name, "focused": focused, "x": 0, "y": 0, "width": width, "height": height, "physicalWidth": mm_w,
                "physicalHeight": mm_h, "scale": scale, "transform": 0, "refreshRate": 60.0, "activeWorkspace": {"id": 1},
                "availableModes": [f"{width}x{height}@60.00Hz"]}

    def test_hooks_run_every_script_and_report_failures(self):
        hooks = self.config / "amadeus/hooks"; (hooks / "post-update.d").mkdir(parents=True)
        (hooks / "post-update").write_text(f'echo "main $1" >>{self.tmp}/hooks\n')
        (hooks / "post-update.d/a").write_text(f'echo "a $1" >>{self.tmp}/hooks\n')
        (hooks / "post-update.d/b").write_text("exit 3\n")
        (hooks / "post-update.d/c.sample").write_text(f'echo sample >>{self.tmp}/hooks\n')
        p = self.run_cmd("amadeus-hook", "post-update", "x")
        self.assert_ok(p)
        self.assertEqual((self.tmp / "hooks").read_text().splitlines(), ["main x", "a x"])
        self.assertIn("Hook failed", p.stderr)
        self.assertNotEqual(self.run_cmd("amadeus-hook", "../escape").returncode, 0)

    def test_version_reports_the_desktop_package(self):
        self.stub("pacman", body='[[ $2 == amadeus-desktop ]] && echo "amadeus-desktop 0.1.0-1"; true')
        self.assertEqual(self.run_cmd("amadeus-version").stdout.strip(), "0.1.0-1")

    def fake_machine(self, pci, dmi=None, cpu=("GenuineIntel", 154), battery=True, intel_names="00:02.0 VGA compatible controller: Intel Corporation Iris Xe Graphics"):
        """A sysfs and /proc for amadeus-hardware: PCI devices as (vendor, device, class)."""
        sys_, proc = self.tmp / "sys", self.tmp / "proc"
        for i, (v, d, c) in enumerate(pci):
            dev = sys_ / f"bus/pci/devices/0000:0{i}:00.0"; dev.mkdir(parents=True)
            for k, val in (("vendor", v), ("device", d), ("class", c)): (dev / k).write_text(val + "\n")
        ident = sys_ / "class/dmi/id"; ident.mkdir(parents=True)
        for k, val in (dmi or {}).items(): (ident / k).write_text(val + "\n")
        if battery: (sys_ / "class/power_supply/BAT0").mkdir(parents=True)
        proc.mkdir(); (proc / "cpuinfo").write_text(f"vendor_id\t: {cpu[0]}\nmodel\t\t: {cpu[1]}\n")
        (proc / "modules").write_text("")
        self.stub("lspci", output=intel_names + "\n")
        self.stub("systemd-detect-virt", rc=1)
        return {"AMADEUS_HW_SYS": str(sys_), "AMADEUS_HW_PROC": str(proc), "AMADEUS_HARDWARE_SHARE": str(ROOT / "desktop/hardware")}

    def test_hardware_picks_the_default_drivers_for_a_hybrid_asus_laptop(self):
        env = self.fake_machine([("0x8086", "0x9a49", "0x030000"), ("0x10de", "0x25a2", "0x030200"), ("0x14e4", "0x43a0", "0x028000")],
                                dmi={"sys_vendor": "ASUSTeK COMPUTER INC.", "product_family": "ROG Zephyrus G14", "product_name": "GA402"})
        names = self.run_cmd("amadeus-hardware", env=env).stdout.split()
        for n in ("cpu-intel", "gpu-intel", "gpu-intel-media", "gpu-nvidia", "gpu-hybrid", "wifi", "wifi-broadcom-wl", "asus-rog", "intel-lpmd", "intel-thermald"):
            self.assertIn(n, names)
        self.assertNotIn("gpu-nvidia-legacy", names)
        pkgs = self.run_cmd("amadeus-hardware", "packages", env=env).stdout.split()
        for p in ("intel-ucode", "linux-cachyos-nvidia-open", "nvidia-utils", "broadcom-wl-dkms", "asusctl", "thermald", "intel-media-driver"):
            self.assertIn(p, pkgs)
        self.assertNotIn("nvidia-580xx-utils", pkgs)
        repos = self.run_cmd("amadeus-hardware", "repos", env=env).stdout
        self.assertIn("SigLevel = Required", repos); self.assertNotIn("[arch-mact2]", repos)
        portable = self.run_cmd("amadeus-hardware", "--portable", "packages", env=env).stdout.split()
        self.assertIn("amd-ucode", portable); self.assertIn("vulkan-radeon", portable); self.assertNotIn("asusctl", portable)
        self.assertNotIn("nvidia-utils", self.run_cmd("amadeus-hardware", "--without", "gpu-nvidia", "packages", env=env).stdout.split())

    def test_hardware_writes_settings_into_a_target_root(self):
        env = self.fake_machine([("0x8086", "0x9a49", "0x030000"), ("0x10de", "0x25a2", "0x030200"), ("0x8086", "0x272b", "0x028000")])
        self.stub("systemctl")
        root = self.tmp / "target"; (root / "etc/conf.d").mkdir(parents=True); (root / "usr/share/zoneinfo").mkdir(parents=True)
        (root / "etc/conf.d/wireless-regdom").write_text("#WIRELESS_REGDOM=\"US\"\n")
        (root / "usr/share/zoneinfo/zone.tab").write_text("IN\t+2232+08822\tAsia/Kolkata\n")
        (root / "usr/share/zoneinfo/Asia").mkdir(); (root / "usr/share/zoneinfo/Asia/Kolkata").write_text("")
        (root / "etc/localtime").symlink_to(root / "usr/share/zoneinfo/Asia/Kolkata")
        p = self.run_cmd("amadeus-hardware", "apply", root, env=env)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("modeset=1", (root / "etc/modprobe.d/nvidia.conf").read_text())
        self.assertIn("fnmode=2", (root / "etc/modprobe.d/hid_apple.conf").read_text())
        self.assertIn("disable_11be=Y", (root / "etc/modprobe.d/iwlwifi-disable-eht.conf").read_text())
        self.assertIn('WIRELESS_REGDOM="IN"', (root / "etc/conf.d/wireless-regdom").read_text())
        enabled = [c for c in self.calls_of("systemctl") if "enable" in c]
        self.assertTrue(any("thermald.service" in c for c in enabled))
        self.assertTrue(any("nvidia-suspend" in c for c in enabled))

    def test_hardware_makes_the_dell_g15_5530_touchpad_bind_at_boot(self):
        env = self.fake_machine([("0x8086", "0xa788", "0x030000")], dmi={"sys_vendor": "Dell Inc.", "product_name": "Dell G15 5530"})
        self.stub("systemctl")
        root = self.tmp / "target"; root.mkdir()
        self.assertEqual(self.run_cmd("amadeus-hardware", "apply", root, env=env).returncode, 0)
        self.assertIn("pre: pinctrl_alderlake intel_lpss_pci", (root / "etc/modprobe.d/dell-g15-touchpad.conf").read_text())
        self.assertIn("intel_lpss_pci pinctrl_alderlake", (root / "etc/mkinitcpio.conf.d/dell-g15-touchpad.conf").read_text())
        # A G15 5535 is a different board.
        env["AMADEUS_HW_SYS"] = str(self.tmp / "sys")
        (self.tmp / "sys/class/dmi/id/product_name").write_text("Dell G15 5535\n")
        self.assertNotIn("dell-g15-touchpad", self.run_cmd("amadeus-hardware", env=env).stdout.split())

    def test_hardware_chooses_the_580xx_branch_and_t2_support(self):
        env = self.fake_machine([("0x10de", "0x1c8d", "0x030000"), ("0x106b", "0x1801", "0x108000")],
                                dmi={"sys_vendor": "Apple Inc.", "product_name": "MacBookPro16,1"})
        names = self.run_cmd("amadeus-hardware", env=env).stdout.split()
        self.assertIn("gpu-nvidia-legacy", names); self.assertNotIn("gpu-nvidia", names)
        self.assertIn("mac-t2", names); self.assertIn("mac-broadcom-wifi", names)
        pkgs = self.run_cmd("amadeus-hardware", "packages", env=env).stdout.split()
        self.assertIn("linux-cachyos-nvidia-580xx", pkgs); self.assertIn("t2:linux-t2", pkgs)
        self.assertIn("[arch-mact2]", self.run_cmd("amadeus-hardware", "repos", env=env).stdout)
        self.assertIn("intel_iommu=on", self.run_cmd("amadeus-hardware", "cmdline", env=env).stdout)

    def fake_gpus(self, *gpus):
        """Display controllers as (vendor, boot_vga) for amadeus-gpu."""
        for i, (vendor, boot) in enumerate(gpus):
            d = self.tmp / f"sys/bus/pci/devices/0000:0{i}:00.0"; d.mkdir(parents=True)
            for k, v in (("vendor", vendor), ("class", "0x030000"), ("boot_vga", boot)): (d / k).write_text(v + "\n")
        return {"AMADEUS_HW_SYS": str(self.tmp / "sys")}

    def test_gpu_modes_follow_the_dedicated_gpus_maker(self):
        env = self.fake_gpus(("0x1002", "1"), ("0x1002", "0"))
        self.assertEqual(self.run_cmd("amadeus-gpu", env=env).stdout.strip(), "auto")
        self.assertEqual(self.run_cmd("amadeus-gpu", "dedicated", env=env).stdout.strip(), "amd")
        self.assert_ok(self.run_cmd("amadeus-gpu", "set", "dedicated", env=env))
        session = (self.config / "uwsm/env-hyprland").read_text()
        self.assertIn("AQ_DRM_DEVICES=/dev/dri/dgpu-card:/dev/dri/igpu-card", session)
        self.assertIn("DRI_PRIME=1", session); self.assertNotIn("nvidia", session)
        self.assert_ok(self.run_cmd("amadeus-gpu", "set", "intel", env=env))
        self.assertEqual(self.run_cmd("amadeus-gpu", env=env).stdout.strip(), "integrated")
        self.assertNotIn("AQ_DRM_DEVICES", (self.config / "uwsm/env-hyprland").read_text())
        self.stub("probe", body='printf "%s|%s\n" "$DRI_PRIME" "$__NV_PRIME_RENDER_OFFLOAD"')
        self.assertEqual(self.run_cmd("amadeus-gpu-run", "probe", env=env).stdout.strip(), "1|")

    def test_gpu_reports_one_without_a_dedicated_card(self):
        env = self.fake_gpus(("0x8086", "1"))
        self.assertEqual(self.run_cmd("amadeus-gpu", env=env).stdout.strip(), "one")
        self.assertNotEqual(self.run_cmd("amadeus-gpu", "set", "dedicated", env=env).returncode, 0)

    def test_gpu_run_sets_the_offload_variables(self):
        self.stub("probe", output="", body='printf "%s|%s|%s\n" "$__NV_PRIME_RENDER_OFFLOAD" "$__GLX_VENDOR_LIBRARY_NAME" "$__VK_LAYER_NV_optimus"')
        p = self.run_cmd("amadeus-gpu-run", "probe")
        self.assert_ok(p)
        self.assertEqual(p.stdout.strip(), "1|nvidia|NVIDIA_only")

if __name__ == "__main__":
    unittest.main(verbosity=2)
