# Utilities

## WebGeminiClient

Async Gemini Web API wrapper with rate limiting, retry, and streaming.

```python
from src.utils.web_client import WebGeminiClient
client = WebGeminiClient()
await client.init()
response = await client.ask("Hello!")
```

## Validation

Extracts tool calls from LLM responses.

```python
from src.utils.validation import extract_tool_call
result = extract_tool_call(text)
# Returns ("tool_name", {"key": "value"}) or None
```
