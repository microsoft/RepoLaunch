"""Canonical schemas shared by all Change2Task task families."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "change2task.workflow.v2"


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(tz=UTC)


class StrictModel(BaseModel):
    """Base model that rejects unknown or misspelled fields."""

    model_config = ConfigDict(extra="forbid")


class TaskFamily(StrEnum):
    """The five supported coding-task families."""

    BUG_FIX = "bug_fix"
    FEATURE_ADDITION = "feature_addition"
    TEST_GENERATION = "test_generation"
    API_MIGRATION = "api_migration"
    SECURITY_REPAIR = "security_repair"

    @classmethod
    def normalize(cls, value: str) -> TaskFamily:
        aliases = {
            "feature": cls.FEATURE_ADDITION,
            "test_generation_issue_reproduction": cls.TEST_GENERATION,
            "test_reproduction": cls.TEST_GENERATION,
            "migration": cls.API_MIGRATION,
            "api_dependency_migration": cls.API_MIGRATION,
            "security": cls.SECURITY_REPAIR,
            "security_vulnerability_repair": cls.SECURITY_REPAIR,
        }
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in aliases:
            return aliases[normalized]
        return cls(normalized)


class ConstructionLevel(StrEnum):
    """The first successful construction route."""

    L1_PATCH_REVERSAL = "L1"
    L2_CODE_MAPPING = "L2"
    L3_AGENT_RECONSTRUCTION = "L3"


class LifecycleState(StrEnum):
    """Executable states in the H -> C -> H' lifecycle."""

    HEALTHY = "H"
    CHALLENGE = "C"
    RESTORED = "R"


class CheckKind(StrEnum):
    TARGET = "target"
    REGRESSION = "regression"
    SYNTAX = "syntax"
    BUILD = "build"
    SCOPE = "scope"


class AttemptStatus(StrEnum):
    GENERATED = "generated"
    REJECTED = "rejected"
    ACCEPTED = "accepted"
    EXHAUSTED = "exhausted"
    INFRASTRUCTURE_ERROR = "infrastructure_error"


class FailureCategory(StrEnum):
    NO_MODERN_HOST = "no_modern_behavior_host"
    EMPTY_PATCH = "empty_patch"
    APPLY = "apply_failure"
    SYNTAX = "syntax_or_build_failure"
    SCOPE = "scope_failure"
    FIDELITY = "fidelity_failure"
    HEALTHY_TARGET = "healthy_target_failure"
    HEALTHY_REGRESSION = "healthy_regression_failure"
    CHALLENGE_TARGET = "challenge_target_failure"
    CHALLENGE_REGRESSION = "challenge_regression_failure"
    RESTORATION = "restoration_failure"
    UNSTABLE = "unstable_repeated_run"
    MODEL = "construction_model_failure"
    INFRASTRUCTURE = "infrastructure_failure"
    BUDGET = "attempt_budget_exhausted"


class CheckSpec(StrictModel):
    """One executable target or protected regression check."""

    check_id: str
    kind: CheckKind
    command: list[str] | str
    shell: bool = False
    cwd: str = "."
    timeout_seconds: int = Field(default=300, ge=1)
    environment: dict[str, str] = Field(default_factory=dict)
    description: str = ""

    @field_validator("command")
    @classmethod
    def command_must_not_be_empty(cls, value: list[str] | str) -> list[str] | str:
        if isinstance(value, str) and not value.strip():
            raise ValueError("check command cannot be empty")
        if isinstance(value, list) and not value:
            raise ValueError("check command cannot be empty")
        return value


class SourceChangeProfile(StrictModel):
    """Observable footprint of a forward maintenance patch."""

    files: int = Field(ge=0)
    hunks: int = Field(ge=0)
    changed_lines: int = Field(ge=0)
    symbols: int = Field(ge=0)
    target_checks: int = Field(ge=0)
    regression_checks: int = Field(ge=0)
    file_paths: list[str] = Field(default_factory=list)
    symbol_names: list[str] = Field(default_factory=list)


class FidelityComponents(StrictModel):
    files: float = Field(ge=0.0, le=1.0)
    hunks: float = Field(ge=0.0, le=1.0)
    changed_lines: float = Field(ge=0.0, le=1.0)
    symbols: float = Field(ge=0.0, le=1.0)
    target_checks: float = Field(ge=0.0, le=1.0)
    regression_checks: float = Field(ge=0.0, le=1.0)


class FidelityReport(StrictModel):
    """Paper-defined source-patch/restoration-patch fidelity result."""

    source: SourceChangeProfile
    modern_restoration: SourceChangeProfile
    components: FidelityComponents
    weighted_score: float = Field(ge=0.0, le=1.0)
    weights: dict[str, float]
    directional_ratios: dict[str, float | None]
    line_scale_ratio: float | None = Field(default=None, ge=0.0)
    passed: bool
    failure_tags: list[str] = Field(default_factory=list)
    gate_version: str = "paper-appendix-fidelity-v1"


class ScopeReport(StrictModel):
    passed: bool
    changed_files: list[str]
    forbidden_files: list[str] = Field(default_factory=list)
    unexpected_files: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class QualificationObservation(StrictModel):
    """One pre-lifecycle syntax or build observation."""

    check_id: str
    check_kind: CheckKind
    command: list[str] | str
    cwd: str
    return_code: int | None
    timed_out: bool
    passed: bool
    duration_seconds: float = Field(ge=0.0)
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str = ""
    stderr_tail: str = ""


class QualificationReport(StrictModel):
    """Shared apply and syntax/build gate for every construction level."""

    task_patch_applied: bool
    diff_check_passed: bool
    reparsed_files: list[str] = Field(default_factory=list)
    reparse_passed: bool
    observations: list[QualificationObservation] = Field(default_factory=list)
    passed: bool
    reasons: list[str] = Field(default_factory=list)


class CommandObservation(StrictModel):
    """One command execution retained for lifecycle and cost accounting."""

    run_id: str
    case_id: str
    state: LifecycleState
    check_id: str
    check_kind: CheckKind
    repeat_index: int = Field(ge=1)
    command: list[str] | str
    cwd: str
    return_code: int | None
    timed_out: bool
    passed: bool
    duration_seconds: float = Field(ge=0.0)
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: str = ""
    stderr_tail: str = ""
    started_at: datetime
    finished_at: datetime


class StateValidation(StrictModel):
    state: LifecycleState
    expected_target_pass: bool
    target_passed: bool
    target_expectation_satisfied: bool
    regression_passed: bool
    stable: bool
    observations: list[CommandObservation] = Field(default_factory=list)


class LifecycleReport(StrictModel):
    """Complete H/C/R validation with repeat evidence."""

    healthy: StateValidation
    challenge: StateValidation
    restored: StateValidation
    restoration_applied: bool
    repeat_count: int = Field(ge=1)
    passed: bool
    failure_categories: list[FailureCategory] = Field(default_factory=list)


class TaskCase(StrictModel):
    """Normalized input contract consumed by every family adapter."""

    schema_version: str = SCHEMA_VERSION
    freeze_id: str
    case_id: str
    family: TaskFamily
    repository: str
    source_collection: str
    source_case_id: str
    source_request: str
    source_patch: str
    source_commit: str
    modern_commit: str
    task_statement: str
    modern_host_files: list[str]
    allowed_paths: list[str]
    source_target_check_ids: list[str]
    source_regression_check_ids: list[str]
    target_checks: list[CheckSpec]
    regression_checks: list[CheckSpec]
    qualification_checks: list[CheckSpec] = Field(default_factory=list)
    source_symbols: list[str] = Field(default_factory=list)
    modern_symbols: list[str] = Field(default_factory=list)
    call_chain: list[str] = Field(default_factory=list)
    source_pr: str | None = None
    source_issue: str | None = None
    source_date: str | None = None
    original_branch_commit: str | None = None
    task_patch: str | None = None
    restoration_patch: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("family", mode="before")
    @classmethod
    def normalize_family(cls, value: object) -> object:
        return TaskFamily.normalize(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def evidence_is_complete(self) -> TaskCase:
        if not self.source_patch.strip():
            raise ValueError("source_patch is required")
        if not self.modern_host_files:
            raise ValueError("at least one modern behavior host is required")
        if not self.allowed_paths:
            raise ValueError("allowed_paths must be explicit")
        if not self.source_target_check_ids:
            raise ValueError("at least one historical target check identity is required")
        if not self.source_regression_check_ids:
            raise ValueError(
                "at least one historical regression check identity is required"
            )
        if not self.target_checks:
            raise ValueError("at least one target check is required")
        if not self.regression_checks:
            raise ValueError("at least one regression check is required")
        check_identity_groups = {
            "source_target_check_ids": self.source_target_check_ids,
            "source_regression_check_ids": self.source_regression_check_ids,
            "target_checks": [check.check_id for check in self.target_checks],
            "regression_checks": [check.check_id for check in self.regression_checks],
            "qualification_checks": [
                check.check_id for check in self.qualification_checks
            ],
        }
        for name, identities in check_identity_groups.items():
            if any(not identity.strip() for identity in identities):
                raise ValueError(f"{name} contains an empty check identity")
            if len(identities) != len(set(identities)):
                raise ValueError(f"{name} contains duplicate check identities")
        invalid_qualification = [
            check.check_id
            for check in self.qualification_checks
            if check.kind not in {CheckKind.SYNTAX, CheckKind.BUILD}
        ]
        if invalid_qualification:
            raise ValueError(
                "qualification_checks must use syntax/build kinds: "
                + ", ".join(invalid_qualification)
            )
        return self


class ModelUsage(StrictModel):
    provider: str
    model: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    raw_usage: dict[str, Any] = Field(default_factory=dict)


class ConstructionAttempt(StrictModel):
    """Append-only record for one L1/L2/L3 attempt."""

    schema_version: str = SCHEMA_VERSION
    attempt_id: str
    case_id: str
    freeze_id: str
    family: TaskFamily
    level: ConstructionLevel
    level_attempt_index: int = Field(ge=1)
    global_attempt_index: int = Field(ge=1)
    status: AttemptStatus
    started_at: datetime
    finished_at: datetime
    task_patch_sha256: str | None = None
    restoration_patch_sha256: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    candidate_rank: int | None = Field(default=None, ge=1)
    candidate_count: int = Field(default=1, ge=1)
    qualification: QualificationReport | None = None
    scope: ScopeReport | None = None
    fidelity: FidelityReport | None = None
    lifecycle: LifecycleReport | None = None
    failure_category: FailureCategory | None = None
    feedback: str = ""
    model_usage: ModelUsage | None = None
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class ConstructionOutcome(StrictModel):
    """Final result of the three-level cascade."""

    schema_version: str = SCHEMA_VERSION
    case_id: str
    freeze_id: str
    family: TaskFamily
    accepted: bool
    first_successful_level: ConstructionLevel | None = None
    accepted_attempt_id: str | None = None
    task_patch: str | None = None
    restoration_patch: str | None = None
    attempts: list[ConstructionAttempt] = Field(default_factory=list)
    terminal_failure: FailureCategory | None = None
    generated_at: datetime = Field(default_factory=utc_now)
