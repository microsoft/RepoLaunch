"""Deterministic L1 Patch Reversal and L2 Code Mapping generators."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from unidiff import PatchSet

from change2task.core.diff_parser import is_test_file
from change2task.workflow.git_utils import IsolatedWorktree


@dataclass
class GeneratedPatch:
    success: bool
    task_patch: str = ""
    restoration_patch: str = ""
    changed_files: list[str] = field(default_factory=list)
    feedback: str = ""


class PatchReversal:
    """Level 1: reverse-apply the historical forward patch once."""

    async def generate(self, worktree: IsolatedWorktree, source_patch: str) -> GeneratedPatch:
        await worktree.clean_to_head()
        applied, error = await worktree.apply_patch(source_patch, reverse=True)
        if not applied:
            return GeneratedPatch(success=False, feedback=error)
        task_patch = await worktree.diff()
        restoration_patch = await worktree.reverse_diff()
        changed_files = await worktree.changed_files()
        if not task_patch.strip():
            return GeneratedPatch(
                success=False,
                feedback="reverse application produced an empty patch",
            )
        return GeneratedPatch(
            success=True,
            task_patch=task_patch,
            restoration_patch=restoration_patch,
            changed_files=changed_files,
        )


@dataclass(frozen=True)
class EditGroup:
    path: str
    before: str
    after: str
    section: str


class CodeMapping:
    """Level 2: strict unique-block mapping with no whole-function fallback."""

    async def generate(self, worktree: IsolatedWorktree, source_patch: str) -> GeneratedPatch:
        await worktree.clean_to_head()
        groups, error = self._eligible_groups(source_patch)
        if error:
            return GeneratedPatch(success=False, feedback=error)
        if not groups:
            return GeneratedPatch(success=False, feedback="no eligible paired source edit group")

        file_contents: dict[Path, str] = {}
        for group in groups:
            resolved = self._resolve_path(worktree.path, group.path)
            if resolved is None:
                return GeneratedPatch(
                    success=False,
                    feedback=f"modern file unresolved or ambiguous: {group.path}",
                )
            content = file_contents.get(resolved)
            if content is None:
                content = resolved.read_text(encoding="utf-8", errors="replace")
            replaced = self._replace_unique(content, group.before, group.after)
            if replaced is None:
                return GeneratedPatch(
                    success=False,
                    feedback=(
                        "historical post-change block is missing or ambiguous in "
                        f"{resolved.relative_to(worktree.path)} ({group.section})"
                    ),
                )
            file_contents[resolved] = replaced

        for path, content in file_contents.items():
            path.write_text(content, encoding="utf-8")
            syntax_error = self._syntax_error(path, content)
            if syntax_error:
                await worktree.clean_to_head()
                return GeneratedPatch(success=False, feedback=syntax_error)

        diff_check = await worktree.git("diff", "--check")
        if diff_check.return_code != 0:
            feedback = diff_check.stderr.decode(errors="replace")
            await worktree.clean_to_head()
            return GeneratedPatch(success=False, feedback=feedback)
        task_patch = await worktree.diff()
        restoration_patch = await worktree.reverse_diff()
        changed_files = await worktree.changed_files()
        if not task_patch.strip():
            return GeneratedPatch(success=False, feedback="code mapping produced an empty patch")
        return GeneratedPatch(
            success=True,
            task_patch=task_patch,
            restoration_patch=restoration_patch,
            changed_files=changed_files,
        )

    def _eligible_groups(self, source_patch: str) -> tuple[list[EditGroup], str]:
        try:
            patch = PatchSet(source_patch)
        except Exception as exc:
            return [], f"invalid historical patch: {exc}"
        groups: list[EditGroup] = []
        for patched_file in patch:
            if is_test_file(patched_file.path):
                continue
            if patched_file.is_added_file or patched_file.is_removed_file:
                return [], "pure file additions/deletions are outside Level 2"
            for hunk in patched_file:
                removed: list[str] = []
                added: list[str] = []

                for line in hunk:
                    if line.is_removed:
                        removed.append(line.value)
                    elif line.is_added:
                        added.append(line.value)
                    else:
                        error = self._flush_group(
                            groups=groups,
                            path=patched_file.path,
                            section=hunk.section_header or "",
                            removed=removed,
                            added=added,
                        )
                        if error:
                            return [], error
                error = self._flush_group(
                    groups=groups,
                    path=patched_file.path,
                    section=hunk.section_header or "",
                    removed=removed,
                    added=added,
                )
                if error:
                    return [], error
        return groups, ""

    @classmethod
    def _flush_group(
        cls,
        *,
        groups: list[EditGroup],
        path: str,
        section: str,
        removed: list[str],
        added: list[str],
    ) -> str | None:
        if not removed and not added:
            return None
        if not removed or not added:
            return "pure additions/deletions are outside Level 2"
        if cls._import_only([*removed, *added]):
            return "import-only edit groups are outside Level 2"
        groups.append(
            EditGroup(
                path=path,
                before="".join(added),
                after="".join(removed),
                section=section,
            )
        )
        removed.clear()
        added.clear()
        return None

    @staticmethod
    def _import_only(lines: list[str]) -> bool:
        meaningful = [line.strip() for line in lines if line.strip()]
        return bool(meaningful) and all(
            line.startswith(("import ", "from ", "using ", "#include "))
            or line in {"(", ")"}
            or line.endswith((",", "(", ")"))
            for line in meaningful
        )

    @staticmethod
    def _resolve_path(root: Path, source_path: str) -> Path | None:
        exact = root / source_path
        if exact.is_file():
            return exact
        source_parent = Path(source_path).parent
        candidates = [
            candidate
            for candidate in root.rglob(Path(source_path).name)
            if candidate.is_file()
            and (
                str(candidate.relative_to(root).parent).endswith(str(source_parent))
                or candidate.parent.name == source_parent.name
            )
        ]
        return candidates[0] if len(candidates) == 1 else None

    @classmethod
    def _replace_unique(cls, source: str, before: str, after: str) -> str | None:
        exact_matches = [match.start() for match in re.finditer(re.escape(before), source)]
        if len(exact_matches) == 1:
            return source[: exact_matches[0]] + after + source[exact_matches[0] + len(before) :]
        normalized = cls._normalized_occurrences(source, before)
        if len(normalized) != 1:
            return None
        start, end, target_indent, source_indent = normalized[0]
        replacement_lines = []
        for line in after.splitlines(keepends=True):
            if line.strip():
                body = line[source_indent:] if len(line) >= source_indent else line.lstrip()
                replacement_lines.append(" " * target_indent + body)
            else:
                replacement_lines.append(line)
        return source[:start] + "".join(replacement_lines) + source[end:]

    @staticmethod
    def _normalized_occurrences(source: str, before: str) -> list[tuple[int, int, int, int]]:
        source_lines = source.splitlines(keepends=True)
        before_lines = before.splitlines(keepends=True)
        if not before_lines:
            return []
        source_indent = min(
            (len(line) - len(line.lstrip(" ")) for line in before_lines if line.strip()),
            default=0,
        )
        needle = [
            line[source_indent:].rstrip("\r\n") if line.strip() else line.rstrip("\r\n")
            for line in before_lines
        ]
        offsets: list[int] = []
        total = 0
        for line in source_lines:
            offsets.append(total)
            total += len(line)
        matches: list[tuple[int, int, int, int]] = []
        for index in range(len(source_lines) - len(needle) + 1):
            window = source_lines[index : index + len(needle)]
            target_indent = min(
                (len(line) - len(line.lstrip(" ")) for line in window if line.strip()),
                default=0,
            )
            normalized = [
                line[target_indent:].rstrip("\r\n") if line.strip() else line.rstrip("\r\n")
                for line in window
            ]
            if normalized == needle:
                start = offsets[index]
                end = offsets[index + len(needle)] if index + len(needle) < len(offsets) else total
                matches.append((start, end, target_indent, source_indent))
        return matches

    @staticmethod
    def _syntax_error(path: Path, content: str) -> str:
        if path.suffix == ".py":
            try:
                ast.parse(content, filename=str(path))
            except SyntaxError as exc:
                return f"Python reparse failed for {path}: {exc}"
        return ""
