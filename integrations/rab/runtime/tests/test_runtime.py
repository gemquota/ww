import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rab import runtime, store

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (store.DATA, store.DB, store.MANIFEST)
        store.DATA = Path(self.tmp.name)
        store.DB = store.DATA / "test.sqlite3"
        store.MANIFEST = store.DATA / "capabilities.json"
        self.marker = Path(self.tmp.name) / "called.txt"
        self.command = Path(self.tmp.name) / "fake-toast"
        self.command.write_text('#!/bin/sh\nprintf "%s" "$1" > ' + str(self.marker) + '\n')
        self.command.chmod(0o755)
        self.manifest = {"capabilities": [{
            "id": "android.toast", "state": "executable",
            "details": {"path": str(self.command)}
        }]}

    def tearDown(self):
        store.DATA, store.DB, store.MANIFEST = self.old
        self.tmp.cleanup()

    def test_execution_id_prevents_duplicate_side_effect(self):
        with patch.object(runtime, "read_manifest", return_value=self.manifest):
            first = runtime.execute("android.toast", {"message": "hello"}, operation_id="same-op")
            second = runtime.execute("android.toast", {"message": "hello"}, operation_id="same-op")
        self.assertEqual(first["status"], "accepted")
        self.assertFalse(first["replayed"])
        self.assertTrue(second["replayed"])
        self.assertEqual(self.marker.read_text(), "hello")

    def test_local_http_bridge_records_accepted_response(self):
        bridge_manifest={"capabilities":[{"id":"automation.rab_android_bridge","state":"executable","details":{}}]}
        with patch.object(runtime,"read_manifest",return_value=bridge_manifest), \
             patch.object(runtime.bridge,"request",return_value={"accepted":True,"body":"RAB_NOTIFY_OK"}) as call:
            result=runtime.execute("automation.rab_android_bridge",{"operation":"notify","title":"RAB","message":"hi"},operation_id="http-op")
        self.assertEqual(result["status"],"acknowledged")
        call.assert_called_once_with("notify",{"title":"RAB","message":"hi"})

    def test_unavailable_capability_is_not_executed(self):
        unavailable = {"capabilities": [{
            "id": "android.notification", "state": "unavailable", "details": {}
        }]}
        with patch.object(runtime, "read_manifest", return_value=unavailable):
            with self.assertRaises(runtime.CapabilityError):
                runtime.execute("android.notification", {"content": "no"})
        self.assertFalse(self.marker.exists())

if __name__ == "__main__":
    unittest.main()
