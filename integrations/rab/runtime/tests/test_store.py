import tempfile
import unittest
from pathlib import Path
from rab import store

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = (store.DATA, store.DB, store.MANIFEST)
        store.DATA = Path(self.tmp.name)
        store.DB = store.DATA / "test.sqlite3"
        store.MANIFEST = store.DATA / "capabilities.json"

    def tearDown(self):
        store.DATA, store.DB, store.MANIFEST = self.old
        self.tmp.cleanup()

    def test_event_replay_is_idempotent(self):
        payload = {"capability": "runtime.python", "state": "executable"}
        self.assertTrue(store.emit("CAPABILITY_DISCOVERED", payload))
        self.assertFalse(store.emit("CAPABILITY_DISCOVERED", payload))
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)

    def test_manifest_round_trip(self):
        manifest = {"schema_version": 1, "capabilities": [{"id": "x"}]}
        store.write_manifest(manifest)
        self.assertEqual(store.read_manifest(), manifest)

    def test_action_record_is_idempotent_and_binds_request(self):
        from rab.store import create_action_record, get_action_record
        create_action_record("action-1", "automation.rab_android_bridge", "tap",
                             {"x": 10, "y": 20}, "Settings screen", dispatched_at=100.0)
        create_action_record("action-1", "automation.rab_android_bridge", "tap",
                             {"x": 10, "y": 20}, "Settings screen", dispatched_at=100.0)
        record = get_action_record("action-1")
        self.assertEqual(record["request"], {"x": 10, "y": 20})
        with self.assertRaises(ValueError):
            create_action_record("action-1", "automation.rab_android_bridge", "tap",
                                 {"x": 99, "y": 99}, "Other screen")

    def test_stale_observation_cannot_verify_action(self):
        from rab.store import create_action_record, record_observation
        create_action_record("action-stale", "automation.rab_android_bridge", "tap",
                             {"x": 10, "y": 20}, "Settings screen", dispatched_at=200.0)
        result = record_observation("action-stale", "Settings screen", "Termalin-VNC",
                                    True, captured_at=199.0, received_at=201.0)
        self.assertEqual(result["verification_status"], "stale_observation")
        self.assertIsNone(result["verified_at"])
        self.assertEqual(result["outcome_confidence"], 0.0)

    def test_fresh_matching_observation_records_claim_without_verifying(self):
        from rab.store import create_action_record, record_observation
        create_action_record("action-fresh", "automation.rab_android_bridge", "tap",
                             {"x": 10, "y": 20}, "Settings screen", dispatched_at=200.0)
        result = record_observation("action-fresh", "Settings screen", "Termalin-VNC",
                                    True, captured_at=201.0, received_at=202.0,
                                    confidence=0.95, artifact_reference="frame-7")
        self.assertEqual(result["verification_status"], "pending")
        self.assertIsNone(result["verified_at"])
        self.assertEqual(result["outcome_confidence"], 0.0)
        self.assertEqual(len(result["evidence"]), 1)
        self.assertEqual(result["evidence"][0]["artifact_reference"], "frame-7")
        self.assertEqual(result["evidence"][0]["payload"]["verification_decision"], "NOT_MADE")
        self.assertTrue(result["evidence"][0]["payload"]["operator_claimed_expected_state_match"])

    def test_ambiguous_observation_never_verifies(self):
        from rab.store import create_action_record, record_observation
        create_action_record("action-ambiguous", "automation.rab_android_bridge", "tap",
                             {"x": 10, "y": 20}, "Settings screen", dispatched_at=200.0)
        result = record_observation("action-ambiguous", "Unknown screen", "Termalin-VNC",
                                    None, captured_at=201.0, received_at=202.0)
        self.assertEqual(result["verification_status"], "indeterminate")

if __name__ == "__main__":
    unittest.main()
