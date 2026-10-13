from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.base import TIMEOUT_EXIT_CODE
from launch.core.platforms.windows import WindowsRuntime


class WindowsExecDeadlineTests(unittest.TestCase):
    def test_blocking_exec_run_honors_runtime_deadline_and_cleans_container(self) -> None:
        class BlockingContainer:
            def __init__(self) -> None:
                self.entered = threading.Event()
                self.release = threading.Event()
                self.killed = False
                self.removed = False

            def exec_run(self, *_args, **_kwargs):
                self.entered.set()
                self.release.wait(timeout=5)
                return type("ExecResult", (), {"output": b"", "exit_code": 0})()

            def kill(self) -> None:
                self.killed = True
                self.release.set()

            def remove(self, force: bool = False) -> None:
                self.removed = force

        runtime = object.__new__(WindowsRuntime)
        runtime.container = BlockingContainer()
        runtime.command_timeout = 1
        runtime.stopped = False
        runtime.working_dir = r"C:\\testbed"

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime.mnt_host = temp_dir
            started = time.monotonic()
            result = runtime.send_command("Start-Sleep -Seconds 600", timeout=0)
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 2)
            self.assertTrue(runtime.container.entered.wait(timeout=1))
            self.assertTrue(runtime.container.killed)
            self.assertTrue(runtime.container.removed)
            self.assertTrue(runtime.stopped)
            self.assertEqual(result.metadata.exit_code, TIMEOUT_EXIT_CODE)
            self.assertIn("Exited due to timeout", result.output)
            self.assertEqual(os.listdir(temp_dir), [])

    def test_completed_exec_keeps_command_result(self) -> None:
        class CompletedContainer:
            def exec_run(self, *_args, **_kwargs):
                metadata = (
                    b'###PS1JSON###\n'
                    b'{"exit_code":0,"username":"u","hostname":"h",'
                    b'"working_dir":"C:\\\\\\testbed","py_interpreter_path":""}\n'
                    b'###PS1END###\n'
                )
                return type("ExecResult", (), {"output": b"done\n" + metadata, "exit_code": 0})()

            def stop(self) -> None:
                pass

            def remove(self, force: bool = False) -> None:
                pass

        runtime = object.__new__(WindowsRuntime)
        runtime.container = CompletedContainer()
        runtime.command_timeout = 1
        runtime.stopped = False
        runtime.working_dir = r"C:\\testbed"

        with tempfile.TemporaryDirectory() as temp_dir:
            runtime.mnt_host = temp_dir
            result = runtime.send_command("Write-Output done", timeout=1)

            self.assertEqual(result.metadata.exit_code, 0)
            self.assertIn("done", result.output)
            self.assertFalse(runtime.stopped)
            self.assertEqual(os.listdir(temp_dir), [])


if __name__ == "__main__":
    unittest.main()