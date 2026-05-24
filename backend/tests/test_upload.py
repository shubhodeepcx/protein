from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PDB_PATH = Path(__file__).resolve().parents[1] / "app" / "static" / "1CRN.pdb"


def test_upload_pdb_returns_summary() -> None:
    with PDB_PATH.open("rb") as f:
        r = client.post(
            "/api/proteins/upload",
            files={"file": ("test.pdb", f, "chemical/x-pdb")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "uploaded"
    assert body["file_format"] == "pdb"
    assert body["residue_count"] > 40
    assert body["file_url"].endswith("/file")
    uid = body["id"]

    # GET the cached summary back
    r2 = client.get(f"/api/proteins/{uid}")
    assert r2.status_code == 200
    assert r2.json()["id"] == uid

    # GET the stored file
    r3 = client.get(f"/api/proteins/{uid}/file")
    assert r3.status_code == 200
    assert len(r3.content) > 1000


def test_upload_rejects_empty_file() -> None:
    r = client.post(
        "/api/proteins/upload",
        files={"file": ("empty.pdb", b"", "chemical/x-pdb")},
    )
    assert r.status_code == 400


def test_upload_rejects_unknown_extension() -> None:
    r = client.post(
        "/api/proteins/upload",
        files={"file": ("test.txt", b"some content", "text/plain")},
    )
    assert r.status_code == 400


def test_upload_garbage_pdb_returns_empty_structure() -> None:
    """BioPython parses garbage PDB as an empty structure rather than erroring."""
    r = client.post(
        "/api/proteins/upload",
        files={"file": ("garbage.pdb", b"this is not a pdb file", "chemical/x-pdb")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["residue_count"] == 0
    assert body["atom_count"] == 0
    assert body["source"] == "uploaded"


def test_get_missing_protein_returns_404() -> None:
    r = client.get("/api/proteins/does-not-exist")
    assert r.status_code == 404


def test_get_missing_protein_file_returns_404() -> None:
    r = client.get("/api/proteins/does-not-exist/file")
    assert r.status_code == 404
