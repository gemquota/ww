import re
import json
from typing import Optional, Tuple, Dict, Any

def extract_tool_call(text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Extracts a tool call from the model's response.
    Expected format:
    ```tool:tool_name
    {"key": "value"}
    ```
    """
    match = re.search(r"```tool:(\w+)\s*\n(.*?)\n```", text, re.DOTALL)
    if not match:
        return None
    
    name = match.group(1)
    args_json = match.group(2).strip()
    
    try:
        args = json.loads(args_json)
        return name, args
    except json.JSONDecodeError:
        # Try a more lenient parse or regex-based extraction if needed
        return None
