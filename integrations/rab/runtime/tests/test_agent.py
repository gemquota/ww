import tempfile
import unittest
from pathlib import Path
from rab import agent, store

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=(store.DATA,store.DB,store.MANIFEST)
        store.DATA=Path(self.tmp.name);store.DB=store.DATA/"state.db";store.MANIFEST=store.DATA/"manifest.json"
        store.write_manifest({"schema_version":1,"capabilities":[
            {"id":"android.notification","state":"unavailable"},
            {"id":"automation.rab_android_bridge","state":"awaiting_setup"}
        ]})

    def tearDown(self):
        store.DATA,store.DB,store.MANIFEST=self.old
        self.tmp.cleanup()

    def test_reconcile_replans_after_capability_changes(self):
        first=agent.submit_goal("Create a notification","obj-1")
        self.assertEqual(first["status"],"awaiting_setup")
        manifest=store.read_manifest()
        manifest["capabilities"][1]["state"]="executable"
        store.write_manifest(manifest)
        result=agent.reconcile_objectives()
        self.assertEqual(result["reconciled"],1)
        objective=agent.list_objectives()[0]
        self.assertEqual(objective["status"],"ready")
        self.assertEqual(objective["plan"]["steps"][0]["tool_name"],"rab_notify")

if __name__=="__main__":
    unittest.main()
