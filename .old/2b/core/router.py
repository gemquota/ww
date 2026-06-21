from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field

class IntentRoutingResult(BaseModel):
    intent: str = Field(..., description="The identified intent: RESEARCH, EDIT, GIT, SYSTEM, or GENERAL.")
    reasoning: str = Field(..., description="Reasoning for selecting this intent.")

class IntentRouter:
    """
    Identifies the high-level intent of a query to subset tools.
    """
    INTENTS = {
        "RESEARCH": ["read_file", "list_dir", "doc_search"],
        "EDIT": ["read_file", "write_file", "replace", "shell_exec"],
        "GIT": ["git", "list_dir"],
        "SYSTEM": ["shell_exec", "list_dir"],
        "GENERAL": ["read_file", "list_dir", "shell_exec", "git", "doc_search", "update_scratchpad"]
    }

    def __init__(self, agent):
        self.agent = agent

    def route(self, user_input: str) -> str:
        """
        Routes the user input to an intent.
        """
        system_prompt = (
            "You must ALWAYS respond with a SINGLE JSON object.\n"
            "Categorize the following user request into one of these intents:\n"
            "- RESEARCH: Reading files, searching docs, understanding code.\n"
            "- EDIT: Modifying files, creating new files.\n"
            "- GIT: Git operations (commit, status, branch).\n"
            "- SYSTEM: General shell commands, environment checks.\n"
            "- GENERAL: If it doesn't fit or needs multiple categories.\n\n"
            "Schema: {\"intent\": \"INTENT\", \"reasoning\": \"string\"}\n\n"
            "Example:\n"
            "User: List the files in src\n"
            "Model: {\"intent\": \"RESEARCH\", \"reasoning\": \"The user wants to explore the directory structure.\"}\n"
        )
        self.agent.set_system_instructions(system_prompt)
        
        prompt = self.agent.format_prompt(f"Identify the intent for: {user_input}")
        intent = "GENERAL"
        raw_output = ""
        
        try:
            # Use generate_json to get a structured intent
            result = self.agent.generate_json(
                f"Identify the intent for: {user_input}", 
                IntentRoutingResult
            )
            if isinstance(result, IntentRoutingResult):
                intent = result.intent.upper()
                raw_output = result.model_dump_json()
            else:
                raw_output = str(result)
        except Exception as e:
            raw_output = f"ERROR: {str(e)}"
        
        from core.telemetry import telemetry
        telemetry.log(self.agent.session_id, "routing", {
            "query": user_input,
            "intent": intent,
            "prompt": prompt,
            "raw_output": raw_output
        })
        return intent

    def get_tools_for_intent(self, intent: str, registry_tools: List[str]) -> List[str]:
        """
        Returns a list of tool names allowed for the given intent,
        filtered by what's actually in the registry.
        """
        allowed = self.INTENTS.get(intent, self.INTENTS["GENERAL"])
        return [t for t in allowed if t in registry_tools]
