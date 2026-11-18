"""Regression tests for terminal prompt input configuration."""

import unittest
from unittest.mock import patch

from src.prompting import create_terminal_session


class TerminalPromptTests(unittest.TestCase):
    @patch("src.prompting.PromptSession")
    def test_terminal_session_enables_multiline_input(self, prompt_session):
        create_terminal_session(style="test-style", complete_while_typing=True)
        prompt_session.assert_called_once_with(
            multiline=True,
            style="test-style",
            complete_while_typing=True,
        )


if __name__ == "__main__":
    unittest.main()
