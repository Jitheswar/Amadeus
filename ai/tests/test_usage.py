"""Display-safe subscription quota collection."""
import json, tempfile, unittest
from pathlib import Path
from unittest import mock
from amadeus import config, usage


class UsageTest(unittest.TestCase):
    def test_bad_usage_numbers_do_not_become_percentages(self):
        for value in (True, "nan", "inf", None):
            self.assertIsNone(usage.fraction(value))
        self.assertEqual(usage.fraction(0.25), 0.25)

    def test_antigravity_handles_exhausted_and_disabled_quota_windows(self):
        self.assertEqual(usage.quota_used({"resetTime": "2026-11-16T00:00:00Z"}), 1)
        self.assertEqual(usage.quota_used({"remainingAmount": "0"}), 1)
        self.assertEqual(usage.quota_used({"remainingFraction": 0.25}), 0.75)
        self.assertIsNone(usage.quota_used({"remainingAmount": "100"}))
        self.assertIsNone(usage.quota_used({"disabled": True, "remainingFraction": 0}))
        self.assertIsNone(usage.quota_used({"remainingFraction": True}))

    def test_claude_only_returns_display_safe_limits(self):
        with mock.patch.object(usage, "read_json", return_value={"claudeAiOauth": {"accessToken": "private-token", "subscriptionType": "pro"}}), mock.patch.object(
                usage, "request", return_value={"five_hour": {"utilization": 25, "resets_at": "2026-11-15T00:00:00Z"}, "seven_day": None}):
            data = usage.claude()
        self.assertEqual(data[0][0]["used"], 0.25)
        self.assertNotIn("private-token", json.dumps(data))

    def test_usage_cache_tracks_a_changed_default(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(config, "STATE", Path(root)):
            (Path(root) / "usage.json").write_text(json.dumps({"checked": usage.time.time(), "providers": [], "default": "claude-cli"}))
            self.assertEqual(usage.collect({"ai": {"provider": "codex-cli"}})["default"], "codex-cli")
