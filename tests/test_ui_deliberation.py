import unittest

from src.ui_deliberation import _extract_json


class SystemTwoParsingTests(unittest.TestCase):
    def test_extracts_plain_json(self):
        self.assertEqual(_extract_json('{"action_id":"open","rationale":"safe"}')["action_id"], "open")

    def test_extracts_fenced_json(self):
        value = _extract_json('```json\n{"action_id":null,"rationale":"unclear"}\n```')
        self.assertIsNone(value["action_id"])

    def test_rejects_non_object(self):
        with self.assertRaises(ValueError):
            _extract_json('["open"]')


if __name__ == "__main__":
    unittest.main()
