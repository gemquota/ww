#!/usr/bin/env python3
"""
WW Neural Bridge — Entry point.

Thin wrapper that imports and runs the orchestrator.
"""
import sys
import os

# Ensure project root and src/ are on sys.path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
if os.path.join(_project_root, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_project_root, "src"))

from src.gemini_bridge import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
