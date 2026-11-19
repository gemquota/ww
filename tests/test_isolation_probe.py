import unittest

from scripts.probe_isolation import collect_report


class IsolationProbeTests(unittest.TestCase):
    def test_probe_is_diagnostic_only_even_when_indicators_exist(self):
        report = collect_report(executable_lookup=lambda name: "/usr/bin/bwrap")
        self.assertEqual(report["result"], "diagnostic_only")
        self.assertIs(report["sandbox_accepted"], False)
        self.assertIn("network isolation", " ".join(report["limitations"]))

    def test_probe_does_not_require_bubblewrap(self):
        report = collect_report(executable_lookup=lambda name: None)
        self.assertIsNone(report["indicators"]["bwrap_path_available"])
        self.assertIs(report["sandbox_accepted"], False)

    def test_namespace_inventory_is_boolean_only(self):
        report = collect_report()
        self.assertTrue(all(
            isinstance(value, bool)
            for value in report["indicators"]["namespace_handles_present"].values()
        ))


if __name__ == "__main__":
    unittest.main()
