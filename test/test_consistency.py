#!/usr/bin/python3
"""Cross-file checks: the parts of the system that have to agree with each other.

The bar, the theme, the shortcuts and the package lists are written in more than one
place by design. These tests fail when one copy is changed and another is not, which
is otherwise only visible on a running system. No display, container or network is
needed; ./build.sh check runs them."""
import ast, glob, json, re, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL = ROOT / "desktop/shell/shell.qml"
THEME = ROOT / "desktop/theme/theme.json"
BIN = ROOT / "desktop/bin"


def read(path):
    return Path(path).read_text()


def between(text, start, end=r"\n\s*\}\)"):
    m = re.search(re.escape(start) + r"(.*?)" + end, text, re.S)
    return m.group(1) if m else ""


def qml_object(text, declaration):
    """The body of a QML property written as an object literal."""
    m = re.search(re.escape(declaration) + r"\s*\(\{(.*?)\}\)", text, re.S)
    return m.group(1) if m else ""


def quoted_list(body, key):
    m = re.search(rf"\b{key}:\s*\[([^\]]*)\]", body, re.S)
    return re.findall(r'"([^"]*)"', m.group(1)) if m else None


def parse_theme_qml():
    values = {}
    for key, fallback in re.findall(r'pick\("AMA_([A-Z0-9_]+)",\s*"([^"]*)"\)', read(ROOT / "ai/shell/components/Theme.qml")):
        values[key.lower()] = fallback
    return values


def parse_shell_theme():
    body = qml_object(read(SHELL), "property var theme:")
    values = {}
    for key, text, number in re.findall(r'(\w+):\s*(?:"([^"]*)"|([0-9.]+))', body):
        values[key] = text if text else float(number) if "." in number else int(number)
    return values


def repo_commands():
    names = set()
    for d in ("desktop/bin", "ai/bin", "installer", "iso/live"):
        for f in (ROOT / d).rglob("*"):
            if f.is_file():
                names.add(f.name)
    return names


class BarTest(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(read(ROOT / "ai/amadeus/tools/desktop.py"))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("BAR_WIDGETS", "BAR_DEFAULT"):
                    values[node.targets[0].id] = ast.literal_eval(node.value)
        self.widgets = values["BAR_WIDGETS"]
        self.default = values["BAR_DEFAULT"]
        shell = read(SHELL)
        self.qml_layout = {}
        body = qml_object(shell, "property var layout:")
        for key in ("left", "center", "right"):
            self.qml_layout[key] = quoted_list(body, key)
        self.qml_widgets = re.findall(r"(\w+):\s*w\w+", qml_object(shell, "readonly property var widgets:"))

    def test_every_widget_has_a_component_and_a_name(self):
        self.assertTrue(self.widgets)
        self.assertEqual(sorted(self.qml_widgets), sorted(self.widgets))
        self.assertEqual(len(self.widgets), len(set(self.widgets)))

    def test_the_three_layout_copies_agree(self):
        shipped = json.loads(read(ROOT / "desktop/shell/bar.default.json"))
        self.assertEqual(self.qml_layout, self.default)
        self.assertEqual(shipped, self.default)

    def test_every_widget_is_in_the_bar_once(self):
        placed = [w for section in self.default.values() for w in section]
        self.assertEqual(sorted(placed), sorted(self.widgets))


class ThemeTest(unittest.TestCase):
    def setUp(self):
        self.theme = json.loads(read(THEME))
        self.shell = parse_shell_theme()
        self.qml = parse_theme_qml()

    def test_the_shell_defaults_match_the_theme_file(self):
        for key, value in self.theme.items():
            self.assertIn(key, self.shell, f"shell.qml has no default for {key}")
            self.assertEqual(self.shell[key], value, f"shell.qml's {key} differs from theme.json")

    def test_the_shared_component_defaults_match_the_theme_file(self):
        for key, value in self.theme.items():
            self.assertIn(key, self.qml, f"Theme.qml has no fallback for {key}")
            self.assertEqual(self.qml[key], str(value), f"Theme.qml's {key} differs from theme.json")


class ShortcutTest(unittest.TestCase):
    def setUp(self):
        self.lua = read(ROOT / "desktop/hypr/default.lua")
        self.binds = []
        for line in self.lua.splitlines():
            m = re.match(r'\s*o\.bind\("([^"]+)",\s*"([^"]*)"(?:,\s*"([^"]*)")?', line)
            if m:
                self.binds.append(m.groups())

    def test_every_shortcut_has_a_description(self):
        self.assertGreaterEqual(len(self.binds), 25)
        for keys, description, _ in self.binds:
            self.assertTrue(description.strip(), f"{keys} has no description")

    def test_no_shortcut_is_bound_twice(self):
        seen = {}
        for keys, _, _ in self.binds:
            normal = re.sub(r"\s*\+\s*", " + ", keys.strip().upper())
            self.assertNotIn(normal, seen, f"{keys} is bound twice")
            seen[normal] = keys

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


class IconTest(unittest.TestCase):
    def test_every_icon_used_is_drawn(self):
        paths = set(re.findall(r'"([a-z0-9-]+)":\s*"M', read(ROOT / "desktop/shell/Icon.qml")))
        self.assertTrue(paths)
        files = list((ROOT / "desktop/shell").glob("*.qml")) + list((ROOT / "ai/shell").rglob("*.qml"))
        for path in files:
            for line in read(path).splitlines():
                for expression in re.findall(r"\b(?:icon|name):\s*([^;\n}]+)", line):
                    for name in re.findall(r'"([a-z][a-z0-9-]+)"', expression):
                        self.assertIn(name, paths, f"{path.name} uses icon {name!r}, which Icon.qml does not draw")


class UseTest(unittest.TestCase):
    def test_every_theme_property_used_exists(self):
        theme = read(ROOT / "ai/shell/components/Theme.qml")
        known = set(re.findall(r"(?:readonly\s+)?property\s+\w+\s+(\w+)\s*:", theme))
        known |= set(re.findall(r"function\s+(\w+)", theme))
        self.assertIn("accent", known)
        for path in list((ROOT / "ai/shell").rglob("*.qml")) + list((ROOT / "desktop/shell").glob("*.qml")):
            for name in set(re.findall(r"Theme\.(\w+)", read(path))):
                self.assertIn(name, known, f"{path.name} uses Theme.{name}, which Theme.qml does not define")


class CoverageTest(unittest.TestCase):
    def test_every_shipped_command_is_exercised(self):
        tests = read(ROOT / "test/selftest.sh") + read(ROOT / "test/test_commands.py")
        commands = sorted(p.name for p in BIN.iterdir() if p.is_file())
        self.assertGreaterEqual(len(commands), 20)
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
        for name in ("base", "desktop", "apps", "nvidia"):
            self.assertIn(f"packages.{name}", text, f"amadeus-install never reads packages.{name}")

    def test_the_named_kernel_is_installed(self):
        installer = read(ROOT / "installer/amadeus-install")
        kernel = re.search(r"^K=(\S+)$", installer, re.M)
        self.assertIsNotNone(kernel, "amadeus-install does not name the kernel once in K=")
        packages = self.lists()[ROOT / "installer/packages.base"]
        self.assertIn(kernel.group(1), packages, f"K={kernel.group(1)} is not installed by packages.base")
        nvidia = self.lists()[ROOT / "installer/packages.nvidia"]
        self.assertTrue(any(p.startswith(kernel.group(1) + "-nvidia") for p in nvidia),
                        "the NVIDIA module does not follow the named kernel")


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
                matches = glob.glob(str(base / ref))
                self.assertTrue(matches, f"{path.name} names {variable}/{ref}, which does not exist")


class CatalogueTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
