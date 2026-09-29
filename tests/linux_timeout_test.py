import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.linux import LinuxRuntime
from launch.core.platforms.base import TIMEOUT_EXIT_CODE


LINUX_RUNTIME = ROOT / "launch" / "core" / "platforms" / "linux.py"


class LinuxTimeoutContractTests(unittest.TestCase):
    def test_timeout_without_prompt_kills_isolated_container(self):
        source = LINUX_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("self.container.kill()", source)
        self.assertIn("self.container.remove(force=True)", source)
        self.assertIn("self.stopped = True", source)

        class FakeContainer:
            def __init__(self):
                self.killed = False
                self.removed = False

            def kill(self):
                self.killed = True

            def remove(self, force=False):
                self.removed = force

        runtime = object.__new__(LinuxRuntime)
        runtime.container = FakeContainer()
        runtime.command_timeout = 1
        runtime.stopped = False
        runtime._clear_initial_prompt = lambda: None
        runtime._send_bytes = lambda data: None
        reads = iter([("partial output", None), ("", None)])
        runtime._read_raw_output = lambda timeout: next(reads)

        result = runtime.send_command("long-running build", timeout=0)

        self.assertEqual(result.metadata.exit_code, TIMEOUT_EXIT_CODE)
        self.assertTrue(runtime.container.killed)
        self.assertTrue(runtime.container.removed)
        self.assertTrue(runtime.stopped)

    def test_linux_runtime_keeps_minute_constructor_contract(self):
        source = LINUX_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("command_timeout: int = 30", source)
        self.assertIn("timeout = self.command_timeout * 60", source)


if __name__ == "__main__":
    unittest.main()