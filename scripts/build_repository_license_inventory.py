#!/usr/bin/env python3
"""Build a pinned-revision license inventory for public task repositories."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

LICENSE_NAMES = {
    "copying",
    "copying.md",
    "copying.txt",
    "copyright",
    "licence",
    "licence.md",
    "licence.txt",
    "license",
    "license.md",
    "license.txt",
    "notice",
    "notice.md",
    "notice.txt",
    "unlicense",
}
DECLARATION_NAMES = {
    "package.json",
    "pom.xml",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
}


def git_text(cache: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(cache), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout


def detect_spdx(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).lower()
    detected: set[str] = set()
    if "apache license" in normalized and "version 2.0" in normalized:
        detected.add("Apache-2.0")
    if "permission is hereby granted, free of charge" in normalized:
        detected.add("MIT")
    if re.search(
        r"(?:license\s*=\s*['\"]mit['\"]|"
        r"<name>\s*mit(?: license)?\s*</name>|"
        r"['\"]license['\"]\s*:\s*['\"]mit['\"])",
        normalized,
    ):
        detected.add("MIT")
    if "gnu affero general public license" in normalized:
        detected.add("AGPL")
    elif "gnu lesser general public license" in normalized:
        detected.add("LGPL")
    elif "gnu general public license" in normalized:
        detected.add("GPL")
    if "mozilla public license version 2.0" in normalized:
        detected.add("MPL-2.0")
    if "eclipse public license" in normalized:
        detected.add("EPL")
    if "redistribution and use in source and binary forms" in normalized:
        detected.add(
            "BSD-3-Clause"
            if "neither the name" in normalized
            else "BSD-2-Clause"
        )
    if "permission to use, copy, modify, and/or distribute this software" in normalized:
        detected.add("ISC")
    if "python software foundation license" in normalized:
        detected.add("PSF-2.0")
    if "the unlicense" in normalized or "unlicensed. for more information" in normalized:
        detected.add("Unlicense")
    if "creative commons attribution 4.0" in normalized:
        detected.add("CC-BY-4.0")
    if "cc0 1.0 universal" in normalized:
        detected.add("CC0-1.0")
    if "business source license 1.1" in normalized:
        detected.add("BUSL-1.1")
    if "mit-cmu license" in normalized or "pil software license" in normalized:
        detected.add("HPND")
    if "license agreement for matplotlib versions 1.3.0 and later" in normalized:
        detected.add("Matplotlib-1.3")
    if "free and unencumbered software released into the public domain" in normalized:
        detected.add("Unlicense")
    return sorted(detected)


def license_paths(cache: Path, ref: str) -> list[str]:
    paths = git_text(cache, "ls-tree", "-r", "--name-only", ref).splitlines()
    candidates = []
    for path in paths:
        relative = Path(path)
        name = relative.name.lower()
        if (
            name in LICENSE_NAMES
            or name.startswith(("license.", "licence.", "copying.", "notice."))
        ) and len(relative.parts) <= 2:
            candidates.append(path)
    return sorted(candidates)


def license_declarations(cache: Path, ref: str) -> list[dict[str, Any]]:
    paths = git_text(cache, "ls-tree", "-r", "--name-only", ref).splitlines()
    declarations = []
    for path in sorted(paths):
        relative = Path(path)
        if len(relative.parts) != 1 or relative.name.lower() not in DECLARATION_NAMES:
            continue
        content = subprocess.check_output(
            ["git", "-C", str(cache), "show", f"{ref}:{path}"]
        )
        detected = detect_spdx(content.decode("utf-8", errors="replace"))
        if detected:
            declarations.append(
                {
                    "path": path,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "detected_spdx": detected,
                }
            )
    return declarations


def read_task_records(dataset_root: Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted((dataset_root / "task_pairs").glob("*.jsonl")):
        records.extend(
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frozen-root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    frozen_root = args.frozen_root.resolve()
    dataset_root = args.dataset_root.resolve()
    repository_rows = json.loads(
        (frozen_root / "repositories.json").read_text(encoding="utf-8")
    )["repositories"]
    private_repositories = {str(row["repo"]): row for row in repository_rows}
    public_records = read_task_records(dataset_root)
    refs_by_repo: dict[str, set[str]] = defaultdict(set)
    sources_by_repo: dict[str, set[str]] = defaultdict(set)
    urls: dict[str, str] = {}
    for record in public_records:
        repo = str(record["repository"]["slug"])
        refs_by_repo[repo].add(str(record["change2task_task"]["base_commit"]))
        sources_by_repo[repo].add(
            str(record["provenance"]["source_collection_id"])
        )
        urls[repo] = str(record["repository"]["url"])

    repositories = []
    status_counts: dict[str, int] = defaultdict(int)
    for repo in sorted(refs_by_repo):
        private = private_repositories.get(repo)
        if private is None:
            raise ValueError(f"repository metadata unavailable: {repo}")
        cache = Path(str(private["cache_path"]))
        if not (cache / ".git").exists():
            raise FileNotFoundError(f"repository cache unavailable: {repo}")
        bases = []
        repo_licenses: set[str] = set()
        for ref in sorted(refs_by_repo[repo]):
            git_text(cache, "cat-file", "-e", f"{ref}^{{commit}}")
            files = []
            for path in license_paths(cache, ref):
                content = subprocess.check_output(
                    ["git", "-C", str(cache), "show", f"{ref}:{path}"]
                )
                detected = detect_spdx(content.decode("utf-8", errors="replace"))
                repo_licenses.update(detected)
                files.append(
                    {
                        "path": path,
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "detected_spdx": detected,
                    }
                )
            declarations = [] if files else license_declarations(cache, ref)
            for declaration in declarations:
                repo_licenses.update(declaration["detected_spdx"])
            bases.append(
                {
                    "commit": ref,
                    "license_files": files,
                    "license_declarations": declarations,
                }
            )
        if repo_licenses:
            status = (
                "license_detected_at_pinned_base"
                if any(base["license_files"] for base in bases)
                else "license_declared_in_project_metadata"
            )
        elif any(base["license_files"] for base in bases):
            status = "license_file_present_but_unclassified"
        else:
            status = "no_license_file_at_pinned_base"
        status_counts[status] += 1
        repositories.append(
            {
                "repository": repo,
                "url": urls[repo],
                "source_collection_ids": sorted(sources_by_repo[repo]),
                "detected_spdx": sorted(repo_licenses),
                "license_status": status,
                "bases": bases,
            }
        )

    payload = {
        "schema_version": "change2task.repository-license-inventory.v1",
        "scope": "license files at the modern base commits in the public task corpus",
        "method": (
            "root or one-directory-deep license/copying/notice files; "
            "SPDX-like text detection"
        ),
        "policy": (
            "Detected identifiers are informational, not legal advice. "
            "Source repository and benchmark terms remain controlling."
        ),
        "repository_count": len(repositories),
        "status_counts": dict(sorted(status_counts.items())),
        "repositories": repositories,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["status_counts"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
