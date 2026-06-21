import asyncio
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.ww_client import WWClient
from src.telemetry import TelemetryManager
from src.config import get_settings

load_dotenv()

async def main():
    """
    NEON_PROTOCOL: AI OBSERVER
    -------------------------
    This script monitors the telemetry database populated by the game
    and uses WW Bridge to provide tactical advice and state analysis.
    """
    settings = get_settings()
    workspace = Path(".").resolve()
    
    # We use the same workspace telemetry DB
    telemetry = TelemetryManager(workspace)
    
    print("\n" + "="*60)
    print(" 👁️  NEON_PROTOCOL: AI_OBSERVER_V1.0")
    print(" Monitoring game telemetry... Play at http://localhost:8000")
    print("="*60 + "\n")

    secure_1psid = os.getenv("SECURE_1PSID")
    secure_1psidts = os.getenv("SECURE_1PSIDTS")
    api_key = os.getenv("GEMINI_API_KEY")

    async with WWClient(
        secure_1psid=secure_1psid,
        secure_1psidts=secure_1psidts,
        api_key=api_key
    ) as client:
        
        last_log_count = 0
        
        try:
            while True:
                # Poll the telemetry history for 'neon_protocol' entries
                history = telemetry.interaction_history
                game_logs = [h for h in history if h.get('role') == 'neon_protocol']
                
                if len(game_logs) > last_log_count:
                    new_logs = game_logs[last_log_count:]
                    last_log_count = len(game_logs)
                    
                    # Consolidate recent events
                    event_summary = "\n".join([l['content'] for l in new_logs])
                    
                    prompt = (
                        "You are the NEON_PROTOCOL Tactical AI. Analyze these recent combat logs "
                        "and provide a short (2-sentence) tactical assessment. Be cold and technical.\n\n"
                        f"LOGS:\n{event_summary}"
                    )
                    
                    print(f"📡 Analyzing {len(new_logs)} new events...")
                    response = await client.ask(prompt)
                    print(f"\n🤖 [TACTICAL_ADVICE]:\n{response}\n")
                    
                    # Record advice back into telemetry
                    telemetry.log_interaction("observer", response, "advice")

                await asyncio.sleep(5) # Poll every 5 seconds
                
        except KeyboardInterrupt:
            print("\nShutting down Observer.")
            telemetry.end_session(summary="AI Observer terminated.")

if __name__ == "__main__":
    asyncio.run(main())
