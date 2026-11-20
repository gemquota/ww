"""Regression tests for WW terminal prompt configuration."""

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src.prompting import COMMANDS, create_terminal_session, history_file_path


class TerminalPromptTests(unittest.TestCase):
    def test_terminal_session_enables_multiline_history_and_completion(self):
        prompt_session = Mock()
        word_completer = Mock()
        file_history = Mock()
        fake_prompt_toolkit = types.SimpleNamespace(PromptSession=prompt_session)
        fake_completion = types.SimpleNamespace(WordCompleter=word_completer)
        fake_history = types.SimpleNamespace(FileHistory=file_history)

        with tempfile.TemporaryDirectory() as directory:
            history_path = Path(directory) / "state" / "ww" / "history"
            with patch.dict(os.environ, {"WW_HISTORY_FILE": str(history_path)}):
                with patch.dict(sys.modules, {
                    "prompt_toolkit": fake_prompt_toolkit,
                    "prompt_toolkit.completion": fake_completion,
                    "prompt_toolkit.history": fake_history,
                }):
                    create_terminal_session(style="test-style")

            self.assertTrue(history_path.parent.is_dir())
            file_history.assert_called_once_with(str(history_path))
            word_completer.assert_called_once_with(
                COMMANDS, ignore_case=True, sentence=True
            )
            prompt_session.assert_called_once()
            kwargs = prompt_session.call_args.kwargs
            self.assertTrue(kwargs["multiline"])
            self.assertTrue(kwargs["enable_history_search"])
            self.assertTrue(kwargs["complete_while_typing"])
            self.assertEqual(kwargs["style"], "test-style")

    def test_history_path_can_be_configured(self):
        with tempfile.TemporaryDirectory() as directory:
            configured = Path(directory) / "custom" / "history.txt"
            with patch.dict(os.environ, {"WW_HISTORY_FILE": str(configured)}):
                self.assertEqual(history_file_path(), configured)


if __name__ == "__main__":
    unittest.main()
