"""Task-family adapters over one shared construction and validation core."""

from __future__ import annotations

from abc import ABC
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Literal

from pr_injector.core.diff_parser import is_test_file
from pr_injector.workflow.models import ScopeReport, TaskCase, TaskFamily

PROTECTED_PATTERNS = (
    ".git/**",
    ".github/**",
    "paper/**",
    "handoff/**",
    "benchmark*/**",
    "evaluation*/**",
    "**/.DS_Store",
    "**/__pycache__/**",
)

DEPENDENCY_MANIFESTS = {
    "Cargo.toml",
    "go.mod",
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "requirements.txt",
    "setup.cfg",
    "setup.py",
}

LOCKFILE_NAMES = {
    "Cargo.lock",
    "Pipfile.lock",
    "package-lock.json",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "yarn.lock",
}


def _matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return fnmatch(normalized, pattern) or PurePosixPath(normalized).match(pattern)


class TaskFamilyAdapter(ABC):
    """Defines objective, scope and evaluation semantics for one family."""

    family: TaskFamily
    construction_condition: str
    evaluation_contract: str
    construction_source_only: bool = True
    construction_tests_only: bool = False
    construction_dependency_manifests_allowed: bool = False
    evaluation_source_only: bool = True
    evaluation_tests_only: bool = False
    evaluation_dependency_manifests_allowed: bool = False

    def scope_report(
        self,
        case: TaskCase,
        changed_files: list[str],
        *,
        phase: Literal["construction", "evaluation"] = "construction",
    ) -> ScopeReport:
        """Validate edits under the family contract for one workflow phase."""

        source_only = getattr(self, f"{phase}_source_only")
        tests_only = getattr(self, f"{phase}_tests_only")
        dependency_manifests_allowed = getattr(
            self,
            f"{phase}_dependency_manifests_allowed",
        )
        changed = sorted(set(path.replace("\\", "/").lstrip("./") for path in changed_files))
        forbidden: list[str] = []
        unexpected: list[str] = []
        reasons: list[str] = []

        for path in changed:
            name = PurePosixPath(path).name
            if any(_matches(path, pattern) for pattern in PROTECTED_PATTERNS):
                forbidden.append(path)
                continue
            if name in LOCKFILE_NAMES:
                forbidden.append(path)
                continue
            if tests_only and not is_test_file(path):
                forbidden.append(path)
                continue
            if source_only and is_test_file(path):
                forbidden.append(path)
                continue
            if name in DEPENDENCY_MANIFESTS and not dependency_manifests_allowed:
                forbidden.append(path)
                continue
            if not any(
                _matches(path, allowed) or path == allowed for allowed in case.allowed_paths
            ):
                unexpected.append(path)

        if not changed:
            reasons.append("empty candidate patch")
        if forbidden:
            reasons.append("task-family scope forbids one or more changed artifacts")
        if unexpected:
            reasons.append("candidate changed paths outside the frozen allowed_paths")
        return ScopeReport(
            passed=bool(changed) and not forbidden and not unexpected,
            changed_files=changed,
            forbidden_files=forbidden,
            unexpected_files=unexpected,
            reasons=reasons,
        )

    def evaluation_scope_report(
        self,
        case: TaskCase,
        changed_files: list[str],
    ) -> ScopeReport:
        """Validate a downstream patch through the same family adapter."""

        return self.scope_report(case, changed_files, phase="evaluation")

    def construction_prompt_contract(self) -> str:
        return self.construction_condition

    def evaluation_prompt_contract(self) -> str:
        return self.evaluation_contract


class BugFixAdapter(TaskFamilyAdapter):
    family = TaskFamily.BUG_FIX
    construction_condition = (
        "Construct an unfixed modern behavior matching the historical defect. "
        "The target checks must pass on H, fail on C, and pass again on R."
    )
    evaluation_contract = (
        "Repair the described defect with a minimal implementation patch while "
        "preserving protected passing behavior."
    )


class FeatureAdditionAdapter(TaskFamilyAdapter):
    family = TaskFamily.FEATURE_ADDITION
    construction_condition = (
        "Remove or disable precisely the requested capability on the modern base "
        "without disturbing unrelated features or current public interfaces."
    )
    evaluation_contract = (
        "Implement the requested behavior and integrate it with the existing "
        "public interface while preserving protected behavior."
    )


class TestGenerationAdapter(TaskFamilyAdapter):
    family = TaskFamily.TEST_GENERATION
    construction_condition = (
        "Construct the observable implementation failure that a new regression "
        "test must expose. Construction edits implementation only; the evaluation "
        "agent is separately restricted to test artifacts."
    )
    evaluation_contract = (
        "Add a minimal automated test that fails on the challenge state and passes "
        "after the hidden restoration. Modify test artifacts only."
    )
    evaluation_source_only = False
    evaluation_tests_only = True


class ApiMigrationAdapter(TaskFamilyAdapter):
    family = TaskFamily.API_MIGRATION
    construction_condition = (
        "Reintroduce the obsolete source API or dependency usage while preserving "
        "the surrounding modern behavior and leaving a bounded migration task."
    )
    evaluation_contract = (
        "Replace obsolete source API usage with the required target API and "
        "preserve externally observable behavior."
    )


class SecurityRepairAdapter(TaskFamilyAdapter):
    family = TaskFamily.SECURITY_REPAIR
    construction_condition = (
        "Reconstruct the vulnerable behavior under the deterministic sandboxed "
        "oracle without weakening the oracle, validation, or adjacent safeguards."
    )
    evaluation_contract = (
        "Remove the vulnerable behavior with a minimal implementation-only patch "
        "while preserving valid functionality and protected checks."
    )


ADAPTERS: dict[TaskFamily, TaskFamilyAdapter] = {
    adapter.family: adapter
    for adapter in (
        BugFixAdapter(),
        FeatureAdditionAdapter(),
        TestGenerationAdapter(),
        ApiMigrationAdapter(),
        SecurityRepairAdapter(),
    )
}


def get_adapter(family: TaskFamily | str) -> TaskFamilyAdapter:
    normalized = TaskFamily.normalize(family) if isinstance(family, str) else family
    return ADAPTERS[normalized]
