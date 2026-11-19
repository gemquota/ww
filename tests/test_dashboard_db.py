import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.dashboard.db import get_db_path, get_memory_db_path


class DashboardDatabasePathTests(unittest.TestCase):
    def test_paths_follow_current_workspace_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"WW_WORKSPACE": directory}):
                root = Path(directory).resolve()
                self.assertEqual(get_db_path(), root / ".tel" / "telemetry.db")
                self.assertEqual(
                    get_memory_db_path(),
                    root / ".tel" / "sessions" / "sessions.db",
                )


if __name__ == "__main__":
    unittest.main()
