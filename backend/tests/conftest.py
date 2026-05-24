from __future__ import annotations

import pytest

from app.api import proteins
from app.storage import local as storage


@pytest.fixture(autouse=True)
def isolate_storage_and_cache(tmp_path, monkeypatch):
    """Per-test: redirect storage to tmp_path; clear summary cache."""
    test_root = tmp_path / "proteins"
    test_root.mkdir()
    monkeypatch.setattr(storage, "STORAGE_ROOT", test_root)
    proteins._SUMMARY_CACHE.clear()
    yield
    proteins._SUMMARY_CACHE.clear()
