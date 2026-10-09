#!/usr/bin/env python3
"""Export the frozen Change2Task corpus without evaluation or local metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

FAMILY_FILES = {
    "bug_fix": "bug_fix.jsonl",
    "feature_addition": "feature_addition.jsonl",
    "test_generation": "test_generation.jsonl",
    "api_migration": "api_migration.jsonl",
    "security_repair": "security_repair.jsonl",
}

SOURCE_ALIASES = {
    "princeton-nlp/SWE-bench": "swe_bench_original",
    "SWE-bench/SWE-bench_Lite": "swe_bench_lite",
    "princeton-nlp/SWE-bench_Verified": "swe_bench_verified",
    "SWE-bench/SWE-bench_Verified": "swe_bench_verified",
    "SWE-bench-Live/SWE-bench-Live": "swe_bench_live",
    "ScaleAI/SWE-bench_Pro": "swe_bench_pro",
    "nebius/SWE-rebench-V2-PRs": "swe_rebench_v2",
    "FEA-Bench": "fea_bench",
    "TuringEnterprises/SWE-Bench-plus-plus": "swe_bench_plus_plus",
    "PyMigBench": "pymigbench",
    "PatchEval executable subset": "patcheval",
    "Vul4J": "vul4j",
    "VJBench": "vjbench",
}

FAMILY_CONTRACTS = {
    "bug_fix": {
        "objective": "Repair the described faulty behavior.",
        "allowed_output": "implementation",
    },
    "feature_addition": {
        "objective": "Implement the described missing behavior.",
        "allowed_output": "implementation",
    },
    "test_generation": {
        "objective": "Add a regression test that exposes the challenge state.",
        "allowed_output": "tests",
    },
    "api_migration": {
        "objective": "Replace obsolete API usage with the required target API.",
        "allowed_output": "implementation",
    },
    "security_repair": {
        "objective": "Repair the vulnerability exposed by the deterministic oracle.",
        "allowed_output": "implementation",
    },
}

EMAIL_RE = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"
)
HUNK_HEADER_RE = re.compile(
    r"@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? "
    r"@@(?P<section>.*)"
)
USER_HOME_RE = re.compile(
    r"(?:/(?:Users|home)/[^/\s\"']+|[A-Za-z]:\\Users\\[^\\\s\"']+)"
)

SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/microsoft/RepoLaunch/blob/change2task/"
    "methods/change2task/data/v1/schema.json",
    "title": "Change2Task public task pair",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema_version",
        "pair_id",
        "family",
        "repository",
        "provenance",
        "historical_task",
        "change2task_task",
        "content_hashes",
    ],
    "properties": {
        "schema_version": {"const": "change2task.public-task-pair.v1"},
        "pair_id": {"type": "string", "minLength": 1},
        "family": {"enum": list(FAMILY_FILES)},
        "repository": {
            "type": "object",
            "additionalProperties": False,
            "required": ["slug", "url"],
            "properties": {
                "slug": {"type": "string", "pattern": r"^[^/]+/[^/]+$"},
                "url": {"type": "string", "format": "uri"},
            },
        },
        "provenance": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "source_collection_id",
                "source_collection_label",
                "source_case_id",
                "restoration_origin",
            ],
            "properties": {
                "source_collection_id": {"type": "string"},
                "source_collection_label": {"type": "string"},
                "source_case_id": {"type": "string"},
                "restoration_origin": {
                    "const": "opposite_apply_mode_of_challenge_patch"
                },
            },
        },
        "historical_task": {"$ref": "#/$defs/task"},
        "change2task_task": {"$ref": "#/$defs/modernTask"},
        "content_hashes": {
            "type": "object",
            "additionalProperties": False,
            "required": ["challenge_patch_sha256", "restoration_patch_sha256"],
            "properties": {
                "challenge_patch_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "restoration_patch_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
            },
        },
    },
    "$defs": {
        "task": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "instance_id",
                "base_commit",
                "task_statement",
                "solution_patch",
                "test_patch",
                "target_tests",
                "regression_tests",
            ],
            "properties": {
                "instance_id": {"type": "string"},
                "base_commit": {"type": "string"},
                "task_statement": {"type": "string", "minLength": 1},
                "solution_patch": {"type": ["string", "null"]},
                "test_patch": {"type": ["string", "null"]},
                "target_tests": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "regression_tests": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
        "modernTask": {
            "type": "object",
            "additionalProperties": False,
            "required": [
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
            ],
            "properties": {
                "instance_id": {"type": "string"},
                "base_commit": {"type": "string"},
                "task_statement": {"type": "string", "minLength": 1},
                "artifact_availability": {
                    "enum": [
                        "embedded",
                        "reference_only_license_restriction",
                    ]
                },
                "challenge_patch": {"type": ["string", "null"]},
                "challenge_apply_mode": {
                    "enum": ["forward", "reverse", None]
                },
                "restoration_patch": {"type": ["string", "null"]},
                "restoration_apply_mode": {
                    "enum": ["forward", "reverse", None]
                },
                "test_patch": {"type": ["string", "null"]},
                "target_tests": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "regression_tests": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "verification_commands": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "changed_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "contract": {"type": "object"},
            },
        },
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalized_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def normalized_patch(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    path_value = text.strip()
    path = Path(path_value)
    if not text.lstrip("\n").startswith(("diff --git", "--- a/")) and path.is_file():
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace(
            "\r", "\n"
        )
    text = text.lstrip("\n")
    if not text.startswith(("diff --git", "--- a/")):
        raise ValueError(f"patch value is neither an inline diff nor a file: {text[:120]}")
    return text.rstrip("\n") + "\n"


def first_patch(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        patch = normalized_patch(row.get(key))
        if patch:
            return patch
    return ""


def first_text(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = normalized_text(row.get(key))
        if value:
            return value
    return ""


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def portable_local_path(value: str) -> str:
    if value.endswith("/.venv/bin/python"):
        return "python"
    if "/goruntimes/" in value and value.endswith("/bin/go"):
        return "go"
    if "/jdks/" in value and value.endswith("/Contents/Home"):
        return "{JAVA_HOME}"
    for marker in (
        "/node_modules/",
        "/tests/",
        "/test/",
        "/lib/",
        "/src/",
        "/spec/",
        "/plugins/",
        "/packages/",
        "/gosrc/",
    ):
        if marker in value:
            return "{REPO_ROOT}" + marker + value.rsplit(marker, 1)[1]
    return "{REPO_ROOT}/" + Path(value).name


def portable_runtime_value(
    value: str,
    local_path_re: re.Pattern[str],
) -> str:
    portable = local_path_re.sub(
        lambda match: portable_local_path(match.group(0)),
        value,
    )
    return USER_HOME_RE.sub("{USER_HOME}", portable)


def portable_string_list(
    value: object,
    local_path_re: re.Pattern[str],
) -> list[str]:
    return [
        portable_runtime_value(item, local_path_re)
        for item in string_list(value)
    ]


def public_task_statement(value: str) -> str:
    redacted = EMAIL_RE.sub("<EMAIL_REDACTED>", value)
    return USER_HOME_RE.sub("{USER_HOME}", redacted)


def range_text(start: int, count: int) -> str:
    return str(start) if count == 1 else f"{start},{count}"


def ordered_hunk_lines(lines: list[str]) -> list[str]:
    ordered: list[str] = []
    removed: list[str] = []
    added: list[str] = []

    def flush() -> None:
        ordered.extend(removed)
        ordered.extend(added)
        removed.clear()
        added.clear()

    for line in lines:
        if line.startswith("-") and not line.startswith("---"):
            removed.append(line)
        elif line.startswith("+") and not line.startswith("+++"):
            added.append(line)
        else:
            flush()
            ordered.append(line)
    flush()
    return ordered


def canonicalize_reverse_serialized_patch(patch: str) -> str:
    """Repair a frozen gold patch that was serialized in reverse-diff form."""

    lines = patch.splitlines()
    output: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git "):
            match = re.match(r"diff --git [ab]/(.+?) [ab]/(.+)$", line)
            if match:
                line = f"diff --git a/{match.group(2)} b/{match.group(2)}"
        elif line.startswith("index "):
            match = re.match(r"index ([0-9a-f]+)\.\.([0-9a-f]+)(.*)", line)
            if match:
                line = f"index {match.group(2)}..{match.group(1)}{match.group(3)}"
        if line.startswith("+++ ") and index + 1 < len(lines) and lines[
            index + 1
        ].startswith("--- "):
            old_path = lines[index + 1][4:].removeprefix("b/")
            new_path = line[4:].removeprefix("a/")
            output.extend([f"--- a/{old_path}", f"+++ b/{new_path}"])
            index += 2
            continue
        if line.startswith("@@ "):
            match = HUNK_HEADER_RE.fullmatch(line)
            if match is None:
                raise ValueError(f"invalid reverse-serialized hunk header: {line}")
            hunk: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].startswith(
                ("@@ ", "diff --git ")
            ):
                hunk.append(lines[index])
                index += 1
            hunk = ordered_hunk_lines(hunk)
            old_count = sum(
                item.startswith((" ", "-")) and not item.startswith("---")
                for item in hunk
            )
            new_count = sum(
                item.startswith((" ", "+")) and not item.startswith("+++")
                for item in hunk
            )
            old_start = int(match.group("new_start"))
            new_start = int(match.group("old_start"))
            output.append(
                f"@@ -{range_text(old_start, old_count)} "
                f"+{range_text(new_start, new_count)} @@{match.group('section')}"
            )
            output.extend(hunk)
            continue
        output.append(line)
        index += 1
    return "\n".join(output).rstrip("\n") + "\n"


def changed_paths(patch: str) -> list[str]:
    paths: set[str] = set()
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(r"diff --git a/(.+?) b/(.+)$", line)
            if match:
                paths.add(match.group(2))
        elif line.startswith("+++ b/"):
            paths.add(line[6:])
    return sorted(path for path in paths if path != "/dev/null")


def source_label(row: dict[str, Any]) -> str:
    label = first_text(row, "source_benchmark", "source_dataset", "A_dataset")
    if label not in SOURCE_ALIASES:
        raise ValueError(f"unknown source collection label: {label!r}")
    return label


def source_case_id(row: dict[str, Any]) -> str:
    return first_text(
        row,
        "A_instance_id",
        "source_instance_id",
        "source_intent_id",
        "variant_of_case_id",
        "case_id",
    )


def task_statement(
    row: dict[str, Any],
    source_rows: dict[str, dict[str, Any]],
    *,
    modern: bool,
) -> str:
    keys = (
        ("B_problem_statement", "shared_task_prompt", "A_problem_statement", "title")
        if modern
        else ("A_problem_statement", "shared_task_prompt", "B_problem_statement", "title")
    )
    statement = first_text(row, *keys)
    if statement:
        return public_task_statement(statement)
    source = source_rows.get(source_case_id(row), {})
    statement = first_text(source, "problem_statement", "task_statement", "title")
    if not statement:
        raise ValueError(f"task statement unavailable: {row.get('case_id')}")
    return public_task_statement(statement)


def historical_solution(
    row: dict[str, Any],
    source_rows: dict[str, dict[str, Any]],
) -> str | None:
    patch = first_patch(row, "A_patch")
    if patch:
        return patch
    source = source_rows.get(source_case_id(row), {})
    patch = first_patch(source, "patch", "solution_patch")
    return patch or None


def historical_test_patch(
    row: dict[str, Any],
    source_rows: dict[str, dict[str, Any]],
) -> str | None:
    patch = first_patch(row, "A_test_patch")
    if patch:
        return patch
    source = source_rows.get(source_case_id(row), {})
    patch = first_patch(source, "test_patch")
    return patch or None


def repository_urls(repository_manifest: Path) -> dict[str, str]:
    payload = json.loads(repository_manifest.read_text(encoding="utf-8"))
    return {
        str(row["repo"]): str(row["url"])
        for row in payload["repositories"]
        if row.get("repo") and row.get("url")
    }


def family_contract(row: dict[str, Any], family: str) -> dict[str, Any]:
    contract = dict(FAMILY_CONTRACTS[family])
    if family == "api_migration":
        contract.update(
            {
                "source_library": row.get("source_library"),
                "target_library": row.get("target_library"),
                "source_api_names": string_list(row.get("source_api_names")),
                "target_api_names": string_list(row.get("target_api_names")),
                "migration_files": string_list(row.get("A_migration_files")),
            }
        )
    elif family == "security_repair":
        contract.update(
            {
                "cve_id": row.get("cve_id"),
                "cwe_id": row.get("cwe_id"),
                "cwe_name": row.get("cwe_name"),
                "language": row.get("language"),
                "target_test_files": string_list(row.get("B_target_test_files")),
            }
        )
    elif family == "test_generation":
        contract.update(
            {
                "challenge": "generated tests execute and at least one fails",
                "restored": "the same generated tests pass after restoration",
                "scope": "test files only",
            }
        )
    return contract


def verification_commands(
    row: dict[str, Any],
    family: str,
    local_path_re: re.Pattern[str],
) -> list[list[str]]:
    if family != "security_repair":
        return []
    commands = []
    for key in ("B_oracle_command", "B_p2p_command"):
        value = row.get(key)
        if isinstance(value, list) and value:
            commands.append(
                [
                    portable_runtime_value(str(item), local_path_re)
                    for item in value
                ]
            )
    return commands


def public_record(
    row: dict[str, Any],
    family: str,
    repo_urls: dict[str, str],
    source_rows: dict[str, dict[str, Any]],
    reference_only_repos: set[str],
    reference_only_sources: set[str],
    local_path_re: re.Pattern[str],
) -> dict[str, Any]:
    case_id = first_text(row, "case_id")
    pair_id = f"{family}::{case_id}"
    repo = first_text(row, "repo", "B_repo", "A_repo")
    if repo not in repo_urls:
        raise ValueError(f"repository URL unavailable: {repo}")
    challenge_patch = first_patch(row, "B_injected_diff")
    challenge_apply_mode = (
        "reverse" if row.get("B_injected_apply_reverse") is True else "forward"
    )
    if challenge_apply_mode == "reverse":
        challenge_patch = canonicalize_reverse_serialized_patch(challenge_patch)
    restoration_patch = challenge_patch
    restoration_apply_mode = (
        "forward" if challenge_apply_mode == "reverse" else "reverse"
    )
    restoration_origin = "opposite_apply_mode_of_challenge_patch"
    original_target = portable_string_list(
        row.get("A_FAIL_TO_PASS") or row.get("A_pov_tests"),
        local_path_re,
    )
    original_regression = portable_string_list(
        row.get("A_PASS_TO_PASS"),
        local_path_re,
    )
    modern_target = portable_string_list(
        row.get("B_FAIL_TO_PASS") or row.get("B_target_test_files"),
        local_path_re,
    )
    modern_regression = portable_string_list(
        row.get("B_PASS_TO_PASS_CLEAN") or row.get("B_PASS_TO_PASS"),
        local_path_re,
    )
    source = source_rows.get(source_case_id(row), {})
    if not original_target:
        original_target = portable_string_list(
            source.get("FAIL_TO_PASS"),
            local_path_re,
        )
    if not original_regression:
        original_regression = portable_string_list(
            source.get("PASS_TO_PASS"),
            local_path_re,
        )
    test_patch = first_patch(row, "B_test_patch") or historical_test_patch(
        row, source_rows
    )
    historical_base = first_text(
        row,
        "A_base_commit",
        "A_checkout_ref",
        "A_gold_ref",
    )
    modern_base = first_text(row, "B_healthy_head", "B_checkout_ref")
    if not historical_base or not modern_base:
        raise ValueError(f"base commit unavailable: {case_id}")
    label = source_label(row)
    source_id = SOURCE_ALIASES[label]
    reference_only = (
        repo in reference_only_repos or source_id in reference_only_sources
    )
    historical_solution_patch = historical_solution(row, source_rows)
    historical_tests_patch = historical_test_patch(row, source_rows)
    historical_statement = task_statement(row, source_rows, modern=False)
    modern_statement = task_statement(row, source_rows, modern=True)
    public_contract = family_contract(row, family)
    public_verification_commands = verification_commands(
        row,
        family,
        local_path_re,
    )
    public_test_patch = test_patch
    public_challenge_patch: str | None = challenge_patch
    public_restoration_patch: str | None = restoration_patch
    public_challenge_mode: str | None = challenge_apply_mode
    public_restoration_mode: str | None = restoration_apply_mode
    artifact_availability = "embedded"
    if reference_only:
        artifact_availability = "reference_only_license_restriction"
        historical_solution_patch = None
        historical_tests_patch = None
        public_test_patch = None
        public_challenge_patch = None
        public_restoration_patch = None
        public_challenge_mode = None
        public_restoration_mode = None
        historical_statement = (
            f"Reference-only {family.replace('_', ' ')} task; "
            "consult the source collection and repository provenance."
        )
        modern_statement = historical_statement
        original_target = []
        original_regression = []
        modern_target = []
        modern_regression = []
        public_verification_commands = []
        public_contract = {
            **FAMILY_CONTRACTS[family],
            "reference_only": True,
        }
    return {
        "schema_version": "change2task.public-task-pair.v1",
        "pair_id": pair_id,
        "family": family,
        "repository": {"slug": repo, "url": repo_urls[repo]},
        "provenance": {
            "source_collection_id": source_id,
            "source_collection_label": label,
            "source_case_id": source_case_id(row),
            "restoration_origin": restoration_origin,
        },
        "historical_task": {
            "instance_id": first_text(row, "A_instance_id", "source_intent_id", "case_id"),
            "base_commit": historical_base,
            "task_statement": historical_statement,
            "solution_patch": historical_solution_patch,
            "test_patch": historical_tests_patch,
            "target_tests": original_target,
            "regression_tests": original_regression,
        },
        "change2task_task": {
            "instance_id": first_text(row, "B_instance_id", "case_id"),
            "base_commit": modern_base,
            "task_statement": modern_statement,
            "artifact_availability": artifact_availability,
            "challenge_patch": public_challenge_patch,
            "challenge_apply_mode": public_challenge_mode,
            "restoration_patch": public_restoration_patch,
            "restoration_apply_mode": public_restoration_mode,
            "test_patch": public_test_patch,
            "target_tests": modern_target,
            "regression_tests": modern_regression,
            "verification_commands": public_verification_commands,
            "changed_paths": changed_paths(challenge_patch),
            "contract": public_contract,
        },
        "content_hashes": {
            "challenge_patch_sha256": sha256_text(challenge_patch),
            "restoration_patch_sha256": sha256_text(restoration_patch),
        },
    }


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--test-source", type=Path, required=True)
    parser.add_argument(
        "--private-root",
        type=Path,
        required=True,
        help="workspace root whose absolute paths must be removed",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--reference-only-repo",
        action="append",
        default=[],
        help="omit copied patch content when no upstream repository license was found",
    )
    parser.add_argument(
        "--reference-only-source",
        action="append",
        default=[],
        help="omit copied patch content for source collections with restricted terms",
    )
    args = parser.parse_args()

    frozen_root = args.frozen_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(output_root)
    manifests_root = frozen_root / "manifests"
    repo_urls = repository_urls(frozen_root / "repositories.json")
    source_rows = {
        str(row.get("instance_id") or row.get("case_id")): row
        for row in read_jsonl(args.test_source.resolve())
    }
    reference_only_repos = set(args.reference_only_repo)
    reference_only_sources = set(args.reference_only_source)
    private_root = str(args.private_root.resolve()).rstrip("/") + "/"
    local_path_re = re.compile(
        re.escape(private_root)
        + rf"(?:(?!{re.escape(private_root)})[^\]\[,\s'\"])+"
    )

    records_by_family: dict[str, list[dict[str, Any]]] = {}
    all_pair_ids: set[str] = set()
    source_counts: dict[str, int] = {}
    repository_slugs: set[str] = set()
    restoration_origins: dict[str, int] = {}
    challenge_apply_modes: dict[str, int] = {}
    artifact_availability_counts: dict[str, int] = {}
    for family, filename in FAMILY_FILES.items():
        records = [
            public_record(
                row,
                family,
                repo_urls,
                source_rows,
                reference_only_repos,
                reference_only_sources,
                local_path_re,
            )
            for row in read_jsonl(manifests_root / filename)
        ]
        records.sort(key=lambda row: row["pair_id"])
        for record in records:
            pair_id = record["pair_id"]
            if pair_id in all_pair_ids:
                raise ValueError(f"duplicate public pair_id: {pair_id}")
            all_pair_ids.add(pair_id)
            source_id = record["provenance"]["source_collection_id"]
            source_counts[source_id] = source_counts.get(source_id, 0) + 1
            repository_slugs.add(record["repository"]["slug"])
            origin = record["provenance"]["restoration_origin"]
            restoration_origins[origin] = restoration_origins.get(origin, 0) + 1
            mode = record["change2task_task"]["challenge_apply_mode"]
            if mode is not None:
                challenge_apply_modes[mode] = challenge_apply_modes.get(mode, 0) + 1
            availability = record["change2task_task"]["artifact_availability"]
            artifact_availability_counts[availability] = (
                artifact_availability_counts.get(availability, 0) + 1
            )
        records_by_family[family] = records

    output_root.mkdir(parents=True)
    data_dir = output_root / "task_pairs"
    data_dir.mkdir()
    file_entries = []
    for family, records in records_by_family.items():
        path = data_dir / f"{family}.jsonl"
        content = "".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
            for record in records
        )
        atomic_write(path, content)
        file_entries.append(
            {
                "path": str(path.relative_to(output_root)),
                "records": len(records),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )

    atomic_write(
        output_root / "schema.json",
        json.dumps(SCHEMA, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    manifest = {
        "schema_version": "change2task.public-dataset-manifest.v1",
        "dataset_version": "v1",
        "source_freeze_id": "frozen900_20260729",
        "paper": "https://arxiv.org/abs/2607.28591",
        "total_pairs": len(all_pair_ids),
        "family_counts": {
            family: len(records) for family, records in records_by_family.items()
        },
        "source_collection_counts": dict(sorted(source_counts.items())),
        "unique_repository_slugs": len(repository_slugs),
        "restoration_origins": dict(sorted(restoration_origins.items())),
        "challenge_apply_modes": dict(sorted(challenge_apply_modes.items())),
        "artifact_availability": dict(
            sorted(artifact_availability_counts.items())
        ),
        "files": sorted(file_entries, key=lambda row: row["path"]),
        "contains_agent_evaluation_results": False,
        "contains_model_telemetry": False,
        "contains_local_paths": False,
        "privacy_policy": {
            "task_statement_emails": "redacted",
            "task_statement_user_homes": "portable_placeholder",
            "local_runtime_paths": "portable_placeholders",
            "public_repository_patches": (
                "preserved when a pinned-base license or project declaration "
                "was detected; otherwise reference-only"
            ),
        },
    }
    atomic_write(
        output_root / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    checksummed = [
        path
        for path in sorted(output_root.rglob("*"))
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    ]
    checksums = "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(output_root)}\n"
        for path in checksummed
    )
    atomic_write(output_root / "CHECKSUMS.sha256", checksums)
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
