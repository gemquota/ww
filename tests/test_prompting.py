"""Regression tests for terminal prompt input configuration."""

import sys
import types
import unittest
from unittest.mock import Mock, patch

from src.prompting import create_terminal_session


class TerminalPromptTests(unittest.TestCase):
    def test_terminal_session_enables_multiline_input(self):
        prompt_session = Mock()
        fake_prompt_toolkit = types.SimpleNamespace(PromptSession=prompt_session)
        with patch.dict(sys.modules, {"prompt_toolkit": fake_prompt_toolkit}):
            create_terminal_session(style="test-style", complete_while_typing=True)
        prompt_session.assert_called_once_with(
            multiline=True,
            style="test-style",
            complete_while_typing=True,
        )


if __name__ == "__main__":
    unittest.main()
