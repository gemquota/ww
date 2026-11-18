import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.responses import Response

from src.dashboard import routes_auth
from src.tools.system_tools import (
    _is_sensitive_workspace_path,
    _read_capped_stream,
    _resolve_workspace_path,
)


class DashboardAuthenticationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_server_key_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(HTTPException) as raised:
                await routes_auth.verify_api_key("anything")
        self.assertEqual(raised.exception.status_code, 503)

    async def test_missing_or_wrong_client_key_is_rejected(self):
        with patch.dict(os.environ, {"WW_DASHBOARD_API_KEY": "correct-key"}):
            for supplied in ("", "wrong-key"):
                with self.subTest(supplied=supplied):
                    with self.assertRaises(HTTPException) as raised:
                        await routes_auth.verify_api_key(supplied)
                    self.assertEqual(raised.exception.status_code, 401)

    async def test_correct_key_is_accepted(self):
        with patch.dict(os.environ, {"WW_DASHBOARD_API_KEY": "correct-key"}):
            self.assertEqual(
                await routes_auth.verify_api_key("correct-key"),
                "correct-key",
            )

    async def test_normal_request_is_dispatched_exactly_once(self):
        routes_auth._rate_limit_store.clear()
        request = SimpleNamespace(
            url=SimpleNamespace(path="/chat"),
            client=SimpleNamespace(host="test-client"),
        )
        calls = 0

        async def call_next(_request):
            nonlocal calls
            calls += 1
            return Response("ok")

        response = await routes_auth.dispatch_request(request, call_next)
        self.assertEqual(calls, 1)
        self.assertEqual(response.headers["X-API-Version"], "v1")

    async def test_rate_limit_client_cache_has_a_hard_bound(self):
        routes_auth._rate_limit_store.clear()
        with patch.object(routes_auth, "_MAX_RATE_LIMIT_CLIENTS", 2):
            for address in ("client-a", "client-b", "client-c"):
                request = SimpleNamespace(
                    url=SimpleNamespace(path="/health"),
                    client=SimpleNamespace(host=address),
                )

                async def call_next(_request):
                    return Response("ok")

                await routes_auth.dispatch_request(request, call_next)
        self.assertLessEqual(len(routes_auth._rate_limit_store), 2)
        routes_auth._rate_limit_store.clear()

    async def test_legacy_api_path_redirects_without_dispatch(self):
        request = SimpleNamespace(
            url=SimpleNamespace(path="/api/health"),
            client=SimpleNamespace(host="test-client"),
        )

        async def call_next(_request):
            self.fail("Redirected requests must not reach the handler.")

        response = await routes_auth.dispatch_request(request, call_next)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/api/v1/health")


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_relative_paths_resolve_inside_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("src.tools.system_tools._get_workspace_root", return_value=Path(directory)):
                self.assertEqual(
                    _resolve_workspace_path("src/main.py"),
                    Path(directory) / "src" / "main.py",
                )

    def test_sibling_prefix_is_not_treated_as_workspace_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ww"
            sibling = Path(directory) / "ww-private"
            root.mkdir()
            sibling.mkdir()
            with patch("src.tools.system_tools._get_workspace_root", return_value=root):
                with self.assertRaises(PermissionError):
                    _resolve_workspace_path(sibling)

    def test_symlink_cannot_escape_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "ww"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "escape").symlink_to(outside, target_is_directory=True)
            with patch("src.tools.system_tools._get_workspace_root", return_value=root):
                with self.assertRaises(PermissionError):
                    _resolve_workspace_path("escape/secret.txt")

    def test_remote_read_guard_rejects_credentials_and_git_metadata(self):
        self.assertTrue(_is_sensitive_workspace_path(Path("/workspace/.env")))
        self.assertTrue(_is_sensitive_workspace_path(Path("/workspace/.env.production")))
        self.assertTrue(_is_sensitive_workspace_path(Path("/workspace/.ssh/id_ed25519")))
        self.assertTrue(_is_sensitive_workspace_path(Path("/workspace/.git/config")))
        self.assertFalse(_is_sensitive_workspace_path(Path("/workspace/src/main.py")))

    def test_subprocess_output_reader_caps_retained_bytes(self):
        import asyncio

        async def run():
            reader = asyncio.StreamReader()
            reader.feed_data(b"abcdefgh")
            reader.feed_eof()
            return await _read_capped_stream(reader, limit=5)

        self.assertEqual(asyncio.run(run()), b"abcde")


if __name__ == "__main__":
    unittest.main()
