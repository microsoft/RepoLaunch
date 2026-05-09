'''
Can be run with pytest -rA

Firstly need to skip different tests for different platform:
# if os == "linux" or "wsl":
# test both LinuxRuntime and AndroidRuntime
# base images: ubuntu:26.04, cimg/android:2026.03.1

# if os == "windows":
# test Windows Runtime
# base images: mcr.microsoft.com/windows/server:ltsc2025

workflow:
instance={
    "instance_id": "laurent22_joplin-a774",
    "repo": "laurent22/joplin",
    "base_commit": "a774c52fc09371456846be9610680481bd37dc7a"
}
-> session=SetupRuntime.from_base_image(base_image, instance=instance)
-> res = session.send_command("ls README.md")
-> assert res.metadata.exit_code == 0 ; assert isinstance(res.output, str) and "README.md" in res.output;
-> session.commit(name=f"repolaunch_test}:{platform}_{instance_id}")
-> session.cleanup()

-> session=SetupRuntime.from_launch_image(f"repolaunch_test}:{platform}_{instance_id}", instance_id=instance_id)
-> res = session.send_command("ls README.md")
-> assert res.metadata.exit_code == 0 ; assert isinstance(res.output, str) and "README.md" in res.output;
-> assert res.apply_patch("""
diff --git a/log.out b/log.out
new file mode 100644
index 0000000..7a754f4
--- /dev/null
+++ b/log.out
@@ -0,0 +1,2 @@
+1
+2
\\ No newline at end of file
""", verbose=True) == True
-> session.cleanup()
'''

import os
import platform as host_platform
import warnings

import docker
import pytest
from docker.errors import APIError, DockerException, ImageNotFound

from launch.core.runtime import SetupRuntime
from launch.core.platforms.linux import LinuxRuntime
from launch.core.platforms.windows import WindowsRuntime
from launch.core.platforms.android import AndroidRuntime
#from launch.core.platforms.macos import MacosRuntime


INSTANCE = {
    "instance_id": "laurent22_joplin-a774",
    "repo": "laurent22/joplin",
    "base_commit": "a774c52fc09371456846be9610680481bd37dc7a",
}
PATCH_CONTENT = """diff --git a/log.out b/log.out\nnew file mode 100644\nindex 0000000..7a754f4\n--- /dev/null\n+++ b/log.out\n@@ -0,0 +1,2 @@\n+1\n+2\n\\ No newline at end of file"""


class FakeSocket:
    pass


class FakeContainer:
    def __init__(self, sock: FakeSocket):
        self.sock = sock

    def attach_socket(self, params):
        return self.sock

    def stop(self):
        pass

    def remove(self, force=False):
        pass


def no_command_result(self, command, timeout=None):
    return None


@pytest.fixture
def patch_runtime_constructor_io(monkeypatch):
    monkeypatch.setattr(LinuxRuntime, "_start_output_thread", lambda self: None)
    monkeypatch.setattr(LinuxRuntime, "_clear_initial_prompt", lambda self: None)
    monkeypatch.setattr(LinuxRuntime, "send_command", no_command_result)
    monkeypatch.setattr(WindowsRuntime, "send_command", no_command_result)
    #monkeypatch.setattr(MacosRuntime, "send_command", no_command_result)
    #monkeypatch.setattr(MacosRuntime, "_wait_until_shell_ready", lambda self: None)
    #monkeypatch.setattr(MacosRuntime, "_mount_swap_directory", lambda self: None)


@pytest.mark.parametrize(
    ("runtime_cls", "expected_attrs"),
    [
        pytest.param(
            LinuxRuntime,
            {
                "platform": "linux",
                "working_dir": r"/testbed",
                "mnt_container": r"/mnt_tmp",
            },
            id="linux",
        ),
        pytest.param(
            WindowsRuntime,
            {
                "platform": "windows",
                "working_dir": r"C:\testbed",
                "mnt_container": r"C:\mnt_tmp",
            },
            id="windows",
        ),
        pytest.param(
            AndroidRuntime,
            {
                "platform": "android",
                "working_dir": r"/testbed",
                "mnt_container": r"/mnt_tmp",
            },
            id="android",
        ),
        #pytest.param(
        #    MacosRuntime,
        #    {
        #        "platform": "macos",
        #        "working_dir": r"/Users/user/testbed",
        #        "mnt_container": r"/Volumes/repolaunch_swap",
        #    },
        #    id="macos",
        #),
    ],
)
def test_runtime_constructor_attributes(runtime_cls, expected_attrs, patch_runtime_constructor_io):
    command_timeout = 17
    sock = FakeSocket()
    runtime = runtime_cls(FakeContainer(sock), command_timeout=command_timeout)

    try:
        assert isinstance(runtime.platform, str)
        assert runtime.platform == expected_attrs["platform"]

        assert isinstance(runtime.command_timeout, int)
        assert runtime.command_timeout == command_timeout

        assert isinstance(runtime.working_dir, str)
        assert runtime.working_dir == expected_attrs["working_dir"]

        assert isinstance(runtime.mnt_host, str)
        assert runtime.mnt_host == os.path.join(os.getcwd(), "tmp")

        assert isinstance(runtime.mnt_container, str)
        assert runtime.mnt_container == expected_attrs["mnt_container"]

        assert isinstance(runtime.sock, FakeSocket)
        assert runtime.sock is sock

        assert isinstance(runtime.stopped, bool)
        assert runtime.stopped is False

        assert isinstance(runtime.preparation_commands, list)

    finally:
        runtime.stopped = True



def supported_integration_platforms() -> set[str]:
    system = host_platform.system().lower()
    if system == "windows":
        return {"windows"}
    if system == "linux":
        platforms = {"linux", "android"}
        #if os.environ.get("REPOLAUNCH_RUN_MACOS_INTEGRATION") == "1" and os.path.exists("/dev/kvm"):
        #    platforms.add("macos")
        return platforms
    return set()


def docker_client_or_skip():
    try:
        client = docker.from_env(timeout=60)
        client.ping()
        return client
    except DockerException as exc:
        pytest.fail(f"Docker is not available: {exc}")


def assert_readme_visible(session) -> None:
    res = session.send_command("ls README.md")
    assert res.metadata.exit_code == 0
    assert isinstance(res.output, str)
    assert "README.md" in res.output.replace("ls README.md", "")


def remove_image_if_present(client, image_ref: str) -> None:
    try:
        client.images.remove(image=image_ref, force=True)
    except (ImageNotFound, APIError):
        pass


def test_android_pull_image_requests_amd64_platform():
    assert AndroidRuntime.pull_image("cimg/android:2026.03.1") is True


@pytest.mark.integration
@pytest.mark.parametrize(
    ("runtime_platform", "base_image"),
    [
        pytest.param("linux", "ubuntu:26.04", id="linux"),
        pytest.param("android", "cimg/android:2026.03.1", id="android"),
        pytest.param("windows", "mcr.microsoft.com/windows/server:ltsc2025", id="windows"),
        #pytest.param("macos", "sickcodes/docker-osx:auto", id="macos"),
    ],
)
def test_runtime_integration_workflow(runtime_platform, base_image):
    if runtime_platform not in supported_integration_platforms():
        #if runtime_platform == "macos" and host_platform.system().lower() == "linux":
        #    warnings.warn("macos integration test uses a big linux container with macos vm inside. Due to efficiency macos support is not tested by default. If you want to test macos behaviour, install kvm and export REPOLAUNCH_RUN_MACOS_INTEGRATION=1.")
        #    pytest.skip("MacosRuntime is not tested by default.")
        #else:
        pytest.skip(f"{runtime_platform} runtime is not supported on this host")

    client = docker_client_or_skip()
    image_repo = "repolaunch_test"
    image_tag = f"{runtime_platform}_{INSTANCE['instance_id']}"
    launch_image = f"{image_repo}:{image_tag}"
    base_session = None
    launch_session = None

    try:
        base_session = SetupRuntime.from_base_image(
            base_image,
            instance=INSTANCE,
            platform=runtime_platform,
        )
        assert_readme_visible(base_session)
        assert len(base_session.preparation_commands) > 0

        assert base_session.apply_patch(PATCH_CONTENT, verbose=True) is True
        rm_res = base_session.send_command("rm log.out")
        assert rm_res.metadata.exit_code == 0, rm_res.output

        committed_image = base_session.commit(image_name=image_repo, tag=image_tag)
        assert committed_image == launch_image

    finally:
        if base_session is not None:
            base_session.cleanup()

    try:
        launch_session = SetupRuntime.from_launch_image(
            launch_image,
            instance_id=INSTANCE["instance_id"],
            platform=runtime_platform,
        )
        assert_readme_visible(launch_session)
        assert launch_session.apply_patch(PATCH_CONTENT, verbose=True) is True
    finally:
        if launch_session is not None:
            launch_session.cleanup()
        remove_image_if_present(client, launch_image)
