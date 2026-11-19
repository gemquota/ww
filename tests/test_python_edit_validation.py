import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.tools.system_tools import file_patch, write_file


class PythonEditValidationTests(unittest.TestCase):
    def test_invalid_python_write_does_not_replace_or_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("src.tools.system_tools._get_workspace_root", return_value=root):
                result = write_file("broken.py", "def broken(")
            self.assertIn("syntax error", result.lower())
            self.assertFalse((root / "broken.py").exists())

    def test_invalid_python_patch_leaves_original_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "valid.py"
            original = "def value():\n    return 1\n"
            target.write_text(original, encoding="utf-8")
            with patch("src.tools.system_tools._get_workspace_root", return_value=root):
                result = file_patch("valid.py", "return 1", "return (")
            self.assertIn("syntax error", result.lower())
            self.assertEqual(target.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
