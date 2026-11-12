import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.ww_settings import (
    assign_chat_folder,
    chats_in_folder,
    folder_names,
    load_settings,
    save_settings,
)


class WWSettingsTests(unittest.TestCase):
    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ww" / "settings.json"
            with patch("src.ww_settings.settings_path", return_value=path):
                settings = load_settings()
                settings["chat_page_size"] = 20
                settings["default_model"] = "gemini-pro"
                save_settings(settings)
                loaded = load_settings()
            self.assertEqual(loaded["chat_page_size"], 20)
            self.assertEqual(loaded["default_model"], "gemini-pro")
            self.assertEqual(loaded["chat_folders"], {})

    def test_local_chat_folders(self):
        chats = [
            SimpleNamespace(cid="a", title="Alpha"),
            SimpleNamespace(cid="b", title="Beta"),
            SimpleNamespace(cid="c", title="Gamma"),
        ]
        settings = {"chat_folders": {}}
        assign_chat_folder(settings, "a", "Project Alpha")
        assign_chat_folder(settings, "b", "  project   alpha ")
        assign_chat_folder(settings, "c", "Personal")
        self.assertEqual(folder_names(settings), ["Personal", "Project Alpha"])
        self.assertEqual(
            [chat.cid for chat in chats_in_folder(chats, settings, "PROJECT ALPHA")],
            ["a", "b"],
        )
        assign_chat_folder(settings, "a", None)
        self.assertEqual(
            [chat.cid for chat in chats_in_folder(chats, settings, "Project Alpha")],
            ["b"],
        )


if __name__ == "__main__":
    unittest.main()
