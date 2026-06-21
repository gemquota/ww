#!/usr/bin/env python3
"""ww dev — Development helper: watch src/, auto-run py_compile + pytest on change."""
import subprocess
import sys
import os
import time

def main():
    watch = "--watch" in sys.argv or "-w" in sys.argv
    
    print("=== ww dev ===")
    print("Running py_compile + pytest...")
    
    # Run py_compile
    result = subprocess.run(
        "python3 -m py_compile src/gemini_bridge.py src/config.py src/context_manager.py "
        "src/permissions.py src/diff_engine.py src/checkpoint.py src/telemetry.py",
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  ✅ py_compile: OK")
    else:
        print(f"  ❌ py_compile: FAILED\n{result.stderr[:300]}")
        if not watch:
            sys.exit(1)
    
    # Run pytest (quick mode)
    result = subprocess.run(
        "python3 -m pytest .tests/ -q --tb=short 2>&1",
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        last = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else "?"
        print(f"  ✅ pytest: {last}")
    else:
        last = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else "?"
        print(f"  ❌ pytest: FAILED\n{last}")
    
    if watch:
        print("\nWatching src/ for changes (Ctrl+C to stop)...")
        try:
            import inotify.adapters
            i = inotify.adapters.Inotify()
            i.add_watch(b'src')
            for event in i.event_gen():
                if event is not None:
                    os.system('clear')
                    print("Change detected! Re-running...\n")
                    main()
        except ImportError:
            # Fallback: poll every 2 seconds
            last_mtimes = {}
            while True:
                changed = False
                for root, dirs, files in os.walk('src'):
                    for f in files:
                        if f.endswith('.py'):
                            path = os.path.join(root, f)
                            mtime = os.path.getmtime(path)
                            if path in last_mtimes and last_mtimes[path] != mtime:
                                changed = True
                            last_mtimes[path] = mtime
                if changed:
                    os.system('clear')
                    print("Change detected! Re-running...\n")
                    main()
                time.sleep(2)

if __name__ == "__main__":
    main()
