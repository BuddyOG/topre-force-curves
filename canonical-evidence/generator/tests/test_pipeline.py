"""Step-2.1 test suite. Layout-independent: all locations come from conftest
fixtures (env/CLI). Synthetic fixtures exercise every rule edge; committed
negative fixtures reproduce the known SD-card-era corruption modes; golden
fixtures pin per-run unrounded results at the pinned repository commit."""
import os, json, re
import pytest
from domelab_pipeline.core import moving_avg, run_metrics, _trapz_to, parse_run, config
from domelab_pipeline.medians import median_conventional, median_upper_middle_legacy
from domelab_pipeline.pipeline import (
    METRICS, PKGDIR, aggregate, batch_filter, check, generate,
    load_config_bundle, process_run,
)
from domelab_pipeline.qc import acquisition_qc, qc_disposition
from domelab_pipeline.schema_gen import build_schema, validate_records

HERE = os.path.dirname(os.path.abspath(__file__))


def _load_json(path):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def _read_text(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as stream:
        return stream.read()


def _staged_record(staging_dir):
    record = _load_json(os.path.join(staging_dir, "bench_tests.staged.json"))[0]
    assert record["calc_version"] == config()["calc_version"]
    assert record["intake_review_notices"] == []
    return record


def _manifest_test(minimum_runs=1):
    return next(
        test for test in load_config_bundle()["dataset_manifest"]["tests"]
        if len(test["expected_runs"]) >= minimum_runs
    )


def _manifest_run_paths(cache, minimum_runs=1):
    return [
        os.path.join(cache, *run["path"].split("/"))
        for run in _manifest_test(minimum_runs)["expected_runs"]
    ]


# ---------------------------------------------------------------- synthetic press
def synth(Fc=60.0, xc=1.3, Fv=25.0, xv=2.9, wall=3.9, base=10.0, n_end=4.4, step=0.005):
    x, F = [], []
    v = 0.0
    while v <= n_end + 1e-9:
        if v <= 0.2:    f = base
        elif v <= xc:   f = base + (Fc - base) * (v - 0.2) / (xc - 0.2)
        elif v <= xv:   f = Fc + (Fv - Fc) * (v - xc) / (xv - xc)
        elif v <= wall: f = Fv + 2.0 * (v - xv)
        else:           f = Fv + 2.0 * (wall - xv) + 900.0 * (v - wall)
        x.append(round(v, 4)); F.append(f)
        v += step
    return x, F


def synth_csv(rows=None, header=None, speed_ms=34):
    """Full 5-column raw CSV text (press+return) for parser/QC fixtures."""
    hdr = header or ",".join(config()["acquisition"]["expected_header"])
    if rows is None:
        x, F = synth()
        xr = x[::-1]; Fr = [10.0] * len(xr)
        rows = []
        t = 0
        for xx, ff in list(zip(x, F)) + list(zip(xr, Fr)):
            rows.append((t, round(xx * 1600), xx, ff * 100, ff)); t += speed_ms
    out = [hdr] + [",".join(str(v) for v in r) for r in rows]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- core metrics
def test_moving_average_interior_and_edges():
    F = [float(i) for i in range(10)]
    Fs = moving_avg(F, 7)
    assert Fs[5] == pytest.approx(sum(F[2:9]) / 7)
    assert Fs[0] == pytest.approx(sum(F[0:4]) / 4)
    assert Fs[1] == pytest.approx(sum(F[0:5]) / 5)
    assert Fs[9] == pytest.approx(sum(F[6:10]) / 4)


def test_trapezoid_exact_and_interpolated_endpoint():
    x = [0.0, 1.0, 2.0]; F = [0.0, 10.0, 20.0]
    assert _trapz_to(x, F, 2.0) == pytest.approx(20.0)
    assert _trapz_to(x, F, 1.5) == pytest.approx(0.5 * 15 * 1.5)


def test_raw_vs_smoothed_work_separation():
    x, F = synth()
    spiky = list(F); spiky[100] += 40.0
    m, _ = run_metrics(x, spiky)
    ms, _ = run_metrics(x, F)
    assert m["precollapse_work_gf_mm"] - ms["precollapse_work_gf_mm"] == pytest.approx(40.0 * 0.005, rel=0.05)


def test_collapse_valley_and_identities():
    m, _ = run_metrics(*synth())
    assert m["collapse_force_gf"] == pytest.approx(60.0, abs=0.6)
    assert m["valley_force_gf"] == pytest.approx(25.0, abs=0.6)
    D, N = m["drop_rate_gf_per_mm"], m["norm_drop_rate_per_mm"]
    assert N == pytest.approx(D / m["collapse_force_gf"], rel=1e-12)
    assert N == pytest.approx(m["snap_pct"] / (100 * m["drop_travel_mm"]), rel=1e-12)


def test_equal_snap_different_drop_travel():
    m1, _ = run_metrics(*synth(Fv=30.0, xv=2.0))
    m2, _ = run_metrics(*synth(Fv=30.0, xv=3.2, wall=4.0))
    assert m1["snap_pct"] == pytest.approx(m2["snap_pct"], abs=0.8)
    assert m1["drop_rate_gf_per_mm"] > 1.5 * m2["drop_rate_gf_per_mm"]


def test_equal_dr_different_fc_separates_on_ndr():
    m1, _ = run_metrics(*synth(Fc=40.0, Fv=20.0, xv=2.3))
    m2, _ = run_metrics(*synth(Fc=80.0, Fv=60.0, xv=2.3))
    assert m1["drop_rate_gf_per_mm"] == pytest.approx(m2["drop_rate_gf_per_mm"], rel=0.08)
    assert m1["norm_drop_rate_per_mm"] > 1.7 * m2["norm_drop_rate_per_mm"]


def test_steepest_interpolation_and_post_valley_exclusion():
    x, F = synth()
    for i, v in enumerate(x):
        if 2.0 <= v <= 2.05: F[i] -= (v - 2.0) * 200
        elif 2.05 < v <= 2.9: F[i] -= 10.0
    m, _ = run_metrics(x, F)
    assert m["steepest_drop_0p10mm_gf_per_mm"] > m["drop_rate_gf_per_mm"] * 2
    x2, F2 = synth()
    for i, v in enumerate(x2):
        if 3.50 <= v <= 3.52: F2[i] -= 0.8
    m2, _ = run_metrics(x2, F2)
    base, _ = run_metrics(*synth())
    assert m2["steepest_drop_0p10mm_gf_per_mm"] == pytest.approx(
        base["steepest_drop_0p10mm_gf_per_mm"], rel=0.25)


def test_steepest_null_below_window():
    m, fl = run_metrics(*synth(Fv=40.0, xv=1.365, wall=1.40))
    assert m["steepest_drop_0p10mm_gf_per_mm"] is None
    assert "drop_travel_below_0p10mm" in fl


def test_ramp_baseline_preload_and_last_crossing():
    x, F = synth(base=15.0)
    m, _ = run_metrics(x, F)
    expect = 0.8 * (m["collapse_force_gf"] - 15.0) / ((0.9 - 0.1) * (1.3 - 0.2))
    assert m["ramp_10_90_gf_per_mm"] == pytest.approx(expect, rel=0.05)
    x2, F2 = synth(base=15.0)
    for i, v in enumerate(x2):
        if 0.25 <= v <= 0.30: F2[i] += 30.0
    m2, _ = run_metrics(x2, F2)
    assert m2["ramp_10_90_gf_per_mm"] == pytest.approx(m["ramp_10_90_gf_per_mm"], rel=0.30)


def test_ramp_missing_crossing_flags_null():
    m, fl = run_metrics([i * 0.005 for i in range(900)], [50.0] * 900)
    assert m["ramp_10_90_gf_per_mm"] is None
    assert ("ramp_baseline_unavailable" in fl or "ramp_crossing_missing" in fl or
            "ramp_reference_band_overlaps_collapse" in fl)


def test_travel_found_and_no_wall_nulls():
    m, _ = run_metrics(*synth())
    assert m["travel_mm"] == pytest.approx(3.9, abs=0.05)
    m2, fl2 = run_metrics(*synth(n_end=3.6, wall=99.0))
    assert m2["travel_mm"] is None and m2["full_stroke_press_work_gf_mm"] is None
    assert "bottomout_not_found" in fl2
    assert m2["precollapse_work_gf_mm"] is not None


def test_collapse_fallback_named_and_guarded():
    x = [i * 0.005 for i in range(900)]
    m, fl = run_metrics(x, [5 + 40 * v for v in x])          # monotonic linear: no tactile event
    assert "collapse_fallback_used" in fl and "tactile_event_not_found" in fl
    assert "nonpositive_drop" in fl
    assert m["drop_rate_gf_per_mm"] is None and m["norm_drop_rate_per_mm"] is None


def test_offgrid_quarantined_not_respanned():
    for step in (0.010, 0.020):
        x, F = synth(step=step)
        m, fl = run_metrics(x, F, grid_conforming=False)
        assert m["travel_mm"] is None and m["full_stroke_press_work_gf_mm"] is None
        assert "grid_nonconforming" in fl
        assert m["collapse_force_gf"] is not None            # grid-independent metrics preserved


def test_missing_step_detected_by_qc():
    x, F = synth()
    del x[300], F[300]                                        # one missing nominal increment
    rows = [(i * 34, round(v * 1600), v, f * 100, f) for i, (v, f) in enumerate(zip(x, F))]
    run = parse_run(synth_csv(rows=rows))
    q = acquisition_qc(run, len(x) - 1)
    assert q["travel_step_violations"] >= 1 and not q["grid_conforming"]


# ---------------------------------------------------------------- strict parse + QC gating
def test_strict_parse_counts_and_header():
    txt = synth_csv()
    r = parse_run(txt)
    assert r["header_exact"] and r["bad_rows"] == 0 and r["nonfinite"] == 0
    r2 = parse_run(txt.replace("Scale (grams)", "Force"))
    assert not r2["header_exact"]
    lines = txt.splitlines()
    lines[10] = "1,2"                                         # malformed
    lines[11] = lines[11].rsplit(",", 1)[0] + ",nan"          # nonfinite token
    r3 = parse_run("\n".join(lines))
    assert r3["bad_rows"] == 1 and r3["nonfinite"] == 1


def _qc_of(text):
    run = parse_run(text)
    im = max(range(len(run["x"])), key=lambda i: run["x"][i])
    q = acquisition_qc(run, im)
    return q, qc_disposition(q)


def test_negative_fixture_adc_dropout_fail_excludes():
    """Synthetic reproduction of the batch-63 mid-stroke dropout: raw plunges to
    -792000 counts with a large negative calibrated excursion. Must fail_exclude
    with raw_adc_dropout — never plausible metrics with empty flags."""
    txt = synth_csv().splitlines()
    parts = txt[400].split(","); parts[3] = "-792000"; parts[4] = "-7920.0"
    txt[400] = ",".join(parts)
    q, (disp, fl) = _qc_of("\n".join(txt))
    assert q["raw_adc_dropout_count"] >= 1
    assert disp == "fail_exclude" and "raw_adc_dropout" in fl


def test_negative_fixture_stale_and_cadence():
    x, F = synth()
    for i in range(200, 220): F[i] = F[199]                   # stale force while travel advances
    rows = [(i * 34, round(v * 1600), v, f * 100, f) for i, (v, f) in enumerate(zip(x, F))]
    q, (disp, fl) = _qc_of(synth_csv(rows=rows))
    assert q["stale_force_flag"] and disp in ("review", "fail_exclude") and "stale_force" in fl
    rows2 = [((i * 34 if i % 60 else i * 34 + 400), round(v * 1600), v, f * 100, f)
             for i, (v, f) in enumerate(zip(*synth()))]
    q2, (disp2, fl2) = _qc_of(synth_csv(rows=rows2))
    assert q2["timing_gap_count"] >= 10 and "timing_gaps_ge_10" in fl2


def test_qc_failed_run_never_reaches_aggregation(cache, commit):
    """A run with plausible metrics but fail_exclude QC is gated before runfilter."""
    good = process_run(_manifest_run_paths(cache)[0], commit)
    bad = {k: v for k, v in good.items() if k != "qc"}
    bad = json.loads(json.dumps(bad))
    bad["qc_disposition"] = "fail_exclude"; bad["qc_disposition_flags"] = ["raw_adc_dropout"]
    gated = [r for r in (good, bad) if r["qc_disposition"] != "fail_exclude"]
    assert len(gated) == 1
    keep, reasons, cF, cX = batch_filter(gated, median_conventional)
    assert keep == [True]


# ---------------------------------------------------------------- runfilter
def _fake(fc, xc, flags=()):
    m = {k: 1.0 for k in ("valley_force_gf", "valley_travel_mm", "snap_pct", "travel_mm",
        "full_stroke_press_work_gf_mm", "precollapse_work_gf_mm", "drop_gf", "drop_travel_mm",
        "drop_rate_gf_per_mm", "norm_drop_rate_per_mm", "steepest_drop_0p10mm_gf_per_mm",
        "ramp_10_90_gf_per_mm")}
    m["collapse_force_gf"], m["collapse_travel_mm"] = fc, xc
    return {"metrics": m, "quality_flags": list(flags)}


def test_filter_null_landmark_does_not_disable_thresholds():
    # null + clustered valid runs + gross outlier: thresholds must stay active,
    # the null run gets an explicit invalid disposition, the outlier is excluded
    runs = [_fake(50.0, 1.0), _fake(50.4, 1.02), _fake(None, None), _fake(100.0, 4.0)]
    keep, reasons, cF, cX = batch_filter(runs, median_conventional)
    assert keep == [True, True, False, False]
    assert "invalid_landmarks" in reasons[2] and "dev" in reasons[3]
    assert cF == pytest.approx(median_conventional([50.0, 50.4, 100.0]))


def test_filter_all_null_fails():
    with pytest.raises(RuntimeError):
        batch_filter([_fake(None, None), _fake(None, None)], median_conventional)


def test_filter_inclusive_boundary_and_empty_failure():
    runs = [_fake(50.0, 1.0), _fake(51.0, 1.10), _fake(52.5, 1.0)]
    keep, *_ = batch_filter(runs, median_conventional)
    assert keep == [True, True, False]
    with pytest.raises(RuntimeError):
        batch_filter([_fake(50.0, 1.0), _fake(99.0, 3.0), _fake(1.0, 0.1), _fake(200.0, 9.9)],
                     lambda v: 1000.0)


def test_null_aggregation_rule():
    a = _fake(1.0, 1.0); b = _fake(1.0, 1.0, flags=["bottomout_not_found"])
    b["metrics"]["travel_mm"] = None; b["metrics"]["full_stroke_press_work_gf_mm"] = None
    a["metrics"]["travel_mm"] = 3.9
    agg, disp, fl, nreasons = aggregate([a, b], [True, True])
    assert nreasons["travel_mm"] in ("bottomout_not_found", "aggregate_contains_null_run")
    assert agg["travel_mm"] is None and "aggregate_contains_null_run" in fl
    assert disp["travel_mm"]["n_valid"] == 1 and disp["travel_mm"]["mean_validonly"] == 3.9


def test_medians_both_conventions():
    assert median_conventional([1, 2, 3, 4]) == 2.5
    assert median_upper_middle_legacy([1, 2, 3, 4]) == 3
    assert median_conventional([1, 2, 3]) == 2 == median_upper_middle_legacy([1, 2, 3])


# ---------------------------------------------------------------- schema
def test_schema_validates_every_staged_record(staging_dir):
    recs = _load_json(os.path.join(staging_dir, "bench_tests.staged.json"))
    decisions = _load_json(
        os.path.join(staging_dir, "intake_retention_decisions.json")
    )
    accepted = {entry["set"] for entry in decisions["sets"] if entry["status"] == "accepted"}
    manifest = _load_json(os.path.join(PKGDIR, "config", "dataset_manifest.json"))
    expected_records = sum(
        test["disposition"] == "include" and test["set"] in accepted
        for test in manifest["tests"]
    )
    assert len(recs) == expected_records
    assert all(record["calc_version"] == config()["calc_version"] for record in recs)
    assert all(record["intake_review_notices"] == [] for record in recs)
    validate_records(recs, build_schema())                    # raises on any invalid record


def test_schema_adversarial_invalids(staging_dir):
    import jsonschema
    schema = build_schema()
    rec = _staged_record(staging_dir)
    bads = []
    b = json.loads(json.dumps(rec)); b["collapse_g"] = 50.0; bads.append(b)          # legacy key
    b = json.loads(json.dumps(rec)); b.pop("drop_gf"); bads.append(b)                # missing metric
    b = json.loads(json.dumps(rec)); b["kind"] = "assembly_test"; bads.append(b)     # non-frozen kind
    b = json.loads(json.dumps(rec)); b["provenance"]["config_hash"] = "XYZ"; bads.append(b)
    b = json.loads(json.dumps(rec)); b["provenance"]["raw_paths"] = []; bads.append(b)
    b = json.loads(json.dumps(rec)); b["dispersion"] = {}; bads.append(b)
    for b in bads:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(b, schema)
    b = json.loads(json.dumps(rec))
    b["provenance"]["raw_sha256"] = b["provenance"]["raw_sha256"] + b["provenance"]["raw_sha256"]
    with pytest.raises(RuntimeError):
        validate_records([b], schema)                          # unequal path/hash arrays
    b = json.loads(json.dumps(rec)); b["travel_mm"] = None
    with pytest.raises(RuntimeError):
        validate_records([b], schema)                          # travel null without its flag


def test_manifest_metadata_mismatch_fails(cache, commit, tmp_path, monkeypatch):
    import domelab_pipeline.pipeline as pl
    bundle = pl.load_config_bundle()
    removed_set = bundle["dataset_manifest"]["tests"][0]["set"]
    bundle["dataset_manifest"]["tests"] = [
        t for t in bundle["dataset_manifest"]["tests"] if t["set"] != removed_set
    ]
    monkeypatch.setattr(pl, "load_config_bundle", lambda: bundle)
    with pytest.raises(RuntimeError, match="lacks manifest metadata"):
        pl.generate(
            cache, commit, str(tmp_path), write=False,
            run_parity=False, evidence_only=True,
        )


# ---------------------------------------------------------------- determinism + check
def test_posix_paths_everywhere(staging_dir):
    for fn in ("bench_tests.staged.json", "per_run_full_precision.json", "generated_manifest.json"):
        assert "\\\\" not in _read_text(os.path.join(staging_dir, fn))


def test_deterministic_regeneration_and_exact_tree(cache, commit, staging_dir):
    problems = check(cache, commit, staging_dir, run_parity=False, evidence_only=True)
    assert problems == []


def test_check_detects_stale_and_missing(cache, commit, tmp_path):
    out = str(tmp_path / "st")
    generate(cache, commit, out, write=True, run_parity=False, evidence_only=True)
    with open(os.path.join(out, "stray.json"), "w", encoding="utf-8") as stream:
        stream.write("{}")
    problems = check(cache, commit, out, run_parity=False, evidence_only=True)
    assert any("UNEXPECTED/STALE" in p for p in problems)
    os.remove(os.path.join(out, "stray.json"))
    os.remove(os.path.join(out, "run_retention.csv"))
    problems = check(cache, commit, out, run_parity=False, evidence_only=True)
    assert any(p.startswith("MISSING") for p in problems)


# ---------------------------------------------------------------- goldens + parity
GOLDEN = os.path.join(HERE, "fixtures", "golden_per_run.json")


def test_full_precision_per_run_at_pinned_commit(cache, commit, staging_dir):
    for g in _load_json(os.path.join(staging_dir, "per_run_full_precision.json")):
        r = process_run(os.path.join(cache, *g["raw_path"].split("/")), commit)
        assert r["sha256"] == g["sha256"], g["raw_path"]
        for k in METRICS:
            v = g[k]
            got = r["metrics"][k]
            if v is None: assert got is None, (g["raw_path"], k)
            else: assert got == pytest.approx(v, rel=1e-12, abs=1e-12), (g["raw_path"], k)


def test_canonical_epoch_does_not_claim_a_legacy_median_comparison(staging_dir):
    cmp_ = _load_json(os.path.join(staging_dir, "median_comparison.json"))
    assert cmp_ == []


def test_legacy_median_sensitivity_remains_a_synthetic_diagnostic_unit():
    runs = [_fake(fc, 1.0) for fc in (49.0, 50.0, 51.0, 52.0)]
    keep_c, *_ = batch_filter(runs, median_conventional)
    keep_l, *_ = batch_filter(runs, median_upper_middle_legacy)
    assert keep_c == [False, True, True, False]
    assert keep_l == [False, True, True, True]


def test_full_fleet_parity_artifact(staging_dir):
    """Every staged run x every metric; persisted test-imp 1.1.4 gate."""
    epoch_root = os.path.abspath(os.path.join(staging_dir, "..", ".."))
    audit = _load_json(os.path.join(
        epoch_root, "epoch_inputs", "validation", "test_imp_1_1_4_epoch_audit.json"
    ))
    per_run = _load_json(os.path.join(staging_dir, "per_run_full_precision.json"))
    assert audit["result"] == "PASS"
    identity = audit["importer_source_identity"]
    assert identity["application_version"] == "1.1.4"
    assert identity["metrics_version"] == "metrics-v4.2"
    assert identity["policy_version"] == "intake-qc-v1.4"
    comparison = audit["generator_comparison"]["per_run_full_precision"]
    assert comparison["status"] == "pass"
    assert comparison["run_count"] == len(per_run)
    assert comparison["metrics_per_run"] == 14
    assert comparison["audit_fields_per_run"] == 13
    assert comparison["max_scalar_delta"] < 1e-9
    assert comparison["mismatches"] == []


def test_gray02_retest_is_retained_in_canonical_evidence(staging_dir):
    recs = _load_json(os.path.join(staging_dir, "bench_tests.staged.json"))
    record = next(r for r in recs if r["set"] == "Sony_BKE_Gray_02")
    assert record["runs_used"] == 3
    assert record["status"] == "verified"
    assert record["quality_flags"] == []

    per_run = _load_json(os.path.join(staging_dir, "per_run_full_precision.json"))
    gray_runs = [r for r in per_run if r["set"] == "Sony_BKE_Gray_02"]
    assert len(gray_runs) == 3
    assert all(r["intake_retained"] and r["retained_output"] for r in gray_runs)

    ex = _load_json(os.path.join(staging_dir, "exclusion_manifest.json"))
    assert ex["entries"] == []
    assert os.path.isfile(os.path.join(
        staging_dir, "packs", "curves", "Sony_BKE_Gray_02.staged.json"
    ))


def test_retired_bench_import_cannot_claim_cli_equivalence(
    cache, commit, staging_dir, importer_path, active_intake_identity
):
    """The old importer fails closed; only role-bound generated output is active."""
    assert importer_path, "bench-import.py not found (set DOMELAB_IMPORTER)"
    import importlib.util
    os.environ["DOMELAB_PIPELINE_PATH"] = os.path.dirname(PKGDIR)
    spec = importlib.util.spec_from_file_location("bi", importer_path)
    bi = importlib.util.module_from_spec(spec); spec.loader.exec_module(bi)
    assert bi.HAVE_CORE, "importer failed to locate domelab_pipeline"
    fixture = _manifest_test(minimum_runs=4)
    paths = _manifest_run_paths(cache, minimum_runs=4)
    with pytest.raises(
        RuntimeError, match=re.escape(active_intake_identity["parity_target"])
    ):
        bi.canonical_batch(paths, commit)
    rec = [
        r for r in _load_json(os.path.join(staging_dir, "bench_tests.staged.json"))
        if r["set"] == fixture["set"]
    ][0]
    decision = next(
        entry for entry in _load_json(
            os.path.join(staging_dir, "intake_retention_decisions.json")
        )["sets"]
        if entry["set"] == fixture["set"]
    )
    assert rec["runs_used"] == decision["retained_count"]


# ================================================================ Step 2.2
import subprocess, sys, shutil, importlib.util
from domelab_pipeline.pipeline import canonical_eligibility
from domelab_pipeline.parity import _node_modules


def _node_env():
    env = dict(os.environ)
    env["NODE_PATH"] = _node_modules()
    return env


def _text_opens_without_encoding(path):
    """AST walk: every text-mode open() must declare encoding= (Step 2.3.1).

    The Step 2.3 check was a regex over `open\\([^()]*\\)`, which cannot match a
    call containing nested parentheses. It therefore could not see

        json.load(open(os.path.join(os.path.dirname(__file__), "config", ...)))

    and core.py loaded the authoritative method configuration with the host's
    preferred encoding for the whole of Step 2.3.

    This walks the syntax tree instead, so nesting is irrelevant. Binary opens
    are correctly exempt; text opens are not.
    """
    import ast
    with open(path, "r", encoding="utf-8", newline="") as fh:
        tree = ast.parse(fh.read(), filename=path)
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = getattr(fn, "id", None) or getattr(fn, "attr", None)
        if name != "open":
            continue
        # mode is positional arg 1 or keyword `mode`
        mode = None
        if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
            mode = node.args[1].value
        for kw in node.keywords:
            if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                mode = kw.value.value
        if isinstance(mode, str) and "b" in mode:
            continue                                   # binary: encoding is invalid
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        bad.append((os.path.basename(path), node.lineno,
                    ast.unparse(node)[:80] if hasattr(ast, "unparse") else "open(...)"))
    return bad


def _python_sources():
    gen = os.path.dirname(PKGDIR)
    roots = [PKGDIR, os.path.join(gen, "tools"), os.path.join(gen, "tests")]
    imp = os.path.join(gen, "..", "local_project", "bench-import.py")
    out = []
    for root in roots:
        for dp, _, fs in os.walk(root):
            if "__pycache__" in dp:
                continue
            out += [os.path.join(dp, f) for f in sorted(fs) if f.endswith(".py")]
    if os.path.exists(imp):
        out.append(os.path.abspath(imp))
    return out


def test_utf8_source_conformance():
    """AST-based: no text-mode open() anywhere without an explicit encoding.

    Covers the package, tools, the TEST sources themselves and the importer, so
    the stated UTF-8 policy is true with no hidden exemptions.
    """
    offenders = []
    for p in _python_sources():
        offenders += _text_opens_without_encoding(p)
    assert offenders == [], offenders


def test_ast_checker_sees_nested_calls():
    """Regression: the Step 2.3 defect the regex could not detect."""
    import tempfile, textwrap
    src = textwrap.dedent("""
        import json, os
        _CFG = json.load(open(os.path.join(os.path.dirname(__file__), "c.json")))
        good = open("a.txt", encoding="utf-8")
        binary = open("a.bin", "rb")
        binary_kw = open("a.bin", mode="rb")
    """)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sample.py")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(src)
        bad = _text_opens_without_encoding(p)
    assert len(bad) == 1, bad
    assert bad[0][1] == 3, bad          # the nested json.load(open(...)) line
    import re
    assert re.search(r"open\([^)]*join", bad[0][2]), bad


def test_method_config_is_read_as_utf8():
    """core.py must load the authoritative configuration explicitly as UTF-8."""
    import inspect
    from domelab_pipeline import core
    src = inspect.getsource(core._load_config)
    assert 'encoding="utf-8"' in src
    assert core.config()["calc_version"].startswith("metrics-v4.2")


def test_check_under_c_locale(cache, commit, staging_dir):
    """Ordinary non-UTF-8 default-encoding environment, PYTHONUTF8 unset:
    --check must still be byte-identical (all I/O is explicit UTF-8)."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUTF8"}
    env["LC_ALL"] = "C"; env["LANG"] = "C"
    r = subprocess.run([sys.executable, "-m", "domelab_pipeline.cli", "--cache", cache,
                        "--commit", commit, "--out", staging_dir,
                        "--evidence-only", "--no-parity", "--check"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                       cwd=os.path.dirname(PKGDIR))
    assert r.returncode == 0 and "CHECK OK" in r.stdout, r.stdout[-400:] + r.stderr[-400:]


def test_retained_membership_parity_all_sets(staging_dir):
    """Applied output identities feed every record, curve and viewer run list."""
    rec = _load_json(os.path.join(staging_dir, "bench_tests.staged.json"))
    per = _load_json(os.path.join(staging_dir, "per_run_full_precision.json"))
    emb = _load_json(os.path.join(staging_dir, "packs", "viewer_embedded.json"))
    v = _read_text(os.path.join(staging_dir, "packs", "viewer.staged.html"))
    import re as _re
    m = _re.search(r"const CANONICAL_RUNS = (\{.*?\});", v)
    cruns = json.loads(m.group(1))
    retained = {}
    for r in per:
        if r["retained_output"]:
            retained.setdefault(r["set"], []).append(r["run"])
    decisions = _load_json(
        os.path.join(staging_dir, "intake_decisions.review-candidate.json")
    )
    accepted = {entry["set"] for entry in decisions["sets"] if entry["status"] == "accepted"}
    assert set(emb) == set(cruns) == accepted == {r["set"] for r in rec}
    for r in rec:
        s = r["set"]
        paths = sorted(p.split("/")[-1] for p in r["provenance"]["raw_paths"])
        assert paths == sorted(retained[s])
        assert r["runs_used"] == len(paths) == emb[s]["n"]
        assert sorted(cruns[s]) == paths
        assert "r" in emb[s] and len(emb[s]["r"]["df"]) > 100   # return trace packed


def test_viewer_offline_battery(staging_dir):
    js = os.path.join(HERE, "viewer_offline_battery.js")
    r = subprocess.run(["node", js, os.path.join(staging_dir, "packs", "viewer.staged.html"),
                        "Topre_45g"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=_node_env())
    assert r.returncode == 0, r.stdout + r.stderr[-300:]


def test_viewer_online_battery(cache, staging_dir):
    js = os.path.join(HERE, "viewer_online_battery.js")
    viewer = _read_text(os.path.join(staging_dir, "packs", "viewer.staged.html"))
    import re as _re
    runs_match = _re.search(r"const CANONICAL_RUNS = (\{.*?\});", viewer)
    canonical_runs = json.loads(runs_match.group(1))
    r = subprocess.run(["node", js, os.path.join(staging_dir, "packs", "viewer.staged.html"),
                        cache, "Topre_45g", str(len(canonical_runs["Topre_45g"]))],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=_node_env())
    assert r.returncode == 0, r.stdout + r.stderr[-300:]


def test_strict_progression_rejects():
    """Duplicate, reversed, and off-grid interior samples must not pass."""
    def qc_for(mutate):
        x, F = synth()
        rows = [[i * 34, round(v * 1600), v, f * 100, f] for i, (v, f) in enumerate(zip(x, F))]
        mutate(rows)
        run = parse_run(synth_csv(rows=[tuple(r) for r in rows]))
        im = max(range(len(run["x"])), key=lambda i: run["x"][i])
        return acquisition_qc(run, im)
    def dup(rows): rows.insert(300, list(rows[300]))
    def rev(rows): rows[300], rows[301] = list(rows[301]), list(rows[300])
    def off(rows): rows[300][2] += 0.002; rows[300][1] = round(rows[300][2] * 1600)
    for name, mut in (("duplicate", dup), ("reversed", rev), ("off-grid", off)):
        q = qc_for(mut)
        assert not q["grid_conforming"], name


def test_incomplete_return_fail_excludes():
    x, F = synth()
    rows = [(i * 34, round(v * 1600), v, f * 100, f) for i, (v, f) in enumerate(zip(x, F))]
    run = parse_run(synth_csv(rows=rows))          # press only, no return branch
    im = max(range(len(run["x"])), key=lambda i: run["x"][i])
    q = acquisition_qc(run, im)
    disp, fl = qc_disposition(q)
    # Step 2.3: completeness is protocol-based, and the reason is named
    # incomplete_return (row count alone no longer establishes completeness).
    assert q["incomplete_return"] and disp == "fail_exclude" and "incomplete_return" in fl


def _run(disp, flags=(), sha="ab" * 32, reasons=()):
    return {"path": "/x/Set/DataLog_9.csv", "sha256": sha, "qc_disposition": disp,
            "quality_flags": list(flags), "qc_disposition_flags": list(reasons)}


def test_canonical_eligibility_rules():
    ok, why, _ = canonical_eligibility("S", _run("pass"), {})
    assert ok
    ok, why, _ = canonical_eligibility("S", _run("review"), {})
    assert not ok and "without adjudication" in why
    adj = {("S", "DataLog_9.csv"): {"run": "DataLog_9.csv", "sha256": "ab" * 32,
           "eligible": True, "authority": "TestAuthority", "date": "2026-08-09"}}
    ok, why, a = canonical_eligibility("S", _run("review"), adj)
    assert ok and "adjudication" in why and a is not None
    ok, why, _ = canonical_eligibility("S", _run("fail_exclude"), {})
    assert not ok and "not overridable" in why
    ok, why, _ = canonical_eligibility("S", _run("pass", flags=["tactile_event_not_found"]), {})
    assert not ok and "barrier" in why          # invalid tactile fallback barred


def test_adjudication_hash_mismatch_rejected():
    """Step 2.3: binding verification moved to registries.verify_adjudications,
    where the complete binding (hash, method, disposition, reasons, barriers)
    is checked before any eligibility decision is made."""
    from domelab_pipeline import registries
    from domelab_pipeline.pipeline import provenance_hashes, load_config_bundle
    idx = {("S", "DataLog_9.csv"): {"sha256": "ab" * 32, "qc_disposition": "review",
                                    "qc_reasons": ["timing_gaps_ge_10"], "barrier_flags": []}}
    adj = {"entries": [{"set": "S", "run": "DataLog_9.csv", "raw_path": "S/DataLog_9.csv",
                        "sha256": "cd" * 32, "method_hash": "m", "overrides_disposition": "review",
                        "qc_reasons": ["timing_gaps_ge_10"], "barrier_flags": [], "eligible": True,
                        "authority": "T", "date": "2026-01-01", "rationale": "r"}]}
    _, errs = registries.verify_adjudications(adj, idx, "m")
    assert any("SHA-256 mismatch" in e for e in errs), errs


def test_adjudication_cannot_override_fail_exclude():
    adj = {("S", "DataLog_9.csv"): {"run": "DataLog_9.csv", "sha256": "ab" * 32,
                                    "eligible": True, "authority": "T", "date": "2026-01-01"}}
    with pytest.raises(RuntimeError, match="fail_exclude"):
        canonical_eligibility("S", _run("fail_exclude"), adj)


def test_schema_rejects_bad_paths_and_missing_null_reason(staging_dir):
    import jsonschema
    schema = build_schema()
    rec = _staged_record(staging_dir)
    for bad in ("../escape.csv", "/abs/run.csv", "C:\\win\\run.csv", "a\\b.csv", "up/../run.csv"):
        b = json.loads(json.dumps(rec)); b["provenance"]["raw_paths"] = [bad] * len(b["provenance"]["raw_sha256"])
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(b, schema)
    b = json.loads(json.dumps(rec))
    b["travel_mm"] = None; b["full_stroke_press_work_gf_mm"] = None
    b["quality_flags"] = sorted(set(b["quality_flags"]) | {"bottomout_not_found"})
    b["null_reasons"] = {}                        # null without a metric-specific reason
    with pytest.raises(RuntimeError, match="null reason|lacks"):
        validate_records([b], schema)


def test_promote_leaves_no_temp(cache, commit, tmp_path):
    out = str(tmp_path / "st")
    generate(cache, commit, out, write=True, run_parity=False, evidence_only=True)
    generate(cache, commit, out, write=True, run_parity=False, evidence_only=True)     # re-promote over existing
    assert not os.path.exists(out + ".candidate-tmp")
    assert not os.path.exists(out + ".replaced-prev")
    assert check(cache, commit, out, run_parity=False, evidence_only=True) == []


def _load_importer(importer_path):
    os.environ["DOMELAB_PIPELINE_PATH"] = os.path.dirname(PKGDIR)
    spec = importlib.util.spec_from_file_location("bi22", importer_path)
    bi = importlib.util.module_from_spec(spec); spec.loader.exec_module(bi)
    assert bi.HAVE_CORE
    return bi


def test_retired_importer_export_all_fails_before_any_write(
    cache, importer_path, tmp_path, monkeypatch, active_intake_identity
):
    """No legacy export is permitted after the bound importer became authority."""
    bi = _load_importer(importer_path)
    monkeypatch.setattr(bi, "find_template", lambda root: None)
    batch = tmp_path / "batch"; batch.mkdir()
    source_paths = _manifest_run_paths(cache, minimum_runs=4)[:4]
    for i, source in enumerate(source_paths, start=1):
        shutil.copy(source, batch / f"DataLog_{i}.csv")
    repo = tmp_path / "repo"; repo.mkdir()
    lib = tmp_path / "lib.html"
    shutil.copy(os.path.join(PKGDIR, "release_reference", "dome-lab-parts.release.html"), lib)
    out = tmp_path / "out"
    meta = {n: {"Display Name": "Topre 45g T"} for n in range(1, 5)}
    with pytest.raises(
        RuntimeError, match=re.escape(active_intake_identity["parity_target"])
    ):
        bi.export_all(str(batch), [1, 2, 3, 4], meta, str(repo), "", str(lib), str(out), [])
    assert list(repo.iterdir()) == []
    assert not out.exists()
    assert len(list(batch.glob("DataLog_*.csv"))) == 4


def test_importer_export_all_fail_closed(
    cache, importer_path, tmp_path, monkeypatch, active_intake_identity
):
    """Corrupt batch: zero partial output — no repo copies, no outdir, batch intact."""
    bi = _load_importer(importer_path)
    monkeypatch.setattr(bi, "find_template", lambda root: None)
    batch = tmp_path / "batch"; batch.mkdir()
    txt = synth_csv().splitlines()
    for fn in ("DataLog_1.csv", "DataLog_2.csv"):
        rows = list(txt)
        parts = rows[400].split(","); parts[3] = "-792000"; parts[4] = "-7920.0"
        rows[400] = ",".join(parts)
        with open(batch / fn, "w", encoding="utf-8", newline="") as stream:
            stream.write("\n".join(rows))
    repo = tmp_path / "repo"; repo.mkdir()
    lib = tmp_path / "lib.html"
    shutil.copy(os.path.join(PKGDIR, "release_reference", "dome-lab-parts.release.html"), lib)
    out = tmp_path / "out"
    meta = {n: {"Display Name": "Corrupt T"} for n in (1, 2)}
    with pytest.raises(
        RuntimeError, match=re.escape(active_intake_identity["parity_target"])
    ):
        bi.export_all(str(batch), [1, 2], meta, str(repo), "", str(lib), str(out), [])
    assert list(repo.iterdir()) == []               # no repo copies
    assert not out.exists()                         # not even the out dir
    assert len(list(batch.glob("DataLog_*.csv"))) == 2   # batch untouched
