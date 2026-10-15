import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.linux import LinuxRuntime


class LinuxDeterministicClockContractTests(unittest.TestCase):
    def _start(self, clock):
        captured = {}

        class FakeContainer:
            def attach_socket(self, **_kwargs):
                return object()

        class FakeContainers:
            def run(self, *_args, **kwargs):
                captured.update(kwargs)
                return FakeContainer()

        class FakeClient:
            containers = FakeContainers()

            def version(self):
                return {"Os": "linux"}

        class FakeDocker:
            def ping(self):
                return True

        environment = {} if not clock else {"SWE_BENCH_LIVE_EVALUATION_CLOCK": clock}
        with patch("launch.core.platforms.linux.docker.from_env", side_effect=[FakeDocker(), FakeClient()]), patch.object(
            LinuxRuntime, "pull_image", return_value=None
        ), patch.object(LinuxRuntime, "_clear_initial_prompt", return_value=None), patch.object(
            LinuxRuntime, "send_command", return_value=MagicMock()
        ) as send_command, patch.dict(os.environ, environment, clear=not bool(clock)):
            runtime = LinuxRuntime._start_container("task-image", "task-id", 30, 1)
        return runtime, captured, send_command

    def test_clock_env_provisions_and_exports_faketime(self):
        _runtime, captured, send_command = self._start("2026-04-10 12:00:00")
        self.assertEqual(captured["environment"], {"TERM": "xterm-mono"})
        clock_commands = [
            call.args[0] for call in send_command.call_args_list if "libfaketime" in call.args[0]
        ]
        self.assertEqual(len(clock_commands), 1)
        command = clock_commands[0]
        self.assertIn("apt-get install -y -qq libfaketime", command)
        self.assertIn("export SWE_BENCH_LIVE_FAKETIME_VALUE='@2026-04-10 12:00:00'", command)
        self.assertIn("swe_bench_live_with_clock()", command)
        self.assertIn("FAKETIME_DONT_RESET=1", command)
        self.assertIn("FAKETIME_DONT_FAKE_MONOTONIC=1", command)
        self.assertIn("LD_PRELOAD=$SWE_BENCH_LIVE_FAKETIME_LIBRARY", command)

    def test_no_clock_preserves_default_environment_and_skips_setup(self):
        _runtime, captured, send_command = self._start("")
        self.assertEqual(captured["environment"], {"TERM": "xterm-mono"})
        self.assertFalse(any("libfaketime" in call.args[0] for call in send_command.call_args_list))


if __name__ == "__main__":
    unittest.main()