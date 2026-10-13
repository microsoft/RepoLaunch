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
        """Execute a command through Docker's non-interactive exec API.

        Windows containers expose a ConPTY when started with ``tty=True``.  The
        old persistent attach path could leave long-running commands in an idle
        PowerShell prompt and only produced zero-byte capture files.  Direct
        ``exec_run`` avoids ConPTY and returns the command output as a normal
        process result while keeping the existing runtime API unchanged.
        """
        timeout_seconds = self.command_timeout * 60 if timeout is None else timeout * 60

        if self.stopped:
            raise RuntimeError(
                "container is stopped. Currently we have not enabled container restart after docker commit. "
                "If you need to restore the container you must launch from the new image you committed."
            )

        import json
        command_name = f"windows-command-{uuid.uuid4().hex}.ps1"
        command_host_path = os.path.join(self.mnt_host, command_name)
        command_guest_path = f"C:\\mnt_tmp\\{command_name}"
        # Each exec is a fresh PowerShell process, so make the runtime working
        # directory explicit rather than relying on persistent shell state.
        script = (
            "Set-Location -LiteralPath 'C:\\testbed'\n"
            + "$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)\n"
            + "$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'\n"
            + command
            + "\n"
            + "$__slai_ec = if ($LASTEXITCODE -ne $null) { [int]$LASTEXITCODE } elseif ($?) { 0 } else { 1 }\n"
            + "Write-Output '###PS1JSON###'\n"
            + "$__slai_obj=[ordered]@{exit_code=$__slai_ec; username=$env:USERNAME; "
            + "hostname=$env:COMPUTERNAME; working_dir=(Get-Location).Path; py_interpreter_path=''}\n"
            + "$__slai_obj | ConvertTo-Json -Compress\n"
            + "Write-Output '###PS1END###'\n"
        )
        os.makedirs(self.mnt_host, exist_ok=True)
        with open(command_host_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(script)

        try:
            # exec_run is deliberately non-TTY: no ConPTY wrapping, no prompt
            # state, and no second capture file are involved.
            result = self.container.exec_run(
                [
                    "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", command_guest_path,
                ],
                workdir=self.working_dir,
                stdout=True,
                stderr=True,
                demux=False,
            )
            raw_output = result.output
            if isinstance(raw_output, tuple):
                raw_output = (raw_output[0] or b"") + (raw_output[1] or b"")
            raw_bytes = raw_output or b""
            # Windows PowerShell redirection uses UTF-16LE by default. Decode
            # the BOM-marked stream before stripping ANSI/control characters;
            # UTF-8 replacement turns every second byte into NULs and makes the
            # Go JSONL parser silently lose the test records.
            if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
                output = raw_bytes.decode("utf-16", errors="replace")
            else:
                output = raw_bytes.decode("utf-8", errors="replace")
            output = ANSI_ESCAPE.sub("", output).replace("\r", "")
            matches = CmdOutputMetadata.matches_ps1_metadata(output)
            metadata = CmdOutputMetadata.from_ps1_match(matches[-1]) if matches else None
            if metadata is not None:
                output = output[:matches[-1].start()]
            else:
                exit_code = result.exit_code
                if exit_code is None:
                    exit_code = TIMEOUT_EXIT_CODE if timeout_seconds <= 0 else 1
                metadata = CmdOutputMetadata(
                    exit_code=int(exit_code),
                    username=None,
                    hostname=None,
                    working_dir=self.working_dir,
                    py_interpreter_path=None,
                )
            return CommandResult(output=output, metadata=metadata)
        finally:
            try:
                os.remove(command_host_path)
            except OSError:
                pass

    def apply_patch(self, patch: str, verbose: bool = False) -> bool:
        """Apply a unified diff using a native Windows container path."""
        output_temp = "\n\n<<<<<<PATCH FAILED TO APPLY CLEANLY\n{out}\n>>>>>>\n\n"
        filename = f"{uuid.uuid4()}.diff"
        hostpath = os.path.join(self.mnt_host, filename)
        guestpath = f"C:\\mnt_tmp\\{filename}"
        os.makedirs(self.mnt_host, exist_ok=True)
        with open(hostpath, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(patch)
        try:
            # LinuxRuntime.apply_patch uses /mnt_tmp, which is invalid inside a
            # Windows container.  Keep the same patch protocol but use the
            # mounted Windows path explicitly.
            res = self.send_command(
                f"git apply --reject --whitespace=nowarn '{guestpath}'"
            )
            ok = int(res.metadata.exit_code) == 0
            if ok:
                if verbose:
                    print(f"git apply {guestpath} ---- Patch applied Successfully!", flush=True)
                return True
            if verbose:
                print(output_temp.format(out=res.output), flush=True)
            return False
        finally:
            try:
                os.remove(hostpath)
            except OSError:
                pass

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
    