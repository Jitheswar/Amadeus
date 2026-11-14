#!/usr/bin/python3
"""Regressions for selecting the QML checker and interpreting its diagnostics."""
import json, subprocess, unittest
from unittest import mock
import test_qml


class QmlCheckerTest(unittest.TestCase):
    def result(self, warnings, success=False, code=1):
        return subprocess.CompletedProcess([], code, json.dumps({"files": [
            {"filename": "x.qml", "success": success, "warnings": warnings}]}), "")

    def test_syntax_errors_fail_but_import_warnings_do_not(self):
        self.assertTrue(test_qml.diagnostics(self.result([{"id": "syntax", "message": "bad token", "line": 2}])))
        self.assertEqual(test_qml.diagnostics(self.result([{"id": "import", "message": "Quickshell not found"}])), [])
        self.assertEqual(test_qml.diagnostics(self.result([], success=True, code=0)), [])

    def test_broken_or_unrecognized_output_cannot_pass(self):
        for output in ("", "file:2 : Expected token", "null", "{}", '{"files": []}'):
            with self.subTest(output=output):
                self.assertTrue(test_qml.diagnostics(subprocess.CompletedProcess([], 1, output, "")))
        self.assertTrue(test_qml.diagnostics(self.result([])))
        self.assertTrue(test_qml.diagnostics(self.result([{"message": "unknown format"}])))

    def test_unversioned_qt5_is_never_selected(self):
        def find(candidate):
            return "/fake/qmllint" if candidate == "qmllint" else None
        with mock.patch.object(test_qml.shutil, "which", side_effect=find), mock.patch.object(
                test_qml.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "qmllint 5.15.18", "")):
            self.assertIsNone(test_qml.find_qmllint())

    def test_explicit_qt6_is_preferred(self):
        with mock.patch.object(test_qml.shutil, "which", side_effect=lambda name: "/fake/" + name), mock.patch.object(
                test_qml.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "qmllint 6.12.0", "")):
            self.assertEqual(test_qml.find_qmllint(), "/fake/qmllint6")


if __name__ == "__main__":
    unittest.main()
