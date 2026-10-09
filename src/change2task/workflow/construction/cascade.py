"""L1 -> L2 -> L3 Change2Task construction cascade."""

from __future__ import annotations

import ast
import json
import shutil
import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from change2task.llm.validator import extract_diff_from_response
from change2task.workflow.adapters import get_adapter
from change2task.workflow.construction.agent import (
    AgentExecution,
    ClaudeCodeBackend,
    ConstructionAgentBackend,
)
from change2task.workflow.construction.generation import (
    CodeMapping,
    GeneratedPatch,
    PatchReversal,
)
from change2task.workflow.fidelity import compare_patches
from change2task.workflow.git_utils import (
    IsolatedWorktree,
    ensure_within,
    run_process,
    sha256_bytes,
    sha256_text,
)
from change2task.workflow.ledger import ConstructionLedger
from change2task.workflow.lifecycle import LifecycleValidator
from change2task.workflow.models import (
    AttemptStatus,
    ConstructionAttempt,
    ConstructionLevel,
    ConstructionOutcome,
    FailureCategory,
    ModelUsage,
    QualificationObservation,
    QualificationReport,
    TaskCase,
)
from change2task.workflow.prompts import build_l3_prompt, fidelity_feedback


class CaseBuilder:
    """Construct one task through the exact three-level escalation policy."""

    def __init__(
        self,
        *,
        repository_cache: Path,
        worktrees_root: Path,
        ledger: ConstructionLedger,
        l3_backend: ConstructionAgentBackend | None = None,
        repeat_count: int = 2,
        max_l3_attempts: int = 4,
        keep_worktree: bool = False,
        capture_agent_io: bool = False,
        capture_command_output: bool = False,
    ) -> None:
        if not 0 <= max_l3_attempts <= 4:
            raise ValueError("max_l3_attempts must be between 0 and 4")
        self.repository_cache = repository_cache.resolve()
        self.worktrees_root = worktrees_root.resolve()
        self.worktrees_root.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.l3_backend = l3_backend or ClaudeCodeBackend()
        self.lifecycle = LifecycleValidator(
            repeat_count=repeat_count,
            capture_command_output=capture_command_output,
        )
        self.max_l3_attempts = max_l3_attempts
        self.keep_worktree = keep_worktree
        self.capture_agent_io = capture_agent_io
        self.capture_command_output = capture_command_output
        self.l1 = PatchReversal()
        self.l2 = CodeMapping()

    @staticmethod
    def _case_ledger_record(case: TaskCase) -> dict[str, Any]:
        payload = case.model_dump(mode="json")
        for field in (
            "target_checks",
            "regression_checks",
            "qualification_checks",
        ):
            for check in payload.get(field, []):
                environment = check.get("environment")
                if environment:
                    check["environment"] = {
                        name: "<redacted>" for name in environment
                    }
        return payload

    async def _create_worktree(self, case: TaskCase) -> IsolatedWorktree:
        if not (self.repository_cache / ".git").exists():
            raise ValueError(f"repository cache is not a git checkout: {self.repository_cache}")
        identity = case.case_id.replace("/", "__")
        path = self.worktrees_root / f"{identity}-{uuid.uuid4().hex[:8]}"
        result = await run_process(
            [
                "git",
                "worktree",
                "add",
                "--detach",
                str(path),
                case.modern_commit,
            ],
            cwd=self.repository_cache,
            timeout_seconds=300,
        )
        if result.return_code != 0:
            raise RuntimeError(result.stderr.decode(errors="replace"))
        worktree = IsolatedWorktree(path)
        if await worktree.head() != case.modern_commit:
            raise RuntimeError("worktree HEAD does not equal frozen modern commit")
        return worktree

    async def _remove_worktree(self, worktree: IsolatedWorktree) -> None:
        if self.keep_worktree:
            return
        result = await run_process(
            ["git", "worktree", "remove", "--force", str(worktree.path)],
            cwd=self.repository_cache,
            timeout_seconds=300,
        )
        if result.return_code != 0 and worktree.path.exists():
            # The target is a generated, case-specific worktree resolved above.
            shutil.rmtree(worktree.path)

    def _store_attempt_artifacts(
        self,
        attempt_id: str,
        generated: GeneratedPatch,
        *,
        prompt: tuple[str, str] | None = None,
        agent: AgentExecution | None = None,
    ) -> dict[str, str]:
        paths: dict[str, str] = {}
        for name, content in (
            ("task_patch.diff", generated.task_patch),
            ("restoration_patch.diff", generated.restoration_patch),
        ):
            if content:
                path, _ = self.ledger.store_text(
                    category="construction",
                    identity=attempt_id,
                    filename=name,
                    content=content,
                )
                paths[name] = str(path)
        if self.capture_agent_io and prompt:
            for name, content in zip(("system_prompt.txt", "task_prompt.txt"), prompt, strict=True):
                path, _ = self.ledger.store_text(
                    category="construction",
                    identity=attempt_id,
                    filename=name,
                    content=content,
                )
                paths[name] = str(path)
        if self.capture_agent_io and agent:
            raw = json.dumps(agent.raw_payload, ensure_ascii=False, indent=2, sort_keys=True)
            path, _ = self.ledger.store_text(
                category="construction",
                identity=attempt_id,
                filename="agent_result.json",
                content=raw + "\n",
            )
            paths["agent_result.json"] = str(path)
            for name, value in (
                ("agent_stdout.txt", agent.process.stdout.decode(errors="replace")),
                ("agent_stderr.txt", agent.process.stderr.decode(errors="replace")),
            ):
                path, _ = self.ledger.store_text(
                    category="construction",
                    identity=attempt_id,
                    filename=name,
                    content=value,
                )
                paths[name] = str(path)
        return paths

    async def _qualification_gate(
        self,
        worktree: IsolatedWorktree,
        case: TaskCase,
        task_patch: str,
    ) -> tuple[QualificationReport, list[str]]:
        """Run the shared apply and syntax/build gate on a clean modern base."""

        await worktree.clean_to_head()
        applied, apply_error = await worktree.apply_patch(task_patch)
        if not applied:
            return (
                QualificationReport(
                    task_patch_applied=False,
                    diff_check_passed=False,
                    reparse_passed=False,
                    passed=False,
                    reasons=[f"candidate patch does not apply cleanly: {apply_error}"],
                ),
                [],
            )

        changed_files = await worktree.changed_files()
        diff_check = await worktree.git("diff", "--check")
        diff_check_passed = diff_check.return_code == 0 and not diff_check.timed_out
        reasons: list[str] = []
        if not diff_check_passed:
            reasons.append(
                "git diff --check failed: " + diff_check.stderr.decode(errors="replace")[-2000:]
            )

        reparsed: list[str] = []
        reparse_passed = True
        for relative in changed_files:
            path = ensure_within(worktree.path, worktree.path / relative)
            if not path.is_file():
                continue
            try:
                if path.suffix == ".py":
                    ast.parse(
                        path.read_text(encoding="utf-8", errors="replace"),
                        filename=str(path),
                    )
                    reparsed.append(relative)
                elif path.suffix == ".json":
                    json.loads(path.read_text(encoding="utf-8"))
                    reparsed.append(relative)
                elif path.suffix == ".toml":
                    tomllib.loads(path.read_text(encoding="utf-8"))
                    reparsed.append(relative)
            except (SyntaxError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
                reparse_passed = False
                reasons.append(f"reparse failed for {relative}: {exc}")

        observations: list[QualificationObservation] = []
        for check in case.qualification_checks:
            cwd = ensure_within(worktree.path, worktree.path / check.cwd)
            result = await run_process(
                check.command,
                cwd=cwd,
                timeout_seconds=check.timeout_seconds,
                environment=check.environment,
                shell=check.shell,
            )
            passed = result.return_code == 0 and not result.timed_out
            observation = QualificationObservation(
                check_id=check.check_id,
                check_kind=check.kind,
                command=check.command,
                cwd=str(cwd.relative_to(worktree.path)),
                return_code=result.return_code,
                timed_out=result.timed_out,
                passed=passed,
                duration_seconds=result.duration_seconds,
                stdout_sha256=sha256_bytes(result.stdout),
                stderr_sha256=sha256_bytes(result.stderr),
                stdout_tail=(
                    result.stdout.decode(errors="replace")[-4000:]
                    if self.capture_command_output
                    else ""
                ),
                stderr_tail=(
                    result.stderr.decode(errors="replace")[-4000:]
                    if self.capture_command_output
                    else ""
                ),
            )
            observations.append(observation)
            if not passed:
                reasons.append(f"qualification check failed: {check.check_id}")

        passed = (
            bool(changed_files)
            and diff_check_passed
            and reparse_passed
            and all(observation.passed for observation in observations)
        )
        if not changed_files:
            reasons.append("candidate patch is empty after clean application")
        return (
            QualificationReport(
                task_patch_applied=True,
                diff_check_passed=diff_check_passed,
                reparsed_files=reparsed,
                reparse_passed=reparse_passed,
                observations=observations,
                passed=passed,
                reasons=reasons,
            ),
            changed_files,
        )

    async def _qualify(
        self,
        *,
        worktree: IsolatedWorktree,
        case: TaskCase,
        level: ConstructionLevel,
        level_attempt_index: int,
        global_attempt_index: int,
        generated: GeneratedPatch,
        started_at: datetime,
        prompt: tuple[str, str] | None = None,
        agent: AgentExecution | None = None,
    ) -> ConstructionAttempt:
        attempt_id = f"{case.case_id}:{level.value}:{level_attempt_index}:{uuid.uuid4().hex[:8]}"
        artifacts = self._store_attempt_artifacts(attempt_id, generated, prompt=prompt, agent=agent)
        adapter = get_adapter(case.family)
        model_usage: ModelUsage | None = agent.usage if agent else None
        if not generated.success:
            category = FailureCategory.MODEL if agent is not None else FailureCategory.APPLY
            attempt = ConstructionAttempt(
                attempt_id=attempt_id,
                case_id=case.case_id,
                freeze_id=case.freeze_id,
                family=case.family,
                level=level,
                level_attempt_index=level_attempt_index,
                global_attempt_index=global_attempt_index,
                status=AttemptStatus.REJECTED,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                failure_category=category,
                feedback=generated.feedback,
                model_usage=model_usage,
                artifact_paths=artifacts,
            )
            self.ledger.append("construction_attempts", attempt)
            return attempt

        qualification, changed_files = await self._qualification_gate(
            worktree,
            case,
            generated.task_patch,
        )
        for observation in qualification.observations:
            self.ledger.append(
                "qualification_runs",
                {
                    "attempt_id": attempt_id,
                    "case_id": case.case_id,
                    "freeze_id": case.freeze_id,
                    "family": case.family.value,
                    "level": level.value,
                    **observation.model_dump(mode="json"),
                },
            )
        if not qualification.passed:
            category = (
                FailureCategory.APPLY
                if not qualification.task_patch_applied
                else FailureCategory.SYNTAX
            )
            attempt = ConstructionAttempt(
                attempt_id=attempt_id,
                case_id=case.case_id,
                freeze_id=case.freeze_id,
                family=case.family,
                level=level,
                level_attempt_index=level_attempt_index,
                global_attempt_index=global_attempt_index,
                status=AttemptStatus.REJECTED,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                task_patch_sha256=sha256_text(generated.task_patch),
                restoration_patch_sha256=sha256_text(generated.restoration_patch),
                changed_files=changed_files or generated.changed_files,
                candidate_rank=1,
                qualification=qualification,
                failure_category=category,
                feedback="; ".join(qualification.reasons),
                model_usage=model_usage,
                artifact_paths=artifacts,
            )
            self.ledger.append("construction_attempts", attempt)
            return attempt

        scope = adapter.scope_report(case, changed_files)
        if not scope.passed:
            attempt = ConstructionAttempt(
                attempt_id=attempt_id,
                case_id=case.case_id,
                freeze_id=case.freeze_id,
                family=case.family,
                level=level,
                level_attempt_index=level_attempt_index,
                global_attempt_index=global_attempt_index,
                status=AttemptStatus.REJECTED,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                task_patch_sha256=sha256_text(generated.task_patch),
                restoration_patch_sha256=sha256_text(generated.restoration_patch),
                changed_files=changed_files,
                candidate_rank=1,
                qualification=qualification,
                scope=scope,
                failure_category=FailureCategory.SCOPE,
                feedback="; ".join(scope.reasons),
                model_usage=model_usage,
                artifact_paths=artifacts,
            )
            self.ledger.append("construction_attempts", attempt)
            return attempt

        fidelity = compare_patches(
            case.source_patch,
            generated.restoration_patch,
            source_target_checks=len(case.source_target_check_ids),
            modern_target_checks=len(case.target_checks),
            source_regression_checks=len(case.source_regression_check_ids),
            modern_regression_checks=len(case.regression_checks),
            source_symbols=case.source_symbols,
            modern_symbols=case.modern_symbols,
        )
        self.ledger.append(
            "fidelity_profiles",
            {
                "case_id": case.case_id,
                "freeze_id": case.freeze_id,
                "family": case.family.value,
                "attempt_id": attempt_id,
                "level": level.value,
                **fidelity.model_dump(mode="json"),
            },
        )
        if not fidelity.passed:
            attempt = ConstructionAttempt(
                attempt_id=attempt_id,
                case_id=case.case_id,
                freeze_id=case.freeze_id,
                family=case.family,
                level=level,
                level_attempt_index=level_attempt_index,
                global_attempt_index=global_attempt_index,
                status=AttemptStatus.REJECTED,
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                task_patch_sha256=sha256_text(generated.task_patch),
                restoration_patch_sha256=sha256_text(generated.restoration_patch),
                changed_files=changed_files,
                candidate_rank=1,
                qualification=qualification,
                scope=scope,
                fidelity=fidelity,
                failure_category=FailureCategory.FIDELITY,
                feedback=fidelity_feedback(fidelity),
                model_usage=model_usage,
                artifact_paths=artifacts,
            )
            self.ledger.append("construction_attempts", attempt)
            return attempt

        lifecycle = await self.lifecycle.validate(
            worktree.path,
            case,
            task_patch=generated.task_patch,
            restoration_patch=generated.restoration_patch,
        )
        for state in (lifecycle.healthy, lifecycle.challenge, lifecycle.restored):
            for observation in state.observations:
                self.ledger.append("lifecycle_runs", observation)
        accepted = lifecycle.passed
        attempt = ConstructionAttempt(
            attempt_id=attempt_id,
            case_id=case.case_id,
            freeze_id=case.freeze_id,
            family=case.family,
            level=level,
            level_attempt_index=level_attempt_index,
            global_attempt_index=global_attempt_index,
            status=AttemptStatus.ACCEPTED if accepted else AttemptStatus.REJECTED,
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            task_patch_sha256=sha256_text(generated.task_patch),
            restoration_patch_sha256=sha256_text(generated.restoration_patch),
            changed_files=changed_files,
            candidate_rank=1,
            qualification=qualification,
            scope=scope,
            fidelity=fidelity,
            lifecycle=lifecycle,
            failure_category=(
                None
                if accepted
                else (
                    lifecycle.failure_categories[0]
                    if lifecycle.failure_categories
                    else FailureCategory.INFRASTRUCTURE
                )
            ),
            feedback=(
                "" if accepted else ", ".join(item.value for item in lifecycle.failure_categories)
            ),
            model_usage=model_usage,
            artifact_paths=artifacts,
        )
        self.ledger.append("construction_attempts", attempt)
        return attempt

    def _modern_context(self, worktree: IsolatedWorktree, case: TaskCase) -> dict[str, str]:
        context: dict[str, str] = {}
        for relative in case.modern_host_files:
            path = (worktree.path / relative).resolve()
            if worktree.path not in path.parents or not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
            context[relative] = content[:100_000]
        return context

    async def _generate_l3(
        self,
        worktree: IsolatedWorktree,
        case: TaskCase,
        feedback: list[str],
        attempt_index: int,
    ) -> tuple[GeneratedPatch, tuple[str, str], AgentExecution]:
        await worktree.clean_to_head()
        prompt = build_l3_prompt(
            case,
            modern_context=self._modern_context(worktree, case),
            prior_feedback=feedback,
            attempt_index=attempt_index,
            max_attempts=self.max_l3_attempts,
        )
        agent = await self.l3_backend.run(
            worktree=worktree.path,
            system_prompt=prompt[0],
            user_prompt=prompt[1],
        )
        task_patch = await worktree.diff()
        if not task_patch.strip():
            response_patch = extract_diff_from_response(agent.result_text)
            if response_patch:
                applied, error = await worktree.apply_patch(response_patch)
                if not applied:
                    return (
                        GeneratedPatch(
                            success=False,
                            feedback=f"agent returned an inapplicable patch: {error}",
                        ),
                        prompt,
                        agent,
                    )
                task_patch = await worktree.diff()
        if agent.process.return_code != 0 and not task_patch.strip():
            return (
                GeneratedPatch(
                    success=False,
                    feedback=(
                        "construction model failed: "
                        + agent.process.stderr.decode(errors="replace")[-2000:]
                    ),
                ),
                prompt,
                agent,
            )
        if not task_patch.strip():
            return (
                GeneratedPatch(
                    success=False,
                    feedback="construction model produced no candidate diff",
                ),
                prompt,
                agent,
            )
        return (
            GeneratedPatch(
                success=True,
                task_patch=task_patch,
                restoration_patch=await worktree.reverse_diff(),
                changed_files=await worktree.changed_files(),
            ),
            prompt,
            agent,
        )

    async def build(self, case: TaskCase) -> ConstructionOutcome:
        """Run L1 once, L2 once, then the configured bounded L3 attempts."""

        self.ledger.append("cases", self._case_ledger_record(case))
        worktree = await self._create_worktree(case)
        attempts: list[ConstructionAttempt] = []
        feedback: list[str] = []
        try:
            started = datetime.now(tz=UTC)
            generated = await self.l1.generate(worktree, case.source_patch)
            attempt = await self._qualify(
                worktree=worktree,
                case=case,
                level=ConstructionLevel.L1_PATCH_REVERSAL,
                level_attempt_index=1,
                global_attempt_index=1,
                generated=generated,
                started_at=started,
            )
            attempts.append(attempt)
            if attempt.status == AttemptStatus.ACCEPTED:
                return self._outcome(case, attempts, generated, attempt)
            feedback.append(f"L1: {attempt.feedback}")

            started = datetime.now(tz=UTC)
            generated = await self.l2.generate(worktree, case.source_patch)
            attempt = await self._qualify(
                worktree=worktree,
                case=case,
                level=ConstructionLevel.L2_CODE_MAPPING,
                level_attempt_index=1,
                global_attempt_index=2,
                generated=generated,
                started_at=started,
            )
            attempts.append(attempt)
            if attempt.status == AttemptStatus.ACCEPTED:
                return self._outcome(case, attempts, generated, attempt)
            feedback.append(f"L2: {attempt.feedback}")

            for l3_index in range(1, self.max_l3_attempts + 1):
                started = datetime.now(tz=UTC)
                generated, prompt, agent = await self._generate_l3(
                    worktree, case, feedback, l3_index
                )
                attempt = await self._qualify(
                    worktree=worktree,
                    case=case,
                    level=ConstructionLevel.L3_AGENT_RECONSTRUCTION,
                    level_attempt_index=l3_index,
                    global_attempt_index=2 + l3_index,
                    generated=generated,
                    started_at=started,
                    prompt=prompt,
                    agent=agent,
                )
                attempts.append(attempt)
                if attempt.status == AttemptStatus.ACCEPTED:
                    return self._outcome(case, attempts, generated, attempt)
                feedback.append(f"L3 attempt {l3_index}: {attempt.feedback}")

            outcome = ConstructionOutcome(
                case_id=case.case_id,
                freeze_id=case.freeze_id,
                family=case.family,
                accepted=False,
                attempts=attempts,
                terminal_failure=FailureCategory.BUDGET,
            )
            self.ledger.append("construction_outcomes", outcome)
            return outcome
        finally:
            await self._remove_worktree(worktree)

    def _outcome(
        self,
        case: TaskCase,
        attempts: list[ConstructionAttempt],
        generated: GeneratedPatch,
        accepted_attempt: ConstructionAttempt,
    ) -> ConstructionOutcome:
        outcome = ConstructionOutcome(
            case_id=case.case_id,
            freeze_id=case.freeze_id,
            family=case.family,
            accepted=True,
            first_successful_level=accepted_attempt.level,
            accepted_attempt_id=accepted_attempt.attempt_id,
            task_patch=generated.task_patch,
            restoration_patch=generated.restoration_patch,
            attempts=attempts,
        )
        self.ledger.append("construction_outcomes", outcome)
        return outcome
