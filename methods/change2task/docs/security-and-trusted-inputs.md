# Security and trusted inputs

Change2Task executes repository code and commands declared by `TaskCase`.
Run it only in a disposable, access-controlled environment.

## Trust boundaries

- Treat `TaskCase` JSON as trusted executable input.
- Treat repository files, commit messages, issue text, and tool output as
  untrusted data.
- Do not expose production credentials to the construction worktree.
- Prefer argument-array commands; enable shell execution only when necessary.
- Pin the repository and modern commit before construction.

## Stored artifacts

Task and restoration patches are required method outputs. Raw prompts, model
responses, stdout, and stderr may contain source code or secrets and are not
stored by default. Enabling `CHANGE2TASK_CAPTURE_AGENT_IO` or
`CHANGE2TASK_CAPTURE_COMMAND_OUTPUT` is an explicit privacy decision.
Environment-variable values attached to checks are redacted before the case is
written to the construction ledger.

The local output root is append-only. Do not commit `.change2task/` or publish
its contents without a separate review.

## Agent execution

The bundled Claude Code backend defaults to `acceptEdits` inside a case-specific
detached Git worktree. Fully bypassing permission checks requires explicit
configuration. In either mode, the checkout must itself be sandboxed; worktree
isolation is not a substitute for operating-system or container isolation.
