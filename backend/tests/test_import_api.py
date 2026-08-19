"""Round-trip tests for POST /api/proteins/import.

These go through the real clients with respx-mocked upstreams, so the whole
chain — download -> store_upload -> parser.parse -> registry.put -> GET
/api/proteins/{id} — is exercised end to end without touching the network.
"""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from app.main import app
from tests.helpers import load_bytes, load_json, pdb_1crn_bytes

client = TestClient(app)

RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/"
RCSB_ENTITY = "https://data.rcsb.org/rest/v1/core/polymer_entity/"
RCSB_FILES = "https://files.rcsb.org/download/"
AF_PREDICTION = "https://alphafold.ebi.ac.uk/api/prediction/"
AF_FILES = "https://alphafold.ebi.ac.uk/files/"
UNIPROT_ENTRY = "https://rest.uniprot.org/uniprotkb/"


@respx.mock
def test_import_from_rcsb_round_trips_to_the_viewer_endpoints() -> None:
    respx.get(f"{RCSB_FILES}1CRN.cif").mock(
        return_value=httpx.Response(200, content=load_bytes("1CRN.cif"))
    )

    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": "1crn"})
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["source"] == "rcsb"
    assert body["source_id"] == "1crn"
    assert body["file_format"] == "mmcif"
    assert body["residue_count"] == 46
    assert body["has_plddt"] is False
    uid = body["id"]
    assert body["file_url"] == f"/api/proteins/{uid}/file"

    # The registry wiring is the point of this test: both viewer endpoints
    # must resolve for the id the import returned.
    summary = client.get(f"/api/proteins/{uid}")
    assert summary.status_code == 200, summary.text
    assert summary.json()["id"] == uid
    assert summary.json()["source"] == "rcsb"

    stored = client.get(f"/api/proteins/{uid}/file")
    assert stored.status_code == 200
    assert stored.content.startswith(b"data_1CRN")

    analytics = client.get(f"/api/proteins/{uid}/analytics")
    assert analytics.status_code == 200, analytics.text
    assert analytics.json()["residue_count"] == 46


@respx.mock
def test_import_from_alphafold_sets_has_plddt_and_registers() -> None:
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    respx.get(url__startswith=AF_FILES).mock(
        return_value=httpx.Response(200, content=pdb_1crn_bytes())
    )

    r = client.post(
        "/api/proteins/import", json={"source": "alphafold", "source_id": "P69905"}
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["source"] == "alphafold"
    assert body["source_id"] == "P69905"
    assert body["file_format"] == "pdb"
    assert body["has_plddt"] is True

    assert client.get(f"/api/proteins/{body['id']}").status_code == 200
    assert client.get(f"/api/proteins/{body['id']}/file").status_code == 200


@respx.mock
def test_import_from_uniprot_stores_the_alphafold_model() -> None:
    respx.get(f"{UNIPROT_ENTRY}P01308.json").mock(
        return_value=httpx.Response(200, json=load_json("uniprot_entry_P01308.json"))
    )
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    respx.get(url__startswith=AF_FILES).mock(
        return_value=httpx.Response(200, content=pdb_1crn_bytes())
    )

    r = client.post("/api/proteins/import", json={"source": "uniprot", "source_id": "P01308"})
    assert r.status_code == 200, r.text
    body = r.json()

    # UniProt has no coordinates of its own, so the stored structure is the
    # AlphaFold model and the summary is labelled accordingly.
    assert body["source"] == "alphafold"
    assert body["source_id"] == "P01308"
    assert body["has_plddt"] is True
    assert client.get(f"/api/proteins/{body['id']}").status_code == 200


@respx.mock
def test_import_alphafold_without_a_model_returns_404() -> None:
    respx.get(url__startswith=AF_PREDICTION).mock(return_value=httpx.Response(404, json={}))

    r = client.post(
        "/api/proteins/import", json={"source": "alphafold", "source_id": "Q0Q0Q0"}
    )

    assert r.status_code == 404, r.text
    assert "AlphaFold DB has no model for accession 'Q0Q0Q0'." == r.json()["detail"]


@respx.mock
def test_import_alphafold_file_outage_returns_502_not_404() -> None:
    """pdbUrl 503 + obsolete v4 fallback 404 is an outage, not a missing model."""
    respx.get(url__startswith=AF_PREDICTION).mock(
        return_value=httpx.Response(200, json=load_json("alphafold_prediction_P69905.json"))
    )
    respx.get(f"{AF_FILES}AF-P69905-F1-model_v6.pdb").mock(return_value=httpx.Response(503))
    respx.get(f"{AF_FILES}AF-P69905-F1-model_v4.pdb").mock(return_value=httpx.Response(404))

    r = client.post(
        "/api/proteins/import", json={"source": "alphafold", "source_id": "P69905"}
    )

    assert r.status_code == 502, r.text
    assert "ALPHAFOLD" in r.json()["detail"].upper()


@respx.mock
def test_import_rcsb_unknown_entry_returns_404() -> None:
    respx.get(url__startswith=RCSB_FILES).mock(return_value=httpx.Response(404))

    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": "9ZZZ"})

    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "RCSB PDB has no entry '9ZZZ'."


@respx.mock
def test_import_uniprot_entry_without_alphafold_crossref_returns_404() -> None:
    entry = load_json("uniprot_entry_P01308.json")
    entry["uniProtKBCrossReferences"] = [
        ref for ref in entry["uniProtKBCrossReferences"] if ref["database"] != "AlphaFoldDB"
    ]
    respx.get(f"{UNIPROT_ENTRY}P01308.json").mock(return_value=httpx.Response(200, json=entry))

    r = client.post("/api/proteins/import", json={"source": "uniprot", "source_id": "P01308"})

    assert r.status_code == 404, r.text
    assert "no AlphaFold model" in r.json()["detail"]


def test_import_malformed_source_id_returns_404_without_any_http() -> None:
    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": "insulin"})
    assert r.status_code == 404, r.text


@respx.mock
def test_import_unparseable_download_returns_400_and_cleans_up() -> None:
    from app.storage import local as storage

    respx.get(url__startswith=RCSB_FILES).mock(
        return_value=httpx.Response(200, content=b"this is definitely not mmCIF\n")
    )

    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": "1CRN"})

    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "parse" in detail.lower()
    # Nothing leaked from the server, and no orphan file was left behind.
    assert "storage" not in detail.lower()
    assert list(storage.STORAGE_ROOT.iterdir()) == []


@respx.mock
def test_import_upstream_outage_returns_502() -> None:
    respx.get(url__startswith=RCSB_FILES).mock(return_value=httpx.Response(503))

    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": "1CRN"})

    assert r.status_code == 502, r.text
    assert "RCSB" in r.json()["detail"]


def test_import_rejects_unknown_source() -> None:
    r = client.post("/api/proteins/import", json={"source": "pdbe", "source_id": "1CRN"})
    assert r.status_code == 422


def test_import_rejects_blank_source_id() -> None:
    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": ""})
    assert r.status_code == 422


@respx.mock
def test_import_from_rcsb_carries_the_organism_into_the_summary() -> None:
    """The whole point of the mmCIF organism fallback, end to end.

    RCSB serves mmCIF, and BioPython's mmCIF header has no source category, so
    before the fallback this field was None on every single RCSB import — the
    viewer showed "Organism: Unknown" seconds after the search card had shown
    the organism correctly.
    """
    respx.get(f"{RCSB_FILES}1CRN.cif").mock(
        return_value=httpx.Response(200, content=load_bytes("1CRN_header.cif"))
    )

    r = client.post("/api/proteins/import", json={"source": "rcsb", "source_id": "1CRN"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["file_format"] == "mmcif"
    assert body["organism"] is not None, "RCSB mmCIF import lost the organism"
    assert "CRAMBE" in body["organism"].upper()
