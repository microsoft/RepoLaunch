from __future__ import annotations
from abc import ABC, abstractmethod
import io
import json
import os
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import docker
from docker.models.containers import Container
from typing_extensions import Self

CMD_OUTPUT_PS1_BEGIN = "\n###PS1JSON###\n"
CMD_OUTPUT_PS1_END = "\n###PS1END###"
CMD_OUTPUT_METADATA_PS1_REGEX = re.compile(
    r"(?m)^\s*" + re.escape(CMD_OUTPUT_PS1_BEGIN.strip()) + r"\s*(.*?)\s*" + re.escape(CMD_OUTPUT_PS1_END.strip()),
    re.DOTALL
)
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

TIMEOUT_EXIT_CODE = 124

MEM_LIMIT = "16g"
CPU_CORES = 4


VAR_PATTERNS = {
    'exit_code': re.compile(r'"exit_code":\s*(-?\d+)\s*(?:,|\})'),
    'username': re.compile(r'"username":\s*"([^"]*)"'),
    'hostname': re.compile(r'"hostname":\s*"([^"]*)"'),
    'working_dir': re.compile(r'"working_dir":\s*"([^"]*)"'),
    'py_interpreter_path': re.compile(r'"py_interpreter_path":\s*"([^"]*)"'),
}

available_platforms = Literal["linux", "windows", "android"]

@dataclass
class CmdOutputMetadata:
    """
    Additional metadata captured from PS1 shell prompt.
    
    Provides context about command execution environment including
    exit codes, user info, working directory, and Python interpreter.
    """

    exit_code: int = -1
    username: str | None = None
    hostname: str | None = None
    working_dir: str | None = None
    py_interpreter_path: str | None = None

    @classmethod
    def to_ps1_prompt(cls) -> str:
        """
        Convert metadata requirements into a PS1 prompt string.
        
        Returns:
            str: PS1 prompt configuration for capturing metadata
        """
        prompt = CMD_OUTPUT_PS1_BEGIN
        json_str = json.dumps(
            {
                "exit_code": "$?",
                "username": r"\u",
                "hostname": r"\h",
                "working_dir": r"$(pwd)",
                "py_interpreter_path": r'$(which python 2>/dev/null || echo "")',
            },
            indent=2,
        )
        # Make sure we escape double quotes in the JSON string
        # So that PS1 will keep them as part of the output
        prompt += json_str.replace('"', r"\"")
        prompt += CMD_OUTPUT_PS1_END + "\n"  # Ensure there's a newline at the end
        return prompt

    @classmethod
    def matches_ps1_metadata(cls, output: str) -> list[re.Match[str]]:
        matches = []
        for match in CMD_OUTPUT_METADATA_PS1_REGEX.finditer(output):
            scope = match.group(1).strip()
            try:
                d = json.loads(scope)  # Try to parse as JSON
                matches.append(match)
            except json.JSONDecodeError:
                d = cls.best_effort_match(scope)
                if len(d) > 0:
                    matches.append(match)
        return matches
    
    @classmethod
    def best_effort_match(cls, scope: str) -> dict:
        out = {}
        for field, pattern in VAR_PATTERNS.items():
            m = pattern.search(scope)
            if m:
                out[field] = m.group(1)
            else:
                out[field] = ""
        return out

    @classmethod
    def from_ps1_match(cls, match: re.Match[str]) -> Self:
        """
        Extract metadata from a PS1 prompt regex match.
        
        Args:
            match (re.Match[str]): Regex match containing JSON metadata
            
        Returns:
            Self: CmdOutputMetadata instance with parsed values
        """
        try:
            metadata = json.loads(match.group(1)) 
        except:
            metadata = cls.best_effort_match(match.group(1))
        # Create a copy of metadata to avoid modifying the original
        processed = metadata.copy()
        # Convert numeric fields
        if "exit_code" in metadata:
            try:
                processed["exit_code"] = int(float(str(metadata["exit_code"])))
            except (ValueError, TypeError):
                processed["exit_code"] = -1
        return cls(**processed)


@dataclass
class CommandResult:
    """
    Result of a command execution with output and metadata.
    
    Attributes:
        output (str): Command output text
        metadata (CmdOutputMetadata): Execution context metadata
    """
    output: str
    metadata: CmdOutputMetadata

    def to_observation(self, strip: bool = True) -> str:
        """
        Convert command result to formatted observation string.
        
        Args:
            strip (bool): Whether to truncate long output
            
        Returns:
            str: Formatted observation with output and context
        """
        # compile regex once for efficiency
        ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        
        output = ANSI_ESCAPE.sub("", self.output).replace("\r", "")

        if len(output) > 1024 * 16 and strip:
            output = (
                output[: 1024 * 8]
                + "....stripped due to length....\n"
                + output[-1024 * 8 :]
            )

        if self.metadata is None:
            return f"\n{output}\n"
        return f"""{output}
{self.metadata.username}@{self.metadata.hostname}:{self.metadata.working_dir} $

exit code: {self.metadata.exit_code}
"""

class BaseRuntime(ABC): 
    """
    Docker container runtime for repository setup and testing.
    
    Manages a Docker container with persistent bash session, command execution,
    file operations, and container lifecycle management.
    """

    container: Container
    mnt_container: str
    mnt_host: str
    platform: available_platforms
    # note: platform means the enviroment inside the container
    # as windows os can run linux container, on windows computer you can also have platform="linux"
    command_timeout: int # in minute
    stopped: bool
    preparation_commands: list[str] = []

    @abstractmethod
    def send_command(self, command: str, timeout: int|None = None) -> CommandResult:
        pass

    @abstractmethod
    def apply_patch(self, patch: str, verbose: bool = False) -> bool:
        pass
    
    def copy_to_container(self, src: str, dest: str) -> None:
        """
        Copy local file or directory 'src' into the container at path 'dest'.

        If 'src' is a directory, all files within that directory (recursively)
        are placed inside 'dest' in the container. If 'src' is a single file,
        it is placed inside 'dest' (which is typically a directory).
        """
        tar_stream = io.BytesIO()
        src = os.path.abspath(src)

        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            if os.path.isdir(src):
                # Add directory contents so they appear directly under `dest`.
                tar.add(src, arcname=".")
            else:
                # Add a single file using its basename.
                tar.add(src, arcname=os.path.basename(src))

        tar_stream.seek(0)

        # Put the archive into the container. `dest` must exist and be a directory
        # when copying directories, or you'll need to ensure it's the appropriate file path
        # when copying a single file.
        self.container.put_archive(dest, tar_stream)

    def copy_dir_to_container(self, src: str, dest: str) -> None:

        src = Path(src)
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            for file_path in src.rglob("*"):
                arcname = file_path.relative_to(src)
                tar.add(str(file_path), arcname=str(arcname))
        tar_stream.seek(0)

        self.container.put_archive(path=dest, data=tar_stream.read())
        if self.platform in ("linux", "android"):
            self.send_command(f'chown -R root:root "{dest}"')

    def commit(self, image_name: str, tag: str = "latest", push: bool = False) -> str:
        '''
        Current implementation means commit to image and remove container.
        '''
        self.container.stop()

        self.container.commit(
            repository=image_name,
            tag=tag,
        )
        print(f"Image {image_name}:{tag} created successfully.")

        if push:
            client = docker.from_env()
            client.images.push(image_name, tag=tag)
            print(f"Image {image_name}:{tag} pushed successfully.")

        #self.container.start()
        self.cleanup()
        # currently restart from stopped container is not enabled. you need to launch a new instance from the new image you committed.
        return f"{image_name}:{tag}"

    @staticmethod
    def pull_image(image_name: str) -> bool:
        """
        Pull Docker image from registry.
        
        Args:
            image_name (str): Name of the Docker image to pull
            
        Returns:
            bool: True if successful, False if image not found
        """
        client = docker.from_env(timeout=3600) # pull should finish in 1 hour
        try:
            # Check if image exists locally
            client.images.get(image_name)
            return True
        except docker.errors.ImageNotFound:
            # Image doesn't exist locally, try to pull it
            try:
                client.images.pull(image_name)
                return True
            except docker.errors.ImageNotFound:
                raise ValueError(f"Image {image_name} not found in registry")

    def cleanup(self, prune_dangling: bool = True) -> None:
        if self.stopped:
            return
        try:
            self.container.stop()
            self.container.remove(force=True)
            self.stopped = True
        except Exception as e:
            print(f"Failed to stop container: {e}")
        if prune_dangling:
            try:
                client = docker.from_env()
                client.images.prune(filters={'dangling': True})
            except Exception as e:
                print(e, "...Skipping...")

    def __del__(self):
        self.cleanup()

    @classmethod
    @abstractmethod
    def start_runtime_from_launch_image(
        cls,
        image_name: str,
        instance_id: str,
        command_timeout: int = 30,
    ) -> BaseRuntime: 
        pass

    @classmethod
    @abstractmethod
    def start_runtime_from_base_image(
        cls,
        image_name: str,
        instance: dict[str, Any],
        command_timeout: int = 30,
    ) -> BaseRuntime: 
        pass

    