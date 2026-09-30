from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pr_injector.workflow.adapters import get_adapter
from pr_injector.workflow.construction.agent import ClaudeCodeBackend
from pr_injector.workflow.construction.cascade import CaseBuilder
from pr_injector.workflow.fidelity import compare_patches, compare_profiles
from pr_injector.workflow.git_utils import IsolatedWorktree
from pr_injector.workflow.ledger import ConstructionLedger
from pr_injector.workflow.lifecycle import LifecycleValidator
from pr_injector.workflow.models import (
    CheckKind,
    CheckSpec,
    ConstructionLevel,
    FailureCategory,
    SourceChangeProfile,
    TaskCase,
    TaskFamily,
)

PATCH = """\
diff --git a/app.py b/app.py
index 1111111..2222222 100644
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-STATE = "bug"
+STATE = "fixed"
"""

TASK_PATCH = """\
diff --git a/app.py b/app.py
index 2222222..1111111 100644
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-STATE = "fixed"
+STATE = "bug"
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_all_five_adapters_have_distinct_contracts() -> None:
    adapters = [get_adapter(family) for family in TaskFamily]
    assert len(adapters) == 5
    assert len({adapter.construction_prompt_contract() for adapter in adapters}) == 5
    assert len({adapter.evaluation_prompt_contract() for adapter in adapters}) == 5


def test_l3_backend_defaults_to_published_model() -> None:
    backend = ClaudeCodeBackend()

    assert backend.model == "claude-opus-4.8"
    assert backend.executable == "claude"
    assert backend.provider_base_url is None


@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        ("feature", TaskFamily.FEATURE_ADDITION),
        ("test_reproduction", TaskFamily.TEST_GENERATION),
        ("api_dependency_migration", TaskFamily.API_MIGRATION),
        ("migration", TaskFamily.API_MIGRATION),
        ("security", TaskFamily.SECURITY_REPAIR),
    ],
)
def test_legacy_family_aliases_normalize(
    legacy: str,
    expected: TaskFamily,
) -> None:
    assert TaskFamily.normalize(legacy) == expected


def test_scope_contracts_are_family_specific() -> None:
    case = TaskCase(
        freeze_id="test-freeze",
        case_id="scope",
        family=TaskFamily.TEST_GENERATION,
        repository="example/repo",
        source_collection="unit",
        source_case_id="source",
        source_request="reproduce behavior",
        source_patch=PATCH,
        source_commit="a" * 40,
        modern_commit="b" * 40,
        task_statement="write a regression test",
        modern_host_files=["app.py"],
        allowed_paths=["app.py"],
        source_target_check_ids=["source-target"],
        source_regression_check_ids=["source-regression"],
        target_checks=[
            CheckSpec(
                check_id="target",
                kind=CheckKind.TARGET,
                command=["true"],
            )
        ],
        regression_checks=[
            CheckSpec(
                check_id="regression",
                kind=CheckKind.REGRESSION,
                command=["true"],
            )
        ],
    )
    adapter = get_adapter(case.family)
    assert adapter.scope_report(case, ["app.py"]).passed
    assert not adapter.scope_report(case, ["tests/test_app.py"]).passed
    evaluation_case = case.model_copy(
        update={"allowed_paths": ["tests/**"]},
    )
    assert adapter.evaluation_scope_report(
        evaluation_case,
        ["tests/test_app.py"],
    ).passed
    assert not adapter.evaluation_scope_report(
        evaluation_case,
        ["app.py"],
    ).passed


def test_fidelity_uses_paper_weights_and_forward_restoration() -> None:
    report = compare_patches(
        PATCH,
        PATCH,
        source_target_checks=1,
        modern_target_checks=1,
        source_regression_checks=2,
        modern_regression_checks=2,
    )
    assert report.weighted_score == pytest.approx(1.0)
    assert report.passed
    assert report.weights == {
        "files": 0.18,
        "hunks": 0.20,
        "changed_lines": 0.28,
        "symbols": 0.10,
        "target_checks": 0.12,
        "regression_checks": 0.12,
    }


def test_fidelity_gate_uses_directional_scope_ratios() -> None:
    source = SourceChangeProfile(
        files=1,
        hunks=1,
        changed_lines=10,
        symbols=1,
        target_checks=1,
        regression_checks=4,
    )
    expanded_but_allowed = source.model_copy(
        update={"files": 3, "changed_lines": 24},
    )
    allowed = compare_profiles(source, expanded_but_allowed)
    assert allowed.components.changed_lines < 0.5
    assert allowed.directional_ratios["changed_lines"] == 2.4
    assert allowed.passed

    overexpanded = compare_profiles(
        source,
        expanded_but_allowed.model_copy(update={"changed_lines": 26}),
    )
    assert not overexpanded.passed
    assert "line_scale_above_2.50" in overexpanded.failure_tags


@pytest.mark.asyncio
async def test_untracked_source_files_are_included_in_candidate_diff(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Change2Task Test")
    (repo / "existing.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "healthy base")

    (repo / "new_module.py").write_text("VALUE = 2\n", encoding="utf-8")
    worktree = IsolatedWorktree(repo)

    assert "new_module.py" in await worktree.changed_files()
    assert "new file mode" in await worktree.diff()
    assert "deleted file mode" in await worktree.reverse_diff()


@pytest.mark.asyncio
async def test_challenge_requires_every_target_check_to_fail(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Change2Task Test")
    (repo / "app.py").write_text('STATE = "fixed"\n', encoding="utf-8")
    (repo / "target.py").write_text(
        'from app import STATE\nraise SystemExit(0 if STATE == "fixed" else 1)\n',
        encoding="utf-8",
    )
    (repo / "always_passes.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "healthy base")
    case = TaskCase(
        freeze_id="unit-freeze",
        case_id="partial-target",
        family=TaskFamily.BUG_FIX,
        repository="example/repo",
        source_collection="unit",
        source_case_id="source",
        source_request="fix the state",
        source_patch=PATCH,
        source_commit="a" * 40,
        modern_commit=git(repo, "rev-parse", "HEAD"),
        task_statement="fix the state",
        modern_host_files=["app.py"],
        allowed_paths=["app.py"],
        source_target_check_ids=["source-behavior", "source-still-passing-target"],
        source_regression_check_ids=["source-regression"],
        target_checks=[
            CheckSpec(
                check_id="behavior",
                kind=CheckKind.TARGET,
                command=["python", "target.py"],
            ),
            CheckSpec(
                check_id="still-passing-target",
                kind=CheckKind.TARGET,
                command=["python", "always_passes.py"],
            ),
        ],
        regression_checks=[
            CheckSpec(
                check_id="regression",
                kind=CheckKind.REGRESSION,
                command=["python", "always_passes.py"],
            )
        ],
    )

    report = await LifecycleValidator(repeat_count=2).validate(
        repo,
        case,
        task_patch=TASK_PATCH,
        restoration_patch=PATCH,
    )

    assert not report.challenge.target_passed
    assert not report.challenge.target_expectation_satisfied
    assert FailureCategory.CHALLENGE_TARGET in report.failure_categories
    assert not report.passed


@pytest.mark.asyncio
async def test_l1_cascade_requires_complete_repeated_hcr(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Change2Task Test")
    (repo / "app.py").write_text('STATE = "fixed"\n', encoding="utf-8")
    (repo / "target.py").write_text(
        'from app import STATE\nraise SystemExit(0 if STATE == "fixed" else 1)\n',
        encoding="utf-8",
    )
    (repo / "regression.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "healthy modern base")
    head = git(repo, "rev-parse", "HEAD")

    case = TaskCase(
        freeze_id="unit-freeze",
        case_id="unit-l1",
        family=TaskFamily.BUG_FIX,
        repository="example/repo",
        source_collection="unit",
        source_case_id="source",
        source_request="fix the state",
        source_patch=PATCH,
        source_commit="a" * 40,
        modern_commit=head,
        task_statement="fix the state",
        modern_host_files=["app.py"],
        allowed_paths=["app.py"],
        source_target_check_ids=["source-target"],
        source_regression_check_ids=["source-regression"],
        target_checks=[
            CheckSpec(
                check_id="target",
                kind=CheckKind.TARGET,
                command=["python", "target.py"],
            )
        ],
        regression_checks=[
            CheckSpec(
                check_id="regression",
                kind=CheckKind.REGRESSION,
                command=["python", "regression.py"],
            )
        ],
    )
    ledger = ConstructionLedger(tmp_path / "ledger")
    builder = CaseBuilder(
        repository_cache=repo,
        worktrees_root=tmp_path / "worktrees",
        ledger=ledger,
        repeat_count=2,
    )
    outcome = await builder.build(case)

    assert outcome.accepted
    assert outcome.first_successful_level == ConstructionLevel.L1_PATCH_REVERSAL
    assert len(outcome.attempts) == 1
    lifecycle = outcome.attempts[0].lifecycle
    assert lifecycle is not None and lifecycle.passed
    assert lifecycle.repeat_count == 2
    assert len(lifecycle.healthy.observations) == 4
    assert len(lifecycle.challenge.observations) == 4
    assert len(lifecycle.restored.observations) == 4
    assert (tmp_path / "ledger/tables/construction_attempts.jsonl").exists()
    assert (tmp_path / "ledger/tables/lifecycle_runs.jsonl").exists()
