import subprocess
import os
import sys
import glob
import time
from pathlib import Path

def get_latest_log():
    log_dir = Path(".tel")
    if not log_dir.exists():
        return None
    files = glob.glob(str(log_dir / "*.jsonl")) + glob.glob(str(log_dir / "*.db"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def run_trial():
    print("🚀 Starting WW CLI Trial...")
    print("----------------------------")
    
    # Task: Fix a typo in demo/buggy.py
    query = "Read demo/buggy.py, fix the typo in the print statement (should be 'Hello World'), and save it."
    
    cmd = [
        sys.executable, 
        "gemini_bridge.py", 
        "--script", 
        query,
        "--verbose"
    ]
    
    start_time = time.time()
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Stream output
        for line in process.stdout:
            print(f"  [BRIDGE] {line.strip()}")
            
        process.wait()
        elapsed = time.time() - start_time
        
        print(f"\n⏱️ Trial took {elapsed:.1f}s")
        print(f"✅ Return Code: {process.returncode}")
        
        # Verify fix
        buggy_path = Path("demo/buggy.py")
        if buggy_path.exists():
            content = buggy_path.read_text().strip()
            print(f"📝 Final Content of {buggy_path}: {content}")
            if "Hello World" in content:
                print("✨ Result: SUCCESS (Typo fixed)")
            else:
                print("⚠️ Result: PENDING (Typo not fixed or bridge failed)")
        
        # Telemetry & Diagnostics
        latest_log = get_latest_log()
        print(f"\n📊 Diagnostics:")
        if latest_log:
            print(f"  Latest Log: {latest_log}")
            # Show last few lines if it's a jsonl
            if str(latest_log).endswith(".jsonl"):
                with open(latest_log, "r") as f:
                    lines = f.readlines()
                    print("  Recent Telemetry Entries:")
                    for l in lines[-5:]:
                        print(f"    {l.strip()}")
        else:
            print("  No telemetry logs found in .tel/")

    except Exception as e:
        print(f"❌ Trial failed with error: {e}")

if __name__ == "__main__":
    run_trial()
