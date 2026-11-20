import os
import tempfile
import unittest
from pathlib import Path

from src.tools.system_tools import doc_search
from src.tools.workspace import set_workspace_root


class DocumentationSearchWorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_uses_configured_workspace_not_process_cwd(self):
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as workspace, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(workspace)
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text(
                "The configured workspace marker is present.", encoding="utf-8"
            )
            set_workspace_root(root)
            os.chdir(elsewhere)
            try:
                result = await doc_search("configured workspace marker")
            finally:
                os.chdir(original_cwd)
                set_workspace_root(original_cwd)
        self.assertIn("configured workspace marker", result)
        self.assertIn("docs/guide.md", result)


if __name__ == "__main__":
    unittest.main()
