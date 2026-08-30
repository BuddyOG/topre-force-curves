import copy
import csv
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path

import pytest

from domelab_pipeline import __version__
from domelab_pipeline import intake_policy
from domelab_pipeline import pipeline
from domelab_pipeline.pipeline import (
    cache_manifest,
    generate,
    load_config_bundle,
    provenance_hashes,
    verify_inputs,
)


COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_ROOT = Path(__file__).resolve().parents[1]
EPOCH_INPUTS = Path(os.environ.get(
    "DOMELAB_EPOCH_INPUTS", REPO_ROOT / "canonical-evidence" / "epoch_inputs"))
CACHE = Path(os.environ.get(
    "DOMELAB_CACHE",
    REPO_ROOT / "canonical-evidence" / "raw_cache" / f"repo-{COMMIT}"))
WORKBOOK = Path(os.environ.get(
    "DOMELAB_WORKBOOK", EPOCH_INPUTS / "source_workbook" / "untested-domes_v2.xlsx"
))
WORKBOOK_SHA256 = "02e85a2fbdc8e025f1445ab8cb7bd830501f755b79d0a755d6ee31e53bca45a4"


def jread(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def bundle():
    return load_config_bundle()


@pytest.fixture(scope="module")
def cache_man():
    assert CACHE.is_dir()
    return cache_manifest(str(CACHE))


@pytest.fixture(scope="module")
def generated(staging_dir):
    staged, records, per_run, _ = generate(
        str(CACHE), COMMIT, str(staging_dir), write=False,
        run_parity=False, evidence_only=True,
    )
    return staged, records, per_run


@pytest.fixture(scope="module")
def staging(staging_dir):
    return Path(staging_dir)


def test_frozen_input_contract(bundle, cache_man):
    result = verify_inputs(str(CACHE), COMMIT, bundle, cache_man)
    assert result == {
        "pinned_files": 189,
        "verified_files": 189,
        "verified_raw_runs": 184,
        "unique_raw_blobs": 180,
        "semantic_sets": 76,
        "independent_measurement_cohorts": 75,
    }


def test_metadata_authority_and_scope(bundle):
    registry = bundle["metadata_registry"]
    assert registry["source_workbook"]["sha256"] == WORKBOOK_SHA256
    assert hashlib.sha256(WORKBOOK.read_bytes()).hexdigest() == WORKBOOK_SHA256
    assert len(registry["rows"]) == 79
    assert sum(row["tested"] == "YES" for row in registry["rows"]) == 65
    assert sum(row["tested"] == "NO" for row in registry["rows"]) == 14
    tests = bundle["dataset_manifest"]["tests"]
    assert len(tests) == 76
    assert sum(t["metadata"]["metadata_source"] == "authoritative_workbook" for t in tests) == 65
    assert sum(t["metadata"]["metadata_source"] == "predecessor_manifest" for t in tests) == 11
    assert all(
        t["metadata"]["tested"] is True
        for t in tests if t["metadata"]["metadata_source"] == "authoritative_workbook"
    )
    assert all(
        t["metadata"]["tested"] is None
        for t in tests if t["metadata"]["metadata_source"] == "predecessor_manifest"
    )
    assert all(t["metadata"]["flag_travel"] is None for t in tests)
    assert all(
        t["metadata"]["status"] == "verified"
        for t in tests if t["metadata"]["metadata_source"] == "authoritative_workbook"
    )


def test_active_registries_are_empty_and_history_is_preserved(bundle):
    assert bundle["exclusions"]["repo_commit"] == COMMIT
    assert bundle["review_register"]["repo_commit"] == COMMIT
    assert bundle["exclusions"]["entries"] == []
    assert bundle["review_register"]["entries"] == []
    assert bundle["adjudications"]["entries"] == []
    events = bundle["evidence_history"]["events"]
    assert len(events) == 6
    assert {event["event_id"] for event in events} == {
        "evt_retest_deskeys_carrot_60g",
        "evt_retest_dynacaps_light_35g",
        "evt_retest_sony_bke_gray_01_02",
        "evt_oem_topre_collection_transition",
        "evt_prune_failed_importer_runs",
        "evt_retest_topre_r2_45g",
    }
    encoded = json.dumps(events, sort_keys=True)
    assert "Topre_55g" in encoded


@pytest.mark.parametrize("registry_name", ["exclusions", "review_register"])
def test_active_registry_commit_tampering_fails_closed(
        bundle, cache_man, registry_name):
    broken = copy.deepcopy(bundle)
    broken[registry_name]["repo_commit"] = "0" * 40
    with pytest.raises(RuntimeError, match=rf"{registry_name}\.repo_commit"):
        verify_inputs(str(CACHE), COMMIT, broken, cache_man)


def test_canonical_decision_manifest_is_complete(bundle):
    decisions = bundle["retained_run_decisions"]
    runs = [run for entry in decisions["sets"] for run in entry["runs"]]
    assert decisions["artifact_role"] == intake_policy.CANONICAL_ROLE
    assert decisions["release_eligible"] is True
    assert len(decisions["sets"]) == 76
    assert len(runs) == 184
    assert all(entry["status"] == "accepted" for entry in decisions["sets"])
    assert all(run["intake_individually_acceptable"] and run["retained"] for run in runs)
    assert not any(run["ramp_review_required"] for run in runs)
    assert decisions["raw_evidence_summary"] == {
        "path_count": 184,
        "unique_acquisition_count": 180,
        "git_object_format": "sha1",
    }


def test_shared_evidence_alias_is_explicit_and_not_independent(bundle):
    manifest = bundle["dataset_manifest"]
    assert len(manifest["evidence_aliases"]) == 1
    alias = manifest["evidence_aliases"][0]
    assert len(alias["run_pairs"]) == 4
    assert all(pair["independent_observation_count"] == 1 for pair in alias["run_pairs"])
    records = {test["set"]: test for test in manifest["tests"]}
    left = records["Topre_HHKB_Pro2_45g"]
    right = records["Topre_Slider_Black"]
    assert left["measurement_cohort_id"] == right["measurement_cohort_id"]
    assert {r["acquisition_id"] for r in left["expected_runs"]} == {
        r["acquisition_id"] for r in right["expected_runs"]
    }


def test_alias_and_metadata_mutations_fail_closed(bundle, cache_man):
    broken = copy.deepcopy(bundle)
    broken["dataset_manifest"]["evidence_aliases"] = []
    with pytest.raises(RuntimeError, match="duplicate/alias"):
        verify_inputs(str(CACHE), COMMIT, broken, cache_man)
    broken = copy.deepcopy(bundle)
    test = next(
        t for t in broken["dataset_manifest"]["tests"]
        if t["set"] == "Astro_Domes_Shiner_35g"
    )
    test["metadata"]["variant"] = "incorrect"
    with pytest.raises(RuntimeError, match="exactly match workbook row"):
        verify_inputs(str(CACHE), COMMIT, broken, cache_man)


def test_manifest_identity_and_alias_tampering_fails_closed(bundle, cache_man):
    mutations = []

    broken = copy.deepcopy(bundle)
    broken["dataset_manifest"]["tests"][1]["test_id"] = broken["dataset_manifest"]["tests"][0]["test_id"]
    mutations.append((broken, "duplicate test_id"))

    broken = copy.deepcopy(bundle)
    broken["dataset_manifest"]["tests"][1]["set"] = broken["dataset_manifest"]["tests"][0]["set"]
    mutations.append((broken, "duplicate set"))

    broken = copy.deepcopy(bundle)
    broken["dataset_manifest"]["counts"]["semantic_records"] = 999
    mutations.append((broken, "counts do not match"))

    broken = copy.deepcopy(bundle)
    workbook_test = next(
        test for test in broken["dataset_manifest"]["tests"]
        if test["metadata"]["metadata_source"] == "authoritative_workbook"
    )
    workbook_test["metadata"]["metadata_source_locator"] = "wrong.xlsx#A1"
    mutations.append((broken, "row locator"))

    broken = copy.deepcopy(bundle)
    workbook_test = next(
        test for test in broken["dataset_manifest"]["tests"]
        if test["metadata"]["metadata_source"] == "authoritative_workbook"
    )
    workbook_test["metadata"]["metadata_override_applied"] = False
    mutations.append((broken, "override"))

    broken = copy.deepcopy(bundle)
    alias = broken["dataset_manifest"]["evidence_aliases"][0]
    alias["run_pairs"].append(copy.deepcopy(alias["run_pairs"][0]))
    mutations.append((broken, "duplicate run-pair"))

    broken = copy.deepcopy(bundle)
    alias = broken["dataset_manifest"]["evidence_aliases"][0]
    alias_tests = {
        test["test_id"]: test for test in broken["dataset_manifest"]["tests"]
        if test["test_id"] in alias["semantic_test_ids"]
    }
    for test in alias_tests.values():
        test["metadata"]["evidence_alias_role"] = "dome_semantic"
    mutations.append((broken, "roles must be distinct"))

    broken = copy.deepcopy(bundle)
    alias = broken["dataset_manifest"]["evidence_aliases"][0]
    unrelated = next(
        test for test in broken["dataset_manifest"]["tests"]
        if test["test_id"] not in alias["semantic_test_ids"]
    )
    unrelated["measurement_cohort_id"] = alias["measurement_cohort_id"]
    mutations.append((broken, "shared outside"))

    broken = copy.deepcopy(bundle)
    legacy = next(
        test for test in broken["dataset_manifest"]["tests"]
        if test["metadata"]["metadata_source"] == "predecessor_manifest"
    )
    legacy["metadata"]["tested"] = True
    mutations.append((broken, "must be null"))

    for broken_bundle, expected in mutations:
        with pytest.raises(RuntimeError, match=expected):
            verify_inputs(str(CACHE), COMMIT, broken_bundle, cache_man)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tracked_files", 1, "tracked_files"),
        ("csvs", 1, "csvs"),
        ("unique_raw_blobs", 1, "unique_raw_blobs"),
        ("git_object_format", "sha256", "git_object_format"),
        ("repository_file_inventory_sha256", "0" * 64, "inventory SHA-256"),
    ],
)
def test_repo_provenance_tampering_fails_closed(
        bundle, cache_man, monkeypatch, field, value, message):
    original = pipeline.ujson

    def tampered(path):
        data = original(path)
        if str(path).endswith("repo_provenance.json"):
            data = copy.deepcopy(data)
            data[field] = value
        return data

    monkeypatch.setattr(pipeline, "ujson", tampered)
    with pytest.raises(RuntimeError, match=message):
        verify_inputs(str(CACHE), COMMIT, bundle, cache_man)


def test_duplicate_inventory_path_fails_closed(tmp_path, monkeypatch):
    source = Path(pipeline.REF) / "repository_file_inventory.csv"
    lines = source.read_text(encoding="utf-8").splitlines()
    ref = tmp_path / "release_reference"
    ref.mkdir()
    (ref / source.name).write_text("\n".join(lines + [lines[1]]) + "\n", encoding="utf-8")
    monkeypatch.setattr(pipeline, "REF", str(ref))
    with pytest.raises(RuntimeError, match="duplicate paths"):
        pipeline.pinned_inventory_rows()


def test_evidence_only_generation_has_no_step3_surface(generated):
    staged, records, per_run = generated
    assert __version__ == "4.2.2"
    assert len(staged) == 95
    assert len(records) == 76
    assert len(per_run) == 184
    assert sum(path.startswith("packs/curves/") for path in staged) == 76
    assert not any(path.lower().endswith(".html") for path in staged)
    assert "packs/viewer.staged.html" not in staged
    assert "packs/picker.staged.html" not in staged
    meta = json.loads(staged["schema_meta.staged.json"])
    assert meta["evidence_epoch"]["force_curve_bench_step3_status"] == "deferred_not_executed"
    assert meta["evidence_epoch"]["force_curve_bench_release_eligible"] is False
    assert all(record["flag_travel"] is None for record in records)


def test_full_precision_and_membership_closure(generated):
    staged, records, per_run = generated
    raw = json.loads(staged["raw_path_manifest.json"])
    decisions = json.loads(staged["intake_retention_decisions.json"])
    retention = list(csv.DictReader(staged["run_retention.csv"].splitlines()))
    raw_paths = {row["path"] for row in raw["rows"]}
    assert len(raw_paths) == 184
    assert raw_paths == {row["raw_path"] for row in per_run}
    assert raw_paths == {row["raw_path"] for row in retention}
    assert raw_paths == {
        run["raw_path"] for entry in decisions["sets"] for run in entry["runs"]
    }
    assert raw_paths == {
        path for record in records for path in record["provenance"]["raw_paths"]
    }
    acquisitions = {
        row["acquisition_id"] for row in raw["rows"]
    }
    assert len(acquisitions) == 180
    assert acquisitions == {
        acquisition for record in records
        for acquisition in record["provenance"]["acquisition_ids"]
    }


def test_epoch_identity_excludes_presentation_identity(bundle, cache_man, generated):
    hashes = provenance_hashes(bundle, cache_man)
    staged, records, _ = generated
    assert all(r["provenance"]["config_hash"] == hashes["evidence_epoch_hash"] for r in records)
    meta = json.loads(staged["schema_meta.staged.json"])
    assert meta["config_hash"] == hashes["bundle_hash"]
    assert meta["evidence_epoch"]["identity"] == hashes["evidence_epoch_hash"]
    assert hashes["evidence_epoch_hash"] != hashes["bundle_hash"]


def test_curve_packs_are_hash_bound_and_explicitly_lossy(generated):
    staged, records, _ = generated
    provenance = json.loads(staged["curve_pack_provenance.json"])
    assert provenance["pack_values_are_derived_and_lossy"] is True
    assert len(provenance["packs"]) == 76
    by_set = {record["set"]: record for record in records}
    for entry in provenance["packs"]:
        assert entry["derived_lossy_display_pack"] is True
        assert entry["authoritative_metrics"] is False
        assert hashlib.sha256(staged[entry["path"]].encode()).hexdigest() == entry["sha256"]
        assert entry["raw_paths"] == by_set[entry["set"]]["provenance"]["raw_paths"]


def test_staged_tree_is_exactly_reproducible(sealed_epoch_source, generated, staging):
    staged, _, _ = generated
    actual = {
        path.relative_to(staging).as_posix()
        for path in staging.rglob("*") if path.is_file()
    }
    assert actual == set(staged)
    for rel, expected in staged.items():
        assert (staging / rel).read_bytes() == expected.encode("utf-8")


def test_epoch_input_reseal_is_deterministic_and_rejects_tampering(sealed_epoch_source, staging, tmp_path):
    """The final v2 seal is reproducible and cannot normalize altered inputs."""
    isolated = tmp_path / "canonical_epoch"
    shutil.copytree(EPOCH_INPUTS, isolated / "epoch_inputs")
    shutil.copytree(
        GENERATOR_ROOT / "domelab_pipeline" / "config",
        isolated / "source" / "generator" / "domelab_pipeline" / "config",
    )
    shutil.copytree(
        staging,
        isolated / "epoch_outputs" / staging.name,
    )

    script = isolated / "epoch_inputs" / "scripts" / "seal_epoch_inputs.py"
    spec = importlib.util.spec_from_file_location("epoch_input_sealer", script)
    assert spec is not None and spec.loader is not None
    sealer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sealer)

    first = sealer.seal_epoch_inputs(isolated)
    report_path = isolated / "epoch_inputs" / "validation" / "validation_report.json"
    index_path = isolated / "epoch_inputs" / "SHA256SUMS.csv"
    first_report = report_path.read_bytes()
    first_index = index_path.read_bytes()
    second = sealer.seal_epoch_inputs(isolated)
    assert report_path.read_bytes() == first_report
    assert index_path.read_bytes() == first_index
    assert first == second
    assert sealer.seal_epoch_inputs(isolated, check=True)["mode"] == "check"

    rows = list(csv.DictReader(first_index.decode("utf-8").splitlines()))
    indexed = {row["path"] for row in rows}
    expected = {
        path.relative_to(isolated / "epoch_inputs").as_posix()
        for path in (isolated / "epoch_inputs").rglob("*")
        if path.is_file()
        and path.name != "SHA256SUMS.csv"
        and path.suffix != ".pyc"
        and "__pycache__" not in path.parts
        and "node_modules" not in path.parts
    }
    assert indexed == expected

    # An already sealed audit artifact cannot be changed and merely re-indexed.
    run_csv = (
        isolated
        / "epoch_inputs"
        / "validation"
        / "test_imp_1_1_4_per_run.csv"
    )
    original_run_csv = run_csv.read_bytes()
    run_csv.write_bytes(original_run_csv + b"\n")
    with pytest.raises(sealer.SealError, match="existing importer seal"):
        sealer.seal_epoch_inputs(isolated)
    run_csv.write_bytes(original_run_csv)

    # Emulate the documented base-builder boundary (v1 has no prior seals),
    # then prove the semantic gates independently reject each authority class.
    base = sealer._validation_base(jread(report_path))
    report_path.write_bytes(sealer._json_bytes(base))

    exclusions_path = (
        isolated
        / "source"
        / "generator"
        / "domelab_pipeline"
        / "config"
        / "exclusions.json"
    )
    original_exclusions = exclusions_path.read_bytes()
    exclusions = json.loads(original_exclusions)
    exclusions["repo_commit"] = "0" * 40
    exclusions_path.write_text(json.dumps(exclusions), encoding="utf-8")
    with pytest.raises(sealer.SealError, match="exclusions registry repo_commit"):
        sealer.seal_epoch_inputs(isolated)
    exclusions_path.write_bytes(original_exclusions)

    decisions_path = (
        isolated
        / "source"
        / "generator"
        / "domelab_pipeline"
        / "config"
        / "retained_run_decisions.json"
    )
    original_decisions = decisions_path.read_bytes()
    decisions = json.loads(original_decisions)
    decisions["owner_decision_inputs_hash"] = "0" * 64
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    with pytest.raises(sealer.SealError, match="owner_decision_inputs_hash"):
        sealer.seal_epoch_inputs(isolated)
    decisions_path.write_bytes(original_decisions)

    audit_path = (
        isolated
        / "epoch_inputs"
        / "validation"
        / "test_imp_1_1_4_epoch_audit.json"
    )
    original_audit = audit_path.read_bytes()
    audit = json.loads(original_audit)
    audit["result"] = "FAIL"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    with pytest.raises(sealer.SealError, match="audit result is not PASS"):
        sealer.seal_epoch_inputs(isolated)
    audit_path.write_bytes(original_audit)

    curve_path = (
        isolated
        / "epoch_outputs"
        / staging.name
        / "packs"
        / "curves"
        / "Topre_R2_45g.staged.json"
    )
    original_curve = curve_path.read_bytes()
    curve_path.write_bytes(original_curve + b"\n")
    with pytest.raises(sealer.SealError, match="generated manifest hash mismatch"):
        sealer.seal_epoch_inputs(isolated)
    curve_path.write_bytes(original_curve)

    # Restored inputs seal and check cleanly from the base-builder boundary.
    sealer.seal_epoch_inputs(isolated)
    sealer.seal_epoch_inputs(isolated, check=True)
