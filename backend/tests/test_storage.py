"""Pins the single-source-of-truth constants `app.storage.local` now exports.

Before this, the 50 MB ceiling was a literal duplicated in both
`api/proteins.py` and `api/import_.py`, and `_ALLOWED_EXTS` existed twice with
different members (client-facing upload extensions vs. what's actually
written to disk) under the same private name — easy to edit one and miss the
other. Both routers now derive from `storage.local`; these tests pin that the
derivation is real, not just present.
"""

from __future__ import annotations

import pytest

from app.api import import_, proteins
from app.storage import local as storage


def test_max_structure_bytes_is_the_single_ceiling_both_routers_use() -> None:
    assert storage.MAX_STRUCTURE_BYTES == 50 * 1024 * 1024
    # Neither router defines its own ceiling anymore — both read this one.
    assert not hasattr(proteins, "MAX_UPLOAD_BYTES")
    assert not hasattr(import_, "MAX_IMPORT_BYTES")


def test_allowed_upload_exts_is_derived_from_stored_exts_and_aliases() -> None:
    assert storage.ALLOWED_UPLOAD_EXTS == {"pdb", "cif", "mmcif"}
    # Every alias must normalize to something actually in STORED_EXTS, or a
    # client-accepted extension could pass validation and then fail to store.
    for alias, target in storage._EXT_ALIASES.items():
        assert alias in storage.ALLOWED_UPLOAD_EXTS
        assert target in storage.STORED_EXTS


def test_store_upload_normalizes_mmcif_alias_to_the_stored_cif_extension() -> None:
    _uid, path = storage.store_upload(b"data_x\n#\n", "mmcif")
    try:
        assert path.suffix == ".cif"
    finally:
        path.unlink(missing_ok=True)


def test_store_upload_rejects_an_extension_outside_the_stored_set() -> None:
    with pytest.raises(ValueError):
        storage.store_upload(b"whatever", "txt")
