"""Unit tests for LLM output validation."""

from __future__ import annotations

from pr_injector.llm.validator import (
    estimate_confidence,
    extract_diff_from_response,
    validate_diff_files,
    validate_diff_syntax,
)


class TestExtractDiff:
    def test_bare_diff(self):
        response = """diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old
+new"""
        diff = extract_diff_from_response(response)
        assert diff is not None
        assert "diff --git" in diff

    def test_markdown_wrapped(self):
        response = """Here is the diff:

```diff
diff --git a/file.py b/file.py
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
-old
+new
```

Done."""
        diff = extract_diff_from_response(response)
        assert diff is not None
        assert "diff --git" in diff

    def test_no_diff(self):
        assert extract_diff_from_response("No diff here") is None

    def test_empty_response(self):
        assert extract_diff_from_response("") is None


class TestValidateDiffSyntax:
    def test_valid_diff(self):
        diff = """diff --git a/f.py b/f.py
--- a/f.py
+++ b/f.py
@@ -1,3 +1,3 @@
-old
+new"""
        valid, errors = validate_diff_syntax(diff)
        assert valid is True
        assert len(errors) == 0

    def test_empty_diff(self):
        valid, errors = validate_diff_syntax("")
        assert valid is False

    def test_missing_hunks(self):
        diff = """diff --git a/f.py b/f.py
--- a/f.py
+++ b/f.py
-old
+new"""
        valid, errors = validate_diff_syntax(diff)
        assert valid is False


class TestValidateDiffFiles:
    def test_allowed_files(self):
        diff = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,1 +1,1 @@
-old
+new"""
        valid, files = validate_diff_files(diff, ["src/app.py"])
        assert valid is True
        assert "src/app.py" in files

    def test_unexpected_files(self):
        diff = """diff --git a/src/secret.py b/src/secret.py
--- a/src/secret.py
+++ b/src/secret.py
@@ -1,1 +1,1 @@
-old
+new"""
        valid, files = validate_diff_files(diff, ["src/app.py"])
        assert valid is False


class TestEstimateConfidence:
    def test_high_similarity(self):
        diff = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
-new
+old"""
        original = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
-old
+new"""
        score = estimate_confidence(diff, original)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should be relatively high for similar diffs

    def test_low_similarity(self):
        diff = """diff --git a/other.py b/other.py
--- a/other.py
+++ b/other.py
@@ -1,3 +1,3 @@
-x
+y"""
        original = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
-old
+new"""
        score = estimate_confidence(diff, original)
        assert 0.0 <= score <= 1.0
