import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.artifacts import list_artifacts, save_model_artifacts, save_research_document


class FakeImage:
    async def save(self, path, filename):
        destination = Path(path) / filename
        destination.write_bytes(b"image")
        return str(destination)


class FakeVideo:
    async def save(self, path, filename):
        destination = Path(path) / filename
        destination.write_bytes(b"video")
        return {"video": str(destination), "video_thumbnail": None}


class FakeMedia:
    async def save(self, path, filename, download_type):
        destination = Path(path) / filename
        destination.write_bytes(b"audio")
        return {"audio": str(destination), "video": None}


class ArtifactTests(unittest.IsolatedAsyncioTestCase):
    async def test_saves_research_and_all_media_types(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = SimpleNamespace(
                title="A Useful Research Report",
                content="# Research\n\nFindings.",
                markdown="# Research\n\nFindings.\n\n## Sources\n",
                ready=True,
            )
            output = SimpleNamespace(
                text="Generated the requested assets.",
                deep_research_document=document,
                images=[FakeImage()],
                videos=[FakeVideo()],
                media=[FakeMedia()],
            )
            with patch("src.artifacts.artifact_root", return_value=root):
                saved = await save_model_artifacts(output, "chat-123", media_mode="audio")
                files = list_artifacts()

            self.assertEqual(len(saved), 4)
            self.assertEqual(len(files), 4)
            self.assertTrue(any(path.suffix == ".md" for path in files))
            self.assertTrue(any(path.suffix == ".png" for path in files))
            self.assertTrue(any(path.suffix == ".mp4" for path in files))
            self.assertTrue(any(path.suffix == ".mp3" for path in files))

    def test_research_document_uses_markdown_export(self):
        with tempfile.TemporaryDirectory() as temporary:
            document = SimpleNamespace(
                title="Research",
                content="body",
                markdown="# Research\n\nbody\n",
                ready=True,
            )
            with patch("src.artifacts.artifact_root", return_value=Path(temporary)):
                path = save_research_document(document, "chat")
            self.assertIsNotNone(path)
            self.assertEqual(path.read_text(encoding="utf-8"), "# Research\n\nbody\n")


if __name__ == "__main__":
    unittest.main()
