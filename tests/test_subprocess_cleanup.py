import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

from src.tools.system_tools import _read_capped_stream, _stop_process_group


@unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "requires POSIX process groups and /proc")
class ProcessGroupCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_cleanup_kills_parent_and_descendant(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "pids"
            child_code = (
                "import signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(60)"
            )
            parent_code = (
                "import os,signal,subprocess,sys,time; "
                f"child=subprocess.Popen([sys.executable, '-c', {child_code!r}]); "
                f"open({str(pid_file)!r}, 'w').write(f'{{os.getpid()}} {{child.pid}}'); "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                "time.sleep(60)"
            )
            process = await asyncio.create_subprocess_exec(
                sys.executable, "-c", parent_code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            stdout_task = asyncio.create_task(_read_capped_stream(process.stdout, 1024))
            stderr_task = asyncio.create_task(_read_capped_stream(process.stderr, 1024))
            streams_task = asyncio.gather(stdout_task, stderr_task)

            try:
                deadline = asyncio.get_running_loop().time() + 5
                while not pid_file.exists():
                    if asyncio.get_running_loop().time() >= deadline:
                        self.fail("parent did not publish child PID")
                    await asyncio.sleep(0.02)
                parent_pid, child_pid = map(int, pid_file.read_text().split())

                await asyncio.wait_for(
                    _stop_process_group(process, streams_task),
                    timeout=6,
                )
                self.assertIsNotNone(process.returncode)

                def stopped(pid: int) -> bool:
                    try:
                        stat_line = Path(f"/proc/{pid}/stat").read_text()
                    except FileNotFoundError:
                        return True
                    state = stat_line[stat_line.rfind(")") + 2:][:1]
                    return state == "Z"

                deadline = asyncio.get_running_loop().time() + 3
                while not all(stopped(pid) for pid in (parent_pid, child_pid)):
                    if asyncio.get_running_loop().time() >= deadline:
                        self.fail("a process in the child process group remained running")
                    await asyncio.sleep(0.05)
            finally:
                if process.returncode is None:
                    await _stop_process_group(process, streams_task)


if __name__ == "__main__":
    unittest.main()
