"""Unit tests for diff parsing utilities."""

from __future__ import annotations

import pytest

from pr_injector.core.diff_parser import (
    get_patch_size,
    is_test_file,
    parse_diff,
    reverse_diff,
)


class TestIsTestFile:
    @pytest.mark.parametrize(
        "path,expected",
        [
            ("tests/test_app.py", True),
            ("test_utils.py", True),
            ("src/app_test.go", True),
            ("__tests__/App.test.js", True),
            ("spec/models/user_spec.rb", True),
            ("src/app.py", False),
            ("lib/utils.js", False),
            ("main.go", False),
        ],
    )
    def test_detection(self, path: str, expected: bool):
        assert is_test_file(path) == expected


class TestParseDiff:
    def test_parse_simple_diff(self, sample_diff):
        analysis = parse_diff(sample_diff)
        assert len(analysis.files_changed) == 1
        assert "src/flask/blueprints.py" in analysis.files_changed

    def test_parse_empty_diff(self):
        analysis = parse_diff("")
        assert len(analysis.files_changed) == 0

    def test_categorizes_test_files(self):
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n"
            "+++ b/src/app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/tests/test_app.py b/tests/test_app.py\n"
            "--- a/tests/test_app.py\n"
            "+++ b/tests/test_app.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old test\n"
            "+new test\n"
        )
        analysis = parse_diff(diff)
        assert "tests/test_app.py" in analysis.test_files
        assert "src/app.py" in analysis.source_files


class TestReverseDiff:
    def test_reverse_additions_deletions(self):
        diff = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 line1
-old_line
+new_line
+extra_line
 line3"""

        reversed_d = reverse_diff(diff)
        assert "+old_line" in reversed_d
        assert "-new_line" in reversed_d
        assert "-extra_line" in reversed_d


class TestGetPatchSize:
    def test_counts_changes(self, sample_diff):
        size = get_patch_size(sample_diff)
        assert size > 0

    def test_empty_diff(self):
        assert get_patch_size("") == 0
