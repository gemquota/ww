import unittest
from types import SimpleNamespace

from src.ww_client import WWClient


class FakeGemini:
    def __init__(self, *_):
        self.chat_calls = []
        self.recent_limit = None

    async def init(self, **_):
        return None

    async def _fetch_recent_chats(self, recent):
        self.recent_limit = recent

    def start_chat(self, **kwargs):
        chat = SimpleNamespace(cid="new-chat", metadata=kwargs.get("metadata"))
        self.chat_calls.append((chat, kwargs))
        return chat

    async def read_chat(self, cid, limit=10):
        output = SimpleNamespace(
            metadata=[cid, "response-id"],
            candidates=[SimpleNamespace(rcid="candidate-id")],
        )
        return SimpleNamespace(
            turns=[SimpleNamespace(role="model", model_output=output)]
        )


class WWClientResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_resume_uses_latest_candidate_metadata(self):
        instances = []

        def factory(*args):
            client = FakeGemini(*args)
            instances.append(client)
            return client

        ww = WWClient("cookie", client_factory=factory, recent_chats=25)
        await ww.resume_conversation("existing-chat")

        self.assertEqual(instances[0].recent_limit, 25)
        self.assertEqual(
            instances[0].chat_calls[-1][1]["metadata"],
            ["existing-chat", "response-id", "candidate-id"],
        )
        await ww.close()


if __name__ == "__main__":
    unittest.main()
