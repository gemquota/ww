import io
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from gemini_bridge import choose_startup_chat, format_chat_date


class ChatPickerTests(unittest.TestCase):
    def test_date_is_fixed_width_year_free_and_zero_padded(self):
        stamp = datetime(2026, 1, 5, 9, 4).timestamp()
        self.assertEqual(format_chat_date(stamp), "05/01 09:04")
        self.assertEqual(len(format_chat_date(stamp)), 11)
        self.assertEqual(format_chat_date(None), " " * 11)

    def test_pagination_and_page_relative_selection(self):
        chats = [
            SimpleNamespace(cid=str(index), title=f"Chat {index}", timestamp=0)
            for index in range(5)
        ]
        output = io.StringIO()
        with patch("builtins.input", side_effect=[">", "1"]), patch("sys.stdout", output):
            selected = choose_startup_chat(chats, page_size=2)
        self.assertEqual(selected, 2)
        self.assertIn("page 1/3", output.getvalue())
        self.assertIn("page 2/3", output.getvalue())

    def test_new_chat_and_cancel_choices(self):
        chats = [SimpleNamespace(cid="1", title="Chat", timestamp=0)]
        with patch("builtins.input", return_value="n"):
            self.assertIsNone(choose_startup_chat(chats))
        with patch("builtins.input", return_value="q"):
            self.assertEqual(choose_startup_chat(chats), -1)


if __name__ == "__main__":
    unittest.main()
