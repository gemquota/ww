import unittest
from unittest.mock import AsyncMock

from src.rab_status import RABTaskPublisher


class RABTaskPublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_mirrors_tool_lifecycle_without_blocking_agent(self):
        publisher = RABTaskPublisher("test-session", "Inspect project")
        publisher._post = AsyncMock()
        publisher._post_result = AsyncMock(return_value={"task_id": "rab-task-1"})

        await publisher.begin()
        await publisher.handle({"type": "tool_start", "tool": "read_file", "call_id": "1"})
        await publisher.handle({
            "type": "tool_result", "tool": "read_file", "call_id": "1",
            "output": "file contents",
        })
        await publisher.handle({"type": "done"})

        self.assertEqual(publisher.task_id, "rab-task-1")
        self.assertEqual(publisher.actions[0]["status"], "completed")
        calls = [call.args[0] for call in publisher._post.await_args_list]
        self.assertIn("/api/event", calls)
        state_calls = [
            call.args[1] for call in publisher._post.await_args_list
            if call.args[0] == "/api/state"
        ]
        self.assertEqual(state_calls[-1]["status"], "COMPLETED")
        self.assertEqual(state_calls[-1]["progress"], {"current": 1, "total": 1})

    async def test_approval_and_execution_limit_are_waiting_states(self):
        publisher = RABTaskPublisher("test-session", "Need approval")
        publisher._post = AsyncMock()
        publisher._post_result = AsyncMock(return_value={"task_id": "rab-task-2"})
        await publisher.handle({"type": "approval_required", "tool": "shell_exec"})
        await publisher.handle({"type": "execution_limit", "message": "limit"})
        states = [
            call.args[1]["status"] for call in publisher._post.await_args_list
            if call.args[0] == "/api/state"
        ]
        self.assertEqual(states, ["WAITING", "WAITING"])


if __name__ == "__main__":
    unittest.main()
