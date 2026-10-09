"""CLI command for the canonical five-family case input schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from change2task.workflow.models import TaskCase

console = Console()


def case_schema(
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Optional path for the JSON Schema; stdout is used when omitted.",
        ),
    ] = None,
) -> None:
    """Print the strict normalized TaskCase JSON Schema."""

    payload = TaskCase.model_json_schema()
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output is None:
        console.print_json(content)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    console.print(str(output.resolve()))
