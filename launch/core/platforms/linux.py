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
    CommandResult,
    BaseRuntime
)

import os, json
from typing import Any, Optional
import queue
import threading
import time
import uuid

import docker
from docker.models.containers import Container

class LinuxRuntime(BaseRuntime):

    def __init__(
                    self, 
                    container: Container, 
                    command_timeout: int = 30
                ):
        """
        Initialize runtime with an existing Docker container.
        
        Args:
            container (Container): Docker container instance to manage
        """
        self.container = container
        self.platform = "linux"
        self.command_timeout=command_timeout
        self.working_dir = r"/testbed"
        self.mnt_host = os.path.join(os.getcwd(), "tmp")
        self.mnt_container = r"/mnt_tmp"
        self.sock = self.container.attach_socket(
            params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
        )
        self.output_queue: queue.Queue[bytes] = queue.Queue()
        self.stopped = False
        self._start_output_thread()
        self._clear_initial_prompt()
        json_str = json.dumps(
            {
                "exit_code": "$?",
                "username": r"\u",
                "hostname": r"\h",
                "working_dir": r"$(pwd)",
                "py_interpreter_path": r'$(which python 2>/dev/null || echo "")',
            },
            indent=2,
        ).replace('"', r"\"")
        ps1 = CMD_OUTPUT_PS1_BEGIN + json_str + CMD_OUTPUT_PS1_END + "\n"
        self.send_command(
            f'export PROMPT_COMMAND=\'export PS1="{ps1}"\'; export PS2=""'
        )
        self.preparation_commands = []

    def _stream_output(self):
        while True:
            try:
                output = self._recv_bytes(4096)
                if not output:
                    break
                self.output_queue.put(output)
            except (OSError, ConnectionError) as e:
                print(f"Connection error in _stream_output: {e}")
                break
            except Exception as e:
                # print(f"Unexpected error in _stream_output: {e}")
                break

    def _start_output_thread(self):
        self.output_thread = threading.Thread(target=self._stream_output, daemon=True)
        self.output_thread.start()

    def _clear_initial_prompt(self):
        time.sleep(1)
        while not self.output_queue.empty():
            self.output_queue.get()

    def _read_raw_output(self, timeout:int=30) -> tuple[str, Optional[CmdOutputMetadata]]:
        '''
        timeout: in seconds
        '''
        
        accumulated_output = ""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                chunk = self.output_queue.get(timeout=0.1)
                accumulated_output += chunk.decode("utf-8", errors="ignore")
                # PSReadLine injects ANSI + cursor control; normalize before matching
                accumulated_clean = ANSI_ESCAPE.sub("", accumulated_output).replace("\r", "")
                ps1_matches = CmdOutputMetadata.matches_ps1_metadata(accumulated_clean)
                if ps1_matches:
                    break
            except queue.Empty:
                continue
        accumulated_output = ANSI_ESCAPE.sub("", accumulated_output).replace("\r", "")
        ps1_matches = CmdOutputMetadata.matches_ps1_metadata(accumulated_output)
        metadata = (
            CmdOutputMetadata.from_ps1_match(ps1_matches[-1]) if ps1_matches else None
        )
        output = self._combine_outputs_between_matches(
            accumulated_output,
            ps1_matches,
        )
        return output, metadata

    def _combine_outputs_between_matches(
        self, pane_content: str, ps1_matches: list[re.Match[str]]
    ) -> str:
        if len(ps1_matches) == 1:
            return pane_content[: ps1_matches[0].start()]
        elif len(ps1_matches) == 0:
            return pane_content
        output_segments = []
        for i in range(len(ps1_matches) - 1):
            output_segment = pane_content[
                ps1_matches[i].end() + 1 : ps1_matches[i + 1].start()
            ]
            output_segments.append(output_segment)
        return "\n".join(output_segments) + "\n" if output_segments else ""

    def _recv_bytes(self, n=4096) -> bytes:
        # Prefer the public API on whatever object the SDK returns
        for m in ("recv", "read"):
            if hasattr(self.sock, m):
                return getattr(self.sock, m)(n)
        # Last-resort fallback for odd wrappers that still expose ._sock
        if hasattr(self.sock, "_sock"):
            for m in ("recv", "read"):
                if hasattr(self.sock._sock, m):
                    return getattr(self.sock._sock, m)(n)
        raise TypeError(f"Don't know how to read from {type(self.sock).__name__}")

    def _send_bytes(self, data: bytes) -> None:
        if hasattr(self.sock, "_sock"):
            for m in ("send", "sendall", "write"):
                if hasattr(self.sock._sock, m):
                    getattr(self.sock._sock, m)(data)
                    return
        for m in ("send", "sendall", "write"):
            if hasattr(self.sock, m):
                getattr(self.sock, m)(data)
                return

        raise TypeError(f"Don't know how to write to {type(self.sock).__name__}")

    def send_command(self, command: str, timeout: int|None = None) -> CommandResult:
        '''
        timeout: deprecated arg for backward compatibility. In minute. If not specified use self.timeout from object inittialization.
        '''
        timeout = self.command_timeout * 60 if timeout is None else timeout * 60 # in seconds

        if self.stopped:
            raise RuntimeError("container is stopped. Currently we have not enabled container restart after docker commit. If you need to restore the container you must launch from the new image you committed.")
        
        if not command.endswith("\n"):
            command += "\n"

        self._clear_initial_prompt()

        self._send_bytes(command.encode())

        output, metadata = self._read_raw_output(timeout=timeout)
        if metadata is not None:
            return CommandResult(output=output, metadata=metadata)

        # handle timeout
        # to kill the task completely, should Ctrl^C for several times
        for _ in range(10):
            self._send_bytes(b"\x03")

        kill_timeout = 5
        kill_output, kill_metadata = self._read_raw_output(timeout=kill_timeout)

        output = output + kill_output + "\n**Exited due to timeout**\n"
        if kill_metadata is not None:
            kill_metadata.exit_code = TIMEOUT_EXIT_CODE
            return CommandResult(output=output, metadata=kill_metadata)

        fallback_metadata = CmdOutputMetadata(
            exit_code=TIMEOUT_EXIT_CODE,
        )

        return CommandResult(output=output, metadata=fallback_metadata)

    def apply_patch(self, patch: str, verbose: bool = False) -> bool:
        output_temp = "\n\n<<<<<<PATCH FAILED TO APPLY CLEANLY\n{out}\n>>>>>>\n\n"

        filename = f"{uuid.uuid4()}.diff"
        hostpath = os.path.join(self.mnt_host, filename)
        with open(hostpath, "w") as f:
            f.write(patch)
        containerpath =  os.path.join(self.mnt_container, filename)
        
        cmd = f"""git apply --reject  --whitespace=nowarn  {containerpath} """
        res = self.send_command(cmd)
        self.send_command(f"rm {containerpath}")
        if int(res.metadata.exit_code) == 0:
            print(f"{cmd} ---- Patch applied Successfully!", flush=True)
            return True
        else:
            if verbose:
                print(output_temp.format(out=res.output), flush=True)
            return False
    
    @classmethod
    def _start_container(
        cls,
        image_name: str,
        container_id: str,
        docker_timeout: int,
        command_timeout: int,
    ) -> LinuxRuntime:
        try:
            docker.from_env().ping()
        except docker.errors.DockerException:
            raise RuntimeError("Docker is not installed or not running.")

        _ = cls.pull_image(image_name)
        client = docker.from_env(timeout=docker_timeout) # commit added layers should finish in 2 hours
        container_name = f"git-launch-{container_id}-{str(uuid.uuid4())[:4]}"
        info = client.version()
        engine_os = (info.get("Os") or info.get("OSType") or "").lower() 
        # which operating system this code is running on, note windows can run linux containers, so engine_os != (container) platform
        extra_hosts = {"host.docker.internal": "host-gateway"} if "linux" in engine_os else None

        os.makedirs(os.path.join(os.getcwd(), "tmp"), exist_ok=True)
        shell_command = "/bin/bash"
        working_dir = "/testbed"
        run_kwargs = {
            "cpu_quota": int(CPU_CORES * 100000),
            "mem_limit": MEM_LIMIT,
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
    ) -> LinuxRuntime:
        """
        Start a Docker container session for repository testing.
        
        Args:
            image_name (str): Base Docker image name
            instance (dict): SWE-bench instance data with repo info
            platform: the platform of the container, linux or windows
            
        Returns:
            SetupRuntime: Configured runtime session ready for command execution
            
        Raises:
            RuntimeError: If Docker is not available
        """
        container_id = instance_id.replace("/", "_")
        session = cls._start_container(
            image_name,
            container_id,
            7200, # commit added layers should finish in 2 hours
            command_timeout
        )
        return session

    @classmethod
    def start_runtime_from_base_image(
        cls,
        image_name: str,
        instance: dict[str, Any],
        command_timeout: int = 30,
    ) -> LinuxRuntime:
        """
        Start a Docker container session for repository testing.
        
        Args:
            image_name (str): Base Docker image name
            instance (dict): SWE-bench instance data with repo info
            platform: the platform of the container, linux or windows
            
        Returns:
            SetupRuntime: Configured runtime session ready for command execution
            
        Raises:
            RuntimeError: If Docker is not available
        """

        # todo: make docker commit a separate thread / process, make it async to accelerate
        container_id = instance["instance_id"].replace("/", "_")
        session = cls._start_container(
            image_name,
            container_id,
            18000,  # commit setup layers usually take very long time, give 5h timeout here
            command_timeout,
        )

        # We avoid copying due to performance issues
        # session.copy_dir_to_container(str(workspace), "/workspace")

        url = f'https://github.com/{instance["repo"]}.git'
        base_commit = instance["base_commit"]

        git_install_cmd = "apt update && apt install -y git"
        repo_clone_cmd = f"git config --global --add safe.directory /testbed; git init /testbed; cd /testbed; git remote add origin {url}; git fetch --depth 1 origin {base_commit}; git reset --hard {base_commit}"
        session.preparation_commands.extend([git_install_cmd, repo_clone_cmd])
        session.send_command(git_install_cmd)
        res: CommandResult = session.send_command(repo_clone_cmd)
        session.send_command("ls")
        
        if int(res.metadata.exit_code) != 0:
            session.cleanup()
            raise RuntimeError(f"Git clone/reset failed: \n{res.output}")

        return session
