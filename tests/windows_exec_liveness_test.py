from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest

from launch.core.platforms import windows
from launch.core.platforms.windows import WindowsRuntime


class _Result:
    def __init__(self, output: bytes, exit_code: int) -> None:
        self.output = output
        self.exit_code = exit_code


class _StoppedWhileExecBlocksContainer:
    def __init__(self) -> None:
        self.release = threading.Event()
        self.attrs = {"State": {"Running": True, "Status": "running"}}
        self.reload_calls = 0

    def exec_run(self, *_args, **_kwargs):
        self.release.wait(timeout=2)
        return _Result(b"late result", 1)

    def reload(self) -> None:
        self.reload_calls += 1
        self.attrs = {"State": {"Running": False, "Status": "exited", "ExitCode": 3221225473}}
        self.release.set()

    def kill(self) -> None:
        raise AssertionError("lost-container recovery must not kill a stopped container")

    def remove(self, force: bool = False) -> None:
        raise AssertionError("lost-container recovery must not remove a stopped container")


class _HealthyContainer:
    def __init__(self) -> None:
        self.attrs = {"State": {"Running": True, "Status": "running"}}
        self.reload_calls = 0

    def exec_run(self, *_args, **_kwargs):
        return _Result(
            b"hello\n###PS1JSON###\n{\"exit_code\":0,\"username\":\"u\",\"hostname\":\"h\",\"working_dir\":\"C:\\\\testbed\",\"py_interpreter_path\":\"\"}\n###PS1END###\n",
            0,
        )

    def reload(self) -> None:
        self.reload_calls += 1

    def stop(self) -> None:
        pass

    def remove(self, force: bool = False) -> None:
        pass


class WindowsExecLivenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_cwd = os.getcwd()
        self._directory = tempfile.TemporaryDirectory()
        os.chdir(self._directory.name)
        self._old_poll = windows.WINDOWS_EXEC_LIVENESS_POLL_SECONDS
        windows.WINDOWS_EXEC_LIVENESS_POLL_SECONDS = 0.01

    def tearDown(self) -> None:
        windows.WINDOWS_EXEC_LIVENESS_POLL_SECONDS = self._old_poll
        os.chdir(self._old_cwd)
        self._directory.cleanup()

    @staticmethod
    def _runtime(container) -> WindowsRuntime:
        runtime = object.__new__(WindowsRuntime)
        runtime.container = container
        runtime.platform = "windows"
        runtime.command_timeout = 1
        runtime.working_dir = r"C:\testbed"
        runtime.mnt_container = r"C:\mnt_tmp"
        runtime.mnt_host = os.path.join(os.getcwd(), "tmp")
        runtime.stopped = False
        runtime.preparation_commands = []
        return runtime

    def test_stopped_container_unblocks_exec_waiter_before_command_timeout(self) -> None:
        container = _StoppedWhileExecBlocksContainer()
        runtime = self._runtime(container)
        started = time.monotonic()
        result = runtime.send_command("Write-Output never-completes")
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 1.0)
        self.assertEqual(result.metadata.exit_code, 125)
        self.assertIn("Windows container execution became unavailable", result.output)
        self.assertIn("status=exited exit_code=3221225473", result.output)
        self.assertTrue(runtime.stopped)
        self.assertGreaterEqual(container.reload_calls, 1)

    def test_patch_application_propagates_lost_container(self) -> None:
        runtime = self._runtime(_StoppedWhileExecBlocksContainer())
        patch = "\n".join([
            "diff --git a/file.txt b/file.txt",
            "index 1111111..2222222 100644",
            "--- a/file.txt",
            "+++ b/file.txt",
            "@@ -1 +1 @@",
            "-old",
            "+new",
            "",
        ])
        with self.assertRaisesRegex(RuntimeError, "Windows container execution became unavailable"):
            runtime.apply_patch(patch)
        self.assertTrue(runtime.stopped)

    def test_completed_exec_does_not_probe_or_change_exit_code(self) -> None:
        container = _HealthyContainer()
        runtime = self._runtime(container)
        result = runtime.send_command("Write-Output hello")

        self.assertEqual(result.metadata.exit_code, 0)
        self.assertEqual(result.output.strip(), "hello")
        self.assertEqual(container.reload_calls, 0)
        self.assertFalse(runtime.stopped)


if __name__ == "__main__":
    unittest.main()
