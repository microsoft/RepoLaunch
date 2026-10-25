import os
import sys
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from launch.core.platforms.linux import LinuxRuntime


def _start_runtime(monkeypatch, devices=None):
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

    if devices is None:
        monkeypatch.delenv("SWE_BENCH_LIVE_DOCKER_DEVICES", raising=False)
    else:
        monkeypatch.setenv("SWE_BENCH_LIVE_DOCKER_DEVICES", devices)

    with patch("launch.core.platforms.linux.docker.from_env", side_effect=[FakeDocker(), FakeClient()]), patch.object(
        LinuxRuntime, "pull_image", return_value=None
    ), patch.object(LinuxRuntime, "_clear_initial_prompt", return_value=None), patch.object(
        LinuxRuntime, "send_command", return_value=MagicMock()
    ):
        LinuxRuntime._start_container("task-image", "task-id", 30, 1)
    return captured


def test_linux_runtime_keeps_devices_disabled_by_default(monkeypatch):
    captured = _start_runtime(monkeypatch)

    assert "devices" not in captured


def test_linux_runtime_passes_trimmed_opt_in_devices(monkeypatch):
    captured = _start_runtime(
        monkeypatch,
        devices=" /dev/net/tun:/dev/net/tun:rwm, , /dev/kvm ",
    )

    assert captured["devices"] == ["/dev/net/tun:/dev/net/tun:rwm", "/dev/kvm"]