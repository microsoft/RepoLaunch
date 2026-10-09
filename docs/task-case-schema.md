# TaskCase input contract

`TaskCase` is a strict JSON object. Unknown fields are rejected.

Required evidence includes:

- one historical forward maintenance patch;
- exact historical and modern commits;
- a healthy modern checkout containing the modern commit;
- explicit modern behavior hosts and allowed paths;
- at least one target check and one protected regression check;
- identities for the corresponding historical check surfaces.

Commands are represented as argument arrays by default:

```json
{
  "check_id": "focused-test",
  "kind": "target",
  "command": ["python", "-m", "pytest", "tests/test_widget.py", "-q"],
  "cwd": ".",
  "timeout_seconds": 300
}
```

String commands are accepted, but are split without a shell unless
`"shell": true` is explicitly set. Treat every case file as trusted executable
input.

Generate the complete machine-readable schema with:

```bash
change2task case-schema --output schemas/task-case.schema.json
```

The synthetic example is validation-only until its placeholder commits and
repository evidence are replaced.
