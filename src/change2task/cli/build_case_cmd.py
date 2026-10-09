"""CLI command for the five-family Change2Task builder."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from change2task.core.config import get_settings
from change2task.workflow.construction.agent import ClaudeCodeBackend
from change2task.workflow.construction.cascade import CaseBuilder
from change2task.workflow.ledger import ConstructionLedger
from change2task.workflow.models import TaskCase

console = Console()


def build_case(
    case_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Normalized Change2Task TaskCase JSON.",
        ),
    ],
    repository_cache: Annotated[
        Path,
        typer.Option(
            "--repository-cache",
            exists=True,
            file_okay=False,
            help="Existing checkout containing the frozen modern commit.",
        ),
    ],
    run_root: Annotated[
        Path | None,
        typer.Option(
            "--run-root",
            help="Append-only local output root; defaults to CHANGE2TASK_RUN_ROOT.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Optional path for the final ConstructionOutcome JSON.",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option("--model", help="Override CHANGE2TASK_L3_MODEL."),
    ] = None,
    keep_worktree: Annotated[
        bool | None,
        typer.Option(
            "--keep-worktree/--remove-worktree",
            help="Keep the isolated construction worktree after completion.",
        ),
    ] = None,
    capture_agent_io: Annotated[
        bool | None,
        typer.Option(
            "--capture-agent-io/--no-capture-agent-io",
            help="Persist L3 prompts and raw agent stdout/stderr. Disabled by default.",
        ),
    ] = None,
) -> None:
    """Build one task through L1, L2, and bounded L3 reconstruction."""

    payload = json.loads(case_file.read_text(encoding="utf-8"))
    case = TaskCase.model_validate(payload)
    settings = get_settings()
    resolved_run_root = run_root or Path(settings.run_root)
    ledger = ConstructionLedger(resolved_run_root / "ledger")
    builder = CaseBuilder(
        repository_cache=repository_cache,
        worktrees_root=resolved_run_root / "worktrees/construction",
        ledger=ledger,
        l3_backend=ClaudeCodeBackend(
            model=model or settings.l3_model,
            executable=settings.l3_executable,
            provider_base_url=settings.l3_provider_base_url,
            permission_mode=settings.l3_permission_mode,
            timeout_seconds=settings.l3_timeout_seconds,
        ),
        repeat_count=settings.lifecycle_repeat_count,
        max_l3_attempts=settings.l3_max_attempts,
        keep_worktree=(
            settings.keep_worktree if keep_worktree is None else keep_worktree
        ),
        capture_agent_io=(
            settings.capture_agent_io
            if capture_agent_io is None
            else capture_agent_io
        ),
        capture_command_output=settings.capture_command_output,
    )
    outcome = asyncio.run(builder.build(case))
    content = outcome.model_dump_json(indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content + "\n", encoding="utf-8")
    console.print_json(content)
    if not outcome.accepted:
        raise typer.Exit(code=2)
