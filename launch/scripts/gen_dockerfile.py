'''
usage:
```
python -m launch.scripts.gen_dockerfile  --dataset data/..../organize.jsonl  --platform linux (windows)  --output_dir data/dockerfiles
```

notes:
1) recover images from: launch/core/runtime.py::SetupRuntime::from_base_image/from_launch_image -> BaseRuntime.send_command(...) -> BaseRuntime.commit(name, tag)
2) three layers: base image, setup layer, optional organize layer if layer info exists
3) put all commands of setup layer into one layer on top of base image
4) if organize layer info exists, put all commands of organize layer into one layer on top of setup layer
5) Note some commands in the command list may fail. The dockerfile build process should continue even some commands fail instead of being interrupted.
6) note some commands might be multi-line, consider multi-line handling both in linux dockerfile and windows container dockerfile
'''

from argparse import ArgumentParser
from pathlib import Path
import json
import os
from typing import Any, Literal, Optional, TypedDict

class LayerInfo(TypedDict):
    base_image: str
    setup_layer: list[str] # list of shell commands
    organize_layer: Optional[list[str]] # list of shell commands


# Match runtime.py defaults so generated images match what the agent commits.
LINUX_WORKDIR = "/testbed"
WINDOWS_WORKDIR = r"C:\testbed"

# Heredoc / here-string delimiters chosen to be unlikely to appear in any real command.
LINUX_HEREDOC_TAG = "RL_CMD_EOF"
WINDOWS_HEREDOC_TAG = "RL_CMD_EOF"


def _render_linux_layer(commands: list[str], comment: str) -> list[str]:
    """
    Render one linux layer (setup or organize) as a single Dockerfile RUN that uses
    a BuildKit heredoc (requires DOCKER_BUILDKIT=1, default on modern docker).

    Each input command is wrapped in a `( ... ) || true` subshell so that:
      - multi-line commands stay verbatim and readable (the subshell groups them);
      - a failing command does not abort the whole RUN (note 5).
    """
    if not commands:
        return []

    out: list[str] = ["", f"# ---- {comment} ----", f"RUN <<'{LINUX_HEREDOC_TAG}'"]
    out.append("set +e")
    for cmd in commands:
        body = cmd.rstrip("\n")
        out.append("(")
        for line in body.splitlines() or [""]:
            out.append(line)
        out.append(") || true")
    out.append(LINUX_HEREDOC_TAG)
    return out


def gen_linux_dockerfile(layers: dict[str, Any]) -> str:
    base_image: str = layers["base_image"]
    setup_cmds: list[str] = list(layers.get("setup_layer") or [])
    organize_cmds: list[str] = list(layers.get("organize_layer") or [])

    lines: list[str] = [
        "# syntax=docker/dockerfile:1.4",
        f"FROM {base_image}",
        f"WORKDIR {LINUX_WORKDIR}",
        'SHELL ["/bin/bash", "-c"]',
    ]
    lines.extend(_render_linux_layer(setup_cmds, "setup layer"))
    lines.extend(_render_linux_layer(organize_cmds, "organize layer"))
    lines.append("")
    return "\n".join(lines)


def _render_windows_layer(commands: list[str], comment: str) -> list[str]:
    """
    Render one windows layer as a single Dockerfile RUN that uses a BuildKit heredoc
    feeding a literal here-string into PowerShell.

    Each input command is wrapped in a try/catch so multi-line commands stay readable
    and one failure does not abort the build (note 5). Single quotes inside the
    `@'...'@` here-string are doubled per PowerShell rules.
    """
    if not commands:
        return []

    out: list[str] = ["", f"# ---- {comment} ----", f"RUN <<'{WINDOWS_HEREDOC_TAG}'"]
    out.append("$ErrorActionPreference = 'Continue'")
    for cmd in commands:
        body = cmd.rstrip("\n").replace("'", "''")
        out.append("try {")
        out.append("  $cmd = @'")
        for line in body.splitlines() or [""]:
            out.append(line)
        out.append("'@")
        out.append("  Invoke-Expression $cmd")
        out.append("} catch { Write-Host $_.Exception.Message }")
    out.append(WINDOWS_HEREDOC_TAG)
    return out


def gen_windows_dockerfile(layers: dict[str, Any]) -> str:
    base_image: str = layers["base_image"]
    setup_cmds: list[str] = list(layers.get("setup_layer") or [])
    organize_cmds: list[str] = list(layers.get("organize_layer") or [])

    lines: list[str] = [
        "# syntax=docker/dockerfile:1.4",
        "# escape=`",
        f"FROM {base_image}",
        f"WORKDIR {WINDOWS_WORKDIR}",
        'SHELL ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command"]',
    ]
    lines.extend(_render_windows_layer(setup_cmds, "setup layer"))
    lines.extend(_render_windows_layer(organize_cmds, "organize layer"))
    lines.append("")
    return "\n".join(lines)


def main(instances: list[dict[str, Any]], output_dir: Path, platform: Literal["linux", "windows"]) -> None:
    for instance in instances:
        filename: str = "Dockerfile_" + instance["instance_id"].strip().replace("/", "_") + "_" + platform
        filepath: Path = (output_dir / filename)
        if platform == "linux":
            dockerfile = gen_linux_dockerfile(instance["docker_image_layers"])
        else:
            dockerfile =  gen_windows_dockerfile(instance["docker_image_layers"])
        filepath.write_text(dockerfile)
    return

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--platform", type=str, choices=["linux", "windows"])
    parser.add_argument("--output_dir", type=Path, required=True)
    args = parser.parse_args()
    instances: list[dict[str, Any]] = [json.loads(i) for i in args.dataset.read_text().splitlines()]
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)
    elif not os.path.isdir(args.output_dir):
        raise ValueError("argument 'output_dir' should be path to a directory.")
    main(instances, args.output_dir, args.platform)
