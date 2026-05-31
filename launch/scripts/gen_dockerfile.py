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
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

class LayerInfo(TypedDict):
    base_image: str
    setup_layer: list[str] # list of shell commands
    organize_layer: Optional[list[str]] # list of shell commands


# Match runtime.py defaults so generated images match what the agent commits.
LINUX_WORKDIR = "/testbed"
WINDOWS_WORKDIR = r"C:\testbed"

# Heredoc delimiter for the linux generator (BuildKit heredoc works on linux).
LINUX_HEREDOC_TAG = "RL_CMD_EOF"

# Windows sentinels. The windows generator must work on the *legacy* Docker builder
# (Docker Desktop in Windows-container mode does not use BuildKit, and no
# `docker/dockerfile` frontend tag publishes a Windows manifest, so heredocs are
# unavailable for windows containers). The legacy builder also strips literal double
# quotes from shell-form RUN instructions. So every command is carried as a
# single-quoted PowerShell string with these substitutions, then reconstituted into a
# .ps1 at build time:
#   "  -> WINDOWS_DQ_SENTINEL  (decoded to [char]34 ; avoids the builder eating quotes)
#   \n -> WINDOWS_NL_SENTINEL  (decoded to [char]10 ; avoids RUN line-splitting)
#   '  -> ''                   (PowerShell single-quoted-string escaping)
# Chosen to be extremely unlikely to appear verbatim in any real command.
WINDOWS_DQ_SENTINEL = "~~RLDQ~~"
WINDOWS_NL_SENTINEL = "~~RLNL~~"


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


def gen_linux_dockerfile(layers: LayerInfo) -> str:
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


def _windows_layer_script_path(comment: str) -> str:
    """Stable, unlikely-to-collide path for the per-layer script staged into the image."""
    slug = comment.strip().lower().replace(" ", "_")
    return rf"C:\rl_{slug}.ps1"


def _encode_windows_command(cmd: str) -> str:
    """
    Encode one command for transport inside a single-quoted PowerShell string on one
    physical (backtick-continued) Dockerfile line. See WINDOWS_*_SENTINEL above.

    Substitution order is significant: hide double quotes first (plain swap), then
    escape single quotes for the surrounding single-quoted string, then hide newlines.
    The two sentinels are disjoint from `'`-doubling so decode order at build time does
    not matter.
    """
    s = cmd.rstrip("\n")
    s = s.replace('"', WINDOWS_DQ_SENTINEL)
    s = s.replace("'", "''")
    s = s.replace("\r\n", "\n").replace("\n", WINDOWS_NL_SENTINEL)
    return s


def _render_windows_layer(commands: list[str], comment: str) -> list[str]:
    """
    Render one windows layer as a single RUN instruction (one layer per setup/organize,
    note 3/4) that assembles a .ps1 inside the image and executes it.

    The RUN does, in order (each step its own backtick-continued physical line):
      - Set-Content an empty .ps1, then one Add-Content per command appending its
        encoded `try { <cmd> } catch { ... }` block (note 5: a failure -- PowerShell
        error -- is swallowed; a nonzero native exit code does not throw, so execution
        simply falls through to the next command);
      - decode the two sentinels back to real `"` and newlines, rewriting the .ps1 as a
        normal multi-line script (note 6: multi-line commands are preserved verbatim);
      - execute the .ps1.

    Why not a heredoc: Docker Desktop builds windows containers with the *legacy*
    builder (no BuildKit), and no `docker/dockerfile` frontend image is published for
    windows, so `RUN <<EOF` / `COPY <<EOF` are unavailable. Why the sentinels: the
    legacy builder strips literal double quotes from shell-form RUN, and a literal
    newline would split the RUN into separate (invalid) instructions. Encoding both
    sidesteps the builder entirely and is plaintext (no base64).
    """
    if not commands:
        return []

    script_path: str = _windows_layer_script_path(comment)

    # Each entry becomes one physical line in the RUN, joined by " ; `" continuations.
    statements: list[str] = [
        f"Set-Content -LiteralPath {script_path} -Value '' -Encoding UTF8",
        f"Add-Content -LiteralPath {script_path} -Value '$ErrorActionPreference = ''Continue'''",
    ]
    for cmd in commands:
        # try/catch swallows PowerShell-thrown errors; `finally { $global:LASTEXITCODE = 0 }`
        # neutralizes a *native* command's nonzero exit (e.g. `dotnet test` failing does
        # not throw, it only sets $LASTEXITCODE). Together: every command exits clean and
        # the next one always runs (note 5), no matter how it failed.
        body = (
            "try {"
            + WINDOWS_NL_SENTINEL
            + _encode_windows_command(cmd)
            + WINDOWS_NL_SENTINEL
            + "} catch { Write-Host $_.Exception.Message } finally { $global:LASTEXITCODE = 0 }"
        )
        statements.append(f"Add-Content -LiteralPath {script_path} -Value '{body}'")
    statements.append(
        f"(Get-Content -LiteralPath {script_path} -Raw)"
        f" -replace '{WINDOWS_DQ_SENTINEL}',[char]34"
        f" -replace '{WINDOWS_NL_SENTINEL}',[char]10"
        f" | Set-Content -LiteralPath {script_path} -Encoding UTF8"
    )
    statements.append(f"& {script_path}")
    # Remove the script in the SAME RUN so it never gets committed into the layer
    # (deleting it in a later RUN would whiteout-mask it but keep it on disk, growing
    # the image). SilentlyContinue so cleanup never fails the RUN.
    statements.append(f"Remove-Item -Force -ErrorAction SilentlyContinue {script_path}")

    # Backtick line-continuation: every physical line but the last ends with " ; `".
    run_lines = [("RUN " if i == 0 else "    ") + stmt for i, stmt in enumerate(statements)]
    run_block = " ; `\n".join(run_lines)

    return ["", f"# ---- {comment} ----", run_block]


def gen_windows_dockerfile(layers: LayerInfo) -> str:
    base_image: str = layers["base_image"]
    setup_cmds: list[str] = list(layers.get("setup_layer") or [])
    organize_cmds: list[str] = list(layers.get("organize_layer") or [])

    # `# escape=`` switches the line-continuation char to a backtick so each layer's RUN
    # can span multiple physical lines (one Add-Content per line). No `# syntax`
    # directive: it would force pulling the dockerfile frontend image, which is not
    # published for windows and fails to resolve.
    lines: list[str] = [
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
    logging.info(("The gen_dockerfile script produces a Dockerfile from the command sequence of RepoLaunch. ",
                  "The Dockerfile behavior strictly aligns with that of RepoLaunch-created images: "
                  "it produces two layers (the setup layer and the organize layer) with error commands silenty bypassed instead of interuptting the build.\n"))
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
