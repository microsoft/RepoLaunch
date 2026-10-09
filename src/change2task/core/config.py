"""Public Change2Task runtime configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Change2TaskSettings(BaseSettings):
    """Runtime settings loaded from ``CHANGE2TASK_*`` variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="CHANGE2TASK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    l3_model: str = "claude-opus-4.8"
    l3_executable: str = "claude"
    l3_provider_base_url: str | None = None
    l3_permission_mode: Literal[
        "default",
        "acceptEdits",
        "bypassPermissions",
    ] = "acceptEdits"
    l3_timeout_seconds: int = Field(default=1800, ge=1)
    l3_max_attempts: int = Field(default=4, ge=0, le=4)

    lifecycle_repeat_count: int = Field(default=2, ge=2)
    run_root: str = ".change2task"
    keep_worktree: bool = False

    capture_agent_io: bool = False
    capture_command_output: bool = False


def get_settings() -> Change2TaskSettings:
    """Load a fresh settings object."""
    return Change2TaskSettings()
