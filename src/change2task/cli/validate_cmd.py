"""Validate a normalized Change2Task input without executing it."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from change2task.workflow.models import TaskCase

console = Console()


def validate_case(
    case_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Normalized Change2Task TaskCase JSON.",
        ),
    ],
) -> None:
    """Validate a TaskCase and print a short, non-executing summary."""

    case = TaskCase.model_validate_json(case_file.read_text(encoding="utf-8"))
    console.print_json(
        json.dumps(
            {
                "valid": True,
                "case_id": case.case_id,
                "family": case.family.value,
                "repository": case.repository,
                "modern_commit": case.modern_commit,
                "target_checks": len(case.target_checks),
                "regression_checks": len(case.regression_checks),
            }
        )
    )
