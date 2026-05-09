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
import queue
import uuid

import docker
from docker.models.containers import Container


class WindowsRuntime(LinuxRuntime):

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
        self.platform = "windows"
        self.command_timeout=command_timeout
        self.working_dir = r"C:\testbed"
        self.mnt_container = r"C:\mnt_tmp"
        self.mnt_host = os.path.join(os.getcwd(), "tmp")
        self.sock = self.container.attach_socket(
            params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
        )
        self.output_queue: queue.Queue[bytes] = queue.Queue()
        self.stopped = False
        self._start_output_thread()
        self._clear_initial_prompt()
        self.send_command(r'''
function prompt {
  if ($?) {$ec=0; $LASTEXITCODE=0} else {if ($LASTEXITCODE -ne 0) {$ec=$LASTEXITCODE} else {$ec=1}}
  $u  = $env:USERNAME
  $h  = $env:COMPUTERNAME
  $wd = (Get-Location).Path
  $pyCmd = Get-Command python -ErrorAction SilentlyContinue
  $py = if ($pyCmd) {
    if ($pyCmd.PSObject.Properties.Match('Path').Count -gt 0 -and $pyCmd.Path) { $pyCmd.Path }
    elseif ($pyCmd.PSObject.Properties.Match('Source').Count -gt 0 -and $pyCmd.Source) { $pyCmd.Source }
    else { '' }
  } else { '' }
  Write-Output ""
  Write-Output "###PS1JSON###"
  $obj = [ordered]@{
    exit_code = $ec
    username = $u
    hostname = $h
    working_dir = $wd
    py_interpreter_path = $py
  }
  $obj | ConvertTo-Json -Compress
  Write-Output "###PS1END###"
  "PS $wd> "
}
''')
        self.preparation_commands = []

    def send_command(self, command: str, timeout: int|None = None) -> CommandResult:
        '''
        timeout: deprecated arg for backward compatibility. In minute. If not specified use self.timeout from object inittialization.
        '''
        timeout = self.command_timeout * 60 if timeout is None else timeout * 60 # in seconds

        if self.stopped:
            raise RuntimeError("container is stopped. Currently we have not enabled container restart after docker commit. If you need to restore the container you must launch from the new image you committed.")

        # Normalize newline semantics for interactive shells
        # For PowerShell, ensure CRLF line endings
        command = command.strip().replace("\r\n", "\n").replace("\n", "\r\n")
        # Add extra CRLF for multi-line blocks to signal completion
        command += "\r\n\r\nprompt\r\n\r\n"

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

    @classmethod
    def _start_container(
        cls,
        image_name: str,
        container_id: str,
        docker_timeout: int,
        command_timeout: int,
    ) -> WindowsRuntime:
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
        shell_command = r"powershell -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -NoExit"
        working_dir = r"C:\testbed"
        run_kwargs = {
            "cpu_count": CPU_CORES,  # cpu_quota is Linux-only
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
                    "bind": r"C:\mnt_tmp",
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
    ) -> WindowsRuntime:
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
            7200,
            command_timeout
        )
        return session



    @classmethod
    def start_runtime_from_base_image(
        cls,
        image_name: str,
        instance: dict[str, Any],
        command_timeout: int = 30,
    ) -> WindowsRuntime:
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

        # commit a new image built from scratch should require many many hours
        # todo: make docker commit a separate thread / process, make it async to accelerate
        container_id = instance["instance_id"].replace("/", "_")
        session = cls._start_container(
            image_name,
            container_id,
            18000,
            command_timeout
        )

        # We avoid copying due to performance issues
        # session.copy_dir_to_container(str(workspace), "/workspace")

        url = f'https://github.com/{instance["repo"]}.git'
        base_commit = instance["base_commit"]
        git_install_cmd = r'''
# Skip if git already present
if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
  try {
    # Prefer Chocolatey (cleaner package mgmt)
    if (-not (Get-Command choco.exe -ErrorAction SilentlyContinue)) {
      Set-ExecutionPolicy Bypass -Scope Process -Force
      [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
      Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    }

    choco install git.install -y --no-progress --params '"/GitOnlyOnPath /NoAutoCrlf"'
  }
  catch {
    Write-Host "Chocolatey install failed: $($_.Exception.Message)  -> falling back to Git for Windows installer"

    # Fallback: Official Git for Windows silent install
    $ProgressPreference = 'SilentlyContinue'
    $temp = Join-Path $env:TEMP 'git-installer.exe'
    # 'latest' link maintained by Git for Windows; resolves to current amd64 EXE
    $url  = 'https://github.com/git-for-windows/git/releases/latest/download/Git-64-bit.exe'
    try {
      Invoke-WebRequest -Uri $url -OutFile $temp
    } catch {
      Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $temp
    }

    # Silent/unattended flags per Git for Windows docs (Inno Setup):
    # /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
    # Optional components: icons, ext\reg\shellhere, assoc, assoc_sh, gitlfs, windowsterminal, scalar
    Start-Process -FilePath $temp -ArgumentList `
      '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-','/CLOSEAPPLICATIONS','/RESTARTAPPLICATIONS',`
      '/COMPONENTS="icons,ext\reg\shellhere,assoc,assoc_sh,gitlfs,windowsterminal,scalar"' `
      -Wait
  }

  # Ensure PATH is updated in this running session (Chocolatey/Git installers update registry only)
  $gitCmd = 'C:\Program Files\Git\cmd'
  $gitBin = 'C:\Program Files\Git\bin'
  if (Test-Path $gitCmd) { $env:PATH = "$gitCmd;$gitBin;$env:PATH" }
}
'''
        repo_clone_cmd = r'git config --global --add safe.directory "C:\testbed"; git init "C:\testbed"; cd "C:\testbed"; git remote add origin {url}; git fetch --depth 1 origin {base}; git reset --hard {base}'.format(
                url=url, base=base_commit
            )
        session.preparation_commands.extend([git_install_cmd, repo_clone_cmd])

        # 2) Ensure Git is installed (Chocolatey if possible; fallback to official silent installer).
        #    - Chocolatey official install script: https://community.chocolatey.org/install.ps1
        #    - git.install package params include /GitOnlyOnPath, /GitAndUnixToolsOnPath, /NoAutoCrlf, etc.
        #    - Git for Windows silent flags are documented by the project itself.
        session.send_command(git_install_cmd)
        res: CommandResult = session.send_command(repo_clone_cmd)
        session.send_command("ls")
        
        if int(res.metadata.exit_code) != 0:
            session.cleanup()
            raise RuntimeError(f"Git clone/reset failed: \n{res.output}")

        return session
    