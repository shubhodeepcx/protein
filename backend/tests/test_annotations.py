"""P6 — the UniProt annotation field set, its projection, and the endpoint.

Every upstream call is mocked with respx against recorded fixtures. Nothing in
this file may reach the network; `@respx.mock` fails the test if it tries.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import app
from app.models.protein import ChainInfo, ProteinSummary
from app.services import annotations as annotations_service
from app.services import registry
from app.services.external import SourceNotFoundError
from app.services.rcsb import _uniprot_accession
from app.services.uniprot import ANNOTATION_FIELDS, UniProtClient
from tests.helpers import load_json

client = TestClient(app)

UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_ENTRY = "https://rest.uniprot.org/uniprotkb/"
RCSB_ENTRY = "https://data.rcsb.org/rest/v1/core/entry/"
RCSB_ENTITY = "https://data.rcsb.org/rest/v1/core/polymer_entity/"

# Storage uids are `uuid4().hex` — 32 lowercase hex characters, no dashes.
UID = "1111111111114111811111111111aaaa"


def register(**overrides: object) -> ProteinSummary:
    """Put a summary in the registry so the endpoint can find it."""
    fields: dict[str, object] = {
        "id": UID,
        "source": "uploaded",
        "source_id": None,
        "name": "Test protein",
        "organism": None,
        "file_url": f"/api/proteins/{UID}/file",
        "file_format": "pdb",
        "chains": [ChainInfo(id=f"{UID}:A", label="A", sequence="TTCC", residue_count=4)],
        "residue_count": 4,
        "atom_count": 30,
        "molecular_weight": 400.0,
        "has_plddt": False,
        "warnings": [],
    }
    fields.update(overrides)
    summary = ProteinSummary.model_validate(fields)
    registry.put(UID, summary)
    return summary


def insulin() -> dict:
    return load_json("uniprot_annotations_P01308.json")


def egfr() -> dict:
    return load_json("uniprot_annotations_P00533.json")


def build(entry: dict, accession: str = "P01308"):
    return annotations_service.build_annotations(
        UID, entry, accession=accession, note="test"
    )


# ------------------------------------------------------- the field set itself


def test_annotation_fields_cover_every_category_the_client_asked_for() -> None:
    """Pins the verified field names.

    Checked against UniProt's own result-fields column enum. If someone
    "tidies" a name into one UniProt does not publish, the request 400s in
    production and every section renders empty — exactly the complaint P6
    exists to fix — so the names are pinned here rather than trusted.
    """
    fields = ANNOTATION_FIELDS.split(",")

    for field in (
        "gene_names",
        "cc_function",
        "cc_catalytic_activity",
        "go_p",
        "go_c",
        "go_f",
        "keyword",
        "cc_subcellular_location",
        "ft_transmem",
        "ft_topo_dom",
        "cc_disease",
        "cc_ptm",
        "ft_mod_res",
        "ft_signal",
        "ft_chain",
        "ft_disulfid",
        "xref_proteomes",
        "xref_reactome",
        "xref_biocyc",
        "xref_signor",
        "organism_name",
        "lineage",
    ):
        assert field in fields, f"{field} dropped from ANNOTATION_FIELDS"

    # UniRef is a separate dataset with its own endpoint, NOT a UniProtKB
    # cross-reference field. Asking for it makes the entry request a 400 and
    # takes every other section down with it.
    assert "xref_uniref" not in fields
    assert len(fields) == len(set(fields)), "duplicate field name"


# ------------------------------------------------------------ the projection


def test_insulin_names_gene_and_origin() -> None:
    result = build(insulin())

    assert result.accession == "P01308"
    assert result.accession_resolved is True
    assert result.entry_name == "INS_HUMAN"
    assert result.protein_name == "Insulin"
    assert result.gene_names == ["INS"]
    assert result.organism == "Homo sapiens"
    assert result.taxon_id == 9606
    assert result.lineage[0] == "Eukaryota"
    assert result.lineage[-1] == "Homo"


def test_function_comment_is_not_truncated_the_way_search_cards_are() -> None:
    result = build(insulin())

    assert len(result.function) == 1
    assert result.function[0].startswith("Insulin decreases blood glucose")
    # The search card trims at 320 chars and appends an ellipsis; the panel has
    # room for the whole comment and must not inherit that trim.
    assert not result.function[0].endswith("…")


def test_gene_ontology_is_split_into_the_three_aspects() -> None:
    result = build(insulin()).gene_ontology

    assert [t.id for t in result.cellular_component] == ["GO:0005615", "GO:0030141"]
    assert [t.id for t in result.molecular_function] == ["GO:0005179", "GO:0005158"]
    assert [t.id for t in result.biological_process] == ["GO:0008286", "GO:0006006"]
    # The aspect prefix is UniProt's encoding, not part of the term label.
    assert result.cellular_component[0].term == "extracellular space"
    # "IDA:UniProtKB" — the evidence code is the part before the source.
    assert result.cellular_component[0].evidence == "IDA"


def test_keywords_keep_their_uniprot_category() -> None:
    keywords = build(insulin()).keywords

    assert [k.name for k in keywords][:2] == [
        "Cleavage on pair of basic residues",
        "Diabetes mellitus",
    ]
    assert keywords[0].id == "KW-0165"
    assert {k.category for k in keywords} >= {"PTM", "Disease", "Molecular function"}


def test_subcellular_location_and_its_note() -> None:
    result = build(insulin())

    assert [loc.location for loc in result.subcellular_locations] == ["Secreted"]
    assert result.subcellular_locations[0].topology is None
    assert len(result.subcellular_location_notes) == 1
    assert "secretory granules" in result.subcellular_location_notes[0]


def test_diseases_carry_acronym_and_omim_id() -> None:
    diseases = build(insulin()).diseases

    assert [d.acronym for d in diseases] == ["IDDM2", "MODY10", "HPRI"]
    assert diseases[0].name == "Diabetes mellitus, insulin-dependent, 2"
    assert diseases[0].mim_id == "125852"
    assert diseases[0].description is not None


def test_ptm_features_carry_their_positions() -> None:
    features = build(insulin()).ptm_features

    assert [(f.type, f.start, f.end) for f in features] == [
        ("Signal", 1, 24),
        ("Chain", 25, 54),
        ("Chain", 90, 110),
        ("Disulfide bond", 31, 96),
        ("Disulfide bond", 43, 109),
        ("Disulfide bond", 95, 100),
    ]
    assert features[1].description == "Insulin B chain"


def test_cross_references_resolve_to_outbound_urls() -> None:
    refs = build(insulin()).cross_references

    assert [(r.database, r.id) for r in refs] == [
        ("Reactome", "R-HSA-264876"),
        ("Reactome", "R-HSA-74749"),
        ("SIGNOR", "P01308"),
        ("Proteomes", "UP000005640"),
    ]
    by_id = {r.id: r for r in refs}
    assert by_id["R-HSA-264876"].url == "https://reactome.org/content/detail/R-HSA-264876"
    assert by_id["R-HSA-264876"].description == "Insulin processing"
    assert by_id["UP000005640"].url == "https://www.uniprot.org/proteomes/UP000005640"
    assert by_id["UP000005640"].description == "Chromosome 11"
    # UniProt writes an absent property value as "-"; that is noise, not a label.
    assert by_id["P01308"].description is None
    # AlphaFoldDB and PDB are cross-references too, but not pathway/network
    # ones — the panel would be a link dump if every database landed here.
    assert {r.database for r in refs}.isdisjoint({"AlphaFoldDB", "PDB", "GO"})


def test_insulin_has_no_catalytic_activity_or_transmembrane_section() -> None:
    """The hide-empty-sections rule, pinned at the source.

    Insulin is not an enzyme and not a membrane protein. If these came back
    non-empty the panel would render two headings over nothing — which is the
    "looks a bit empty" complaint this phase exists to fix.
    """
    result = build(insulin())

    assert result.catalytic_activity == []
    assert result.transmembrane == []
    assert result.ptm == []


def test_catalytic_activity_carries_reaction_ec_rhea_and_chebi() -> None:
    activities = build(egfr(), accession="P00533").catalytic_activity

    assert len(activities) == 1
    activity = activities[0]
    assert activity.reaction is not None and activity.reaction.startswith("L-tyrosyl-[protein]")
    assert activity.ec_number == "2.7.10.1"
    assert activity.rhea_ids == ["RHEA:10596"]
    assert activity.chebi_ids == ["CHEBI:30616", "CHEBI:46858", "CHEBI:456216"]


def test_transmembrane_section_keeps_spans_and_topological_domains_in_order() -> None:
    features = build(egfr(), accession="P00533").transmembrane

    assert [(f.type, f.start, f.end, f.description) for f in features] == [
        ("Topological domain", 25, 645, "Extracellular"),
        ("Transmembrane", 646, 668, "Helical"),
        ("Topological domain", 669, 1210, "Cytoplasmic"),
    ]


def test_egfr_gene_synonyms_follow_the_primary_name() -> None:
    assert build(egfr(), accession="P00533").gene_names == [
        "EGFR",
        "ERBB",
        "ERBB1",
        "HER1",
    ]


def test_ptm_comment_and_modified_residues_are_separate_fields() -> None:
    result = build(egfr(), accession="P00533")

    assert len(result.ptm) == 1
    assert "autophosphorylation" in result.ptm[0]
    assert [(f.type, f.start) for f in result.ptm_features if f.type == "Modified residue"] == [
        ("Modified residue", 1068),
        ("Modified residue", 1172),
    ]


def test_biocyc_identifier_is_percent_encoded_into_its_url() -> None:
    """BioCyc ids embed a colon; pasted raw it would break the query string."""
    refs = {r.database: r for r in build(egfr(), accession="P00533").cross_references}

    assert refs["BioCyc"].id == "MetaCyc:HS08109-MONOMER"
    assert refs["BioCyc"].url == "https://biocyc.org/getid?id=MetaCyc%3AHS08109-MONOMER"
    assert refs["NDEx"].url == "https://www.ndexbio.org/viewer/networks/EBS3129"


def test_projection_survives_a_junk_payload() -> None:
    """Untrusted JSON must degrade to empty sections, never raise."""
    result = build({"comments": "not-a-list", "features": [None, 7], "keywords": {}})

    assert result.function == []
    assert result.keywords == []
    assert result.ptm_features == []
    assert result.gene_ontology.biological_process == []


def test_empty_annotations_is_a_valid_payload_with_every_section_empty() -> None:
    result = annotations_service.empty_annotations(UID, "no accession")

    assert result.accession_resolved is False
    assert result.accession is None
    assert result.resolution_note == "no accession"
    assert result.function == [] and result.keywords == [] and result.diseases == []
    assert result.gene_ontology.molecular_function == []


# ------------------------------------------------------------- the HTTP leg


@respx.mock
async def test_fetch_annotations_requests_the_full_field_set_and_caches() -> None:
    route = respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=insulin())
    )
    uniprot = UniProtClient()

    first = await uniprot.fetch_annotations("p01308")
    second = await uniprot.fetch_annotations("P01308")

    assert first["primaryAccession"] == "P01308"
    assert second == first
    assert route.call_count == 1, "second lookup should be served from the cache"
    assert route.calls.last.request.url.params["fields"] == ANNOTATION_FIELDS


@respx.mock
async def test_fetch_annotations_404_raises_not_found() -> None:
    respx.get(url__startswith=UNIPROT_ENTRY).mock(return_value=httpx.Response(404))

    with pytest.raises(SourceNotFoundError):
        await UniProtClient().fetch_annotations("P01308")


@respx.mock
async def test_find_accession_for_pdb_reads_the_first_hit() -> None:
    respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_search_pdb_xref.json"))
    )

    assert await UniProtClient().find_accession_for_pdb("1CRN") == "P01542"


@respx.mock
async def test_find_accession_for_pdb_returns_none_when_nothing_matches() -> None:
    respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    assert await UniProtClient().find_accession_for_pdb("9XYZ") is None


def test_rcsb_reads_the_accession_from_either_identifier_shape() -> None:
    flat = load_json("rcsb_polymer_entity_1CRN_1.json")
    assert _uniprot_accession(flat) == "P01542"

    identifiers = flat["rcsb_polymer_entity_container_identifiers"]
    del identifiers["uniprot_ids"]
    assert _uniprot_accession(flat) is None

    identifiers["reference_sequence_identifiers"] = [
        {"database_name": "GenBank", "database_accession": "AAA1234"},
        {"database_name": "UniProt", "database_accession": "p01542"},
    ]
    assert _uniprot_accession(flat) == "P01542"


# --------------------------------------------------------------- the endpoint


def test_unknown_protein_is_404() -> None:
    response = client.get(f"/api/proteins/{UID}/annotations")

    assert response.status_code == 404


@respx.mock
def test_uploaded_protein_returns_an_empty_but_valid_payload() -> None:
    """The endpoint must never 500 just because there is nothing to annotate.

    `@respx.mock` also proves it: an upload resolves to no accession without
    making a single outbound request, so an unmocked call would fail here.
    """
    register()

    response = client.get(f"/api/proteins/{UID}/annotations")

    assert response.status_code == 200
    body = response.json()
    assert body["accession_resolved"] is False
    assert body["accession"] is None
    assert "no database identifier" in body["resolution_note"]
    assert body["function"] == []
    assert body["gene_ontology"] == {
        "biological_process": [],
        "cellular_component": [],
        "molecular_function": [],
    }


@respx.mock
@pytest.mark.parametrize("source", ["uniprot", "alphafold"])
def test_uniprot_and_alphafold_imports_resolve_straight_from_source_id(source: str) -> None:
    register(source=source, source_id="P01308")
    respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=insulin())
    )

    body = client.get(f"/api/proteins/{UID}/annotations").json()

    assert body["accession"] == "P01308"
    assert body["accession_resolved"] is True
    assert body["protein_name"] == "Insulin"
    assert len(body["gene_ontology"]["cellular_component"]) == 2


@respx.mock
def test_rcsb_import_maps_through_the_polymer_entity() -> None:
    register(source="rcsb", source_id="1CRN")
    respx.get(url__startswith=RCSB_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    respx.get(url__startswith=RCSB_ENTITY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_polymer_entity_1CRN_1.json"))
    )
    entry = respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=insulin())
    )
    search = respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    body = client.get(f"/api/proteins/{UID}/annotations").json()

    assert body["accession"] == "P01542"
    assert "polymer entity" in body["resolution_note"]
    assert entry.called
    # The polymer entity answered, so the search fallback must not have run.
    assert not search.called


@respx.mock
def test_rcsb_import_falls_back_to_the_uniprot_pdb_index() -> None:
    register(source="rcsb", source_id="1CRN")
    entity = load_json("rcsb_polymer_entity_1CRN_1.json")
    del entity["rcsb_polymer_entity_container_identifiers"]["uniprot_ids"]
    respx.get(url__startswith=RCSB_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    respx.get(url__startswith=RCSB_ENTITY).mock(return_value=httpx.Response(200, json=entity))
    search = respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json=load_json("uniprot_search_pdb_xref.json"))
    )
    respx.get(url__startswith=UNIPROT_ENTRY).mock(
        return_value=httpx.Response(200, json=insulin())
    )

    body = client.get(f"/api/proteins/{UID}/annotations").json()

    assert search.called
    assert body["accession"] == "P01542"
    assert "UniProt's index" in body["resolution_note"]


@respx.mock
def test_rcsb_entry_with_no_uniprot_counterpart_is_still_a_200() -> None:
    register(source="rcsb", source_id="1CRN")
    entity = load_json("rcsb_polymer_entity_1CRN_1.json")
    del entity["rcsb_polymer_entity_container_identifiers"]["uniprot_ids"]
    respx.get(url__startswith=RCSB_ENTRY).mock(
        return_value=httpx.Response(200, json=load_json("rcsb_entry_1CRN.json"))
    )
    respx.get(url__startswith=RCSB_ENTITY).mock(return_value=httpx.Response(200, json=entity))
    respx.get(url__startswith=UNIPROT_SEARCH).mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    response = client.get(f"/api/proteins/{UID}/annotations")

    assert response.status_code == 200
    assert response.json()["accession_resolved"] is False
    assert "No UniProt entry cross-references PDB 1CRN" in response.json()["resolution_note"]


@respx.mock
def test_uniprot_outage_on_a_known_accession_is_a_502_not_a_500() -> None:
    register(source="uniprot", source_id="P01308")
    respx.get(url__startswith=UNIPROT_ENTRY).mock(return_value=httpx.Response(503))

    response = client.get(f"/api/proteins/{UID}/annotations")

    assert response.status_code == 502
    assert "UniProt" in response.json()["detail"]


@respx.mock
def test_accession_with_no_uniprot_entry_degrades_to_an_empty_payload() -> None:
    register(source="uniprot", source_id="P01308")
    respx.get(url__startswith=UNIPROT_ENTRY).mock(return_value=httpx.Response(404))

    response = client.get(f"/api/proteins/{UID}/annotations")

    assert response.status_code == 200
    body = response.json()
    assert body["accession_resolved"] is False
    assert body["accession"] == "P01308"
    assert "no entry for accession P01308" in body["resolution_note"]
