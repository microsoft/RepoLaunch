import os
from unittest.mock import Mock, patch

import docker
import pytest

from launch.core.platforms.base import BaseRuntime


class TestPullImageRetry:
    def test_retries_transient_api_error_then_verifies_image(self):
        client = Mock()
        client.images.get.side_effect = [
            docker.errors.ImageNotFound("missing before first pull"),
            docker.errors.ImageNotFound("missing before retry"),
            object(),
        ]
        client.images.pull.side_effect = [
            docker.errors.APIError("unexpected EOF"),
            object(),
        ]

        with patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.time.sleep") as sleep, \
             patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_ATTEMPTS": "3", "REPOLAUNCH_IMAGE_PULL_BACKOFF_SECONDS": "2"}, clear=False):
            assert BaseRuntime.pull_image("example/image:latest") is True

        assert client.images.pull.call_count == 2
        assert client.images.get.call_count == 3
        assert sleep.call_count == 1
        sleep.assert_called_once_with(2)

    def test_retries_docker_exception_and_reports_terminal_detail(self):
        client = Mock()
        client.images.get.side_effect = docker.errors.ImageNotFound("missing")
        client.images.pull.side_effect = docker.errors.DockerException("502 Bad Gateway")

        with patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.time.sleep"), \
             patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_ATTEMPTS": "2", "REPOLAUNCH_IMAGE_PULL_BACKOFF_SECONDS": "0"}, clear=False):
            with pytest.raises(RuntimeError, match=r"failed after 2 attempts: 502 Bad Gateway"):
                BaseRuntime.pull_image("example/image:latest")

        assert client.images.pull.call_count == 2

    def test_retries_when_pull_returns_before_image_is_locally_visible(self):
        client = Mock()
        client.images.get.side_effect = [
            docker.errors.ImageNotFound("missing before first pull"),
            docker.errors.ImageNotFound("missing after first pull"),
            docker.errors.ImageNotFound("missing before retry pull"),
            object(),
        ]
        client.images.pull.side_effect = [object(), object()]

        with patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.time.sleep") as sleep, \
             patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_ATTEMPTS": "3", "REPOLAUNCH_IMAGE_PULL_BACKOFF_SECONDS": "0"}, clear=False):
            assert BaseRuntime.pull_image("example/image:latest") is True

        assert client.images.pull.call_count == 2
        assert client.images.get.call_count == 4
        sleep.assert_not_called()

    def test_retries_transient_cache_lookup_error(self):
        client = Mock()
        client.images.get.side_effect = [
            docker.errors.DockerException("502 Bad Gateway"),
            docker.errors.ImageNotFound("missing after retry"),
            object(),
        ]
        client.images.pull.return_value = object()

        with patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch("launch.core.platforms.base.time.sleep") as sleep, \
             patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_ATTEMPTS": "2", "REPOLAUNCH_IMAGE_PULL_BACKOFF_SECONDS": "2"}, clear=False):
            assert BaseRuntime.pull_image("example/image:latest") is True

        client.images.pull.assert_called_once_with("example/image:latest")
        assert client.images.get.call_count == 3
        sleep.assert_called_once_with(2)

    def test_uses_long_default_timeout_for_large_images(self):
        client = Mock()
        client.images.get.return_value = object()

        with patch("launch.core.platforms.base.docker.from_env", return_value=client) as from_env:
            assert BaseRuntime.pull_image("example/image:latest") is True

        from_env.assert_called_once_with(timeout=3600)

    def test_does_not_retry_definitive_missing_image(self):
        client = Mock()
        client.images.get.side_effect = docker.errors.ImageNotFound("missing")
        client.images.pull.side_effect = docker.errors.ImageNotFound("not in registry")

        with patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch.dict(os.environ, {"REPOLAUNCH_IMAGE_PULL_ATTEMPTS": "5"}, clear=False):
            with pytest.raises(ValueError, match="not found in registry"):
                BaseRuntime.pull_image("example/image:latest")

        client.images.pull.assert_called_once_with("example/image:latest")

    @pytest.mark.parametrize("name,value", [
        ("REPOLAUNCH_IMAGE_PULL_ATTEMPTS", "0"),
        ("REPOLAUNCH_IMAGE_PULL_ATTEMPTS", "bad"),
        ("REPOLAUNCH_IMAGE_PULL_BACKOFF_SECONDS", "-1"),
        ("REPOLAUNCH_IMAGE_PULL_BACKOFF_SECONDS", "bad"),
    ])
    def test_rejects_invalid_retry_configuration(self, name, value):
        client = Mock()
        client.images.get.side_effect = docker.errors.ImageNotFound("missing")
        with patch("launch.core.platforms.base.docker.from_env", return_value=client), \
             patch.dict(os.environ, {name: value}, clear=False):
            with pytest.raises(ValueError):
                BaseRuntime.pull_image("example/image:latest")
        client.images.pull.assert_not_called()