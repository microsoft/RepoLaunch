#!/usr/bin/env python3
"""Validate the public Change2Task task-only dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

FAMILY_COUNTS = {
    "bug_fix": 500,
    "feature_addition": 100,
    "test_generation": 100,
    "api_migration": 100,
    "security_repair": 100,
}
REFERENCE_ONLY_SOURCE_IDS = {"fea_bench", "swe_bench_plus_plus"}
TOP_LEVEL_KEYS = {
    "schema_version",
    "pair_id",
    "family",
    "repository",
    "provenance",
    "historical_task",
    "change2task_task",
    "content_hashes",
}
TASK_KEYS = {
    "instance_id",
    "base_commit",
    "task_statement",
    "solution_patch",
    "test_patch",
    "target_tests",
    "regression_tests",
}
MODERN_KEYS = {
    "instance_id",
    "base_commit",
    "task_statement",
    "artifact_availability",
    "challenge_patch",
    "challenge_apply_mode",
    "restoration_patch",
    "restoration_apply_mode",
    "test_patch",
    "target_tests",
    "regression_tests",
    "verification_commands",
    "changed_paths",
    "contract",
}
REPOSITORY_KEYS = {"slug", "url"}
PROVENANCE_KEYS = {
    "source_collection_id",
    "source_collection_label",
    "source_case_id",
    "restoration_origin",
}
CONTENT_HASH_KEYS = {
    "challenge_patch_sha256",
    "restoration_patch_sha256",
}
FORBIDDEN_TEXT = (
    "pr-injector-main",
    ".pri-workspace",
    "runs/change2task",
    "handoff/change2task",
    "agent_config_id",
    "provider_route",
)
SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----"
        r"\s+[A-Za-z0-9+/=\r\n]{80,}"
        r"-----END [A-Z ]*PRIVATE KEY-----"
    ),
)
EMAIL_RE = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"
)
WINDOWS_USER_HOME_RE = re.compile(r"[A-Za-z]:\\Users\\")
POSIX_USER_HOME_RE = re.compile(r"/(?:Users|home)/[^/\s\"']+")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_patch(value: str, identity: str) -> None:
    if not value.startswith(("diff --git", "--- a/")):
        raise ValueError(f"{identity}: not a unified diff")
    result = subprocess.run(
        ["git", "apply", "--numstat", "-"],
        input=value,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
            f"{identity}: invalid unified diff: {result.stderr.strip()}"
        )


def validate_keys(record: dict[str, Any], identity: str) -> None:
    if set(record) != TOP_LEVEL_KEYS:
        raise ValueError(f"{identity}: unexpected top-level keys")
    if set(record["historical_task"]) != TASK_KEYS:
        raise ValueError(f"{identity}: unexpected historical_task keys")
    if set(record["change2task_task"]) != MODERN_KEYS:
        raise ValueError(f"{identity}: unexpected change2task_task keys")
    if set(record["repository"]) != REPOSITORY_KEYS:
        raise ValueError(f"{identity}: unexpected repository keys")
    if set(record["provenance"]) != PROVENANCE_KEYS:
        raise ValueError(f"{identity}: unexpected provenance keys")
    if set(record["content_hashes"]) != CONTENT_HASH_KEYS:
        raise ValueError(f"{identity}: unexpected content_hash keys")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_root", type=Path)
    args = parser.parse_args()
    root = args.dataset_root.resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    sources = json.loads((root / "sources.json").read_text(encoding="utf-8"))
    repository_licenses = json.loads(
        (root / "repository_licenses.json").read_text(encoding="utf-8")
    )
    source_ids = {row["id"] for row in sources["sources"]}
    license_by_repo = {
        row["repository"]: row for row in repository_licenses["repositories"]
    }
    records: list[dict[str, Any]] = []
    family_counts: Counter[str] = Counter()
    pair_ids: set[str] = set()
    repo_slugs: set[str] = set()
    restoration_origins: Counter[str] = Counter()
    challenge_apply_modes: Counter[str] = Counter()
    artifact_availability: Counter[str] = Counter()

    for family, expected in FAMILY_COUNTS.items():
        path = root / "task_pairs" / f"{family}.jsonl"
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(rows) != expected:
            raise ValueError(f"{family}: expected {expected}, found {len(rows)}")
        records.extend(rows)

    serialized = "\n".join(json.dumps(row, ensure_ascii=False) for row in records)
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in serialized:
            raise ValueError(f"forbidden private/evaluation marker: {forbidden}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(serialized):
            raise ValueError(f"credential-like content: {pattern.pattern}")

    for record in records:
        identity = str(record.get("pair_id"))
        validate_keys(record, identity)
        if record["schema_version"] != "change2task.public-task-pair.v1":
            raise ValueError(f"{identity}: invalid schema version")
        if identity in pair_ids:
            raise ValueError(f"duplicate pair_id: {identity}")
        pair_ids.add(identity)
        family = record["family"]
        family_counts[family] += 1
        if record["provenance"]["source_collection_id"] not in source_ids:
            raise ValueError(f"{identity}: unknown source collection")
        origin = record["provenance"]["restoration_origin"]
        restoration_origins[origin] += 1
        repository = record["repository"]
        if not repository["url"].startswith("https://github.com/"):
            raise ValueError(f"{identity}: non-public repository URL")
        repo_slugs.add(repository["slug"])
        license_row = license_by_repo.get(repository["slug"])
        if license_row is None:
            raise ValueError(f"{identity}: repository license entry missing")
        historical = record["historical_task"]
        modern = record["change2task_task"]
        non_patch_payload = json.dumps(
            {
                "repository": repository,
                "provenance": record["provenance"],
                "historical": {
                    "instance_id": historical["instance_id"],
                    "base_commit": historical["base_commit"],
                    "task_statement": historical["task_statement"],
                    "target_tests": historical["target_tests"],
                    "regression_tests": historical["regression_tests"],
                },
                "modern": {
                    "instance_id": modern["instance_id"],
                    "base_commit": modern["base_commit"],
                    "task_statement": modern["task_statement"],
                    "target_tests": modern["target_tests"],
                    "regression_tests": modern["regression_tests"],
                    "verification_commands": modern["verification_commands"],
                    "changed_paths": modern["changed_paths"],
                    "contract": modern["contract"],
                },
            },
            ensure_ascii=False,
        )
        if POSIX_USER_HOME_RE.search(non_patch_payload) or WINDOWS_USER_HOME_RE.search(
            non_patch_payload
        ):
            raise ValueError(f"{identity}: non-portable user-home path")
        for task_name, task in (("historical", historical), ("change2task", modern)):
            if not task["instance_id"] or not task["base_commit"] or not task["task_statement"]:
                raise ValueError(f"{identity}: incomplete {task_name} task")
            if EMAIL_RE.search(task["task_statement"]):
                raise ValueError(f"{identity}: unredacted email in task statement")
        availability = modern["artifact_availability"]
        expected_availability = (
            "reference_only_license_restriction"
            if (
                license_row["license_status"] == "no_license_file_at_pinned_base"
                or "BUSL-1.1" in license_row["detected_spdx"]
                or record["provenance"]["source_collection_id"]
                in REFERENCE_ONLY_SOURCE_IDS
            )
            else "embedded"
        )
        if availability != expected_availability:
            raise ValueError(f"{identity}: artifact availability violates license gate")
        artifact_availability[availability] += 1
        if availability == "embedded":
            validate_patch(modern["challenge_patch"], f"{identity}:challenge")
            validate_patch(modern["restoration_patch"], f"{identity}:restoration")
            if modern["challenge_apply_mode"] not in {"forward", "reverse"}:
                raise ValueError(f"{identity}: invalid challenge apply mode")
            challenge_apply_modes[modern["challenge_apply_mode"]] += 1
            expected_restoration_mode = (
                "reverse"
                if modern["challenge_apply_mode"] == "forward"
                else "forward"
            )
            if modern["restoration_apply_mode"] != expected_restoration_mode:
                raise ValueError(f"{identity}: invalid restoration apply mode")
            if modern["restoration_patch"] != modern["challenge_patch"]:
                raise ValueError(f"{identity}: reverse restoration patch mismatch")
        elif availability == "reference_only_license_restriction":
            if any(
                modern[key] is not None
                for key in (
                    "challenge_patch",
                    "challenge_apply_mode",
                    "restoration_patch",
                    "restoration_apply_mode",
                    "test_patch",
                )
            ):
                raise ValueError(f"{identity}: reference-only artifacts must be omitted")
            if historical["solution_patch"] is not None or historical["test_patch"] is not None:
                raise ValueError(f"{identity}: reference-only historical patches must be omitted")
            if any(
                (
                    historical["target_tests"],
                    historical["regression_tests"],
                    modern["target_tests"],
                    modern["regression_tests"],
                    modern["verification_commands"],
                )
            ):
                raise ValueError(f"{identity}: reference-only verifier data must be omitted")
            if modern["contract"].get("reference_only") is not True:
                raise ValueError(f"{identity}: reference-only contract marker missing")
        else:
            raise ValueError(f"{identity}: invalid artifact availability")
        if modern["test_patch"]:
            validate_patch(modern["test_patch"], f"{identity}:modern tests")
        if historical["solution_patch"]:
            validate_patch(historical["solution_patch"], f"{identity}:historical solution")
        if historical["test_patch"]:
            validate_patch(historical["test_patch"], f"{identity}:historical tests")
        hashes = record["content_hashes"]
        if availability == "embedded":
            if hashes["challenge_patch_sha256"] != sha256_text(
                modern["challenge_patch"]
            ):
                raise ValueError(f"{identity}: challenge hash mismatch")
            if hashes["restoration_patch_sha256"] != sha256_text(
                modern["restoration_patch"]
            ):
                raise ValueError(f"{identity}: restoration hash mismatch")
        if availability == "embedded" and family in {
            "bug_fix",
            "feature_addition",
            "test_generation",
        } and (not modern["target_tests"] or not modern["regression_tests"]):
            raise ValueError(f"{identity}: missing target/regression tests")
        if (
            availability == "embedded"
            and family == "security_repair"
            and not modern["verification_commands"]
        ):
            raise ValueError(f"{identity}: missing security verification commands")
        if availability == "embedded" and family == "api_migration":
            contract = modern["contract"]
            if not contract.get("source_api_names") or not contract.get(
                "target_api_names"
            ):
                raise ValueError(f"{identity}: missing API migration contract")

    if family_counts != Counter(FAMILY_COUNTS):
        raise ValueError(f"family counts mismatch: {family_counts}")
    if len(records) != 900 or len(pair_ids) != 900:
        raise ValueError("dataset must contain 900 unique task pairs")
    if manifest["total_pairs"] != 900:
        raise ValueError("manifest total_pairs mismatch")
    if manifest["family_counts"] != FAMILY_COUNTS:
        raise ValueError("manifest family_counts mismatch")
    if manifest["unique_repository_slugs"] != len(repo_slugs):
        raise ValueError("manifest repository count mismatch")
    if repository_licenses["repository_count"] != len(repo_slugs):
        raise ValueError("repository license inventory count mismatch")
    if set(license_by_repo) != repo_slugs:
        raise ValueError("repository license inventory does not match task corpus")
    if manifest["restoration_origins"] != dict(sorted(restoration_origins.items())):
        raise ValueError("manifest restoration origins mismatch")
    if manifest["challenge_apply_modes"] != dict(
        sorted(challenge_apply_modes.items())
    ):
        raise ValueError("manifest challenge apply modes mismatch")
    if manifest["artifact_availability"] != dict(
        sorted(artifact_availability.items())
    ):
        raise ValueError("manifest artifact availability mismatch")

    checksum_lines = (root / "CHECKSUMS.sha256").read_text(encoding="utf-8").splitlines()
    checksum_paths = {
        line.split("  ", 1)[1]
        for line in checksum_lines
        if line.strip()
    }
    expected_checksum_paths = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    }
    if checksum_paths != expected_checksum_paths:
        raise ValueError(
            "checksum inventory mismatch: "
            f"missing={sorted(expected_checksum_paths - checksum_paths)}, "
            f"unexpected={sorted(checksum_paths - expected_checksum_paths)}"
        )
    for line in checksum_lines:
        expected, relative = line.split("  ", 1)
        path = root / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"checksum mismatch: {relative}")
    print(
        json.dumps(
            {
                "valid": True,
                "pairs": len(records),
                "families": dict(sorted(family_counts.items())),
                "repositories": len(repo_slugs),
                "source_collections": len(source_ids),
                "restoration_origins": dict(sorted(restoration_origins.items())),
                "challenge_apply_modes": dict(sorted(challenge_apply_modes.items())),
                "artifact_availability": dict(
                    sorted(artifact_availability.items())
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
