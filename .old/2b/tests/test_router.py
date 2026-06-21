import asyncio
from core.router import IntentRouter
from core.agent import GemmaOutlinesAgent
import os

class MockAgent:
    def __init__(self):
        self.instructions = ""
        self.history = []

    def set_system_instructions(self, inst):
        self.instructions = inst

    def generate_json(self, msg, schema):
        from core.router import IntentRoutingResult
        # Simple heuristic for testing
        if "read" in msg.lower() or "list" in msg.lower():
            return IntentRoutingResult(intent="RESEARCH", reasoning="Testing research intent")
        if "git" in msg.lower():
            return IntentRoutingResult(intent="GIT", reasoning="Testing git intent")
        return IntentRoutingResult(intent="GENERAL", reasoning="Defaulting")

async def test_router_logic():
    agent = MockAgent()
    router = IntentRouter(agent)
    
    registry_tools = ["read_file", "list_dir", "git", "shell_exec", "update_scratchpad"]
    
    print("Test 1: Research Intent")
    intent = router.route("I want to read the source code of agent.py")
    tools = router.get_tools_for_intent(intent, registry_tools)
    print(f"Detected Intent: {intent}")
    print(f"Allowed Tools: {tools}")
    assert "read_file" in tools
    assert "list_dir" in tools
    assert "git" not in tools

    print("\nTest 2: Git Intent")
    intent = router.route("Show me the git status")
    tools = router.get_tools_for_intent(intent, registry_tools)
    print(f"Detected Intent: {intent}")
    print(f"Allowed Tools: {tools}")
    assert "git" in tools
    assert "read_file" not in tools

    print("\nTest 3: General Intent")
    intent = router.route("What is the meaning of life?")
    tools = router.get_tools_for_intent(intent, registry_tools)
    print(f"Detected Intent: {intent}")
    print(f"Allowed Tools: {tools}")
    assert len(tools) == len(registry_tools)

if __name__ == "__main__":
    asyncio.run(test_router_logic())
