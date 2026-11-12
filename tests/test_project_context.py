import tempfile
import unittest
from pathlib import Path

from src.project_context import export_project, find_project_root


class ProjectContextTests(unittest.TestCase):
    def test_inventories_tree_and_embeds_small_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            output = root / ".ww" / "context.json"
            document = export_project(root, root, output)
            files = {entry["path"]: entry for entry in document["entries"] if entry["type"] == "file"}
            self.assertEqual(files["src/main.py"]["content"], "print('hello')\n")
            self.assertEqual(files["README.md"]["kind"], "text")
            self.assertEqual(document["summary"]["files"], 2)

    def test_samples_large_text_and_omits_sensitive_and_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "large.txt").write_text("A" * 40 + "MIDDLE" + "Z" * 40, encoding="utf-8")
            (root / ".env").write_text("SECRET=never-export", encoding="utf-8")
            (root / "image.bin").write_bytes(b"\x00\x01\x02")
            document = export_project(
                root, root, root / "context.json",
                full_limit=16, sample_bytes=8,
            )
            entries = {entry["path"]: entry for entry in document["entries"] if entry["type"] == "file"}
            self.assertTrue(entries["large.txt"]["sampled"])
            self.assertIn("CONTENT SAMPLED", entries["large.txt"]["content"])
            self.assertIsNone(entries[".env"]["content"])
            self.assertEqual(entries[".env"]["content_omitted"], "sensitive_file")
            self.assertEqual(entries["image.bin"]["kind"], "binary")

    def test_content_budget_preserves_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("A" * 20, encoding="utf-8")
            (root / "b.txt").write_text("B" * 20, encoding="utf-8")
            document = export_project(
                root, root, root / "context.json",
                full_limit=100, max_content_bytes=24,
            )
            files = [entry for entry in document["entries"] if entry["type"] == "file"]
            self.assertEqual(len(files), 2)
            self.assertEqual(sum(entry.get("content") is not None for entry in files), 1)
            self.assertEqual(document["summary"]["content_omitted"], 1)

    def test_project_root_detection_honours_explicit_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            nested = root / "a" / "b"
            nested.mkdir(parents=True)
            (root / "pyproject.toml").touch()
            self.assertEqual(find_project_root(nested), root)
            self.assertEqual(find_project_root(nested, str(nested)), nested)


if __name__ == "__main__":
    unittest.main()
