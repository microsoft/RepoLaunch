# Contributing to Change2Task

Change2Task welcomes bug fixes, task-family adapters, verifier improvements,
documentation, and reproducibility work.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the complete local checks:

```bash
python -m pytest -q
python -m ruff check .
python scripts/validate_public_dataset.py data/v1
(cd data/v1 && sha256sum -c CHECKSUMS.sha256)
```

## Change guidelines

- Preserve the L1 → L2 → bounded L3 escalation policy.
- Apply identical qualification, scope, fidelity, and lifecycle gates at every
  construction level.
- Treat infrastructure failures separately from task failures.
- Do not commit credentials, local paths, model transcripts, or evaluation
  results.
- Keep public task records task-only. Agent outcomes, telemetry, and statistics
  belong outside this repository.
- Update schemas, examples, documentation, tests, and checksums with any public
  data-format change.
- Respect source benchmark terms and upstream repository licenses.

## Pull requests

Keep changes focused and describe:

1. the behavior or contract being changed;
2. the validation performed;
3. any compatibility, provenance, privacy, or licensing impact.

Most contributions require agreeing to the
[Microsoft Contributor License Agreement](https://cla.microsoft.com).
This project follows the
[Microsoft Open Source Code of Conduct](CODE_OF_CONDUCT.md).
