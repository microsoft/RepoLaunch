from __future__ import annotations

from launch.core.platforms.base import (
    CMD_OUTPUT_PS1_BEGIN,
    CMD_OUTPUT_PS1_END,
    CMD_OUTPUT_METADATA_PS1_REGEX,
    ANSI_ESCAPE,
    TIMEOUT_EXIT_CODE,
    MEM_LIMIT,
    CPU_CORES,
    VAR_PATTERNS
)
from launch.core.platforms.base import (
    CmdOutputMetadata,
    CommandResult
)
from launch.core.platforms.linux import LinuxRuntime

import os
from typing import Any
import uuid

import docker
from docker.models.containers import Container


class AndroidRuntime(LinuxRuntime):
    '''
    recommended base image: {
        "cimg/android:2026.03.1": "Android SDK and CLI tools installed",
        "cimg/android:2026.03.1-node": "Node.js installed",
        "cimg/android:2026.03.1-browsers":"Node.js, Selenium, and browser dependencies installed",
        "cimg/android:2026.03.1-ndk": "Android Native Development Kit installed",
    }
    '''

    def __init__(
                    self,
                    container: Container,
                    command_timeout: int = 30
                ):
        super().__init__(container, command_timeout=command_timeout)
        self.platform = "android"

    @classmethod
    def _start_container(
        cls,
        image_name: str,
        container_id: str,
        docker_timeout: int,
        command_timeout: int,
    ) -> AndroidRuntime:
        try:
            docker.from_env().ping()
        except docker.errors.DockerException:
            raise RuntimeError("Docker is not installed or not running.")

        _ = cls.pull_image(image_name)
        client = docker.from_env(timeout=docker_timeout)
        container_name = f"git-launch-{container_id}-{str(uuid.uuid4())[:4]}"
        info = client.version()
        engine_os = (info.get("Os") or info.get("OSType") or "").lower()
        extra_hosts = {"host.docker.internal": "host-gateway"} if "linux" in engine_os else None

        os.makedirs(os.path.join(os.getcwd(), "tmp"), exist_ok=True)
        shell_command = "/bin/bash"
        working_dir = "/testbed"
        run_kwargs = {
            "cpu_quota": int(CPU_CORES * 100000),
            "mem_limit": MEM_LIMIT,
            "user": "root",
        }

        container = client.containers.run(
            image_name,
            name=container_name,
            command=shell_command,
            stdin_open=True,
            tty=True,
            detach=True,
            environment={
                "TERM": "xterm-mono",
            },
            working_dir=working_dir,
            extra_hosts=extra_hosts,
            volumes={
                os.path.join(os.getcwd(), "tmp"): {
                    "bind": "/mnt_tmp",
                    "mode": "rw",
                }
            },
            **run_kwargs,
        )

        session = cls(
                    container,
                    command_timeout=command_timeout,
                )

        return session

    @classmethod
    def start_runtime_from_launch_image(
        cls,
        image_name: str,
        instance_id: str,
        command_timeout: int = 30,
    ) -> AndroidRuntime:
        container_id = instance_id.replace("/", "_")
        return cls._start_container(
            image_name=image_name,
            container_id=container_id,
            docker_timeout=7200,
            command_timeout=command_timeout,
        )

    @classmethod
    def start_runtime_from_base_image(
        cls,
        image_name: str,
        instance: dict[str, Any],
        command_timeout: int = 30,
    ) -> AndroidRuntime:
        container_id = instance["instance_id"].replace("/", "_")
        session = cls._start_container(
            image_name=image_name,
            container_id=container_id,
            docker_timeout=18000,
            command_timeout=command_timeout,
        )

        url = f'https://github.com/{instance["repo"]}.git'
        base_commit = instance["base_commit"]

        git_install_cmd = "command -v git >/dev/null || (apt-get update && apt-get install -y git)"
        repo_clone_cmd = f"git config --global --add safe.directory /testbed; git init /testbed; cd /testbed; git remote add origin {url}; git fetch --depth 1 origin {base_commit}; git reset --hard {base_commit}"
        session.preparation_commands.extend([git_install_cmd, repo_clone_cmd])
        session.send_command(git_install_cmd)
        res: CommandResult = session.send_command(repo_clone_cmd)
        session.send_command("ls")

        if int(res.metadata.exit_code) != 0:
            session.cleanup()
            raise RuntimeError(f"Git clone/reset failed: \n{res.output}")

        return session