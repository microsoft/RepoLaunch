"""Validation for LLM-generated diffs and injections."""

from __future__ import annotations

import re

from pr_injector.core.logging import get_logger

logger = get_logger(__name__)


def extract_diff_from_response(response: str) -> str | None:
    """Extract a unified diff from an LLM response.

    Handles cases where the LLM wraps the diff in markdown code blocks
    or adds explanatory text.

    Args:
        response: Raw LLM response text.

    Returns:
        Extracted diff string, or None if no valid diff found.
    """
    # Try to find diff in code blocks first (```diff or ``` blocks)
    code_block_match = re.search(
        r"```(?:diff)?\s*\n(.*?)```", response, re.DOTALL
    )
    if code_block_match:
        block = code_block_match.group(1).strip()
        # Verify it looks like a diff
        if any(line.startswith(("diff --git", "---", "@@")) for line in block.split("\n")):
            return block

    # Try to find bare diff starting with "diff --git"
    diff_match = re.search(r"(diff --git\s+.*)", response, re.DOTALL)
    if diff_match:
        return diff_match.group(1).strip()

    # Try to find diff starting with ---/+++ (no diff --git header)
    patch_match = re.search(
        r"(---\s+a/\S+.*?\+\+\+\s+b/\S+.*)", response, re.DOTALL
    )
    if patch_match:
        return patch_match.group(1).strip()

    # Try to find any @@ hunk and extract surrounding context
    hunk_match = re.search(r"(---\s+\S+.*)", response, re.DOTALL)
    if hunk_match:
        candidate = hunk_match.group(1).strip()
        if "@@" in candidate:
            return candidate

    return None


def validate_diff_syntax(diff_text: str) -> tuple[bool, list[str]]:
    """Validate that a diff has correct unified diff syntax.

    Args:
        diff_text: Unified diff string.

    Returns:
        Tuple of (is_valid, list_of_errors).
    """
    errors: list[str] = []

    if not diff_text.strip():
        errors.append("Diff is empty")
        return False, errors

    lines = diff_text.split("\n")
    has_file_header = False
    has_hunk = False

    for i, line in enumerate(lines):
        if line.startswith("diff --git"):
            has_file_header = True
        elif line.startswith("@@"):
            has_hunk = True
            # Validate hunk header format
            if not re.match(r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", line):
                errors.append(f"Line {i + 1}: Invalid hunk header: {line[:60]}")

    if not has_file_header and not any(
        line.startswith("---") or line.startswith("+++") for line in lines
    ):
        errors.append("No file header (diff --git or ---/+++) found")

    if not has_hunk:
        errors.append("No hunk headers (@@) found")

    return len(errors) == 0, errors


def validate_diff_files(
    diff_text: str, allowed_files: list[str] | None = None
) -> tuple[bool, list[str]]:
    """Validate that a diff only modifies expected files.

    Args:
        diff_text: Unified diff string.
        allowed_files: List of file paths that may be modified.

    Returns:
        Tuple of (is_valid, list_of_modified_files).
    """
    modified_files: list[str] = []

    for line in diff_text.split("\n"):
        if line.startswith("diff --git"):
            # Extract file path from "diff --git a/path b/path"
            match = re.match(r"diff --git a/(\S+) b/(\S+)", line)
            if match:
                modified_files.append(match.group(2))
        elif line.startswith("+++ b/"):
            path = line[6:].strip()
            if path and path not in modified_files:
                modified_files.append(path)

    if allowed_files is not None:
        unexpected = [f for f in modified_files if f not in allowed_files]
        if unexpected:
            logger.warning(
                "diff_modifies_unexpected_files",
                unexpected=unexpected,
                allowed=allowed_files,
            )
            return False, modified_files

    return True, modified_files


def estimate_confidence(
    diff_text: str, original_diff: str
) -> float:
    """Estimate confidence score for an LLM-generated injection.

    Higher scores indicate the injection is more likely to be a valid
    recreation of the original bug.

    Args:
        diff_text: LLM-generated diff.
        original_diff: Original fix diff for comparison.

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    score = 0.5  # Base score

    # Check if similar number of files are modified
    gen_files = set(re.findall(r"diff --git a/(\S+)", diff_text))
    orig_files = set(re.findall(r"diff --git a/(\S+)", original_diff))

    if gen_files and orig_files:
        file_overlap = len(gen_files & orig_files) / max(len(gen_files), len(orig_files))
        score += 0.2 * file_overlap

    # Check if similar size
    gen_changes = diff_text.count("\n+") + diff_text.count("\n-")
    orig_changes = original_diff.count("\n+") + original_diff.count("\n-")

    if orig_changes > 0:
        size_ratio = min(gen_changes, orig_changes) / max(gen_changes, orig_changes)
        score += 0.2 * size_ratio

    # Syntax validity bonus
    valid, _ = validate_diff_syntax(diff_text)
    if valid:
        score += 0.1

    return min(1.0, max(0.0, score))
