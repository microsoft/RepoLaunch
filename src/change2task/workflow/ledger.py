"""Append-only construction ledger and artifact store."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

TABLES = {
    "cases",
    "construction_attempts",
    "construction_outcomes",
    "qualification_runs",
    "lifecycle_runs",
    "fidelity_profiles",
}


class ConstructionLedger:
    """Concurrency-safe JSONL ledger for one local construction run."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.tables_dir = self.root / "tables"
        self.artifacts_dir = self.root / "artifacts"
        self.tables_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def append(self, table: str, record: BaseModel | dict[str, Any]) -> Path:
        if table not in TABLES:
            raise ValueError(f"unknown ledger table: {table}")
        payload = (
            record.model_dump(mode="json", exclude_none=False)
            if isinstance(record, BaseModel)
            else dict(record)
        )
        payload.setdefault(
            "_ledger_recorded_at_utc",
            datetime.now(tz=UTC).isoformat(),
        )
        payload.setdefault("_ledger_schema", "change2task.construction-ledger.v1")
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        path = self.tables_dir / f"{table}.jsonl"
        lock_path = self.tables_dir / f".{table}.lock"
        with lock_path.open("a", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        return path

    def store_text(
        self,
        *,
        category: str,
        identity: str,
        filename: str,
        content: str,
    ) -> tuple[Path, str]:
        safe_identity = identity.replace("/", "__").replace("..", "_")
        directory = self.artifacts_dir / category / safe_identity
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        encoded = content.encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        if path.exists() and path.read_bytes() != encoded:
            path = directory / f"{path.stem}.{digest[:12]}{path.suffix}"
        if not path.exists():
            path.write_bytes(encoded)
        return path, digest
