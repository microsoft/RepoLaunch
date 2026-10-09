"""Shared synthetic fixtures for public tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_diff() -> str:
    return """\
diff --git a/src/flask/blueprints.py b/src/flask/blueprints.py
index 1111111..2222222 100644
--- a/src/flask/blueprints.py
+++ b/src/flask/blueprints.py
@@ -1,2 +1,2 @@
-OLD_VALUE = False
+OLD_VALUE = True
 CONTEXT = "synthetic"
"""
