"""Safe subprocess and isolated-worktree helpers."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shlex
import signal
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessResult:
    command: list[str] | str
    return_code: int | None
    stdout: bytes
    stderr: bytes
    duration_seconds: float
    timed_out: bool


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def ensure_within(root: Path, candidate: Path) -> Path:
    """Resolve a path and reject traversal outside ``root``."""

    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"path escapes worktree: {candidate}")
    return resolved


async def run_process(
    command: list[str] | str,
    *,
    cwd: Path,
    timeout_seconds: int,
    environment: dict[str, str] | None = None,
    unset_environment: Iterable[str] | None = None,
    stdin: bytes | None = None,
    shell: bool = False,
) -> ProcessResult:
    """Run a bounded command without silently discarding timeout evidence."""

    started = time.monotonic()
    env = os.environ.copy()
    for name in unset_environment or ():
        env.pop(name, None)
    if environment:
        env.update(environment)
    if shell:
        if not isinstance(command, str):
            command = shlex.join(command)
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=str(cwd),
            env=env,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    else:
        argv = shlex.split(command) if isinstance(command, str) else command
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(cwd),
            env=env,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(stdin), timeout=timeout_seconds)
        return_code: int | None = process.returncode
        timed_out = False
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            await asyncio.sleep(1)
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = await process.communicate()
        return_code = None
        timed_out = True
    return ProcessResult(
        command=command,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=time.monotonic() - started,
        timed_out=timed_out,
    )


class IsolatedWorktree:
    """A git worktree that may safely be reset by construction code."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        marker = self.path / ".git"
        if not marker.exists():
            raise ValueError(f"not a git worktree: {self.path}")

    async def git(
        self,
        *args: str,
        timeout_seconds: int = 300,
        stdin: bytes | None = None,
    ) -> ProcessResult:
        return await run_process(
            ["git", *args],
            cwd=self.path,
            timeout_seconds=timeout_seconds,
            stdin=stdin,
        )

    async def clean_to_head(self) -> None:
        """Reset only this explicitly constructed worktree."""

        reset = await self.git("reset", "--hard", "HEAD")
        if reset.return_code != 0:
            raise RuntimeError(reset.stderr.decode(errors="replace"))
        clean = await self.git("clean", "-fd")
        if clean.return_code != 0:
            raise RuntimeError(clean.stderr.decode(errors="replace"))

    async def apply_patch(self, patch: str, *, reverse: bool = False) -> tuple[bool, str]:
        args = ["apply"]
        if reverse:
            args.append("--reverse")
        check = await self.git(*args, "--check", "-", stdin=patch.encode())
        if check.return_code != 0:
            return False, check.stderr.decode(errors="replace")
        applied = await self.git(*args, "-", stdin=patch.encode())
        return (
            applied.return_code == 0,
            applied.stderr.decode(errors="replace"),
        )

    async def _intent_to_add_untracked(self) -> None:
        """Expose new files to ``git diff`` without staging their contents."""

        result = await self.git(
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        )
        if result.return_code != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        paths = [
            item.decode("utf-8", errors="surrogateescape")
            for item in result.stdout.split(b"\0")
            if item
        ]
        if paths:
            added = await self.git("add", "--intent-to-add", "--", *paths)
            if added.return_code != 0:
                raise RuntimeError(added.stderr.decode(errors="replace"))

    async def diff(self) -> str:
        await self._intent_to_add_untracked()
        result = await self.git("diff", "--binary")
        if result.return_code != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout.decode(errors="replace")

    async def reverse_diff(self) -> str:
        await self._intent_to_add_untracked()
        result = await self.git("diff", "-R", "--binary")
        if result.return_code != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout.decode(errors="replace")

    async def changed_files(self) -> list[str]:
        await self._intent_to_add_untracked()
        result = await self.git("diff", "--name-only")
        if result.return_code != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return sorted(
            line.strip()
            for line in result.stdout.decode(errors="replace").splitlines()
            if line.strip()
        )

    async def head(self) -> str:
        result = await self.git("rev-parse", "HEAD")
        if result.return_code != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        return result.stdout.decode().strip()
