from types import SimpleNamespace

import pytest

from src.core_chat import GeminiWebChat


class FakeChat:
    def __init__(self):
        self.messages = []

    async def send_message(self, prompt):
        self.messages.append(prompt)
        return SimpleNamespace(text=f"reply: {prompt}")


class FakeClient:
    def __init__(self, cookie, cookie_ts):
        self.credentials = (cookie, cookie_ts)
        self.chat = FakeChat()
        self.init_calls = 0

    async def init(self, **kwargs):
        self.init_calls += 1

    def start_chat(self):
        return self.chat


@pytest.mark.asyncio
async def test_send_connects_once_and_preserves_conversation():
    clients = []

    def factory(cookie, cookie_ts):
        client = FakeClient(cookie, cookie_ts)
        clients.append(client)
        return client

    gemini = GeminiWebChat("cookie", "cookie-ts", client_factory=factory)
    assert await gemini.send("first") == "reply: first"
    assert await gemini.send("second") == "reply: second"
    assert len(clients) == 1
    assert clients[0].init_calls == 1
    assert clients[0].chat.messages == ["first", "second"]


@pytest.mark.asyncio
async def test_missing_credentials_fail_clearly():
    gemini = GeminiWebChat("", "", client_factory=FakeClient)
    with pytest.raises(RuntimeError, match="credentials are missing"):
        await gemini.connect()


@pytest.mark.asyncio
async def test_empty_prompt_is_rejected():
    gemini = GeminiWebChat("cookie", "cookie-ts", client_factory=FakeClient)
    with pytest.raises(ValueError, match="must not be empty"):
        await gemini.send("   ")


@pytest.mark.asyncio
async def test_new_conversation_replaces_chat():
    class RotatingClient(FakeClient):
        def __init__(self, cookie, cookie_ts):
            super().__init__(cookie, cookie_ts)
            self.chats = [self.chat]

        def start_chat(self):
            chat = FakeChat()
            self.chats.append(chat)
            return chat

    clients = []
    def factory(cookie, cookie_ts):
        client = RotatingClient(cookie, cookie_ts)
        clients.append(client)
        return client

    gemini = GeminiWebChat("cookie", "cookie-ts", client_factory=factory)
    await gemini.send("before")
    old_chat = gemini.chat
    await gemini.new_conversation()
    assert gemini.chat is not old_chat
    assert gemini.chat.messages == []


@pytest.mark.asyncio
async def test_send_wraps_transport_errors():
    class BrokenChat:
        async def send_message(self, prompt):
            raise OSError("network down")

    class BrokenClient(FakeClient):
        def start_chat(self):
            return BrokenChat()

    gemini = GeminiWebChat("cookie", "cookie-ts", client_factory=BrokenClient)
    with pytest.raises(ConnectionError, match="network down"):
        await gemini.send("hello")
