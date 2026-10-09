"""Prompts used by the public Change2Task construction pipeline."""

from __future__ import annotations

import json
from collections.abc import Sequence

from change2task.workflow.adapters import get_adapter
from change2task.workflow.models import FidelityReport, TaskCase


def _checks(case: TaskCase) -> str:
    target = "\n".join(
        f"- {check.check_id}: {check.description or check.command}"
        for check in case.target_checks
    )
    regression = "\n".join(
        f"- {check.check_id}: {check.description or check.command}"
        for check in case.regression_checks
    )
    return (
        f"Target checks:\n{target}\n\n"
        f"Protected regression checks:\n{regression}"
    )


def build_l3_prompt(
    case: TaskCase,
    *,
    modern_context: dict[str, str],
    prior_feedback: Sequence[str] = (),
    attempt_index: int,
    max_attempts: int = 4,
) -> tuple[str, str]:
    """Build the bounded Agent Reconstruction prompt."""

    adapter = get_adapter(case.family)
    system = """\
You are the construction agent for Change2Task. Reconstruct on a healthy
modern revision the unresolved maintenance condition represented by a
historical pull request. Preserve the modern repository structure, public
interfaces, later unrelated behavior, tests, fixtures, CI, generated files,
dependency locks, and benchmark metadata.

The authoritative output is the clean unified diff left in the isolated
worktree. Work directly in that worktree. Do not merely explain a patch.
Inspect the modern call path before editing, make the smallest coherent
semantic transformation, run focused syntax/build checks, and review the final
diff for completeness and scope.

Never use test-specific branches, hard-coded expected values, broad exception
handling, dead code, stubs, unrelated deletion, wholesale historical source
restoration, or unrelated refactoring. Do not modify hidden or visible tests.
"""
    context = "\n\n".join(
        f"### {path}\n```\n{content}\n```"
        for path, content in modern_context.items()
    )
    feedback = (
        "\n".join(f"- {item}" for item in prior_feedback)
        if prior_feedback
        else "- No prior candidate feedback; this is the first Agent Reconstruction attempt."
    )
    user = f"""\
# Change2Task Agent Reconstruction — attempt {attempt_index}/{max_attempts}

## Task family and construction condition
Family: {case.family.value}
Condition to construct: {adapter.construction_prompt_contract()}

## Historical developer evidence
Source collection: {case.source_collection}
Source case: {case.source_case_id}
Source request:
{case.source_request}

Historical forward maintenance patch P_s:
```diff
{case.source_patch}
```

## Frozen modern base
Repository: {case.repository}
Healthy modern commit H: {case.modern_commit}
Modern behavior hosts: {json.dumps(case.modern_host_files)}
Historical changed symbols: {json.dumps(case.source_symbols)}
Mapped modern symbols: {json.dumps(case.modern_symbols)}
Mapped call chain: {json.dumps(case.call_chain)}
Permitted paths: {json.dumps(case.allowed_paths)}

{_checks(case)}

## Source change profile requirement
The candidate must remain comparable to P_s in changed files, hunks, changed
lines, symbols, target-check surface, and regression-check surface. The
external gate rejects aggregate score below 0.65; modern/source file, hunk, or
line ratios below 0.50; modern/source line expansion above 2.50x; or a
modern/source regression-check ratio below 0.25.

Historical target checks ({len(case.source_target_check_ids)}):
{json.dumps(case.source_target_check_ids)}
Historical regression checks ({len(case.source_regression_check_ids)}):
{json.dumps(case.source_regression_check_ids)}
Modern target checks: {len(case.target_checks)}
Modern regression checks: {len(case.regression_checks)}

## Prior structured feedback
{feedback}

## Relevant modern context
{context}

## Required procedure
1. Confirm the historical behavior still has a defensible host in the modern code.
2. Trace the modern call path and identify the smallest complete semantic slice.
3. Construct the unresolved task condition without reverting unrelated evolution.
4. Cover every affected modern call site necessary for the same obligation.
5. Run available focused syntax/build checks.
6. Leave only the candidate task-state diff applied in the worktree.

Finish with a concise CONSTRUCTION_REPORT naming modified files, reconstructed
behavioral slice, expected target effect, protected behavior, and checks run.
"""
    return system, user


def fidelity_feedback(report: FidelityReport) -> str:
    """Render structured fidelity feedback for a subsequent L3 attempt."""

    values = report.components.model_dump()
    return (
        f"Fidelity gate failed: score={report.weighted_score:.4f}; "
        f"components={json.dumps(values, sort_keys=True)}; "
        f"line_scale={report.line_scale_ratio}; "
        f"tags={','.join(report.failure_tags)}"
    )
