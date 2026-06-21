#!/usr/bin/env python3
"""Thin wrapper that imports and runs the orchestrator."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from src.orchestrator import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
