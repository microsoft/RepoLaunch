# Change2Task Reference

## Install

```bash
python -m pip install \
  "git+https://github.com/microsoft/RepoLaunch.git@change2task"
```

## CLI

```bash
change2task --help
change2task case-schema --output schemas/task-case.schema.json
change2task validate-case examples/task_case.synthetic.json
change2task build-case CASE.json \
  --repository-cache REPOSITORY \
  --output .change2task/outcome.json
```

## Required TaskCase evidence

- historical forward patch and request;
- exact historical and modern revisions;
- modern behavior-host and allowed-path lists;
- at least one target check and one protected regression check;
- source and modern check identities.

`TaskCase` rejects unknown fields. Prefer command argument arrays; use shell
commands only when unavoidable.

## Python API

```python
from pathlib import Path

from change2task.workflow.construction import CaseBuilder
from change2task.workflow.ledger import ConstructionLedger
from change2task.workflow.models import TaskCase

case = TaskCase.model_validate_json(Path("case.json").read_text())
ledger = ConstructionLedger(Path(".change2task/ledger"))
builder = CaseBuilder(
    repository_cache=Path("/path/to/repository"),
    worktrees_root=Path(".change2task/worktrees"),
    ledger=ledger,
)
```

## Public data

- `data/v1/manifest.json`: counts and release properties.
- `data/v1/task_pairs/*.jsonl`: five family partitions.
- `data/v1/schema.json`: strict public record schema.
- `data/v1/sources.json`: benchmark provenance and terms.
- `data/v1/repository_licenses.json`: pinned-base license inventory.
- `data/v1/AUDIT.md`: privacy and integrity review.

`embedded` records contain task artifacts. `reference_only_license_restriction`
records contain provenance and hashes but intentionally omit copied content.
