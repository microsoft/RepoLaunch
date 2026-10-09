"""Smoke tests for the public CLI surface."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from change2task.cli.app import app

runner = CliRunner()


def test_cli_only_exposes_public_method_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "build-case" in result.stdout
    assert "case-schema" in result.stdout
    assert "validate-case" in result.stdout
    assert "rq3" not in result.stdout.lower()
    assert "evidence" not in result.stdout.lower()


def test_validate_case_accepts_synthetic_example() -> None:
    example = Path(__file__).parents[1] / "examples/task_case.synthetic.json"
    result = runner.invoke(app, ["validate-case", str(example)])

    assert result.exit_code == 0
    assert '"valid": true' in result.stdout
    assert '"family": "bug_fix"' in result.stdout


def test_build_case_runs_l1_end_to_end(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Change2Task Test"],
        cwd=repo,
        check=True,
    )
    (repo / "app.py").write_text('STATE = "fixed"\n', encoding="utf-8")
    (repo / "target.py").write_text(
        'from app import STATE\nraise SystemExit(0 if STATE == "fixed" else 1)\n',
        encoding="utf-8",
    )
    (repo / "regression.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "healthy base"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    case = {
        "freeze_id": "cli-test",
        "case_id": "CLI_L1",
        "family": "bug_fix",
        "repository": "example/repo",
        "source_collection": "synthetic",
        "source_case_id": "source",
        "source_request": "fix state",
        "source_patch": (
            "diff --git a/app.py b/app.py\n"
            "index 1111111..2222222 100644\n"
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1 +1 @@\n"
            '-STATE = "bug"\n'
            '+STATE = "fixed"\n'
        ),
        "source_commit": "1" * 40,
        "modern_commit": head,
        "task_statement": "fix state",
        "modern_host_files": ["app.py"],
        "allowed_paths": ["app.py"],
        "source_target_check_ids": ["source-target"],
        "source_regression_check_ids": ["source-regression"],
        "target_checks": [
            {
                "check_id": "target",
                "kind": "target",
                "command": ["python", "target.py"],
                "environment": {"SYNTHETIC_TOKEN": "do-not-record"},
            }
        ],
        "regression_checks": [
            {
                "check_id": "regression",
                "kind": "regression",
                "command": ["python", "regression.py"],
            }
        ],
    }
    case_path = tmp_path / "case.json"
    case_path.write_text(json.dumps(case), encoding="utf-8")
    run_root = tmp_path / "run"
    output = tmp_path / "outcome.json"

    result = runner.invoke(
        app,
        [
            "build-case",
            str(case_path),
            "--repository-cache",
            str(repo),
            "--run-root",
            str(run_root),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.stdout
    outcome = json.loads(output.read_text(encoding="utf-8"))
    assert outcome["accepted"] is True
    assert outcome["first_successful_level"] == "L1"
    assert (run_root / "ledger/tables/construction_outcomes.jsonl").is_file()
    case_ledger = (run_root / "ledger/tables/cases.jsonl").read_text(
        encoding="utf-8"
    )
    assert "do-not-record" not in case_ledger
    assert '"SYNTHETIC_TOKEN":"<redacted>"' in case_ledger
    assert not any((run_root / "worktrees/construction").iterdir())
