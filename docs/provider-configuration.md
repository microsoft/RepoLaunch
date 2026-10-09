# L3 provider configuration

The public release defines a small `ConstructionAgentBackend` protocol. The
included `ClaudeCodeBackend` runs an installed Claude Code CLI inside the
isolated construction worktree.

Configure it through `CHANGE2TASK_*` environment variables or a local `.env`:

```dotenv
CHANGE2TASK_L3_MODEL=claude-opus-4.8
CHANGE2TASK_L3_EXECUTABLE=claude
CHANGE2TASK_L3_PERMISSION_MODE=acceptEdits
CHANGE2TASK_L3_TIMEOUT_SECONDS=1800
CHANGE2TASK_L3_MAX_ATTEMPTS=4
```

An optional `CHANGE2TASK_L3_PROVIDER_BASE_URL` is passed to Claude Code as
`ANTHROPIC_BASE_URL`. Authentication remains the responsibility of the CLI or
the caller's environment. This project does not read keychains, ship tokens, or
contain organization-specific routes.

The default permission mode is `acceptEdits`. `bypassPermissions` must be an
explicit configuration choice and should be used only inside a disposable,
access-controlled sandbox.

To use another coding agent, implement `ConstructionAgentBackend.run(...)` and
pass the backend to `CaseBuilder`. The backend must either edit the supplied
worktree or return an applicable unified diff.

Record the exact model and backend used when publishing derived datasets.
