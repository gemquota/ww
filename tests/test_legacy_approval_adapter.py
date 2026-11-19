import unittest

from src.ui_adapter import SilentUIAdapter


class SilentApprovalTests(unittest.IsolatedAsyncioTestCase):
    async def test_noninteractive_adapter_never_auto_approves(self):
        adapter = SilentUIAdapter()
        self.assertFalse(await adapter.request_approval("run a command"))


if __name__ == "__main__":
    unittest.main()
