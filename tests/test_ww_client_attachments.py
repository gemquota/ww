import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.ww_client import WWClient


class AttachmentChat:
    def __init__(self):
        self.calls = []

    async def send_message(self, prompt, files=None):
        self.calls.append((prompt, files))
        return SimpleNamespace(text="attached")


class AttachmentGemini:
    def __init__(self, *_):
        self.chat = AttachmentChat()

    async def init(self, **_):
        return None

    def start_chat(self, **_):
        return self.chat


class WWClientAttachmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_ask_output_attaches_existing_local_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "context.json"
            path.write_text("{}", encoding="utf-8")
            ww = WWClient("cookie", client_factory=AttachmentGemini)
            output = await ww.ask_output("Review this project", files=[path])
            self.assertEqual(output.text, "attached")
            self.assertEqual(ww._chat.calls, [("Review this project", [str(path)])])
            await ww.close()

    async def test_missing_attachment_fails_before_network_request(self):
        ww = WWClient("cookie", client_factory=AttachmentGemini)
        with self.assertRaises(FileNotFoundError):
            await ww.ask_output("Review this", files=["/definitely/missing/context.json"])
        self.assertIsNone(ww._client)
        await ww.close()


if __name__ == "__main__":
    unittest.main()
