"""Shared pytest fixtures and import paths.

Adds the repo root (for `logoscanner`) and `tools/` (for the standalone helper
scripts) to `sys.path` so tests run without installing the package.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS = REPO_ROOT / "tests" / "assets"

for entry in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))


@pytest.fixture(scope="session")
def dummy_logo_path() -> Path:
    """Path to the committed fake logo, regenerating it if it is missing."""
    path = ASSETS / "dummy_logo.png"
    if not path.is_file():
        import make_dummy_logo

        make_dummy_logo.main(["--out", str(path)])
    return path
