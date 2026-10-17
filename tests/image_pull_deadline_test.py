import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import docker
from launch.core.platforms.base import BaseRuntime


class _Images:
    def __init__(self):
        self.get_calls = 0

    def get(self, image_name):
        self.get_calls += 1
        if self.get_calls == 1:
            raise docker.errors.ImageNotFound("not local")
        return object()


class _Client:
    def __init__(self):
        self.images = _Images()


class ImagePullDeadlineTests(unittest.TestCase):
    def test_missing_image_uses_bounded_docker_cli_pull(self):
        client = _Client()
        completed = SimpleNamespace(returncode=0, stdout="pulled", stderr="")
        with patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_TIMEOUT_SECONDS": "7"}, clear=False), \
             patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.subprocess.run", return_value=completed) as run:
            self.assertTrue(BaseRuntime.pull_image("example/image"))

        run.assert_called_once_with(
            ["docker", "pull", "example/image"],
            capture_output=True,
            text=True,
            timeout=7,
            check=False,
        )
        self.assertEqual(client.images.get_calls, 2)

    def test_pull_timeout_has_a_terminal_error(self):
        client = _Client()
        timed_out = subprocess.TimeoutExpired(
            cmd=["docker", "pull", "example/image"], timeout=3,
        )
        with patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_TIMEOUT_SECONDS": "3"}, clear=False), \
             patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.subprocess.run", side_effect=timed_out):
            with self.assertRaisesRegex(RuntimeError, "timed out after 3 seconds"):
                BaseRuntime.pull_image("example/image")

    def test_nonzero_pull_exposes_the_docker_error(self):
        client = _Client()
        completed = SimpleNamespace(returncode=1, stdout="", stderr="registry unavailable")
        with patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_TIMEOUT_SECONDS": "3"}, clear=False), \
             patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "registry unavailable"):
                BaseRuntime.pull_image("example/image")

    def test_invalid_timeout_configuration_is_rejected(self):
        with patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_TIMEOUT_SECONDS": "zero"}, clear=False):
            with self.assertRaisesRegex(ValueError, "positive integer"):
                BaseRuntime._image_pull_timeout_seconds()


if __name__ == "__main__":
    unittest.main()