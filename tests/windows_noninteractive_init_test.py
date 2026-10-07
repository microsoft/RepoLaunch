import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.windows import WindowsRuntime


class RejectLegacyAttachContainer:
    def __init__(self):
        self.attach_attempts = 0

    def attach_socket(self, **_kwargs):
        self.attach_attempts += 1
        raise AssertionError("WindowsRuntime must not initialize an attach transport")

    def stop(self):
        pass

    def remove(self, **_kwargs):
        pass


class WindowsNoninteractiveInitTests(unittest.TestCase):
    def test_windows_runtime_init_does_not_open_legacy_attach_transport(self):
        container = RejectLegacyAttachContainer()
        runtime = WindowsRuntime(container, command_timeout=1)

        self.assertEqual(container.attach_attempts, 0)
        self.assertFalse(runtime.stopped)
        self.assertEqual(runtime.working_dir, r"C:\testbed")
        self.assertEqual(runtime.mnt_container, r"C:\mnt_tmp")
        self.assertEqual(runtime.mnt_host, os.path.join(os.getcwd(), "tmp"))
        runtime.stopped = True


if __name__ == "__main__":
    unittest.main()