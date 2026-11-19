#!/usr/bin/python3
"""Cross-file checks: the parts of the system that have to agree with each other.

The bar, the theme, the shortcuts and the package lists are written in more than one
place by design. These tests fail when one copy is changed and another is not, which
is otherwise only visible on a running system. No display, container or network is
needed; ./build.sh check runs them."""
import ast, glob, json, re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HYPR = ROOT / "desktop/system/usr/share/amadeus/default/hypr"
THEME = ROOT / "desktop/theme/theme.json"
BIN = ROOT / "desktop/bin"


def read(path):
    return Path(path).read_text()


def between(text, start, end=r"\n\s*\}\)"):
    m = re.search(re.escape(start) + r"(.*?)" + end, text, re.S)
    return m.group(1) if m else ""




def parse_theme_qml():
    values = {}
    for key, fallback in re.findall(r'pick\("AMA_([A-Z0-9_]+)",\s*"([^"]*)"\)', read(ROOT / "ai/shell/components/Theme.qml")):
        values[key.lower()] = fallback
    return values



def repo_commands():
    names = set()
    for d in ("desktop/bin", "ai/bin", "installer", "iso/live", "desktop/system/usr/share/amadeus/bin"):
        for f in (ROOT / d).rglob("*"):
            if f.is_file():
                names.add(f.name)
    return names


class BarTest(unittest.TestCase):
    def test_the_assistant_knows_every_bar_section(self):
        tree = ast.parse(read(ROOT / "ai/amadeus/tools/desktop.py"))
        sections = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                        and getattr(n.targets[0], "id", "") == "SECTIONS")
        shipped = json.loads(read(ROOT / "desktop/system/usr/share/amadeus/config/amadeus/shell.json"))["bar"]["layout"]
        self.assertTrue(set(shipped) <= set(sections), f"the bar has sections {set(shipped) - set(sections)} the assistant does not know")


class ThemeTest(unittest.TestCase):
    def setUp(self):
        self.theme = json.loads(read(THEME))
        self.qml = parse_theme_qml()


    def test_the_shared_component_defaults_match_the_theme_file(self):
        for key, value in self.theme.items():
            self.assertIn(key, self.qml, f"Theme.qml has no fallback for {key}")
            self.assertEqual(self.qml[key], str(value), f"Theme.qml's {key} differs from theme.json")


class ShortcutTest(unittest.TestCase):
    def setUp(self):
        self.binds = []
        self.files = {}
        for path in sorted(HYPR.rglob("*.lua")):
            for line in read(path).splitlines():
                m = re.match(r'\s*o\.bind\(\s*"([^"]+)",\s*"([^"]*)"(?:,\s*"([^"]*)")?', line)
                if m:
                    self.binds.append(m.groups())
                    self.files.setdefault(re.sub(r"\s*\+\s*", " + ", m.group(1).strip().upper()), set()).add(path.name)

    def test_every_shortcut_has_a_description(self):
        self.assertGreaterEqual(len(self.binds), 25)
        for keys, description, _ in self.binds:
            self.assertTrue(description.strip(), f"{keys} has no description")

    def test_no_shortcut_is_claimed_by_two_modules(self):
        # Within one module a key may run several actions in order (Alt+Tab focuses, then
        # raises); two modules binding the same key is a clash.
        for keys, files in self.files.items():
            self.assertEqual(len(files), 1, f"{keys} is bound in {sorted(files)}")

    def test_named_amadeus_commands_exist(self):
        names = repo_commands()
        for keys, _, command in self.binds:
            first = (command or "").split()[0] if command else ""
            if first.startswith(("amadeus-", "ama")):
                self.assertIn(first, names, f"{keys} runs {first}, which is not in the repository")


class ComponentTest(unittest.TestCase):
    def test_qmldir_lists_every_component(self):
        directory = ROOT / "ai/shell/components"
        listed = {}
        for line in read(directory / "qmldir").splitlines():
            parts = line.split()
            if len(parts) >= 2 and not parts[0].startswith("#"):
                if parts[0] == "singleton":
                    listed[parts[1]] = parts[2]
                else:
                    listed[parts[0]] = parts[-1]
        files = {p.stem for p in directory.glob("*.qml")}
        self.assertEqual(set(listed), files)
        for name, file in listed.items():
            self.assertTrue((directory / file).is_file(), f"qmldir's {name} points at missing {file}")



class UseTest(unittest.TestCase):
    def test_every_theme_property_used_exists(self):
        theme = read(ROOT / "ai/shell/components/Theme.qml")
        known = set(re.findall(r"(?:readonly\s+)?property\s+\w+\s+(\w+)\s*:", theme))
        known |= set(re.findall(r"function\s+(\w+)", theme))
        self.assertIn("accent", known)
        for path in (ROOT / "ai/shell").rglob("*.qml"):
            for name in set(re.findall(r"Theme\.(\w+)", read(path))):
                self.assertIn(name, known, f"{path.name} uses Theme.{name}, which Theme.qml does not define")


class CoverageTest(unittest.TestCase):
    def test_every_shipped_command_is_exercised(self):
        tests = read(ROOT / "test/selftest.sh") + read(ROOT / "test/test_commands.py")
        commands = sorted(p.name for p in BIN.iterdir() if p.is_file())
        self.assertGreaterEqual(len(commands), 10)
        for name in commands:
            self.assertIn(name, tests, f"{name} is not exercised by the self-test or the command tests")


class PackageListTest(unittest.TestCase):
    def lists(self):
        return {p: [w for line in read(p).splitlines() if not line.startswith("#") for w in line.split()]
                for p in sorted(ROOT.glob("installer/packages.*"))}

    def test_lists_hold_only_clean_package_names(self):
        lists = self.lists()
        self.assertIn(ROOT / "installer/packages.base", lists)
        for path, packages in lists.items():
            self.assertTrue(packages, f"{path.relative_to(ROOT)} is empty")
            for name in packages:
                self.assertRegex(name, r"^[a-z0-9@._+-]+$", f"{path.name}: {name!r} is not a package name")

    def test_no_package_is_listed_twice(self):
        seen = {}
        for path, packages in self.lists().items():
            for name in packages:
                self.assertNotIn(name, seen, f"{name} is in both {seen.get(name)} and {path.name}")
                seen[name] = path.name

    def test_the_try_session_list_is_clean(self):
        packages = [w for line in read(ROOT / "iso/live/packages.try").splitlines() if not line.startswith("#") for w in line.split()]
        self.assertEqual(len(packages), len(set(packages)))
        for name in packages:
            self.assertRegex(name, r"^[a-z0-9@._+-]+$")

    def test_the_installer_reads_each_list_by_name(self):
        text = read(ROOT / "installer/amadeus-install")
        for name in ("base", "desktop", "apps", "system", "extras", "aur"):
            self.assertIn(f"packages.{name}", text, f"amadeus-install never reads packages.{name}")

    def test_the_named_kernel_is_installed(self):
        installer = read(ROOT / "installer/amadeus-install")
        kernel = re.search(r"^K=(\S+)$", installer, re.M)
        self.assertIsNotNone(kernel, "amadeus-install does not name the kernel once in K=")
        packages = self.lists()[ROOT / "installer/packages.base"]
        self.assertIn(kernel.group(1), packages, f"K={kernel.group(1)} is not installed by packages.base")
        hardware = dict(line.split("\t", 1) for line in read(ROOT / "desktop/hardware/packages.list").splitlines()
                        if line and not line.startswith("#"))
        for name in ("gpu-nvidia", "gpu-nvidia-legacy"):
            self.assertTrue(any(p.startswith(kernel.group(1) + "-nvidia") for p in hardware[name].split()),
                            f"the {name} module does not follow the named kernel")

    def test_every_hardware_line_is_detected_and_names_clean_packages(self):
        script = read(ROOT / "desktop/bin/amadeus-hardware")
        for line in read(ROOT / "desktop/hardware/packages.list").splitlines():
            if not line or line.startswith("#"):
                continue
            name, packages = line.split("\t")
            self.assertRegex(script, rf"\b{re.escape(name)}\b", f"amadeus-hardware never detects {name}")
            for p in packages.split():
                self.assertRegex(p, r"^((hw|t2):)?[a-z0-9@._+-]+$", f"{name}: {p!r} is not a package name")


class BuildReferenceTest(unittest.TestCase):
    def referenced_paths(self, path, variable):
        for raw in read(path).splitlines():
            line = raw.split("#", 1)[0]
            for ref in re.findall(rf"\${variable}/([A-Za-z0-9_./*{{}},+-]+)", line):
                ref = ref.rstrip(".,")
                for expanded in self.expand_braces(ref):
                    yield expanded

    @staticmethod
    def expand_braces(ref):
        m = re.search(r"\{([^{}]+)\}", ref)
        if not m:
            return [ref]
        return [ref[:m.start()] + part + rest
                for part in m.group(1).split(",")
                for rest in BuildReferenceTest.expand_braces(ref[m.end():])]

    def test_every_source_path_the_build_scripts_name_exists(self):
        # $startdir in a PKGBUILD is that package's directory; $SRC in mkiso.sh is the tree.
        for path, variable, base in ((ROOT / "iso/mkiso.sh", "$SRC", ROOT),
                                     (ROOT / "desktop/PKGBUILD", "$src", ROOT / "desktop"),
                                     (ROOT / "ai/PKGBUILD", "$src", ROOT / "ai")):
            for ref in self.referenced_paths(path, variable.lstrip("$")):
                where = base
                # The ISO build places the installer's package lists in the desktop package as packages/.
                if base.name == "desktop" and (ref == "packages" or ref.startswith("packages/")):
                    where, ref = ROOT / "installer", ref[len("packages/"):] or "."
                matches = glob.glob(str(where / ref))
                self.assertTrue(matches, f"{path.name} names {variable}/{ref}, which does not exist")


class CatalogueTest(unittest.TestCase):
    def test_optional_clients_are_absent_from_default_package_lists(self):
        defaults = set()
        for name in ("apps", "extras", "aur"):
            for line in read(ROOT / ("installer/packages." + name)).splitlines():
                if not line.startswith("#"):
                    defaults.update(line.split())
        self.assertFalse(defaults & {"steam", "protonplus", "discord", "telegram-desktop", "claude-desktop"})

    def test_optional_menus_use_only_official_repository_sources(self):
        expected = {"gaming": {"pacman:multilib/steam"},
                    "chat": {"pacman:extra/discord", "pacman:extra/telegram-desktop"}}
        for category, sources in expected.items():
            actual = set()
            for line in read(ROOT / ("desktop/catalog/" + category + ".list")).splitlines():
                if line.strip() and not line.startswith("#"):
                    actual.update(line.split("\t", 1)[1].split())
            self.assertEqual(actual, sources)

    def test_every_catalogue_line_names_a_source(self):
        files = sorted((ROOT / "desktop/catalog").glob("*.list"))
        self.assertTrue(files)
        for path in files:
            for line in read(path).splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                self.assertIn("\t", line, f"{path.name}: {line!r} has no tab before its sources")
                title, sources = line.split("\t", 1)
                self.assertTrue(title.strip())
                for source in sources.split():
                    self.assertRegex(source, r"^(pacman|aur|mise):[^:\s]+$", f"{path.name}: {source!r}")

    def test_system_repositories_come_before_the_aur(self):
        # The order the catalogue documents and the commands enforce: official builds first.
        for path in sorted((ROOT / "desktop/catalog").glob("*.list")):
            for line in read(path).splitlines():
                if not line.strip() or line.startswith("#") or "\t" not in line:
                    continue
                seen_aur = False
                for source in line.split("\t", 1)[1].split():
                    if source.startswith("aur:"):
                        seen_aur = True
                    elif source.startswith("pacman:"):
                        self.assertFalse(seen_aur, f"{path.name}: {line!r} lists the AUR before the repositories")


if __name__ == "__main__":
    unittest.main(verbosity=2)
