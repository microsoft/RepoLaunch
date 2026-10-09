"""Tests for the public runtime configuration."""

from __future__ import annotations

from change2task.core.config import Change2TaskSettings


def test_public_defaults_do_not_require_private_routing() -> None:
    settings = Change2TaskSettings(_env_file=None)

    assert settings.l3_model == "claude-opus-4.8"
    assert settings.l3_executable == "claude"
    assert settings.l3_provider_base_url is None
    assert settings.l3_permission_mode == "acceptEdits"
    assert settings.l3_max_attempts == 4
    assert settings.lifecycle_repeat_count == 2
    assert not settings.capture_agent_io
    assert not settings.capture_command_output


def test_environment_prefix(monkeypatch) -> None:
    monkeypatch.setenv("CHANGE2TASK_L3_MODEL", "test-model")
    monkeypatch.setenv("CHANGE2TASK_L3_MAX_ATTEMPTS", "2")

    settings = Change2TaskSettings(_env_file=None)

    assert settings.l3_model == "test-model"
    assert settings.l3_max_attempts == 2
