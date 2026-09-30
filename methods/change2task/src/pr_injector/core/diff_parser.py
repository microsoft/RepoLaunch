"""Unified diff parsing and analysis utilities."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from unidiff import PatchSet

from pr_injector.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChangedFunction:
    """A function or method that was modified in a diff."""

    name: str
    file_path: str
    start_line: int
    end_line: int
    change_type: str  # "modified", "added", "deleted"


@dataclass
class DiffAnalysis:
    """Analysis results of a unified diff."""

    files_changed: list[str] = field(default_factory=list)
    files_added: list[str] = field(default_factory=list)
    files_deleted: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    source_files: list[str] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    changed_functions: list[ChangedFunction] = field(default_factory=list)


# Common test file patterns across languages
TEST_PATTERNS = [
    re.compile(r"test[_/]"),
    re.compile(r"[_/]test\."),
    re.compile(r"tests[_/]"),
    re.compile(r"spec[_/]"),
    re.compile(r"__tests__/"),
    re.compile(r"_test\.(py|go|rs|js|ts|java)$"),
    re.compile(r"\.test\.(js|ts|jsx|tsx)$"),
    re.compile(r"\.spec\.(js|ts|jsx|tsx)$"),
]


def is_test_file(file_path: str) -> bool:
    """Check if a file path looks like a test file."""
    path_lower = file_path.lower()
    return any(pattern.search(path_lower) for pattern in TEST_PATTERNS)


def parse_diff(diff_text: str) -> DiffAnalysis:
    """Parse a unified diff and extract analysis.

    Args:
        diff_text: Raw unified diff string.

    Returns:
        DiffAnalysis with categorized file changes.
    """
    analysis = DiffAnalysis()

    if not diff_text.strip():
        return analysis

    try:
        patch_set = PatchSet(diff_text)
    except Exception as e:
        logger.warning("diff_parse_failed", error=str(e))
        return analysis

    for patched_file in patch_set:
        file_path = patched_file.path
        analysis.files_changed.append(file_path)

        if patched_file.is_added_file:
            analysis.files_added.append(file_path)
        elif patched_file.is_removed_file:
            analysis.files_deleted.append(file_path)
        else:
            analysis.files_modified.append(file_path)

        if is_test_file(file_path):
            analysis.test_files.append(file_path)
        else:
            analysis.source_files.append(file_path)

        analysis.total_additions += patched_file.added
        analysis.total_deletions += patched_file.removed

    return analysis


def reverse_diff(diff_text: str) -> str:
    """Reverse a unified diff (swap additions and deletions).

    Converts a patch that applies a fix into a patch that undoes it,
    effectively creating the golden patch from an injection diff.

    After swapping +/- prefixes, reorders lines within each change group
    so that deletions (-) come before additions (+), which is required
    by the unified diff format.
    """
    lines = diff_text.split("\n")
    swapped_lines: list[str] = []

    # Step 1: swap +/- and headers
    for line in lines:
        if line.startswith("diff --git"):
            swapped_lines.append(line)
        elif line.startswith("---"):
            swapped_lines.append(line.replace("--- a/", "--- b/").replace("--- b/", "--- a/", 1))
        elif line.startswith("+++"):
            swapped_lines.append(line.replace("+++ b/", "+++ a/").replace("+++ a/", "+++ b/", 1))
        elif line.startswith("@@"):
            # Swap hunk headers: @@ -old,count +new,count @@ -> @@ -new,count +old,count @@
            match = re.match(r"@@ -(\d+(?:,\d+)?) \+(\d+(?:,\d+)?) @@(.*)", line)
            if match:
                swapped_lines.append(f"@@ -{match.group(2)} +{match.group(1)} @@{match.group(3)}")
            else:
                swapped_lines.append(line)
        elif line.startswith("+"):
            swapped_lines.append("-" + line[1:])
        elif line.startswith("-"):
            swapped_lines.append("+" + line[1:])
        else:
            swapped_lines.append(line)

    # Step 2: reorder change groups so - lines come before + lines
    result: list[str] = []
    plus_buf: list[str] = []
    minus_buf: list[str] = []

    def flush_buffers() -> None:
        result.extend(minus_buf)
        result.extend(plus_buf)
        minus_buf.clear()
        plus_buf.clear()

    for line in swapped_lines:
        if line.startswith("+") and not line.startswith("+++"):
            plus_buf.append(line)
        elif line.startswith("-") and not line.startswith("---"):
            minus_buf.append(line)
        else:
            flush_buffers()
            result.append(line)

    flush_buffers()
    return "\n".join(result)


def extract_test_diff(diff_text: str) -> str:
    """Extract only test file changes from a diff."""
    try:
        patch_set = PatchSet(diff_text)
    except Exception:
        return ""

    test_diffs: list[str] = []
    for patched_file in patch_set:
        if is_test_file(patched_file.path):
            test_diffs.append(str(patched_file))

    return "\n".join(test_diffs)


def extract_source_diff(diff_text: str) -> str:
    """Extract only source (non-test) file changes from a diff."""
    try:
        patch_set = PatchSet(diff_text)
    except Exception:
        return ""

    source_diffs: list[str] = []
    for patched_file in patch_set:
        if not is_test_file(patched_file.path):
            source_diffs.append(str(patched_file))

    return "\n".join(source_diffs)


def get_patch_size(diff_text: str) -> int:
    """Get total lines changed (additions + deletions)."""
    try:
        patch_set = PatchSet(diff_text)
        total = 0
        for patched_file in patch_set:
            total += patched_file.added + patched_file.removed
        return total
    except Exception:
        return 0
