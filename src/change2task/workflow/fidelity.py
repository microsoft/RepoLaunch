"""Six-component source-to-modern change-profile fidelity."""

from __future__ import annotations

import re
from collections.abc import Iterable

from unidiff import PatchSet

from change2task.workflow.models import (
    FidelityComponents,
    FidelityReport,
    SourceChangeProfile,
)

FIDELITY_WEIGHTS = {
    "files": 0.18,
    "hunks": 0.20,
    "changed_lines": 0.28,
    "symbols": 0.10,
    "target_checks": 0.12,
    "regression_checks": 0.12,
}

SYMBOL_PATTERNS = (
    re.compile(r"\b(?:async\s+def|def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"\b(?:function|class|interface|enum)\s+([A-Za-z_$][A-Za-z0-9_$]*)"),
    re.compile(
        r"\b(?:public|private|protected|static|final|synchronized|abstract|\s)+"
        r"[A-Za-z_$][A-Za-z0-9_$<>, ?\[\]]*\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\("
    ),
    re.compile(r"\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    re.compile(r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
)


def _similarity(left: int, right: int) -> float:
    if left == 0 and right == 0:
        return 1.0
    if left == 0 or right == 0:
        return 0.0
    return min(left, right) / max(left, right)


def _directional_ratio(left: int, right: int) -> float | None:
    if left == 0 and right == 0:
        return 1.0
    if left == 0:
        return None
    return right / left


def _extract_symbols(patch: PatchSet, explicit_symbols: Iterable[str]) -> list[str]:
    symbols = {symbol.strip() for symbol in explicit_symbols if symbol.strip()}
    for patched_file in patch:
        for hunk in patched_file:
            header = (hunk.section_header or "").strip()
            if header:
                # Hunk headers often contain a qualified function or class name.
                tail = header.split("(", 1)[0].split()[-1].strip(":")
                if re.match(r"^[A-Za-z_$][A-Za-z0-9_.$:-]*$", tail):
                    symbols.add(tail)
            for line in hunk:
                if not (line.is_added or line.is_removed):
                    continue
                for pattern in SYMBOL_PATTERNS:
                    symbols.update(pattern.findall(line.value))
    return sorted(symbols)


def profile_patch(
    patch_text: str,
    *,
    target_checks: int,
    regression_checks: int,
    explicit_symbols: Iterable[str] = (),
) -> SourceChangeProfile:
    """Compute the six fidelity dimensions for one forward maintenance patch."""

    try:
        patch = PatchSet(patch_text)
    except Exception:
        patch = PatchSet("")
    paths = sorted({patched_file.path for patched_file in patch})
    hunks = sum(len(patched_file) for patched_file in patch)
    changed_lines = sum(patched_file.added + patched_file.removed for patched_file in patch)
    symbols = _extract_symbols(patch, explicit_symbols)
    return SourceChangeProfile(
        files=len(paths),
        hunks=hunks,
        changed_lines=changed_lines,
        symbols=len(symbols),
        target_checks=target_checks,
        regression_checks=regression_checks,
        file_paths=paths,
        symbol_names=symbols,
    )


def compare_profiles(
    source: SourceChangeProfile,
    modern_restoration: SourceChangeProfile,
) -> FidelityReport:
    """Apply the published Change2Task weights and thresholds."""

    components = FidelityComponents(
        files=_similarity(source.files, modern_restoration.files),
        hunks=_similarity(source.hunks, modern_restoration.hunks),
        changed_lines=_similarity(source.changed_lines, modern_restoration.changed_lines),
        symbols=_similarity(source.symbols, modern_restoration.symbols),
        target_checks=_similarity(source.target_checks, modern_restoration.target_checks),
        regression_checks=_similarity(
            source.regression_checks, modern_restoration.regression_checks
        ),
    )
    values = components.model_dump()
    weighted = sum(values[name] * weight for name, weight in FIDELITY_WEIGHTS.items())
    directional_ratios = {
        "files": _directional_ratio(source.files, modern_restoration.files),
        "hunks": _directional_ratio(source.hunks, modern_restoration.hunks),
        "changed_lines": _directional_ratio(
            source.changed_lines,
            modern_restoration.changed_lines,
        ),
        "symbols": _directional_ratio(source.symbols, modern_restoration.symbols),
        "target_checks": _directional_ratio(
            source.target_checks,
            modern_restoration.target_checks,
        ),
        "regression_checks": _directional_ratio(
            source.regression_checks,
            modern_restoration.regression_checks,
        ),
    }
    line_scale = directional_ratios["changed_lines"]
    tags: list[str] = []
    if weighted < 0.65:
        tags.append("aggregate_fidelity_below_0.65")
    if directional_ratios["files"] is None or directional_ratios["files"] < 0.50:
        tags.append("file_scope_below_0.50")
    if directional_ratios["hunks"] is None or directional_ratios["hunks"] < 0.50:
        tags.append("hunk_scope_below_0.50")
    if line_scale is None or line_scale < 0.50:
        tags.append("line_scope_below_0.50")
    if line_scale is None or line_scale > 2.50:
        tags.append("line_scale_above_2.50")
    regression_ratio = directional_ratios["regression_checks"]
    if regression_ratio is None or regression_ratio < 0.25:
        tags.append("insufficient_regression_surface")
    return FidelityReport(
        source=source,
        modern_restoration=modern_restoration,
        components=components,
        weighted_score=weighted,
        weights=dict(FIDELITY_WEIGHTS),
        directional_ratios=directional_ratios,
        line_scale_ratio=line_scale,
        passed=not tags,
        failure_tags=tags,
    )


def compare_patches(
    source_patch: str,
    restoration_patch: str,
    *,
    source_target_checks: int,
    modern_target_checks: int,
    source_regression_checks: int,
    modern_regression_checks: int,
    source_symbols: Iterable[str] = (),
    modern_symbols: Iterable[str] = (),
) -> FidelityReport:
    """Compare historical ``P_s`` with modern forward restoration ``G``."""

    source = profile_patch(
        source_patch,
        target_checks=source_target_checks,
        regression_checks=source_regression_checks,
        explicit_symbols=source_symbols,
    )
    modern = profile_patch(
        restoration_patch,
        target_checks=modern_target_checks,
        regression_checks=modern_regression_checks,
        explicit_symbols=modern_symbols,
    )
    return compare_profiles(source, modern)
