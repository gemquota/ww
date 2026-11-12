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


class FakeResearchGemini(FakeGemini):
    def start_chat(self, **kwargs):
        async def send_message(prompt):
            return SimpleNamespace(text=f"response: {prompt}", images=[])
        chat = SimpleNamespace(
            cid="research-chat",
            metadata=kwargs.get("metadata"),
            send_message=send_message,
        )
        self.chat_calls.append((chat, kwargs))
        return chat

    async def create_deep_research_plan(self, prompt, chat=None):
        return SimpleNamespace(query=prompt, cid=chat.cid)

    async def start_deep_research(self, plan, chat=None):
        return SimpleNamespace(text="Research started")

    async def wait_for_deep_research(self, plan, poll_interval, timeout):
        return SimpleNamespace(done=True, document=SimpleNamespace(content="Report", ready=True))

    async def read_chat(self, cid, limit=10):
        document = SimpleNamespace(content="Completed report", ready=True)
        output = SimpleNamespace(deep_research_document=document)
        return SimpleNamespace(turns=[SimpleNamespace(role="model", model_output=output)])


class WWClientStructuredTests(unittest.IsolatedAsyncioTestCase):
    async def test_ask_output_preserves_the_structured_response(self):
        ww = WWClient("cookie", client_factory=FakeResearchGemini)
        output = await ww.ask_output("hello")
        self.assertEqual(output.text, "response: hello")
        await ww.close()

    async def test_ask_stream_yields_incremental_text(self):
        ww = WWClient("cookie", client_factory=FakeResearchGemini)
        await ww.connect()

        async def stream(prompt):
            yield SimpleNamespace(text_delta="hello")
            yield SimpleNamespace(text=" world")

        ww._chat.send_message_stream = stream
        chunks = [chunk async for chunk in ww.ask_stream("hello")]
        self.assertEqual(chunks, ["hello", " world"])
        await ww.close()

    async def test_ask_stream_falls_back_to_complete_response(self):
        ww = WWClient("cookie", client_factory=FakeResearchGemini)
        chunks = [chunk async for chunk in ww.ask_stream("fallback")]
        self.assertEqual(chunks, ["response: fallback"])
        await ww.close()

    async def test_deep_research_wrappers_use_active_chat(self):
        ww = WWClient("cookie", client_factory=FakeResearchGemini)
        plan = await ww.create_research_plan("Compare two ecosystems")
        self.assertEqual(plan.query, "Compare two ecosystems")
        await ww.start_research(plan)
        result = await ww.wait_for_research(plan, poll_interval=1, timeout=5)
        self.assertTrue(result.done)
        self.assertEqual(result.document.content, "Report")
        document = await ww.latest_research_document()
        self.assertEqual(document.content, "Completed report")
        await ww.close()


if __name__ == "__main__":
    unittest.main()
