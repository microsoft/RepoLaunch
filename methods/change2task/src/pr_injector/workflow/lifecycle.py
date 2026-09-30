"""Strict repeated H/C/R lifecycle validation."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from pr_injector.workflow.git_utils import (
    IsolatedWorktree,
    ensure_within,
    run_process,
    sha256_bytes,
)
from pr_injector.workflow.models import (
    CheckKind,
    CheckSpec,
    CommandObservation,
    FailureCategory,
    LifecycleReport,
    LifecycleState,
    StateValidation,
    TaskCase,
)


def _tail(value: bytes, limit: int = 4000) -> str:
    text = value.decode("utf-8", errors="replace")
    return text[-limit:]


class LifecycleValidator:
    """Validate target pass/fail/pass and regression pass/pass/pass."""

    def __init__(
        self,
        *,
        repeat_count: int = 2,
        capture_command_output: bool = False,
    ) -> None:
        if repeat_count < 2:
            raise ValueError("lifecycle validation requires at least two repeated runs")
        self.repeat_count = repeat_count
        self.capture_command_output = capture_command_output

    async def _run_check(
        self,
        root: Path,
        case: TaskCase,
        state: LifecycleState,
        check: CheckSpec,
        repeat_index: int,
    ) -> CommandObservation:
        cwd = ensure_within(root, root / check.cwd)
        started = datetime.now(tz=UTC)
        result = await run_process(
            check.command,
            cwd=cwd,
            timeout_seconds=check.timeout_seconds,
            environment=check.environment,
            shell=check.shell,
        )
        finished = datetime.now(tz=UTC)
        return CommandObservation(
            run_id=str(uuid.uuid4()),
            case_id=case.case_id,
            state=state,
            check_id=check.check_id,
            check_kind=check.kind,
            repeat_index=repeat_index,
            command=check.command,
            cwd=str(cwd.relative_to(root)),
            return_code=result.return_code,
            timed_out=result.timed_out,
            passed=result.return_code == 0 and not result.timed_out,
            duration_seconds=result.duration_seconds,
            stdout_sha256=sha256_bytes(result.stdout),
            stderr_sha256=sha256_bytes(result.stderr),
            stdout_tail=(
                _tail(result.stdout) if self.capture_command_output else ""
            ),
            stderr_tail=(
                _tail(result.stderr) if self.capture_command_output else ""
            ),
            started_at=started,
            finished_at=finished,
        )

    async def _validate_state(
        self,
        root: Path,
        case: TaskCase,
        state: LifecycleState,
        *,
        expected_target_pass: bool,
    ) -> StateValidation:
        observations: list[CommandObservation] = []
        checks = [*case.target_checks, *case.regression_checks]
        for repeat_index in range(1, self.repeat_count + 1):
            for check in checks:
                observations.append(await self._run_check(root, case, state, check, repeat_index))

        by_check: dict[str, list[CommandObservation]] = defaultdict(list)
        for observation in observations:
            by_check[observation.check_id].append(observation)
        stable = all(
            len({(item.return_code, item.timed_out) for item in values}) == 1
            for values in by_check.values()
        )

        target_rows = [item for item in observations if item.check_kind == CheckKind.TARGET]
        regression_rows = [item for item in observations if item.check_kind == CheckKind.REGRESSION]
        target_passed = bool(target_rows) and all(item.passed for item in target_rows)
        target_failed_as_expected = bool(target_rows) and all(
            not item.passed
            and not item.timed_out
            and item.return_code is not None
            and item.return_code != 0
            for item in target_rows
        )
        regression_passed = bool(regression_rows) and all(item.passed for item in regression_rows)
        return StateValidation(
            state=state,
            expected_target_pass=expected_target_pass,
            target_passed=target_passed,
            target_expectation_satisfied=(
                target_passed if expected_target_pass else target_failed_as_expected
            ),
            regression_passed=regression_passed,
            stable=stable,
            observations=observations,
        )

    async def validate(
        self,
        worktree_path: Path,
        case: TaskCase,
        *,
        task_patch: str,
        restoration_patch: str,
    ) -> LifecycleReport:
        """Run a clean H/C/R validation in an isolated worktree."""

        worktree = IsolatedWorktree(worktree_path)
        await worktree.clean_to_head()
        healthy = await self._validate_state(
            worktree.path,
            case,
            LifecycleState.HEALTHY,
            expected_target_pass=True,
        )

        task_applied, task_error = await worktree.apply_patch(task_patch)
        if not task_applied:
            empty = StateValidation(
                state=LifecycleState.CHALLENGE,
                expected_target_pass=False,
                target_passed=True,
                target_expectation_satisfied=False,
                regression_passed=False,
                stable=False,
                observations=[],
            )
            restored = StateValidation(
                state=LifecycleState.RESTORED,
                expected_target_pass=True,
                target_passed=False,
                target_expectation_satisfied=False,
                regression_passed=False,
                stable=False,
                observations=[],
            )
            return LifecycleReport(
                healthy=healthy,
                challenge=empty,
                restored=restored,
                restoration_applied=False,
                repeat_count=self.repeat_count,
                passed=False,
                failure_categories=[FailureCategory.APPLY],
            )

        challenge = await self._validate_state(
            worktree.path,
            case,
            LifecycleState.CHALLENGE,
            expected_target_pass=False,
        )
        restoration_applied, restoration_error = await worktree.apply_patch(restoration_patch)
        if restoration_applied:
            restored = await self._validate_state(
                worktree.path,
                case,
                LifecycleState.RESTORED,
                expected_target_pass=True,
            )
        else:
            restored = StateValidation(
                state=LifecycleState.RESTORED,
                expected_target_pass=True,
                target_passed=False,
                target_expectation_satisfied=False,
                regression_passed=False,
                stable=False,
                observations=[],
            )

        failures: list[FailureCategory] = []
        if not healthy.target_expectation_satisfied:
            failures.append(FailureCategory.HEALTHY_TARGET)
        if not healthy.regression_passed:
            failures.append(FailureCategory.HEALTHY_REGRESSION)
        if not challenge.target_expectation_satisfied:
            failures.append(FailureCategory.CHALLENGE_TARGET)
        if not challenge.regression_passed:
            failures.append(FailureCategory.CHALLENGE_REGRESSION)
        if (
            not restoration_applied
            or not restored.target_expectation_satisfied
            or not restored.regression_passed
        ):
            failures.append(FailureCategory.RESTORATION)
        if not all((healthy.stable, challenge.stable, restored.stable)):
            failures.append(FailureCategory.UNSTABLE)
        # Preserve otherwise-unused errors for callers inspecting debug output.
        _ = task_error, restoration_error
        return LifecycleReport(
            healthy=healthy,
            challenge=challenge,
            restored=restored,
            restoration_applied=restoration_applied,
            repeat_count=self.repeat_count,
            passed=not failures,
            failure_categories=failures,
        )
