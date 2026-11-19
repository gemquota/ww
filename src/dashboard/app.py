"""FastAPI application for WW Bridge — REST API + dashboard.

Provides:
  - GET  /health          — bridge health check
  - POST /chat            — single-turn query (script mode via API)
  - GET  /session/{id}    — session history from telemetry DB
  - GET  /sessions        — list all sessions
  - GET  /stats           — telemetry event timeline + tool usage stats
"""
import sys, os, json, sqlite3, datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from fastapi import FastAPI, HTTPException, Security
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, StreamingResponse
    from pydantic import BaseModel, Field
    from src.ww_client import WWClient
    from dotenv import load_dotenv
except ImportError as _e:
    missing = str(_e).replace("No module named ", "").strip("'").strip('"')
    raise ImportError(
        f"Missing optional dependency: {missing}.\n"
        f"Install with: pip install -r requirements-dashboard.txt\n"
        f"Or: pip install fastapi uvicorn pydantic python-dotenv"
    ) from _e

load_dotenv()

from src.cookie_loader import extract_gemini_cookies
from src.conversation_runtime import ConversationRuntime
from src.dashboard.routes_auth import verify_api_key

app = FastAPI(title="WW Local API", version="0.3.0", description="Local WW conversation and tool execution API")

# Browser access is limited to explicitly trusted origins. Override with a
# comma-separated WW_CORS_ORIGINS environment variable when using a custom
# domain or another frontend. Never use "*" with an authenticated API.
_default_cors_origins = "https://gemquota.github.io"
_cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("WW_CORS_ORIGINS", _default_cors_origins).split(",")
    if origin.strip()
]
if "*" in _cors_origins:
    raise RuntimeError("WW_CORS_ORIGINS must list explicit origins; wildcard CORS is unsafe.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

WORKSPACE_ROOT = Path(os.getenv("WW_WORKSPACE", os.getcwd())).expanduser().resolve()
from src.tools.workspace import set_workspace_root

set_workspace_root(WORKSPACE_ROOT)


class ChatRequest(BaseModel):
    message: str
    session_name: str = "api_default"
    history: Optional[list[dict[str, str]]] = None
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    status: str
    response: str
    session_name: str
    conversation_id: Optional[str] = None


from src.dashboard.db import get_db_path, get_memory_db_path




# API Versioning & Rate Limiting
from src.dashboard.routes_auth import dispatch_request

@app.middleware("http")
async def api_versioning_and_rate_limit(request, call_next):
    return await dispatch_request(request, call_next)
@app.get("/memory/graph/{session_id}", dependencies=[Security(verify_api_key)])
async def get_memory_graph(session_id: int):
    """Get the Persistent Cognitive Graph (PCG) for a session."""
    db_path = get_memory_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No memory database found")
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        # Get nodes
        cursor = conn.execute(
            "SELECT id, event_id, label FROM graph_nodes WHERE session_id = ?",
            (session_id,)
        )
        nodes = [dict(row) for row in cursor.fetchall()]
        
        # Get edges
        cursor = conn.execute(
            "SELECT source_id, target_id, type FROM graph_edges WHERE session_id = ?",
            (session_id,)
        )
        edges = [dict(row) for row in cursor.fetchall()]
        
        # Get scratchpad summary for context
        cursor = conn.execute(
            "SELECT key, value FROM scratchpad WHERE session_id = ?",
            (session_id,)
        )
        scratchpad = {row["key"]: row["value"] for row in cursor.fetchall()}
        
        conn.close()
        return {
            "session_id": session_id,
            "nodes": nodes,
            "edges": edges,
            "scratchpad": scratchpad
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/health", dependencies=[Security(verify_api_key)])
async def health():
    """Bridge health check endpoint."""
    db_exists = get_db_path().exists()
    return {
        "status": "ok",
        "version": "0.3.0",
        "database": "connected" if db_exists else "no sessions yet"
    }


from src.dashboard.session_store import BrowserSessionStore, SessionCapacityError

_browser_sessions = BrowserSessionStore(max_sessions=64, idle_ttl=1800)


class BrowserConversation:
    """One browser session backed by the same client and runtime as the terminal."""

    def __init__(self, client: WWClient, runtime: ConversationRuntime):
        self.client = client
        self.runtime = runtime

    async def close(self) -> None:
        await self.client.close()


async def _create_browser_client(session_id: str) -> BrowserConversation:
    # Match the terminal's authentication path, including the optional
    # SECURE_1PSIDTS cookie and Netscape cookies.txt fallback.
    if not os.getenv("SECURE_1PSID"):
        cookie_file = Path(os.getenv("WW_COOKIE_FILE", "cookies.txt")).expanduser()
        if cookie_file.is_file():
            try:
                for key, value in extract_gemini_cookies(cookie_file).items():
                    os.environ.setdefault(key, value)
            except ValueError as exc:
                raise HTTPException(status_code=503, detail=f"Invalid Gemini cookie file: {exc}") from exc

    client = WWClient()
    try:
        await client.connect()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Gemini Web Chat is unavailable. Check SECURE_1PSID and WW_COOKIE_FILE.",
        ) from exc
    runtime = ConversationRuntime(client, workspace_root=WORKSPACE_ROOT, session_id=session_id)
    return BrowserConversation(client, runtime)


@app.on_event("shutdown")
async def close_browser_sessions() -> None:
    await _browser_sessions.close_all()


@app.get("/api/v1/runtime", dependencies=[Security(verify_api_key)])
async def runtime_status():
    """Describe the active local backend without exposing credentials or full paths."""
    return {
        "status": "ok",
        "workspace": WORKSPACE_ROOT.name,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "execution_backend": os.getenv("WW_EXECUTION_BACKEND", "current-process"),
        "gemini_credentials_configured": bool(
            os.getenv("SECURE_1PSID")
            or Path(os.getenv("WW_COOKIE_FILE", "cookies.txt")).expanduser().is_file()
        ),
        "features": ["conversation-runtime", "tool-feedback", "local-approval", "sse-streaming"],
    }


@app.post("/chat", response_model=ChatResponse, dependencies=[Security(verify_api_key)])
async def chat(request: ChatRequest):
    """Stateful browser chat through the shared terminal/browser conversation runtime."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    session_name = request.session_name.strip()[:128] or "api_default"
    try:
        async with _browser_sessions.acquire(
            session_name, lambda: _create_browser_client(session_name)
        ) as conversation:
            if request.conversation_id and request.conversation_id != conversation.client.active_chat_id:
                await conversation.client.resume_conversation(request.conversation_id)
                conversation.runtime.conversation_changed()
            output = await conversation.runtime.ask_output(request.message)
            response_text = getattr(output, "text", None) or str(output)
            return ChatResponse(
                status="ok",
                response=response_text,
                session_name=session_name,
                conversation_id=conversation.client.active_chat_id,
            )
    except SessionCapacityError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WW conversation failed: {type(exc).__name__}") from exc


@app.post("/api/v1/chat/stream", dependencies=[Security(verify_api_key)])
async def chat_stream(request: ChatRequest):
    """Stream visible model text and tool lifecycle events as server-sent events."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    session_name = request.session_name.strip()[:128] or "api_default"

    async def events():
        try:
            async with _browser_sessions.acquire(
                session_name, lambda: _create_browser_client(session_name)
            ) as conversation:
                if request.conversation_id and request.conversation_id != conversation.client.active_chat_id:
                    await conversation.client.resume_conversation(request.conversation_id)
                    conversation.runtime.conversation_changed()
                yield "data: " + json.dumps({
                    "type": "connected",
                    "conversation_id": conversation.client.active_chat_id,
                    "session_name": session_name,
                }) + "\n\n"
                async for event in conversation.runtime.stream(request.message):
                    if event.get("type") == "done":
                        event["conversation_id"] = conversation.client.active_chat_id
                    yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({
                "type": "error",
                "message": f"WW conversation failed: {type(exc).__name__}",
            }) + "\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/sessions", dependencies=[Security(verify_api_key)])
async def list_sessions(skip: int = 0, limit: int = 20):
    """List recent sessions from telemetry database."""
    db_path = get_db_path()
    if not db_path.exists():
        return {"sessions": [], "total": 0}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, start_timestamp, end_timestamp, summary FROM sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, skip)
        )
        sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}", dependencies=[Security(verify_api_key)])
async def get_session(session_id: int):
    """Get full interaction history for a session."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No database found")
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        session = cursor.fetchone()
        if not session:
            conn.close()
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        cursor = conn.execute(
            "SELECT timestamp, role, content, type FROM interactions WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        )
        interactions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return {"session": dict(session), "interactions": interactions, "total_interactions": len(interactions)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats", dependencies=[Security(verify_api_key)])
async def stats():
    """Aggregated telemetry statistics: event timeline, tool usage counts."""
    db_path = get_db_path()
    if not db_path.exists():
        return {"error": "No telemetry database found"}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        # Total counts
        session_count = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"]
        interaction_count = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]
        
        # Tool usage (content containing 'tool:' patterns)
        tool_cursor = conn.execute(
            "SELECT content FROM interactions WHERE content LIKE '%tool:%' OR type = 'tool_output'"
        )
        tool_types = {"read": 0, "write": 0, "shell": 0, "search": 0, "replace": 0, "delegate": 0, "other": 0}
        for row in tool_cursor:
            text = row["content"].lower()
            for t in list(tool_types.keys()):
                if f"tool:{t}" in text or f"({t.upper()})" in text:
                    tool_types[t] = tool_types.get(t, 0) + 1
        
        # Interactions by type
        type_cursor = conn.execute("SELECT type, COUNT(*) as c FROM interactions GROUP BY type")
        by_type = {row["type"]: row["c"] for row in type_cursor.fetchall()}
        
        conn.close()
        return {
            "sessions": session_count,
            "total_interactions": interaction_count,
            "tool_usage": tool_types,
            "interactions_by_type": by_type
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ToolExecuteRequest(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)
    session_name: str = "api_default"


@app.post("/tools/execute", dependencies=[Security(verify_api_key)])
async def execute_tool(request: ToolExecuteRequest):
    """Execute an opt-in read-only tool through the shared conversation runtime."""
    # Direct browser tool requests remain read-only and opt-in. Model-generated
    # privileged operations use the shared runtime and require terminal approval.
    if os.getenv("WW_REMOTE_TOOLS_ENABLED", "").strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(
            status_code=403,
            detail="Remote tools are disabled. Set WW_REMOTE_TOOLS_ENABLED=1 to enable read-only tools.",
        )
    from src.tools.tool_policy import remote_tool_allowed

    if not remote_tool_allowed(request.tool):
        raise HTTPException(
            status_code=403,
            detail=f"Remote tool '{request.tool}' is not exposed by the read-only browser API.",
        )

    session_name = request.session_name.strip()[:128] or "api_default"
    try:
        async with _browser_sessions.acquire(
            session_name, lambda: _create_browser_client(session_name)
        ) as conversation:
            result = await conversation.runtime.execute_tool(request.tool, request.args)
            return {"status": "ok", **result}
    except SessionCapacityError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {type(exc).__name__}") from exc


@app.get("/api/v1/stats/metering", dependencies=[Security(verify_api_key)])
async def usage_metering():
    """Usage metering: requests/min, active sessions, error rate, latency percentiles.
    Addresses NEW-F1#3 (Naomi Chen)."""
    db_path = get_db_path()
    if not db_path.exists():
        return {"error": "No telemetry database found"}
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        import time as _time2
        now = _time2.time()
        window_5min = now - 300
        
        # Requests in last 5 min
        recent = conn.execute(
            "SELECT COUNT(*) as c FROM interactions WHERE timestamp >= ?",
            (window_5min,)
        ).fetchone()["c"]
        
        # Active sessions (with activity in last 5 min)
        active = conn.execute(
            "SELECT COUNT(DISTINCT session_id) as c FROM interactions WHERE timestamp >= ?",
            (window_5min,)
        ).fetchone()["c"]
        
        # Error rate
        total_ops = conn.execute("SELECT COUNT(*) as c FROM interactions").fetchone()["c"]
        errors = conn.execute(
            "SELECT COUNT(*) as c FROM interactions WHERE content LIKE '%error%' OR content LIKE '%fail%' OR content LIKE '%exception%'"
        ).fetchone()["c"]
        error_rate = round(errors / max(total_ops, 1) * 100, 2) if total_ops > 0 else 0.0
        
        total_sessions = conn.execute("SELECT COUNT(*) as c FROM sessions").fetchone()["c"] if db_path.exists() else 0
        conn.close()
        return {
            "requests_per_min": round(recent / 5, 1),
            "active_sessions_5min": active,
            "total_sessions": total_sessions,
            "error_rate_percent": error_rate,
            "total_operations": total_ops,
            "timestamp": now,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chat-ui", include_in_schema=False)
async def chat_ui():
    """Serve the lightweight browser chat client."""
    return FileResponse(Path(__file__).with_name("chat.html"), media_type="text/html")


@app.get("/")
async def root():
    """Dashboard index with API documentation."""
    return {
        "name": "WW Bridge API",
        "version": "0.2.0",
        "endpoints": {
            "GET  /health": "Bridge health check",
            "POST /chat": "Single-turn Gemini query",
            "GET  /sessions": "List recent sessions",
            "GET  /session/{id}": "Get session history",
            "GET  /stats": "Aggregated telemetry statistics",
            "GET  /docs": "OpenAPI documentation (Swagger UI)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
