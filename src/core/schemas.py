from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class ToolCall(BaseModel):
    thought: str = Field(..., description="Your step-by-step reasoning about the task.")
    tool_name: Optional[str] = Field(None, description="The name of the tool to use, or null if finished.")
    tool_args: Optional[Dict[str, Any]] = Field(None, description="The arguments for the tool as a dictionary.")
    final_answer: Optional[str] = Field(None, description="Your final response to the user if the task is complete.")
