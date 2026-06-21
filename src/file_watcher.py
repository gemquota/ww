"""
File Watcher — lightweight polling-based workspace change monitor.

Provides context-aware workspace monitoring that detects file changes
(saves, deletions, renames) and can trigger context refresh callbacks.

Uses polling (os.stat mtime checks) rather than inotify for maximum
cross-platform compatibility. Designed for the WW Bridge agentic loop
to stay aware of filesystem changes made by tools or external editors.
"""

import os
import time
import asyncio
from pathlib import Path
from typing import Callable, Dict, Optional, Set
from loguru import logger
from src.constants import BASE_IGNORE


class FileWatcher:
    """Polling-based file watcher for workspace changes.
    
    Monitors file modification times (mtime) at configurable intervals
    and calls a callback when changes are detected.
    
    Args:
        workspace_root: Root directory to watch.
        interval: Polling interval in seconds (default 2.0).
        callback: Async callable fn(changed_files: Set[Path]) -> None.
        pattern: Optional glob pattern to filter files (e.g., "*.py").
    """

    def __init__(
        self,
        workspace_root: Path,
        interval: float = 2.0,
        callback: Optional[Callable] = None,
        pattern: Optional[str] = None,
    ):
        self.root = workspace_root.resolve()
        self.interval = interval
        self.callback = callback
        self.pattern = pattern
        self._snapshot: Dict[Path, float] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def _scan(self) -> Dict[Path, float]:
        """Scan workspace and return {path: mtime} for all matching files."""
        snapshot: Dict[Path, float] = {}
        base_ignore = {".git", "node_modules", "__pycache__", ".ww", ".logs", ".venv", "venv"}

        try:
            for root, dirs, files in os.walk(self.root):
                # Filter ignored directories
                dirs[:] = [d for d in dirs if d not in base_ignore and not d.startswith(".")]

                for fname in files:
                    fpath = Path(root) / fname
                    # Apply pattern filter
                    if self.pattern and not fpath.match(self.pattern):
                        continue
                    try:
                        mtime = fpath.stat().st_mtime
                        snapshot[fpath] = mtime
                    except (OSError, PermissionError):
                        continue
        except Exception as e:
            logger.warning(f"FileWatcher scan error: {e}")

        return snapshot

    async def _poll_loop(self):
        """Main polling loop — compares snapshots and fires callback on changes."""
        self._snapshot = await self._scan()
        logger.debug(f"FileWatcher: initial snapshot: {len(self._snapshot)} files")

        while self._running:
            await asyncio.sleep(self.interval)
            try:
                current = await self._scan()
                changed: Set[Path] = set()

                # Check for modified files
                for path, mtime in current.items():
                    old_mtime = self._snapshot.get(path)
                    if old_mtime is None or abs(mtime - old_mtime) > 0.001:
                        changed.add(path)

                # Check for deleted files
                for path in self._snapshot:
                    if path not in current:
                        changed.add(path)

                if changed and self.callback:
                    try:
                        if asyncio.iscoroutinefunction(self.callback):
                            await self.callback(changed)
                        else:
                            self.callback(changed)
                    except Exception as e:
                        logger.warning(f"FileWatcher callback error: {e}")

                self._snapshot = current
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"FileWatcher poll error: {e}")

    async def start(self):
        """Start the file watcher polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"FileWatcher started: {self.root} (interval={self.interval}s)")

    async def stop(self):
        """Stop the file watcher."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("FileWatcher stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_file_count(self) -> int:
        return len(self._snapshot)


# Convenience: create a watcher that refreshes workspace context
def create_context_watcher(
    workspace_root: Path,
    context_refresh_fn: Callable,
    interval: float = 3.0,
) -> FileWatcher:
    """Create a FileWatcher pre-configured to trigger context refresh.
    
    Args:
        workspace_root: Root directory to watch.
        context_refresh_fn: Async callable that rebuilds workspace context.
        interval: Polling interval in seconds.
    
    Returns:
        Configured FileWatcher instance.
    """
    return FileWatcher(
        workspace_root=workspace_root,
        interval=interval,
        callback=context_refresh_fn,
    )
