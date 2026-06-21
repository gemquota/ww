import os
import sys
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.telemetry import TelemetryManager
from src.config import get_settings

app = FastAPI(title="NEON PROTOCOL BRIDGE")

# Initialize Telemetry
settings = get_settings()
workspace = Path(".").resolve()
telemetry = TelemetryManager(workspace)
telemetry.start_session()

@app.get("/", response_class=HTMLResponse)
async def get_game():
    game_path = Path(__file__).parent / "game.html"
    return game_path.read_text()

@app.post("/telemetry")
async def post_telemetry(request: Request):
    data = await request.json()
    
    # Log to WW Telemetry
    event = data.get("event", "unknown_event")
    msg_type = data.get("type", "info")
    stats = data.get("stats", {})
    
    content = f"[NEON_PROTOCOL] {event} | HP: {stats.get('health')}% | KILLS: {stats.get('kills')} | THREAT: {stats.get('threat')}"
    
    telemetry.log_interaction("neon_protocol", content, msg_type)
    
    # Print to console for visibility during trial
    color = "\033[94m" if msg_type == "info" else "\033[91m"
    print(f"{color}[GAME_EVENT] {content}\033[0m")
    
    return {"status": "logged"}

def start():
    print("🔮 NEON PROTOCOL BRIDGE starting on http://localhost:8000")
    print("📊 Telemetry session active. All game events are being recorded to WW Bridge.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")

if __name__ == "__main__":
    start()
