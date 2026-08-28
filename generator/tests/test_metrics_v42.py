"""metrics-v4.2 method-domain, audit-evidence and algebra regressions."""
import copy
import ast
import inspect
import json
import os
import shutil
import subprocess
import tempfile

import pytest

from domelab_pipeline.core import (config, ramp_metric, run_metrics,
                                   validate_per_run_algebra)
from domelab_pipeline import core
from domelab_pipeline.reference_js import js_reference_analyzer_source


def _ramp_case(x, force, peak=None, ramp_config=None):
    peak = len(x) - 1 if peak is None else peak
    return ramp_metric(x, force, peak, force[peak], x[peak], ramp_config)


def _boundary_config():
    # Isolate the post-seating coordinate boundary from the production
    # reference-band geometry. With the production band beginning at xs and a
    # last-crossing rule, a median below T10 mathematically entails a later
    # recrossing; this configured subcase tests the inclusive boundary itself.
    c = copy.deepcopy(config()["ramp"])
    c.update(reference_band_low_mm=0.0, reference_band_high_mm=0.04,
             minimum_band_samples=3)
    return c


def test_one_authoritative_python_ramp_path():
    tree = ast.parse(inspect.getsource(core))
    defs = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert defs.count("ramp_metric") == 1
    assert not any(n in ("_ramp", "_ramp_metric", "calculate_ramp", "_calculate_ramp") for n in defs)
    src = inspect.getsource(run_metrics)
    assert src.count("ramp_metric(") == 1


def test_ramp_exact_crossing_at_seating_boundary_passes():
    x = [0.0, 0.02, 0.04, 0.05, 0.13, 0.20]
    F = [0, 0, 0, 10, 90, 100]
    value, flags, audit = _ramp_case(x, F, ramp_config=_boundary_config())
    assert value is not None and flags == []
    assert audit["ramp_x10_mm"] == pytest.approx(0.05)
    assert audit["ramp_x90_mm"] == pytest.approx(0.13)


def test_ramp_crossing_below_seating_is_ineligible():
    x = [0.0, 0.02, 0.04, 0.13, 0.20]
    F = [0, 0, 10, 90, 100]
    value, flags, audit = _ramp_case(x, F, ramp_config=_boundary_config())
    assert value is None and flags == ["ramp_crossing_missing"]
    assert audit["ramp_x10_cross_count"] == 1
    assert audit["ramp_x10_eligible_cross_count"] == 0


def test_ramp_segment_straddling_seating_uses_interpolated_coordinate():
    # No knot at xs. The low-threshold segment straddles it and interpolates to
    # an eligible coordinate above xs.
    x = [0.0, 0.02, 0.04, 0.049, 0.051, 0.13, 0.20]
    F = [0, 0, 0, 9, 11, 90, 100]
    value, flags, audit = _ramp_case(x, F, ramp_config=_boundary_config())
    assert value is not None and flags == []
    assert audit["ramp_x10_mm"] == pytest.approx(0.05)


def test_ramp_later_eligible_recrossing_wins():
    x = [0, .025, .05, .075, .10, .125, .15, .16, .17, .18, .19, .20]
    F = [0, 0, 10, 40, 8, 20, 70, 95, 60, 95, 98, 100]
    value, flags, audit = _ramp_case(x, F)
    assert value is not None and flags == []
    assert audit["ramp_x10_eligible_cross_count"] >= 2
    assert audit["ramp_x90_eligible_cross_count"] >= 2
    assert audit["ramp_x10_mm"] > 0.10
    assert audit["ramp_x90_mm"] > 0.17


@pytest.mark.parametrize("xc", [0.15, 0.1500000005])
def test_ramp_collapse_at_or_within_tolerance_of_band_high_is_named_null(xc):
    x = [0.0, .025, .05, .075, .10, .125, .15, xc]
    F = [0, 0, 5, 15, 30, 50, 80, 100]
    value, flags, _ = ramp_metric(x, F, len(x) - 1, F[-1], xc)
    assert value is None
    assert flags == ["ramp_reference_band_overlaps_collapse"]


def test_ramp_incomplete_band_has_distinct_exact_reason_and_trace_span_semantics():
    x = [0.06, .08, .10, .12, .14, .20]
    F = [0, 5, 10, 20, 40, 100]
    value, flags, audit = _ramp_case(x, F)
    assert value is None
    assert flags == ["ramp_baseline_band_incomplete"]
    assert audit["ramp_band_sample_count"] >= config()["ramp"]["minimum_band_samples"]
    assert audit["ramp_band_complete"] is False


def test_ramp_too_few_band_samples_is_unavailable_not_incomplete():
    x = [0.0, .05, .15, .20]
    F = [0, 0, 70, 100]
    value, flags, audit = _ramp_case(x, F)
    assert value is None
    assert flags == ["ramp_baseline_unavailable"]
    assert audit["ramp_band_complete"] is True
    assert audit["ramp_band_sample_count"] == 2


def test_ramp_insufficient_span_named_null():
    c = copy.deepcopy(config()["ramp"])
    c["min_span_mm"] = 0.03
    x = [0, .05, .10, .15, .16, .17, .18, .20]
    F = [0, 0, 0, 0, 10, 90, 100, 100]
    value, flags, _ = ramp_metric(x, F, len(x) - 1, F[-1], x[-1], c)
    assert value is None and flags == ["ramp_span_too_small"]


def test_per_run_algebra_validator_rejects_each_corrupted_drop_family_field():
    x = [i * .005 for i in range(881)]
    F = []
    for v in x:
        if v <= .2: f = 10
        elif v <= 1.3: f = 10 + 50 * (v - .2) / 1.1
        elif v <= 2.9: f = 60 - 35 * (v - 1.3) / 1.6
        elif v <= 3.9: f = 25 + 2 * (v - 2.9)
        else: f = 27 + 900 * (v - 3.9)
        F.append(f)
    metrics, flags, audit = run_metrics(x, F, return_audit=True)
    validate_per_run_algebra(metrics, audit, flags)
    for field in ("drop_gf", "drop_travel_mm", "snap_pct",
                  "drop_rate_gf_per_mm", "norm_drop_rate_per_mm"):
        bad = dict(metrics); bad[field] *= 1.2
        with pytest.raises(RuntimeError, match="per-run algebra"):
            validate_per_run_algebra(bad, audit, flags)


def test_no_wall_audit_is_null_and_never_substitutes_final_sample():
    x = [i * .005 for i in range(721)]
    F = [10 + min(v, 1.3) * 30 if v <= 1.3 else 49 - min(v - 1.3, 1.5) * 20 for v in x]
    metrics, flags, audit = run_metrics(x, F, return_audit=True)
    assert metrics["travel_mm"] is None
    assert metrics["full_stroke_press_work_gf_mm"] is None
    assert audit["force_wall_found"] is False
    assert audit["force_wall_travel_mm"] is None
    assert "bottomout_not_found" in flags


def _full_curve(*, start=0.0, xc=1.3, wall=3.9, end=4.4):
    x, F, v = [], [], start
    xv, Fc, Fv, base = max(xc + .30, 2.9), 60.0, 25.0, 10.0
    while v <= end + 1e-12:
        if v <= .2: f = base
        elif v <= xc: f = base + (Fc - base) * (v - .2) / max(xc - .2, .001)
        elif v <= xv: f = Fc + (Fv - Fc) * (v - xc) / (xv - xc)
        elif v <= wall: f = Fv + 2.0 * (v - xv)
        else: f = Fv + 2.0 * (wall - xv) + 900.0 * (v - wall)
        x.append(round(v, 6)); F.append(f); v += .005
    return x, F


@pytest.mark.parametrize("mutation", [
    "wall_false_with_numeric_values", "wall_work_null_mismatch", "wall_null_without_reason",
    "ramp_null_without_reason", "ramp_numeric_with_null_flag", "ramp_reason_audit_mismatch",
    "ramp_coordinate_count_mismatch", "steep_null_without_reason", "steep_numeric_with_null_flag",
    "positive_rate_is_null", "positive_domain_flag_leak", "missing_audit_field",
    "terminal_flag_with_landmarks", "terminal_null_without_reason",
])
def test_per_run_coherence_mutations_fail_closed(mutation):
    x, F = _full_curve()
    metrics, flags, audit = run_metrics(x, F, return_audit=True)
    metrics, flags, audit = dict(metrics), list(flags), dict(audit)
    if mutation == "wall_false_with_numeric_values":
        audit["force_wall_found"] = False
    elif mutation == "wall_work_null_mismatch":
        metrics["full_stroke_press_work_gf_mm"] = None
    elif mutation == "wall_null_without_reason":
        audit["force_wall_found"] = False
        audit["force_wall_travel_mm"] = None
        metrics["travel_mm"] = None
        metrics["full_stroke_press_work_gf_mm"] = None
    elif mutation == "ramp_null_without_reason":
        metrics["ramp_10_90_gf_per_mm"] = None
    elif mutation == "ramp_numeric_with_null_flag":
        flags.append("ramp_crossing_missing")
    elif mutation == "ramp_reason_audit_mismatch":
        metrics["ramp_10_90_gf_per_mm"] = None
        flags.append("ramp_crossing_missing")
    elif mutation == "ramp_coordinate_count_mismatch":
        audit["ramp_x10_eligible_cross_count"] = 0
    elif mutation == "steep_null_without_reason":
        metrics["steepest_drop_0p10mm_gf_per_mm"] = None
        audit["steepest_drop_start_mm"] = None
        audit["steepest_drop_end_mm"] = None
    elif mutation == "steep_numeric_with_null_flag":
        flags.append("drop_travel_below_0p10mm")
    elif mutation == "positive_rate_is_null":
        metrics["drop_rate_gf_per_mm"] = None
    elif mutation == "positive_domain_flag_leak":
        flags.append("nonpositive_drop")
    elif mutation == "missing_audit_field":
        del audit["ramp_band_sample_count"]
    elif mutation == "terminal_flag_with_landmarks":
        flags.append("valley_not_found")
    elif mutation == "terminal_null_without_reason":
        metrics = {k: None for k in metrics}
        audit = {k: None for k in core.PER_RUN_AUDIT_FIELDS}
        audit.update(force_wall_found=False, ramp_x10_cross_count=0, ramp_x90_cross_count=0,
                     ramp_x10_eligible_cross_count=0, ramp_x90_eligible_cross_count=0,
                     ramp_band_sample_count=0, ramp_band_complete=False)
        flags = []
    with pytest.raises(RuntimeError, match="per-run algebra validation failed"):
        validate_per_run_algebra(metrics, audit, flags)


def test_reference_js_exact_null_flag_and_audit_edge_parity():
    node = shutil.which("node")
    assert node, "Node is required for the generated-reference parity gate"
    cases = []
    for x, F, grid in (
        (*_full_curve(), True),
        (*_full_curve(wall=99.0, end=3.6), True),
        (*_full_curve(), False),
        (*_full_curve(start=.06), True),
        (*_full_curve(xc=.14, wall=3.4), True),
    ):
        metrics, flags, audit = run_metrics(x, F, grid_conforming=grid, return_audit=True)
        cases.append({"x": x, "F": F, "grid": grid, "python": [metrics, flags, audit]})
    js = """const fs=require('fs');
function movAvg(F,k){const n=F.length,out=new Float64Array(n),h=Math.floor(k/2);
for(let i=0;i<n;i++){let s=0,c=0;for(let j=i-h;j<=i+h;j++)if(j>=0&&j<n){s+=F[j];c++;}out[i]=s/c;}return out;}
""" + js_reference_analyzer_source() + "\n" + (
        "const cs=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify(cs.map(c=>analyze(c.x,c.F,c.grid))));")
    payload = json.dumps([{k: c[k] for k in ("x", "F", "grid")} for c in cases], separators=(",", ":"))
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "edge-parity.js")
        data_path = os.path.join(td, "edge-cases.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh: fh.write(js)
        with open(data_path, "w", encoding="utf-8", newline="\n") as fh: fh.write(payload)
        proc = subprocess.run([node, path, data_path], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    pairs = {"collapse_force_gf": "Fpeak", "collapse_travel_mm": "xpeak",
             "valley_force_gf": "Fval", "valley_travel_mm": "xval", "snap_pct": "snap",
             "travel_mm": "travel", "full_stroke_press_work_gf_mm": "E",
             "precollapse_work_gf_mm": "Epc", "drop_gf": "dropF", "drop_travel_mm": "dropX",
             "drop_rate_gf_per_mm": "dropRate", "norm_drop_rate_per_mm": "ndr",
             "steepest_drop_0p10mm_gf_per_mm": "steep", "ramp_10_90_gf_per_mm": "ramp"}
    for expected_case, actual in zip(cases, got):
        metrics, flags, audit = expected_case["python"]
        assert actual["flags"] == flags
        for pk, jk in pairs.items():
            if metrics[pk] is None: assert actual[jk] is None, pk
            else: assert actual[jk] == pytest.approx(metrics[pk], rel=0, abs=1e-12), pk
        for key in core.PER_RUN_AUDIT_FIELDS:
            if key in {"force_wall_found", "ramp_band_complete"}:
                assert type(actual["audit"][key]) is bool and type(audit[key]) is bool
                assert actual["audit"][key] == audit[key], key
            elif key.endswith("_count"):
                assert type(actual["audit"][key]) is int and type(audit[key]) is int
                assert actual["audit"][key] == audit[key], key
            elif audit[key] is None: assert actual["audit"][key] is None, key
            else: assert actual["audit"][key] == pytest.approx(audit[key], rel=0, abs=1e-12), key
