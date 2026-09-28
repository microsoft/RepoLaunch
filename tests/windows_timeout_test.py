import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.windows import WindowsRuntime


WINDOWS_RUNTIME = ROOT / "launch" / "core" / "platforms" / "windows.py"


class WindowsTimeoutContractTests(unittest.TestCase):
    def test_windows_runtime_keeps_timeout_in_seconds_for_reader(self):
        source_text = WINDOWS_RUNTIME.read_text(encoding="utf-8")
        tree = ast.parse(source_text)
        send_command = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "send_command"
        )
        source = ast.get_source_segment(source_text, send_command)
        self.assertIsNotNone(source)
        assert source is not None
        self.assertIn("self.command_timeout * 60", source)
        self.assertIn("_read_raw_output(timeout=timeout)", source)
        self.assertIn("TIMEOUT_EXIT_CODE", source)

    def test_timeout_without_prompt_kills_isolated_container(self):
        source = WINDOWS_RUNTIME.read_text(encoding="utf-8")
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

        runtime = object.__new__(WindowsRuntime)
        runtime.container = FakeContainer()
        runtime.command_timeout = 1
        runtime.stopped = False
        runtime._clear_initial_prompt = lambda: None
        runtime._send_bytes = lambda data: None
        reads = iter([("partial output", None), ("", None)])
        runtime._read_raw_output = lambda timeout: next(reads)

        result = runtime.send_command("long-running build", timeout=0)

        self.assertEqual(result.metadata.exit_code, 124)
        self.assertTrue(runtime.container.killed)
        self.assertTrue(runtime.container.removed)
        self.assertTrue(runtime.stopped)

    def test_windows_runtime_documents_minute_constructor_contract(self):
        source = WINDOWS_RUNTIME.read_text(encoding="utf-8")
        self.assertIn("command_timeout: int = 30", source)
        self.assertIn("timeout = self.command_timeout * 60", source)


if __name__ == "__main__":
    unittest.main()