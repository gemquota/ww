import tempfile
import unittest
from pathlib import Path

from src.permissions import ApprovalPolicy, PermissionLevel, PermissionManager


class PermissionManagerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.manager = PermissionManager(self.root, ApprovalPolicy.ON_REQUEST)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_normal_project_commands_run_automatically(self):
        self.assertEqual(
            self.manager.classify_command("python -m pytest -q"),
            PermissionLevel.ALLOW,
        )
        self.assertEqual(
            self.manager.classify_command("git status --short"),
            PermissionLevel.ALLOW,
        )

    def test_destructive_commands_require_approval(self):
        self.assertEqual(
            self.manager.classify_command("rm -rf build"),
            PermissionLevel.ASK,
        )
        self.assertEqual(
            self.manager.classify_command("git reset --hard HEAD"),
            PermissionLevel.ASK,
        )

    def test_system_destructive_commands_are_denied(self):
        for command in ("rm -rf /", "rm -fr ~", "mkfs.ext4 /dev/sda", "shutdown now"):
            with self.subTest(command=command):
                self.assertEqual(
                    self.manager.classify_command(command),
                    PermissionLevel.DENY,
                )

    def test_protected_files_are_never_writable(self):
        for name in (".env", ".env.development", "credentials", "private.pem"):
            with self.subTest(name=name):
                self.assertEqual(
                    self.manager.classify_write(str(self.root / name)),
                    PermissionLevel.DENY,
                )

    def test_writes_stay_inside_workspace(self):
        self.assertEqual(
            self.manager.classify_write(str(self.root / "src" / "module.py")),
            PermissionLevel.ALLOW,
        )
        self.assertEqual(
            self.manager.classify_write(str(self.root.parent / "outside.py")),
            PermissionLevel.DENY,
        )

    def test_always_policy_prompts_for_normal_commands(self):
        manager = PermissionManager(self.root, ApprovalPolicy.ALWAYS)
        self.assertEqual(
            manager.classify_command("python -m pytest"),
            PermissionLevel.ASK,
        )

    def test_never_policy_skips_prompts_but_keeps_hard_denies(self):
        manager = PermissionManager(self.root, ApprovalPolicy.NEVER)
        self.assertEqual(
            manager.classify_command("python -m pytest"),
            PermissionLevel.ALLOW,
        )
        self.assertEqual(
            manager.classify_command("rm -rf /"),
            PermissionLevel.DENY,
        )


if __name__ == "__main__":
    unittest.main()
