"""Shared pytest fixtures and import paths.

Adds the repo root (for `logoscanner`) and `tools/` (for the standalone helper
scripts) to `sys.path` so tests run without installing the package.
"""

from __future__ import annotations

import shutil
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


@pytest.fixture(scope="session")
def fake_logo_dir(tmp_path_factory, dummy_logo_path) -> Path:
    """A `logo/`-shaped folder holding only the fake mark (phase03 SIFT)."""
    folder = tmp_path_factory.mktemp("fake_logo")
    shutil.copy(dummy_logo_path, folder / dummy_logo_path.name)
    return folder


@pytest.fixture(scope="session")
def _empty_logo_dir(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("no_logo")


@pytest.fixture(autouse=True)
def isolate_logo_dir(monkeypatch, _empty_logo_dir):
    """Privacy guard: no test ever reads the real `logo/`.

    `config.LOGO_DIR` points at an empty folder by default, so the SIFT signal
    is inert unless a test opts in with `fake_logo_dir`.
    """
    from logoscanner import config

    monkeypatch.setattr(config, "LOGO_DIR", str(_empty_logo_dir))
