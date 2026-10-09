---
name: change2task
description: Constructs and validates executable coding-agent tasks from historical repository changes with the Change2Task L1/L2/L3 pipeline. Use when converting a PR or commit into a TaskCase, running healthy/challenge/restored validation, inspecting the public 900-pair corpus, or invoking the change2task CLI.
---

# Change2Task

Use the repository CLI instead of reimplementing task construction.

## Select the workflow

- **Inspect the public corpus:** read `data/v1/manifest.json`, then the relevant
  family JSONL file.
- **Validate a case:** run `change2task validate-case CASE.json`.
- **Construct a task:** run `change2task build-case` against a trusted checkout.
- **Generate the schema:** run `change2task case-schema`.

## Construct a task

1. Confirm the target repository is a Git checkout containing the exact
   `modern_commit` in the `TaskCase`.
2. Treat the case file as executable input. Review all commands, working
   directories, environments, and shell flags.
3. Validate without execution:

   ```bash
   change2task validate-case path/to/case.json
   ```

4. Run in a disposable sandbox:

   ```bash
   change2task build-case path/to/case.json \
     --repository-cache /path/to/repository \
     --output .change2task/outcome.json
   ```

5. Report the accepted construction level or the explicit terminal failure.
   Never turn infrastructure errors into task failures.

## Method invariants

- Escalate L1 Patch Reversal → L2 Code Mapping → bounded L3 Agent
  Reconstruction.
- Apply the same qualification, scope, fidelity, and repeated H/C/R lifecycle
  gates at every level.
- Target checks must pass/fail/pass across healthy/challenge/restored states.
- Protected regression checks must pass in all three states.
- Never expose construction traces or hidden checks to a downstream agent.

## Public corpus

Validate before use:

```bash
python scripts/validate_public_dataset.py data/v1
(cd data/v1 && sha256sum -c CHECKSUMS.sha256)
```

The corpus contains task definitions, not agent-evaluation results. Respect
`artifact_availability`, `sources.json`, and `repository_licenses.json`.

## Safety

- Do not run unreviewed `TaskCase` commands on a developer workstation.
- Do not expose credentials to the worktree or L3 backend.
- Keep raw model I/O capture disabled unless explicitly required.
- Do not publish `.change2task/` runtime artifacts without a separate review.

For the input contract, Python API, output interpretation, and dataset layout,
read [reference.md](reference.md).
