import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

from src.conversation_runtime import ConversationRuntime, ToolFenceFilter, parse_tool_arguments
from src.tools.registry import ToolRegistry


class FakeApproval:
    def authorize(self, tool_name, arguments, permission_mgr=None):
        return True


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.connected = False
        self.active_chat_id = "fake-chat"

    async def connect(self):
        self.connected = True

    async def ask_output(self, prompt):
        self.prompts.append(prompt)
        text = self.responses.pop(0) if self.responses else "Finished."
        return SimpleNamespace(text=text)

    async def ask_stream(self, prompt):
        self.prompts.append(prompt)
        text = self.responses.pop(0) if self.responses else "Finished."
        for index in range(0, len(text), 7):
            yield text[index:index + 7]


class RuntimeProtocolTests(unittest.TestCase):
    def test_parse_json_arguments(self):
        self.assertEqual(
            parse_tool_arguments("write_file", '{"file_path":"a b.txt","content":"hi"}'),
            {"file_path": "a b.txt", "content": "hi"},
        )

    def test_parse_multiline_arguments_and_legacy_aliases(self):
        parsed = parse_tool_arguments(
            "replace",
            "filepath: notes.txt\nfind: before\nreplace:\nafter\nsecond line",
        )
        self.assertEqual(parsed, {
            "file_path": "notes.txt",
            "search_text": "before",
            "replace_text": "after\nsecond line",
        })

    def test_plain_command_body_is_supported(self):
        self.assertEqual(
            parse_tool_arguments("shell", "printf 'hello world'"),
            {"command": "printf 'hello world'"},
        )

    def test_stream_filter_hides_only_executable_tool_fences(self):
        fence = chr(96) * 3
        stream = ToolFenceFilter()
        visible = stream.feed(
            "Visible text\n" + fence + "python\nprint('keep')\n" + fence + "\n"
            + fence + "tool:read_file\nfile_path: secret.txt\n"
        )
        visible += stream.feed(fence + "\nFinal text")
        visible += stream.finish()
        self.assertEqual(
            visible,
            "Visible text\n" + fence + "python\nprint('keep')\n" + fence + "\nFinal text",
        )


class RegistryValidationTests(unittest.IsolatedAsyncioTestCase):
    async def test_registry_validates_schema_and_runs_sync_tools_off_loop(self):
        class Args(BaseModel):
            value: int

        registry = ToolRegistry()
        registry.register("double", lambda value: value * 2, "Double a value.", Args)
        self.assertEqual(await registry.execute("double", {"value": 4}), "8")
        self.assertIn("TOOL ERROR", await registry.execute("double", {"value": "not-an-int"}))


class ConversationRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_shared_runtime_executes_tool_and_returns_final_model_output(self):
        fence = chr(96) * 3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.txt").write_text("hello from workspace", encoding="utf-8")
            client = FakeClient([
                "Instructions acknowledged.",
                "I will inspect that now.\n\n" + fence + "tool:read_file\nfile_path: note.txt\n" + fence,
                "The file says hello from workspace.",
            ])
            events = []
            runtime = ConversationRuntime(client, workspace_root=root, event_sink=events.append)
            output = await runtime.ask_output("Inspect note.txt.")
            self.assertEqual(output.text, "The file says hello from workspace.")
            self.assertTrue(client.connected)
            self.assertEqual(len(client.prompts), 3)
            self.assertIn("tool_start", [event["type"] for event in events])
            result = next(event for event in events if event["type"] == "tool_result")
            self.assertIn("hello from workspace", result["output"])

    async def test_privileged_tool_requires_approval_before_write(self):
        fence = chr(96) * 3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = FakeClient([
                "Instructions acknowledged.",
                fence + "tool:write_file\nfile_path: notes with spaces.txt\ncontent:\nwritten safely\n" + fence,
                "File created.",
            ])
            events = []
            runtime = ConversationRuntime(
                client, workspace_root=root, approval_controller=FakeApproval(),
                event_sink=events.append,
            )
            output = await runtime.ask_output("Create notes with spaces.txt.")
            self.assertEqual(output.text, "File created.")
            self.assertEqual(
                (root / "notes with spaces.txt").read_text(encoding="utf-8"),
                "written safely",
            )
            self.assertIn("approval_required", [event["type"] for event in events])

    async def test_stream_emits_text_and_tool_lifecycle_events(self):
        fence = chr(96) * 3
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "note.txt").write_text("streamed content", encoding="utf-8")
            client = FakeClient([
                "Instructions acknowledged.",
                "Checking.\n" + fence + "tool:read_file\nfile_path: note.txt\n" + fence,
                "Done with streamed content.",
            ])
            runtime = ConversationRuntime(client, workspace_root=root)
            events = [event async for event in runtime.stream("Read note.txt.")]
            self.assertIn("Checking.\n", "".join(
                event.get("text", "") for event in events if event["type"] == "delta"
            ))
            self.assertIn("tool_result", [event["type"] for event in events])
            self.assertIn("done", [event["type"] for event in events])


if __name__ == "__main__":
    unittest.main()
