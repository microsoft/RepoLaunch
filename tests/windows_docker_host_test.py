from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from launch.core.platforms.windows import (
    DEFAULT_WINDOWS_DOCKER_HOST,
    WindowsRuntime,
)


class WindowsDockerHostTests(unittest.TestCase):
    def test_native_pipe_is_selected_when_callers_do_not_set_docker_host(self) -> None:
        class FakeDocker:
            def __init__(self) -> None:
                self.pings = 0

            def from_env(self, **_kwargs):
                return self

            def ping(self) -> None:
                self.pings += 1

        fake_docker = FakeDocker()
        with patch.dict(os.environ, {}, clear=True), patch(
            "launch.core.platforms.windows.docker", fake_docker
        ), patch.object(
            WindowsRuntime,
            "pull_image",
            side_effect=RuntimeError("stop-after-ping"),
        ):
            with self.assertRaisesRegex(RuntimeError, "stop-after-ping"):
                WindowsRuntime._start_container("image", "instance", 1, 1)
            self.assertEqual(os.environ["DOCKER_HOST"], DEFAULT_WINDOWS_DOCKER_HOST)
            self.assertEqual(fake_docker.pings, 1)

    def test_explicit_docker_host_remains_authoritative(self) -> None:
        class FakeDocker:
            def from_env(self, **_kwargs):
                return self

            def ping(self) -> None:
                pass

        explicit = "npipe:////./pipe/custom_engine"
        with patch.dict(os.environ, {"DOCKER_HOST": explicit}, clear=True), patch(
            "launch.core.platforms.windows.docker", FakeDocker()
        ), patch.object(
            WindowsRuntime,
            "pull_image",
            side_effect=RuntimeError("stop-after-ping"),
        ):
            with self.assertRaisesRegex(RuntimeError, "stop-after-ping"):
                WindowsRuntime._start_container("image", "instance", 1, 1)
            self.assertEqual(os.environ["DOCKER_HOST"], explicit)


if __name__ == "__main__":
    unittest.main()