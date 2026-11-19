import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path

from src.tools.system_tools import _run_process


@unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "requires POSIX process groups and /proc")
class ProcessGroupCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_kills_parent_and_descendant(self):
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
            runner = asyncio.create_task(
                _run_process(sys.executable, "-c", parent_code, timeout=0.5)
            )
            try:
                deadline = asyncio.get_running_loop().time() + 5
                while not pid_file.exists():
                    if asyncio.get_running_loop().time() >= deadline:
                        self.fail("parent did not publish child PID")
                    await asyncio.sleep(0.02)
                parent_pid, child_pid = map(int, pid_file.read_text().split())

                with self.assertRaises(asyncio.TimeoutError):
                    await runner

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
                if not runner.done():
                    runner.cancel()
                    await asyncio.gather(runner, return_exceptions=True)


    async def test_cancellation_kills_parent_and_descendant(self):
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
            runner = asyncio.create_task(
                _run_process(sys.executable, "-c", parent_code, timeout=30)
            )
            try:
                deadline = asyncio.get_running_loop().time() + 5
                while not pid_file.exists():
                    if asyncio.get_running_loop().time() >= deadline:
                        self.fail("parent did not publish child PID")
                    await asyncio.sleep(0.02)
                parent_pid, child_pid = map(int, pid_file.read_text().split())

                runner.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await runner

                def stopped(pid: int) -> bool:
                    try:
                        stat_line = Path(f"/proc/{pid}/stat").read_text()
                    except FileNotFoundError:
                        return True
                    return stat_line[stat_line.rfind(")") + 2:][:1] == "Z"

                deadline = asyncio.get_running_loop().time() + 3
                while not all(stopped(pid) for pid in (parent_pid, child_pid)):
                    if asyncio.get_running_loop().time() >= deadline:
                        self.fail("a process in the child process group remained running")
                    await asyncio.sleep(0.05)
            finally:
                if not runner.done():
                    runner.cancel()
                    await asyncio.gather(runner, return_exceptions=True)



    async def test_timeout_kills_process_that_ignores_term_after_closing_pipes(self):
        command = (
            "import os,signal,time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "os.close(1); os.close(2); time.sleep(60)"
        )
        with self.assertRaises(asyncio.TimeoutError):
            await _run_process(sys.executable, "-c", command, timeout=0.25)

    async def test_timeout_applies_after_process_closes_output_streams(self):
        command = (
            "import os,time; os.close(1); os.close(2); time.sleep(60)"
        )
        with self.assertRaises(asyncio.TimeoutError):
            await _run_process(sys.executable, "-c", command, timeout=0.25)


if __name__ == "__main__":
    unittest.main()
