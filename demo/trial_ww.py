import asyncio
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from src
sys.path.append(str(Path(__file__).parent.parent))

from src.ww_client import WWClient
from src.telemetry import TelemetryManager
from src.config import get_settings
from dotenv import load_dotenv

load_dotenv()

async def main():
    """
    WW Bridge Trial Program
    -----------------------
    This program demonstrates using the WW Bridge SDK (WWClient)
    combined with the TelemetryManager for full diagnostics.
    """
    # 1. Configuration and Initialization
    settings = get_settings()
    workspace = Path(".").resolve()
    
    # Initialize Telemetry
    print("🛠️ Initializing Telemetry Manager...")
    telemetry = TelemetryManager(workspace)
    telemetry.start_session()
    telemetry.log_interaction("system", "Starting WW Bridge Trial Program", "status")
    
    # Load credentials from environment
    secure_1psid = os.getenv("SECURE_1PSID", settings.gemini.credentials.secure_1psid)
    secure_1psidts = os.getenv("SECURE_1PSIDTS", settings.gemini.credentials.secure_1psidts)
    api_key = os.getenv("GEMINI_API_KEY", "")
    
    if not api_key and (not secure_1psid or not secure_1psidts):
        print("❌ Error: Credentials not found in .env or settings.")
        return

    print("🚀 Connecting to WW Bridge...")
    
    try:
        # 2. Use WWClient (SDK)
        async with WWClient(
            secure_1psid=secure_1psid,
            secure_1psidts=secure_1psidts,
            api_key=api_key,
            verbose=True
        ) as client:
            
            # --- Trial Stage 1: Connectivity ---
            prompt_1 = "Confirm connectivity by responding with 'WW Bridge Active'."
            print(f"\n📝 Stage 1: {prompt_1}")
            telemetry.log_interaction("user", prompt_1)
            
            response_1 = await client.ask(prompt_1)
            print(f"🤖 Response:\n{response_1}")
            telemetry.log_interaction("assistant", response_1)
            
            # --- Trial Stage 2: Codebase Context ---
            prompt_2 = "Summarize the core purpose of the files in src/core/ based on their names."
            print(f"\n📝 Stage 2: {prompt_2}")
            telemetry.log_interaction("user", prompt_2)
            
            response_2 = await client.ask(prompt_2)
            print(f"🤖 Response:\n{response_2}")
            telemetry.log_interaction("assistant", response_2)
            
            # --- Trial Stage 3: Feature Analysis ---
            prompt_3 = "Explain how the TelemetryManager in src/telemetry.py handles session persistence."
            print(f"\n📝 Stage 3: {prompt_3}")
            telemetry.log_interaction("user", prompt_3)
            
            response_3 = await client.ask(prompt_3)
            print(f"🤖 Response:\n{response_3}")
            telemetry.log_interaction("assistant", response_3)

        # 3. Export Diagnostics
        print("\n📊 Generating diagnostics report...")
        md_path = telemetry.export_markdown()
        print(f"✅ Trial Complete!")
        print(f"📄 Diagnostics Report: {md_path}")
        print(f"📂 Session Logs: {telemetry.session_log_path}")
        
        telemetry.end_session(summary="WW Bridge Trial completed successfully via SDK.")

    except Exception as e:
        print(f"❌ An error occurred during the trial: {e}")
        telemetry.log_interaction("system", f"Trial Error: {e}", "error")
        telemetry.end_session(summary=f"Trial failed: {e}")

if __name__ == "__main__":
    # Ensure we run the async loop
    asyncio.run(main())
