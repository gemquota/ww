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
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from src.utils.web_client import WebGeminiClient
    from src.telemetry import TelemetryManager
    from dotenv import load_dotenv
except ImportError as _e:
    missing = str(_e).replace("No module named ", "").strip("'").strip('"')
    raise ImportError(
        f"Missing optional dependency: {missing}.\n"
        f"Install with: pip install 'ww-bridge[dashboard]'\n"
        f"Or: pip install fastapi uvicorn pydantic python-dotenv"
    ) from _e

load_dotenv()

from src.dashboard.routes_auth import verify_api_key
from src.core.api_keys import APIKeyManager

app = FastAPI(title="WW Bridge API", version="0.2.0", description="Gemini Multi-Agent Bridge REST Interface")

WORKSPACE_ROOT = Path(os.getenv("WW_WORKSPACE", os.getcwd()))


class ChatRequest(BaseModel):
    message: str
    session_name: str = "api_default"


class ChatResponse(BaseModel):
    status: str
    response: str
    session_name: str


from src.dashboard.db import get_db_path, get_memory_db_path
from src.core.api_keys import APIKeyManager




# API Versioning & Rate Limiting
from src.dashboard.routes_auth import rate_limit_middleware, api_versioning_redirect
from src.core.api_keys import APIKeyManager

@app.middleware("http")
async def api_versioning_and_rate_limit(request, call_next):
    # API versioning first
    redirect = await api_versioning_redirect(request, call_next)
    if redirect.status_code in (307, 308):
        return redirect
    # Then rate limiting
    return await rate_limit_middleware(request, call_next)
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


@app.get("/api/v1/health")
async def health():
    """Bridge health check endpoint."""
    db_exists = get_db_path().exists()
    return {
        "status": "ok",
        "version": "0.2.0",
        "workspace": str(WORKSPACE_ROOT),
        "database": "connected" if db_exists else "no sessions yet"
    }


@app.post("/chat", response_model=ChatResponse, dependencies=[Security(verify_api_key)])
async def chat(request: ChatRequest):
    """Single-turn query via Gemini Web API."""
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    import os
    client = WebGeminiClient(
        secure_1psid=os.getenv("SECURE_1PSID", ""),
        secure_1psidts=os.getenv("SECURE_1PSIDTS", ""),
        api_key=os.getenv("GEMINI_API_KEY", ""),
    )
    if not await client.init():
        raise HTTPException(status_code=503, detail="Gemini Web API not available (check credentials)")
    try:
        resp = await client.ask(request.message)
        if resp is None:
            raise HTTPException(status_code=502, detail="No response from Gemini")
        return ChatResponse(status="ok", response=resp, session_name=request.session_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    args: dict = {}


@app.post("/tools/execute", dependencies=[Security(verify_api_key)])
async def execute_tool(request: ToolExecuteRequest):
    """Execute a registered tool via the ToolRegistry.
    
    Args:
        tool: Name of the registered tool (e.g., read_file, write_file).
        args: Dictionary of arguments for the tool.
    
    Returns:
        Tool output as JSON.
    """
    from src.tools.registry import ToolRegistry
    from src.tools.system_tools import (
        read_file, write_file, list_dir, shell_exec, git_tool,
        doc_search, request_clarification, code_search, file_patch, url_fetch,
        ReadFileArgs, ListDirArgs, WriteFileArgs, ShellExecArgs,
        GitArgs, DocSearchArgs, ClarificationArgs,
        CodeSearchArgs, FilePatchArgs, UrlFetchArgs
    )
    
    registry = ToolRegistry()
    registry.register("read_file", read_file, "Read contents of a file.", ReadFileArgs)
    registry.register("write_file", write_file, "Write contents to a file.", WriteFileArgs)
    registry.register("list_dir", list_dir, "List files in a directory.", ListDirArgs)
    registry.register("shell_exec", shell_exec, "Execute a shell command.", ShellExecArgs)
    registry.register("git", git_tool, "Execute git commands.", GitArgs)
    registry.register("doc_search", doc_search, "Search project documentation.", DocSearchArgs)
    registry.register("request_clarification", request_clarification, "Ask user for clarification.", ClarificationArgs)
    registry.register("code_search", code_search, "Search for regex pattern across files.", CodeSearchArgs)
    registry.register("file_patch", file_patch, "Apply surgical text replacement.", FilePatchArgs)
    registry.register("url_fetch", url_fetch, "Fetch a URL via HTTP GET.", UrlFetchArgs)
    
    try:
        result = await registry.execute(request.tool, request.args)
        return {"status": "ok", "tool": request.tool, "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")

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
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
