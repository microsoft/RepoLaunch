import queue
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.base import CmdOutputMetadata
from launch.core.platforms.linux import LinuxRuntime


class LinuxOutputDrainTests(unittest.TestCase):
    def test_large_output_scans_for_prompt_once_and_accepts_split_delimiter(self):
        runtime = object.__new__(LinuxRuntime)
        runtime.stopped = True
        runtime.output_queue = queue.Queue()
        for _ in range(256):
            runtime.output_queue.put(b"x" * 4096)
        runtime.output_queue.put(b'\n###PS1JSON###\n{"exit_code": "0", "username": "root"')
        runtime.output_queue.put(
            b', "hostname": "test", "working_dir": "/testbed", '
            b'"py_interpreter_path": ""}\n###PS1END###\n'
        )

        original_matches = CmdOutputMetadata.matches_ps1_metadata
        calls = 0

        def counted_matches(output_text):
            nonlocal calls
            calls += 1
            return original_matches(output_text)

        with patch.object(
            CmdOutputMetadata,
            "matches_ps1_metadata",
            new=counted_matches,
        ):
            output, metadata = runtime._read_raw_output(timeout=1)

        self.assertEqual(calls, 1)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.exit_code, 0)
        self.assertEqual(metadata.working_dir, "/testbed")
        self.assertTrue(output.startswith("x" * 4096))
        self.assertEqual(output.count("x"), 256 * 4096)


if __name__ == "__main__":
    unittest.main()