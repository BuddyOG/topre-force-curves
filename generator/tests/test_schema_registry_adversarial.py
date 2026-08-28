"""Step 2.3 adversarial schema, registry and adjudication tests.

Each case was reproduced against the Step 2.2 generator first. The Step 2.2
schema accepted five path adversarials, both duplicate cases, and forced travel
to be null whenever any metric was null; the Step 2.2 generator excluded sets by
name without validating a single registry binding and let a forged duplicate
adjudication key silently win.
"""
import copy
import json
import os

import jsonschema
import pytest

from domelab_pipeline import registries
from domelab_pipeline.core import config
from domelab_pipeline.schema_gen import (build_schema, validate_records, METRICS,
                                         METADATA_FIELDS, NULL_REASONS, NULLABLE)


@pytest.fixture(scope="module")
def schema():
    return build_schema()


@pytest.fixture(scope="module")
def record(staging_dir):
    with open(os.path.join(staging_dir, "bench_tests.staged.json"), encoding="utf-8") as f:
        recs = json.load(f)
    record = recs[0]
    assert record["calc_version"] == config()["calc_version"]
    assert record["intake_review_notices"] == []
    return record


# ------------------------------------------------- complete record model
def test_every_staged_record_is_complete(staging_dir, schema):
    with open(os.path.join(staging_dir, "bench_tests.staged.json"), encoding="utf-8") as f:
        recs = json.load(f)
    required = set(schema["required"])
    for r in recs:
        missing = sorted(required - set(r))
        assert not missing, f"{r.get('test_id')}: missing {missing}"


def test_metadata_fields_are_required_not_optional(schema):
    for f in METADATA_FIELDS:
        assert f in schema["required"], f


def test_flag_travel_and_silencing_ring_present_everywhere(staging_dir):
    """The two fields Step 2.2 dropped from 8 and 15 records respectively."""
    with open(os.path.join(staging_dir, "bench_tests.staged.json"), encoding="utf-8") as f:
        recs = json.load(f)
    for r in recs:
        assert "flag_travel" in r, r["test_id"]
        assert "silencing_ring" in r, r["test_id"]
        assert r["flag_travel"] is None or isinstance(r["flag_travel"], bool)


def test_incomplete_record_is_rejected(schema, record):
    V = jsonschema.Draft202012Validator(schema)
    for f in (
        "flag_travel",
        "silencing_ring",
        "dispersion",
        "status",
        "notes",
        "intake_review_notices",
    ):
        bad = copy.deepcopy(record)
        bad.pop(f, None)
        assert list(V.iter_errors(bad)), f"removing {f} was accepted"


# ------------------------------------------------------- path adversarials
GOOD_PATHS = ["Topre_R1_45g/DataLog_2.csv", "a/b/c.csv", "x.csv"]
BAD_PATHS = ["../x.csv", "./run.csv", "a/./b.csv", "a//b.csv", "a\\b.csv",
             "/abs/run.csv", "C:/run.csv", "C:\\win\\run.csv", "file:///tmp/run.csv",
             "a/../b.csv", "", "a/", "..", ".", "http://x/y.csv"]


@pytest.mark.parametrize("p", GOOD_PATHS)
def test_normalized_paths_accepted(schema, p):
    V = jsonschema.Draft202012Validator(
        schema["properties"]["provenance"]["properties"]["raw_paths"]["items"])
    assert not list(V.iter_errors(p)), p


@pytest.mark.parametrize("p", BAD_PATHS)
def test_path_adversarials_rejected(schema, p):
    V = jsonschema.Draft202012Validator(
        schema["properties"]["provenance"]["properties"]["raw_paths"]["items"])
    assert list(V.iter_errors(p)), f"{p!r} was accepted"


@pytest.mark.parametrize("p", BAD_PATHS)
def test_registry_path_helper_rejects_same_set(p):
    assert registries.normalized_posix_problems(p), f"{p!r} produced no problem"


# ------------------------------------------------------------- duplicates
def test_duplicate_quality_flags_rejected(schema, record):
    V = jsonschema.Draft202012Validator(schema)
    bad = copy.deepcopy(record)
    bad["quality_flags"] = ["bottomout_not_found", "bottomout_not_found"]
    assert list(V.iter_errors(bad))


def test_duplicate_raw_paths_rejected(schema, record):
    V = jsonschema.Draft202012Validator(schema)
    bad = copy.deepcopy(record)
    p = bad["provenance"]["raw_paths"][0]
    h = bad["provenance"]["raw_sha256"][0]
    bad["provenance"]["raw_paths"] = [p, p]
    bad["provenance"]["raw_sha256"] = [h, h]
    bad["runs_used"] = 2
    assert list(V.iter_errors(bad))


# ------------------------------------------------------------ null semantics
def test_ramp_only_null_does_not_force_travel_null(schema, record):
    """Step 2.2 rejected this: a generic aggregate_contains_null_run flag forced
    travel to be null even when only RAMP was unavailable."""
    r = copy.deepcopy(record)
    r["ramp_10_90_gf_per_mm"] = None
    r["quality_flags"] = sorted(set(r["quality_flags"]) |
                                {"aggregate_contains_null_run", "ramp_crossing_missing"})
    r["null_reasons"] = {"ramp_10_90_gf_per_mm": "ramp_crossing_missing"}
    validate_records([r], schema)          # must not raise
    assert r["travel_mm"] is not None


def _coherent_null(record, metric, reason):
    """Build a record whose null state is MECHANICALLY coherent (Step 2.3.1).

    Nulling a metric in isolation can contradict physics: work to a bottom-out
    onset cannot be null while travel is numeric, and SNAP cannot be null for
    'nonpositive_collapse_force' while collapse force is positive. Step 2.3's
    fixtures did exactly that and validated cleanly.
    """
    r = copy.deepcopy(record)
    r[metric] = None
    reasons = {metric: reason}
    if metric in ("travel_mm", "full_stroke_press_work_gf_mm"):
        # the pair is mechanically coupled in both directions
        r["travel_mm"] = None
        r["full_stroke_press_work_gf_mm"] = None
        reasons = {"travel_mm": reason, "full_stroke_press_work_gf_mm": reason}
    if metric == "snap_pct" and reason == "nonpositive_collapse_force":
        r["collapse_force_gf"] = 0.0          # the condition the reason names
        r["drop_gf"] = -r["valley_force_gf"] # preserve linear aggregate identity
        r["drop_rate_gf_per_mm"] = None
        r["norm_drop_rate_per_mm"] = None
        reasons.update({"drop_rate_gf_per_mm": "nonpositive_collapse_force",
                        "norm_drop_rate_per_mm": "nonpositive_collapse_force"})
    r["null_reasons"] = reasons
    r["quality_flags"] = sorted(set(r["quality_flags"]) | set(reasons.values()))
    return r


@pytest.mark.parametrize("metric,reason", [
    (m, reason) for m, reasons in NULL_REASONS.items() for reason in reasons])
def test_every_nullable_metric_accepts_every_allowed_reason(schema, record, metric, reason):
    validate_records([_coherent_null(record, metric, reason)], schema)


def test_non_null_metric_must_not_carry_a_null_reason(schema, record):
    r = copy.deepcopy(record)
    r["null_reasons"] = {"ramp_10_90_gf_per_mm": "ramp_crossing_missing"}
    r["quality_flags"] = sorted(set(r["quality_flags"]) | {"ramp_crossing_missing"})
    with pytest.raises(RuntimeError, match="carries null reason"):
        validate_records([r], schema)


def test_null_metric_without_a_reason_is_rejected(schema, record):
    r = copy.deepcopy(record)
    r["ramp_10_90_gf_per_mm"] = None
    with pytest.raises(RuntimeError, match="lacks a metric-specific null reason"):
        validate_records([r], schema)


def test_null_reason_absent_from_quality_flags_is_rejected(schema, record):
    r = copy.deepcopy(record)
    r["ramp_10_90_gf_per_mm"] = None
    r["null_reasons"] = {"ramp_10_90_gf_per_mm": "ramp_crossing_missing"}
    with pytest.raises(RuntimeError, match="not present in quality_flags"):
        validate_records([r], schema)


def test_snap_pct_is_nullable_and_reachable(schema, record):
    """The core emits snap_pct=None when collapse force is nonpositive, so the
    schema must permit it. Step 2.2 declared a null reason while forbidding the
    value, making the path unreachable-by-schema yet reachable-by-code."""
    assert "snap_pct" in NULLABLE
    assert "snap_pct" in NULL_REASONS
    validate_records([_coherent_null(record, "snap_pct", "nonpositive_collapse_force")], schema)


def test_snap_pct_null_path_exists_in_the_core():
    """Prove the emitting branch is live rather than assuming it."""
    import inspect
    from domelab_pipeline import core
    src = inspect.getsource(core.run_metrics)
    assert 'flags.append("nonpositive_collapse_force")' in src
    assert "if Fc > 0:" in src


def test_full_stroke_work_must_be_null_when_travel_is_null(schema, record):
    r = copy.deepcopy(record)
    r["travel_mm"] = None
    r["null_reasons"] = {"travel_mm": "bottomout_not_found"}
    r["quality_flags"] = sorted(set(r["quality_flags"]) | {"bottomout_not_found"})
    with pytest.raises(RuntimeError, match="full-stroke work must be null"):
        validate_records([r], schema)


# ---------------------------------------------------- exclusion registry
def _bundle(staging_dir):
    from domelab_pipeline.pipeline import load_config_bundle, cache_manifest, pinned_inventory
    return load_config_bundle(), pinned_inventory()


def test_exclusion_registry_verifies_clean(cache, staging_dir):
    from domelab_pipeline.pipeline import load_config_bundle, cache_manifest, pinned_inventory
    b = load_config_bundle()
    errs = registries.verify_exclusion_registry(b["exclusions"], b["dataset_manifest"],
                                                cache_manifest(cache), pinned_inventory())
    assert errs == []


@pytest.mark.parametrize("mutate,expect", [
    ("stale_hash", "stale SHA-256"),
    ("missing_path", "incomplete path list"),
    ("extra_path", "not part of this set"),
    ("nonexistent_set", "does not exist"),
    ("duplicate_set", "duplicate excluded-set entry"),
    ("duplicate_binding", "duplicate run bindings"),
    ("bad_path_form", "rejected path"),
])
def test_exclusion_registry_binding_mismatch_rejected(cache, mutate, expect):
    from domelab_pipeline.pipeline import load_config_bundle, cache_manifest, pinned_inventory
    b = load_config_bundle()
    fixture = b["dataset_manifest"]["tests"][0]
    ex = {
        "entries": [{
            "set": fixture["set"],
            "raw_runs": [
                {"path": run["path"], "sha256": run["sha256"]}
                for run in fixture["expected_runs"]
            ],
        }]
    }
    e = ex["entries"][0]
    if mutate == "stale_hash":
        e["raw_runs"][0]["sha256"] = "0" * 64
    elif mutate == "missing_path":
        e["raw_runs"].pop()
    elif mutate == "extra_path":
        e["raw_runs"].append({"path": f"{fixture['set']}/DataLog_99.csv", "sha256": "1" * 64})
    elif mutate == "nonexistent_set":
        e["set"] = "No_Such_Set"
    elif mutate == "duplicate_set":
        ex["entries"].append(copy.deepcopy(e))
    elif mutate == "duplicate_binding":
        e["raw_runs"].append(copy.deepcopy(e["raw_runs"][0]))
    elif mutate == "bad_path_form":
        e["raw_runs"][0]["path"] = "./" + e["raw_runs"][0]["path"]
    errs = registries.verify_exclusion_registry(ex, b["dataset_manifest"],
                                                cache_manifest(cache), pinned_inventory())
    assert any(expect in x for x in errs), (mutate, errs)


def test_current_exclusions_are_empty_and_pruned_history_is_exact(staging_dir):
    with open(os.path.join(staging_dir, "exclusion_manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    assert man["entries"] == []
    with open(os.path.join(staging_dir, "evidence_history.staged.json"), encoding="utf-8") as f:
        history = json.load(f)
    event = next(
        item for item in history["events"]
        if item["event_id"] == "evt_prune_failed_importer_runs"
    )
    assert len(event["exclusions"]) == 9
    assert all(len(item["sha256"]) == 64 for item in event["exclusions"])


# ------------------------------------------------------- adjudications
BASE_IDX = {("S", "R.csv"): {"sha256": "ab" * 32, "qc_disposition": "review",
                             "qc_reasons": ["timing_gaps_ge_10"], "barrier_flags": []}}


def _adj(**over):
    a = {"set": "S", "run": "R.csv", "raw_path": "S/R.csv", "sha256": "ab" * 32,
         "method_hash": "m", "overrides_disposition": "review",
         "qc_reasons": ["timing_gaps_ge_10"], "barrier_flags": [], "eligible": True,
         "authority": "T", "date": "2026-01-01", "rationale": "r"}
    a.update(over)
    return {"entries": [a]}


def test_complete_binding_accepted():
    b, errs = registries.verify_adjudications(_adj(), BASE_IDX, "m")
    assert errs == [] and ("S", "R.csv") in b


@pytest.mark.parametrize("over,expect", [
    ({"sha256": "cd" * 32}, "SHA-256 mismatch"),
    ({"method_hash": "other"}, "method hash mismatch"),
    ({"overrides_disposition": "quarantine_retest"}, "disposition mismatch"),
    ({"qc_reasons": ["stale_force"]}, "QC-reason set mismatch"),
    ({"barrier_flags": ["tactile_event_not_found"]}, "barrier-flag set mismatch"),
    ({"raw_path": "../R.csv"}, "rejected path"),
    ({"run": "Nope.csv"}, "nonexistent file"),
])
def test_adjudication_mismatches_rejected(over, expect):
    _, errs = registries.verify_adjudications(_adj(**over), BASE_IDX, "m")
    assert any(expect in e for e in errs), (over, errs)


def test_duplicate_adjudication_key_rejected():
    a = _adj()
    a["entries"].append(copy.deepcopy(a["entries"][0]))
    _, errs = registries.verify_adjudications(a, BASE_IDX, "m")
    assert any("duplicate adjudication key" in e for e in errs)


def test_extraneous_adjudication_rejected():
    idx = {("S", "R.csv"): {"sha256": "ab" * 32, "qc_disposition": "pass",
                            "qc_reasons": [], "barrier_flags": []}}
    _, errs = registries.verify_adjudications(
        _adj(overrides_disposition="pass", qc_reasons=[]), idx, "m")
    assert any("extraneous" in e for e in errs)


def test_fail_exclude_never_overridable():
    idx = {("S", "R.csv"): {"sha256": "ab" * 32, "qc_disposition": "fail_exclude",
                            "qc_reasons": ["incomplete_return"], "barrier_flags": []}}
    _, errs = registries.verify_adjudications(
        _adj(overrides_disposition="fail_exclude", qc_reasons=["incomplete_return"]), idx, "m")
    assert any("never overridable" in e for e in errs)


def test_missing_binding_field_rejected():
    a = _adj()
    del a["entries"][0]["method_hash"]
    _, errs = registries.verify_adjudications(a, BASE_IDX, "m")
    assert any("missing required binding field" in e for e in errs)


# -------------------------------------- canonical intake application
def test_canonical_fleet_uses_intake_membership_not_legacy_qc(staging_dir):
    with open(os.path.join(staging_dir, "eligibility_decisions.json"), encoding="utf-8") as f:
        rows = json.load(f)
    with open(os.path.join(
        staging_dir, "intake_retention_decisions.json"
    ), encoding="utf-8") as f:
        decisions = json.load(f)
    expected_run_count = sum(len(entry["runs"]) for entry in decisions["sets"])
    assert len(rows) == expected_run_count
    assert all(row["artifact_role"] == "canonical_retention_authority" for row in rows)
    assert all(row["canonical_eligible"] is None for row in rows)
    assert all(row["adjudication"] is None for row in rows)
    assert all("legacy QC is diagnostic only" in row["decision"] for row in rows)

    assert decisions["artifact_role"] == "canonical_retention_authority"
    assert all(entry["status"] == "accepted" for entry in decisions["sets"])
    assert all(
        run["retained"]
        for entry in decisions["sets"] for run in entry["runs"]
    )


def test_no_adjudication_claims_buddyog_authority():
    from domelab_pipeline.pipeline import load_config_bundle
    b = load_config_bundle()
    assert b["adjudications"]["entries"] == []
    assert b["review_register"]["entries"] == []
    event = next(
        item for item in b["evidence_history"]["events"]
        if item["event_id"] == "evt_oem_topre_collection_transition"
    )
    assert event["prior_topre_55g_no_retest_decision"][
        "decision_was_satisfied_by_this_commit"
    ] is False


def test_eligibility_output_persists_the_complete_binding(staging_dir):
    with open(os.path.join(staging_dir, "eligibility_decisions.json"), encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        for k in ("set", "run", "sha256", "qc_disposition", "qc_disposition_flags",
                  "barrier_flags", "method_hash", "canonical_eligible", "decision"):
            assert k in r, (r.get("run"), k)


# ------------------------------------------- Step 2.3.1 null coherence
def test_null_work_with_numeric_travel_rejected(schema, record):
    """Step 2.3 accepted this: a detected bottom-out onset with no integral."""
    r = copy.deepcopy(record)
    r["full_stroke_press_work_gf_mm"] = None
    r["null_reasons"] = {"full_stroke_press_work_gf_mm": "bottomout_not_found"}
    r["quality_flags"] = sorted(set(r["quality_flags"]) | {"bottomout_not_found"})
    with pytest.raises(RuntimeError, match="cannot be null when travel is numeric"):
        validate_records([r], schema)


def test_null_travel_with_numeric_work_rejected(schema, record):
    r = copy.deepcopy(record)
    r["travel_mm"] = None
    r["null_reasons"] = {"travel_mm": "bottomout_not_found"}
    r["quality_flags"] = sorted(set(r["quality_flags"]) | {"bottomout_not_found"})
    with pytest.raises(RuntimeError, match="must be null when travel is null"):
        validate_records([r], schema)


def test_snap_null_reason_requires_nonpositive_collapse(schema, record):
    """Step 2.3 accepted a null SNAP blamed on nonpositive collapse force while
    collapse force was 51.6 gf."""
    r = copy.deepcopy(record)
    r["snap_pct"] = None
    r["null_reasons"] = {"snap_pct": "nonpositive_collapse_force"}
    r["quality_flags"] = sorted(set(r["quality_flags"]) | {"nonpositive_collapse_force"})
    assert r["collapse_force_gf"] > 0
    with pytest.raises(RuntimeError, match="collapse_force_gf=.* is positive"):
        validate_records([r], schema)


def test_snap_null_accepted_when_collapse_actually_nonpositive(schema, record):
    validate_records([_coherent_null(record, "snap_pct", "nonpositive_collapse_force")], schema)


def test_aggregate_flag_without_any_null_metric_rejected(schema, record):
    r = copy.deepcopy(record)
    r["quality_flags"] = sorted(set(r["quality_flags"]) | {"aggregate_contains_null_run"})
    with pytest.raises(RuntimeError, match="no canonical metric is null"):
        validate_records([r], schema)


def test_null_reason_key_must_name_a_metric(schema, record):
    r = copy.deepcopy(record)
    r["null_reasons"] = {"not_a_metric": "bottomout_not_found"}
    with pytest.raises(RuntimeError):
        validate_records([r], schema)


def test_every_staged_record_is_null_coherent(staging_dir, schema):
    """The shipped fleet must satisfy the tightened rules with no exceptions."""
    with open(os.path.join(staging_dir, "bench_tests.staged.json"), encoding="utf-8") as f:
        recs = json.load(f)
    validate_records(recs, schema)
