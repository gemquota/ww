import unittest
from unittest.mock import MagicMock

from src.terminal import COMMANDS, _command_completer, get_line_history, search_line_history


class TerminalHelperTests(unittest.TestCase):
    def test_command_completion_only_matches_slash_prefixes(self):
        self.assertEqual(_command_completer("/his", 0), "/history")
        self.assertIsNone(_command_completer("/his", 1))
        self.assertIsNone(_command_completer("hello", 0))
        self.assertIn("/stream", COMMANDS)

    def test_history_search_returns_newest_matches_with_original_indexes(self):
        history = ["first prompt", "/help", "second prompt", "FIRST followup"]
        self.assertEqual(
            search_line_history(history, "first"),
            [(4, "FIRST followup"), (1, "first prompt")],
        )

    def test_history_search_is_case_insensitive_and_bounded(self):
        history = [f"query {index}" for index in range(30)]
        matches = search_line_history(history, "QUERY", limit=3)
        self.assertEqual([index for index, _ in matches], [30, 29, 28])

    def test_readline_history_is_copied(self):
        readline = MagicMock()
        readline.get_current_history_length.return_value = 2
        readline.get_history_item.side_effect = ["one", "two"]
        self.assertEqual(get_line_history(readline, ["fallback"]), ["one", "two"])

    def test_fallback_history_is_not_mutated(self):
        fallback = ["one"]
        result = get_line_history(None, fallback)
        result.append("two")
        self.assertEqual(fallback, ["one"])


if __name__ == "__main__":
    unittest.main()
