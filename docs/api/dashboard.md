# Dashboard API

The FastAPI dashboard provides a web interface for the WW Bridge.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API index with all endpoints |
| GET | `/health` | Bridge health + DB connectivity |
| POST | `/chat` | Single-turn Gemini query |
| GET | `/sessions` | List recent sessions |
| GET | `/session/{id}` | Full interaction history |
| GET | `/stats` | Aggregated telemetry + tool usage |

## Usage

```bash
# Start the dashboard
python3 -c "import uvicorn; uvicorn.run('src.dashboard.app:app', host='0.0.0.0', port=8080)"

# Health check
curl http://localhost:8080/health

# Chat
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "list files"}'
```
