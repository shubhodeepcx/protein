"""A1 — pLDDT bands, low-confidence regions, PAE binning, and the endpoint.

Every upstream call is mocked with respx against fixtures recorded live from
`alphafold.ebi.ac.uk` on 2026-08-24 for **AF-P01308-F1** (human insulin, 110
residues): the prediction payload, the 110x110 PAE document (35 KB), and the
PDB model whose B-factor column holds the per-residue pLDDT. Nothing here may
reach the network; `@respx.mock` defaults to `assert_all_mocked=True` and fails
the test if it tries.

Two directions are load-bearing in this feature and both are pinned here:

* **pLDDT is a confidence** — high is good, and the band edges are AlphaFold's
  (>90 / 70-90 / 50-70 / <50). `test_bands_match_alphafolds_own_fractions`
  cross-checks the four counts against the `fractionPlddt*` numbers AlphaFold
  publishes in its own prediction payload, so the thresholds are validated
  against upstream rather than against our own arithmetic.
* **PAE is an error** — low is good. The two must never be conflated, and
  `test_pae_diagonal_is_zero_error` states the fact that makes the direction
  checkable: a residue is perfectly aligned with itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.models.protein import ChainInfo, ProteinSummary
from app.services import confidence, registry
from app.services.alphafold import MAX_PAE_DOC_BYTES, AlphaFoldClient
from app.services.external import SourceNotFoundError, SourceUnavailableError
from app.storage import local as storage
from tests.helpers import FIXTURES, load_json

client = TestClient(app)

PREDICTION = "https://alphafold.ebi.ac.uk/api/prediction/"
PAE_URL = (
    "https://alphafold.ebi.ac.uk/files/AF-P01308-F1-predicted_aligned_error_v6.json"
)

UID = "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"


def prediction_payload() -> list[dict]:
    return load_json("alphafold_prediction_P01308.json")


def pae_payload() -> list[dict]:
    return load_json("alphafold_pae_P01308.json")


def af_model_bytes() -> bytes:
    return (FIXTURES / "AF-P01308-F1.pdb").read_bytes()


def register(
    *,
    source: str = "alphafold",
    source_id: str | None = "P01308",
    has_plddt: bool = True,
    store_file: bool = True,
    residue_count: int = 110,
) -> ProteinSummary:
    """Register an AlphaFold summary and (optionally) drop its model on disk."""
    if store_file:
        (storage.STORAGE_ROOT / f"{UID}.pdb").write_bytes(af_model_bytes())
    summary = ProteinSummary.model_validate(
        {
            "id": UID,
            "source": source,
            "source_id": source_id,
            "name": "Insulin",
            "organism": "Homo sapiens",
            "file_url": f"/api/proteins/{UID}/file",
            "file_format": "pdb",
            "chains": [
                ChainInfo(
                    id=f"{UID}:A",
                    label="A",
                    sequence="M" * residue_count,
                    residue_count=residue_count,
                )
            ],
            "residue_count": residue_count,
            "atom_count": 839,
            "molecular_weight": 12000.0,
            "has_plddt": has_plddt,
            "warnings": [],
        }
    )
    registry.put(UID, summary)
    return summary


def structure_chains() -> list[tuple[str, list[float]]]:
    """Per-residue pLDDT straight out of the recorded AlphaFold model."""
    from app.api.proteins import parse_structure_for_analytics

    path = FIXTURES / "AF-P01308-F1.pdb"
    return confidence.extract_plddt(parse_structure_for_analytics(path))


# --------------------------------------------------------------- band edges


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (100.0, "very_high"),
        (90.1, "very_high"),
        (90.0, "very_high"),  # the edge belongs to the band above
        (89.9, "confident"),
        (70.0, "confident"),
        (69.9, "low"),
        (50.0, "low"),
        (49.9, "very_low"),
        (0.0, "very_low"),
    ],
)
def test_band_for_uses_alphafolds_thresholds(value: float, expected: str) -> None:
    assert confidence.band_for(value) == expected


def test_band_edges_are_ordered_high_is_confident() -> None:
    """pLDDT is a confidence, so the bands must ascend with quality.

    Inverting these produces a table that is internally consistent and
    completely wrong — the same class of bug the pLDDT colour domain shipped
    once. Assert the ordering, not just the values.
    """
    assert confidence.VERY_HIGH_MIN > confidence.CONFIDENT_MIN > confidence.LOW_MIN
    assert confidence.LOW_CONFIDENCE_THRESHOLD == confidence.CONFIDENT_MIN


def test_bands_are_exhaustive_and_disjoint() -> None:
    """Every value 0-100 lands in exactly one band, so the counts always sum."""
    values = [i / 10 for i in range(0, 1001)]
    bands = confidence.summarise_bands(values)
    assert [b.key for b in bands] == ["very_high", "confident", "low", "very_low"]
    assert sum(b.residue_count for b in bands) == len(values)
    assert sum(b.fraction for b in bands) == pytest.approx(1.0)


def test_summarise_bands_keeps_empty_bands() -> None:
    """An absent band still gets a row: zero is a finding, absence is not."""
    bands = confidence.summarise_bands([95.0, 96.0])
    assert len(bands) == 4
    very_low = next(b for b in bands if b.key == "very_low")
    assert very_low.residue_count == 0
    assert very_low.label == "Very low"


def test_bands_match_alphafolds_own_fractions() -> None:
    """Cross-check our thresholds against AlphaFold's published fractions.

    The recorded prediction payload for P01308 carries
    `fractionPlddtVeryLow/Low/Confident/VeryHigh`. Computing the same four
    fractions from the model file's B-factor column must reproduce them. If a
    threshold here drifts from AlphaFold's convention, this fails — which is
    the whole point: it validates against upstream, not against us.
    """
    entry = prediction_payload()[0]
    chains = structure_chains()
    values = [v for _, chain_values in chains for v in chain_values]
    bands = {b.key: b.fraction for b in confidence.summarise_bands(values)}

    assert bands["very_low"] == pytest.approx(entry["fractionPlddtVeryLow"], abs=5e-4)
    assert bands["low"] == pytest.approx(entry["fractionPlddtLow"], abs=5e-4)
    assert bands["confident"] == pytest.approx(
        entry["fractionPlddtConfident"], abs=5e-4
    )
    assert bands["very_high"] == pytest.approx(
        entry["fractionPlddtVeryHigh"], abs=5e-4
    )


def test_mean_plddt_matches_alphafolds_global_metric() -> None:
    """The mean we compute from the file must match AlphaFold's own headline."""
    entry = prediction_payload()[0]
    values = [v for _, cv in structure_chains() for v in cv]
    assert sum(values) / len(values) == pytest.approx(
        entry["globalMetricValue"], abs=0.05
    )


# ------------------------------------------------------------ pLDDT extraction


def test_extract_plddt_reads_the_real_model() -> None:
    chains = structure_chains()
    assert [(label, len(values)) for label, values in chains] == [("A", 110)]
    # AlphaFold writes one pLDDT per residue onto every atom, so the first
    # residue's value is exactly what the file says.
    assert chains[0][1][0] == pytest.approx(64.44)
    assert min(chains[0][1]) == pytest.approx(37.66)
    assert max(chains[0][1]) == pytest.approx(85.56)


# ---------------------------------------------------------------- regions


def test_low_confidence_regions_finds_contiguous_runs() -> None:
    chains = [("A", [95.0, 92.0, 60.0, 55.0, 40.0, 88.0, 30.0])]
    regions = confidence.low_confidence_regions(chains)
    assert [(r.start, r.end, r.length) for r in regions] == [(3, 5, 3), (7, 7, 1)]
    assert regions[0].min_plddt == pytest.approx(40.0)
    assert regions[0].band == "very_low"
    assert regions[0].likely_disordered is True
    assert regions[1].length == 1


def test_a_run_that_never_dips_below_fifty_is_low_not_disordered() -> None:
    """<50 is a *different claim* from <70 and must not be conflated."""
    regions = confidence.low_confidence_regions([("A", [95.0, 65.0, 62.0, 95.0])])
    assert len(regions) == 1
    assert regions[0].band == "low"
    assert regions[0].likely_disordered is False
    assert "caution" in regions[0].label
    assert "disordered" not in regions[0].label


def test_region_runs_to_the_end_of_the_chain() -> None:
    """A run touching the last residue must still be emitted."""
    regions = confidence.low_confidence_regions([("A", [95.0, 40.0, 41.0])])
    assert [(r.start, r.end) for r in regions] == [(2, 3)]


def test_regions_do_not_span_chains() -> None:
    """Two chains each ending/starting low are two regions, not one."""
    regions = confidence.low_confidence_regions([("A", [40.0]), ("B", [41.0])])
    assert [(r.chain_id, r.start, r.end) for r in regions] == [("A", 1, 1), ("B", 1, 1)]


def test_a_fully_confident_chain_has_no_regions() -> None:
    assert confidence.low_confidence_regions([("A", [95.0, 91.0, 80.0])]) == []


def test_region_labels_are_readable_without_colour() -> None:
    """The warning must be legible as text — colour alone is not the message."""
    regions = confidence.low_confidence_regions([("A", [95.0, 30.0, 31.0])])
    label = regions[0].label
    assert "Chain A" in label
    assert "residues 2-3" in label
    assert "pLDDT" in label
    assert "disordered" in label


def test_regions_are_not_truncated() -> None:
    """A pathological alternating model yields many regions and reports them all.

    A cap here would silently drop findings from exactly the disordered
    proteins this analysis exists for.
    """
    values = [30.0 if i % 2 == 0 else 95.0 for i in range(400)]
    regions = confidence.low_confidence_regions([("A", values)])
    assert len(regions) == 200


def test_real_model_regions() -> None:
    """The recorded insulin model: a disordered C-terminal 95-residue tail."""
    regions = confidence.low_confidence_regions(structure_chains())
    assert [(r.start, r.end, r.length) for r in regions] == [(1, 1, 1), (16, 110, 95)]
    assert regions[1].likely_disordered is True


# ------------------------------------------------------------- PAE binning


def test_full_resolution_when_the_matrix_already_fits() -> None:
    matrix = [[float(i + j) for j in range(10)] for i in range(10)]
    binned, bin_size = confidence.downsample_pae(matrix, max_cells=16_384)
    assert bin_size == 1
    assert binned == matrix


def test_binning_respects_the_cell_budget() -> None:
    """The guard is on cells. Any N must come back within budget."""
    for residue_count in (1, 2, 128, 129, 500, 1_273, 2_700, 10_000):
        bin_size = confidence.bin_size_for(residue_count, max_cells=16_384)
        size = -(-residue_count // bin_size)  # ceil
        assert size * size <= 16_384, (residue_count, bin_size, size)


def test_binning_averages_and_keeps_the_ragged_last_block() -> None:
    """N not a multiple of bin_size must not drop the tail."""
    matrix = [[1.0, 1.0, 5.0], [1.0, 1.0, 5.0], [9.0, 9.0, 100.0]]
    binned, bin_size = confidence.downsample_pae(matrix, max_cells=4)
    assert bin_size == 2
    assert len(binned) == 2
    # Top-left is the mean of the four 1.0s; bottom-right is the lone 100.0,
    # averaged over the one residue pair it actually covers.
    assert binned[0][0] == pytest.approx(1.0)
    assert binned[1][1] == pytest.approx(100.0)
    assert binned[0][1] == pytest.approx(5.0)
    assert binned[1][0] == pytest.approx(9.0)


def test_binning_is_a_mean_not_a_max() -> None:
    """A single bad pair must not repaint its whole block."""
    matrix = [[0.0, 0.0], [0.0, 20.0]]
    binned, _ = confidence.downsample_pae(matrix, max_cells=1)
    assert binned == [[5.0]]


def test_build_pae_matrix_declares_its_resolution() -> None:
    matrix = [[float((i * j) % 30) for j in range(300)] for i in range(300)]
    built = confidence.build_pae_matrix(matrix, max_error=31.75, max_cells=16_384)
    assert built.available is True
    assert built.residue_count == 300
    assert built.downsampled is True
    assert built.bin_size == 3
    assert built.size == 100
    assert built.aggregation == "mean"
    # The label must name the binning in words — an undeclared downsample is a
    # lie about the data.
    assert "Binned 3x" in built.resolution_label
    assert "300 residues" in built.resolution_label
    assert "100 x 100" in built.resolution_label


def test_full_resolution_label_says_so() -> None:
    built = confidence.build_pae_matrix([[0.0, 1.0], [1.0, 0.0]], max_error=5.0)
    assert built.downsampled is False
    assert built.bin_size == 1
    assert built.aggregation == "none"
    assert "Full resolution" in built.resolution_label


def test_pae_diagonal_is_zero_error() -> None:
    """A residue is perfectly aligned with itself — this fixes the direction.

    If PAE were ever read as a confidence, the diagonal would be the *maximum*.
    Its being zero is what makes 'low is good' checkable from the data itself.
    """
    matrix = pae_payload()[0]["predicted_aligned_error"]
    assert all(matrix[i][i] == 0 for i in range(len(matrix)))


def test_recorded_pae_is_square_and_matches_the_model_length() -> None:
    matrix = pae_payload()[0]["predicted_aligned_error"]
    assert len(matrix) == 110
    assert all(len(row) == 110 for row in matrix)
    assert len(matrix) == prediction_payload()[0]["uniprotEnd"]


def test_unavailable_pae_carries_a_reason_and_no_values() -> None:
    empty = confidence.unavailable_pae("nope")
    assert empty.available is False
    assert empty.unavailable_reason == "nope"
    assert empty.values == []


# ----------------------------------------------------------------- client


@respx.mock
@pytest.mark.asyncio
async def test_fetch_pae_uses_the_url_from_the_payload() -> None:
    """The PAE URL is read off `paeDocUrl`, never guessed from a template."""
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    route = respx.get(PAE_URL).mock(
        return_value=httpx.Response(200, json=pae_payload())
    )

    document = await AlphaFoldClient().fetch_pae("P01308")

    assert route.called
    assert document.size == 110
    assert document.max_error == pytest.approx(31.75)
    assert document.source_url == PAE_URL


@respx.mock
@pytest.mark.asyncio
async def test_fetch_pae_raises_not_found_when_the_payload_has_no_pae_url() -> None:
    entry = dict(prediction_payload()[0])
    entry.pop("paeDocUrl")
    respx.get(f"{PREDICTION}P01308").mock(return_value=httpx.Response(200, json=[entry]))

    with pytest.raises(SourceNotFoundError):
        await AlphaFoldClient().fetch_pae("P01308")


@respx.mock
@pytest.mark.asyncio
async def test_fetch_pae_404_is_not_found() -> None:
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx.get(PAE_URL).mock(return_value=httpx.Response(404))

    with pytest.raises(SourceNotFoundError):
        await AlphaFoldClient().fetch_pae("P01308")


@respx.mock
@pytest.mark.asyncio
async def test_fetch_pae_5xx_is_unavailable() -> None:
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx.get(PAE_URL).mock(return_value=httpx.Response(503))

    with pytest.raises(SourceUnavailableError):
        await AlphaFoldClient().fetch_pae("P01308")


@respx.mock
@pytest.mark.asyncio
async def test_fetch_pae_rejects_a_ragged_matrix() -> None:
    """A non-square document means we misread the format. Guessing would ship a
    heatmap whose axes do not mean what the legend says."""
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx.get(PAE_URL).mock(
        return_value=httpx.Response(
            200,
            json=[{"predicted_aligned_error": [[0, 1, 2], [0, 1]],
                   "max_predicted_aligned_error": 5}],
        )
    )

    with pytest.raises(SourceUnavailableError, match="square"):
        await AlphaFoldClient().fetch_pae("P01308")


@respx.mock
@pytest.mark.asyncio
async def test_fetch_pae_rejects_a_document_over_the_byte_budget(monkeypatch) -> None:
    """The budget is checked against decoded bytes as they stream in.

    Bounded here by a patched budget rather than a 48 MB body, so the test
    costs nothing — but it exercises the same streaming check.
    """
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx.get(PAE_URL).mock(return_value=httpx.Response(200, json=pae_payload()))

    monkeypatch.setattr("app.services.alphafold.MAX_PAE_DOC_BYTES", 1024)
    with pytest.raises(SourceUnavailableError, match="budget"):
        await AlphaFoldClient().fetch_pae("P01308")


def test_the_byte_budget_admits_the_largest_alphafold_fragment() -> None:
    """2,700 residues is AlphaFold's fragment limit; a 1,273-residue entry was
    measured at 9.4 MB, so the ceiling extrapolates to about 42 MB."""
    measured_bytes_per_cell = 9_399_636 / (1_273 * 1_273)
    largest = measured_bytes_per_cell * 2_700 * 2_700
    assert largest < MAX_PAE_DOC_BYTES


@respx.mock
@pytest.mark.asyncio
async def test_pae_matrix_for_degrades_instead_of_raising() -> None:
    """An upstream failure becomes a reason, never an exception or a zero grid."""
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx.get(PAE_URL).mock(return_value=httpx.Response(500))

    matrix = await confidence.pae_matrix_for("P01308", AlphaFoldClient())
    assert matrix.available is False
    assert matrix.values == []
    assert "P01308" in matrix.unavailable_reason


@respx.mock
@pytest.mark.asyncio
async def test_pae_matrix_is_cached() -> None:
    """The binned matrix is cached, so a second view costs no upstream call."""
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    route = respx.get(PAE_URL).mock(
        return_value=httpx.Response(200, json=pae_payload())
    )

    af = AlphaFoldClient()
    first = await confidence.pae_matrix_for("P01308", af)
    second = await confidence.pae_matrix_for("P01308", af)

    assert route.call_count == 1
    assert first.size == second.size == 110


# ---------------------------------------------------------------- endpoint


@respx.mock
def test_confidence_endpoint_returns_bands_regions_and_pae() -> None:
    register()
    respx.get(f"{PREDICTION}P01308").mock(
        return_value=httpx.Response(200, json=prediction_payload())
    )
    respx.get(PAE_URL).mock(return_value=httpx.Response(200, json=pae_payload()))

    response = client.get(f"/api/proteins/{UID}/confidence")
    assert response.status_code == 200
    body = response.json()

    assert body["has_plddt"] is True
    assert body["accession"] == "P01308"
    assert body["residue_count"] == 110
    assert body["mean_plddt"] == pytest.approx(52.91, abs=0.05)
    assert body["low_confidence_threshold"] == 70.0
    assert [b["key"] for b in body["bands"]] == [
        "very_high",
        "confident",
        "low",
        "very_low",
    ]
    assert body["low_confidence_residue_count"] == 96
    assert [(r["start"], r["end"]) for r in body["low_confidence_regions"]] == [
        (1, 1),
        (16, 110),
    ]
    assert body["pae"]["available"] is True
    assert body["pae"]["size"] == 110
    assert body["pae"]["bin_size"] == 1
    assert body["pae"]["max_error"] == pytest.approx(31.75)
    assert len(body["pae"]["values"]) == 110
    assert body["warnings"] == []


def test_experimental_structure_is_not_applicable_not_an_error() -> None:
    """No pLDDT, no PAE, 200, and a sentence saying why. Never a zeroed grid."""
    register(source="rcsb", source_id="1CRN", has_plddt=False)

    response = client.get(f"/api/proteins/{UID}/confidence")
    assert response.status_code == 200
    body = response.json()

    assert body["has_plddt"] is False
    assert body["bands"] == []
    assert body["low_confidence_regions"] == []
    assert body["mean_plddt"] is None
    assert body["pae"]["available"] is False
    assert body["pae"]["values"] == []
    assert "experimental" in body["note"].lower()
    assert "temperature factor" in body["note"].lower()
    assert body["pae"]["unavailable_reason"]


def test_uploaded_alphafold_model_gets_plddt_but_no_pae() -> None:
    """An upload has pLDDT in the file but no accession to fetch PAE with.

    The bands and regions must still be computed — the analysis does not depend
    on AlphaFold DB — and the PAE block must say exactly why it is empty.
    """
    register(source="uploaded", source_id=None, has_plddt=True)

    response = client.get(f"/api/proteins/{UID}/confidence")
    assert response.status_code == 200
    body = response.json()

    assert body["has_plddt"] is True
    assert body["accession"] is None
    assert body["residue_count"] == 110
    assert len(body["low_confidence_regions"]) == 2
    assert body["pae"]["available"] is False
    assert "uploaded directly" in body["pae"]["unavailable_reason"]


@respx.mock
def test_endpoint_survives_an_alphafold_outage() -> None:
    """PAE is a supplement. An outage must not cost the user the pLDDT analysis."""
    register()
    respx.get(f"{PREDICTION}P01308").mock(return_value=httpx.Response(503))

    response = client.get(f"/api/proteins/{UID}/confidence")
    assert response.status_code == 200
    body = response.json()

    assert body["has_plddt"] is True
    assert len(body["bands"]) == 4
    assert body["pae"]["available"] is False
    assert body["pae"]["unavailable_reason"]


def test_unknown_protein_is_404() -> None:
    assert client.get("/api/proteins/" + "0" * 32 + "/confidence").status_code == 404


def test_malformed_uid_is_404() -> None:
    assert client.get("/api/proteins/not-a-uid/confidence").status_code == 404


def test_missing_file_is_404() -> None:
    register(store_file=False)
    assert client.get(f"/api/proteins/{UID}/confidence").status_code == 404


def test_residue_count_mismatch_is_warned_not_hidden() -> None:
    """If the pLDDT walk and the parser's walk disagree, every residue range is
    offset. Say so rather than shipping ranges that do not line up."""
    register(residue_count=99)

    summary = registry.get(UID)
    assert summary is not None
    built = confidence.build_confidence(
        UID, summary, structure_chains(), confidence.unavailable_pae("n/a")
    )
    assert built.warnings
    assert "offset" in built.warnings[0]


def test_a_model_with_no_scored_residues_is_not_applicable() -> None:
    """`has_plddt` true but nothing scored is still an absence, not a zero."""
    register()
    summary = registry.get(UID)
    assert summary is not None
    built = confidence.build_confidence(UID, summary, [], confidence.unavailable_pae("x"))
    assert built.has_plddt is False
    assert built.bands == []
    assert built.note


def test_recorded_pae_fixture_is_the_real_thing() -> None:
    """Guard against the fixture being replaced by a hand-written stub."""
    raw = json.loads((FIXTURES / "alphafold_pae_P01308.json").read_text())
    assert isinstance(raw, list) and len(raw) == 1
    assert set(raw[0]) == {"predicted_aligned_error", "max_predicted_aligned_error"}
    assert Path(FIXTURES / "AF-P01308-F1.pdb").read_text().startswith("HEADER")
