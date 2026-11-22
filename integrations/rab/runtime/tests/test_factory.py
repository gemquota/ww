import tempfile
import unittest
from pathlib import Path
from rab import factory, store

class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old=(store.DATA,store.DB,store.MANIFEST)
        store.DATA=Path(self.tmp.name); store.DB=store.DATA/"state.db"; store.MANIFEST=store.DATA/"manifest.json"
        store.write_manifest({"schema_version":1,"capabilities":[{"id":"android.macrodroid_app","state":"verified"}]})

    def tearDown(self):
        store.DATA,store.DB,store.MANIFEST=self.old
        self.tmp.cleanup()

    def spec(self, **overrides):
        value={"id":"automation.bridge","description":"Bridge","state":"awaiting_setup",
               "adapter":"macrodroid_mcp","dependencies":["android.macrodroid_app"],
               "permissions":["user must import"],"details":{}}
        value.update(overrides)
        return value

    def test_registers_capability_with_known_dependencies(self):
        result=factory.register_capability(self.spec())
        self.assertTrue(result["registered"])
        self.assertEqual(store.read_manifest()["capabilities"][-1]["id"],"automation.bridge")

    def test_rejects_unapproved_permission_expansion(self):
        with self.assertRaises(ValueError):
            factory.register_capability(self.spec(state="executable"))

    def test_rejects_unknown_dependency(self):
        with self.assertRaises(ValueError):
            factory.register_capability(self.spec(dependencies=["unknown.capability"]))

if __name__=="__main__":
    unittest.main()
