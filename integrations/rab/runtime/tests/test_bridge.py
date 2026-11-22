import unittest
from unittest.mock import patch
from rab import bridge

class FakeResponse:
    status=200
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n): return b"RAB_NOTIFY_OK"

class BridgeTests(unittest.TestCase):
    def test_request_uses_localhost_allowlisted_endpoint(self):
        with patch.object(bridge,"settings",return_value={"host":"127.0.0.1","http_port":8080,"timeout_seconds":3}), \
             patch.object(bridge.urllib.request,"urlopen",return_value=FakeResponse()) as opened:
            result=bridge.request("notify",{"title":"RAB","message":"hello"})
        req=opened.call_args.args[0]
        self.assertEqual(req.full_url,"http://127.0.0.1:8080/rab/notify?title=RAB&message=hello")
        self.assertTrue(result["accepted"])

    def test_stream_and_clear_use_dedicated_overlay_endpoints(self):
        self.assertEqual(bridge._validate("stream", {"message": "VERIFY: PASS"}), {"message": "VERIFY: PASS"})
        self.assertEqual(bridge._validate("clear", {}), {})
        self.assertEqual(bridge.OPERATIONS["stream"]["path"], "stream")
        self.assertEqual(bridge.OPERATIONS["clear"]["path"], "clear")

    def test_unknown_operations_and_extra_parameters_are_rejected(self):
        with self.assertRaises(ValueError): bridge.request("shell",{})
        with self.assertRaises(ValueError): bridge._validate("ping",{"command":"id"})

    def test_gesture_bounds_are_checked(self):
        with self.assertRaises(ValueError):
            bridge._validate("drag",{"start_x":1,"start_y":2,"end_x":3,"end_y":4,"duration_ms":5})

if __name__=="__main__":
    unittest.main()
