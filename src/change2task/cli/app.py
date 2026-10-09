"""Change2Task command-line application."""

from __future__ import annotations

import typer

from change2task.cli.build_case_cmd import build_case
from change2task.cli.schema_cmd import case_schema
from change2task.cli.validate_cmd import validate_case

app = typer.Typer(
    name="change2task",
    help="Build executable coding-agent tasks from historical repository changes.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

app.command(name="case-schema")(case_schema)
app.command(name="validate-case")(validate_case)
app.command(name="build-case")(build_case)
