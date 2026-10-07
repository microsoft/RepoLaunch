from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launch.core.platforms import windows


class WindowsContainerDockerPipeTest(unittest.TestCase):
    def test_mount_is_disabled_without_an_explicit_source(self) -> None:
        with mock.patch.dict(
            os.environ,
            {windows.WINDOWS_CONTAINER_DOCKER_PIPE_SOURCE_ENV: ""},
            clear=False,
        ):
            self.assertEqual(windows.build_windows_container_docker_mounts(), [])

    def test_explicit_source_is_mounted_at_the_conventional_guest_pipe(self) -> None:
        observed: list[dict[str, str]] = []

        def fake_mount(**kwargs: str) -> dict[str, str]:
            observed.append(kwargs)
            return kwargs

        with mock.patch.dict(
            os.environ,
            {
                windows.WINDOWS_CONTAINER_DOCKER_PIPE_SOURCE_ENV:
                r"\\.\pipe\docker_engine_windows"
            },
            clear=False,
        ), mock.patch.object(windows.docker.types, "Mount", side_effect=fake_mount):
            mounts = windows.build_windows_container_docker_mounts()

        self.assertEqual(mounts, observed)
        self.assertEqual(observed, [{
            "source": r"\\.\pipe\docker_engine_windows",
            "target": r"\\.\pipe\docker_engine",
            "type": "npipe",
        }])


if __name__ == "__main__":
    unittest.main()