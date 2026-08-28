"""Step 2.3 adversarial acquisition QC.

Every case here was reproduced against the Step 2.2 generator first: the
turnaround jump, the partial return and the cropped stroke all PASSED, and a
malformed canonical row was silently dropped from the trajectory. Each test
exercises the real production path (core.parse_run -> core.split_press_return
-> qc.acquisition_qc -> qc.qc_disposition), not a stub.
"""
import csv
import os
import pytest

from domelab_pipeline.core import parse_run, split_press_return, config
from domelab_pipeline.qc import acquisition_qc, qc_disposition
from domelab_pipeline.pipeline import load_config_bundle

HDR = "Millis,Steps,Travel (mm),Scale raw,Scale (grams)"
STEP = 0.005
NSTEP = 8


def _force(x):
    """Smooth, monotone-ish synthetic force with a wall; no spurious spikes."""
    base = 8.0 + 12.0 * x
    if x > 3.0:
        base += 60.0 * (x - 3.0) ** 2
    return base


def rows_to_csv(rows, header=HDR):
    out = [header]
    for ms, st, x, F in rows:
        out.append(f"{ms},{st},{x:.3f},{int(round(F * 100))},{F:.2f}")
    return "\n".join(out) + "\n"


def build(press_start=0.005, press_end=4.400, ret_end=0.000,
          duplicate_turnaround=True, first_return_x=None, dt=34,
          return_stop=None):
    """Nominal-grid synthetic acquisition with explicit control of the join."""
    rows, ms = [], 0
    n = int(round((press_end - press_start) / STEP))
    xs = [round(press_start + i * STEP, 3) for i in range(n + 1)]
    for x in xs:
        rows.append((ms, int(round(x * 1600)), x, _force(x)))
        ms += dt
    if duplicate_turnaround and first_return_x is None:
        rows.append((ms, int(round(press_end * 1600)), press_end, _force(press_end)))
        ms += dt
        cur = round(press_end - STEP, 3)
    elif first_return_x is not None:
        cur = round(first_return_x, 3)
    else:
        cur = round(press_end - STEP, 3)
    stop = ret_end if return_stop is None else return_stop
    while cur >= stop - 1e-9:
        # hysteresis ramps in smoothly over 0.2 mm so the join carries no
        # artificial force step (an artefact would trip force_spikes and mask
        # the geometry defect each fixture is meant to isolate)
        frac = min(1.0, max(0.0, (press_end - cur) / 0.2))
        rows.append((ms, int(round(cur * 1600)), cur, _force(cur) * (1.0 - 0.28 * frac)))
        ms += dt
        cur = round(cur - STEP, 3)
    return rows_to_csv(rows)


def judge(text):
    r = parse_run(text)
    _, _, im = split_press_return(r["x"], r["F"])
    q = acquisition_qc(r, im)
    disp, flags = qc_disposition(q)
    return q, disp, flags


# ------------------------------------------------------------ control
def test_control_full_cycle_passes():
    q, disp, flags = judge(build())
    assert disp == "pass", (disp, flags)
    assert q["grid_conforming"]
    assert q["turnaround_documented_duplicate"]
    assert q["return_completion_conform"] and q["origin_zone_conform"]


# ------------------------------------------------------ turnaround (A)
def test_nonduplicate_turnaround_jump_fails():
    """Press ends 4.400, first return row 4.000: a 0.400 mm / 640-step jump.

    Step 2.2 skipped index im+1 unconditionally, so this passed silently.
    """
    q, disp, flags = judge(build(duplicate_turnaround=False, first_return_x=4.000))
    assert not q["turnaround_documented_duplicate"]
    assert q["invalid_turnaround"], q
    assert disp == "fail_exclude"
    assert "invalid_turnaround" in flags
    assert abs(q["turnaround_travel_delta_mm"] - (-0.400)) < 1e-9
    assert abs(q["turnaround_step_delta"] - (-640)) < 0.5


def test_missing_duplicate_turnaround_fails():
    """No duplicate max row: the join steps straight to -0.005 mm."""
    q, disp, flags = judge(build(duplicate_turnaround=False))
    assert not q["turnaround_documented_duplicate"]
    assert disp == "fail_exclude"
    assert "missing_duplicate_turnaround" in flags or "invalid_turnaround" in flags


def test_documented_duplicate_turnaround_is_exempt():
    q, disp, flags = judge(build(duplicate_turnaround=True))
    d = q["turnaround_detail"]
    assert all(d[k] for k in ("boundary_present", "consecutive_max_rows", "travel_identical",
                              "steps_identical", "is_expected_shared_maximum",
                              "phase_split_satisfied"))
    assert disp == "pass"


# -------------------------------------------------- partial return (B)
def test_partial_return_over_100_rows_fails():
    """>100 return rows but the return stops at 3.805 mm (13% travelled).

    Step 2.2's completeness test was `return_rows >= 100`, so this passed.
    """
    q, disp, flags = judge(build(return_stop=3.805))
    assert q["return_rows"] > 100, q["return_rows"]
    assert q["return_rows_supplementary_ok"] is True   # row count alone still "ok"
    assert not q["return_completion_conform"]
    assert disp == "fail_exclude"
    assert "incomplete_return" in flags


def test_return_completion_fraction_is_the_criterion():
    q, _, _ = judge(build())
    proto = config()["protocol"]
    assert q["return_completion_fraction"] >= proto["min_return_completion_fraction"]


def test_bad_return_endpoint_fails():
    """Return ends well outside the configured endpoint zone."""
    q, disp, flags = judge(build(return_stop=1.500))
    assert not q["endpoint_zone_conform"]
    assert disp == "fail_exclude"
    assert "bad_return_endpoint" in flags


# --------------------------------------------------- cropped stroke (C)
def test_cropped_mid_stroke_cycle_fails():
    """3.000 -> 4.400 -> 3.000 mm. Step 2.2 passed this on both checks."""
    q, disp, flags = judge(build(press_start=3.000, return_stop=3.000))
    assert not q["origin_zone_conform"]
    assert not q["press_span_conform"]
    assert not q["endpoint_zone_conform"]
    assert q["cropped_stroke"]
    assert disp == "fail_exclude"
    for f in ("bad_origin", "bad_return_endpoint", "cropped_stroke", "incomplete_press"):
        assert f in flags, (f, flags)


def test_bad_origin_alone_fails():
    q, disp, flags = judge(build(press_start=0.500, return_stop=0.000))
    assert not q["origin_zone_conform"]
    assert disp == "fail_exclude"
    assert "bad_origin" in flags


# ---------------------------------------------- parse / trajectory (D)
def test_malformed_row_fails_acquisition_integrity(cache):
    """A malformed row in a real canonical raw file must fail integrity,
    not be silently dropped from the trajectory."""
    raw_path = load_config_bundle()["dataset_manifest"]["tests"][0]["expected_runs"][0]["path"]
    p = os.path.join(cache, *raw_path.split("/"))
    with open(p, "rb") as f:
        good = f.read().decode("utf-8-sig")
    lines = good.replace("\r\n", "\n").split("\n")
    lines[500] = ",".join(lines[500].split(",")[:3])
    q, disp, flags = judge("\n".join(lines))
    assert q["malformed_rows"] == 1
    assert disp == "fail_exclude"
    assert "malformed_rows" in flags


def test_nonfinite_row_fails():
    rows = build()
    lines = rows.split("\n")
    parts = lines[400].split(",")
    parts[4] = "nan"
    lines[400] = ",".join(parts)
    q, disp, flags = judge("\n".join(lines))
    assert q["nonfinite_values"] == 1
    assert disp == "fail_exclude"
    assert "nonfinite_values" in flags


def test_header_mismatch_fails():
    q, disp, flags = judge(build().replace(HDR, "Millis,Steps,Travel,Raw,Grams", 1))
    assert not q["header_exact"]
    assert disp == "fail_exclude"
    assert "header_mismatch" in flags


def test_timestamp_nonmonotonicity_fails():
    lines = build().split("\n")
    parts = lines[300].split(",")
    parts[0] = lines[299].split(",")[0]
    lines[300] = ",".join(parts)
    q, disp, flags = judge("\n".join(lines))
    assert not q["millis_strictly_increasing"]
    assert disp == "fail_exclude"
    assert "timestamp_nonmonotonic" in flags


def test_duplicate_interior_sample_detected():
    lines = build().split("\n")
    lines.insert(300, lines[300])
    q, disp, flags = judge("\n".join(lines))
    assert q["travel_step_violations"] > 0
    assert not q["grid_conforming"]
    assert "grid_nonconforming" in flags


def test_missing_interior_sample_detected():
    lines = build().split("\n")
    del lines[300]
    q, _, flags = judge("\n".join(lines))
    assert q["travel_step_violations"] > 0
    assert "grid_nonconforming" in flags


def test_reversed_interior_sample_detected():
    lines = build().split("\n")
    lines[300], lines[301] = lines[301], lines[300]
    q, disp, flags = judge("\n".join(lines))
    assert not q["grid_conforming"]


def test_offgrid_sample_detected():
    lines = build().split("\n")
    parts = lines[300].split(",")
    parts[2] = f"{float(parts[2]) + 0.0013:.4f}"
    lines[300] = ",".join(parts)
    q, _, flags = judge("\n".join(lines))
    assert q["travel_step_violations"] > 0 or q["travel_steps_ratio_violations"] > 0
    assert not q["grid_conforming"]


# ------------------------------------------------------------ cadence (E)
def test_cadence_nonconformance_is_review_never_automatic_acceptance():
    q, disp, flags = judge(build(dt=200))          # far slower than the cohort
    assert not q["rate_cohort_conform"]
    assert disp == "review"
    assert "rate_cohort_nonconform" in flags
    assert disp not in ("pass", "pass_with_offset_note")


def test_cadence_policy_is_declared_in_config():
    pol = config()["qc_dispositions"]["cadence_policy"]
    assert "review/retest" in pol and "adjudication" in pol


# --------------------------------------------------- fleet non-regression
def test_every_pinned_run_matches_canonical_evidence_disposition(cache, staging_dir):
    """Every frozen run must reproduce its staged diagnostic disposition."""
    with open(os.path.join(staging_dir, "acquisition_qc.csv"), encoding="utf-8", newline="") as f:
        expected = {row["raw_path"]: row["qc_disposition"] for row in csv.DictReader(f)}
    actual = {}
    for s in sorted(os.listdir(cache)):
        d = os.path.join(cache, s)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(".csv"):
                continue
            with open(os.path.join(d, fn), "rb") as f:
                _, disp, _ = judge(f.read().decode("utf-8-sig", "replace"))
            actual[f"{s}/{fn}"] = disp
    assert actual == expected


def test_thresholds_come_from_config_not_hardcoded():
    proto = config()["protocol"]
    for k in ("origin_zone_mm", "return_endpoint_zone_mm", "min_press_span_mm",
              "min_return_span_mm", "min_return_completion_fraction"):
        assert isinstance(proto[k], (int, float))
    sensitivity = proto["sensitivity"]
    assert set(sensitivity) == {"scope", "evidence_location", "conclusion_rule"}
    assert sensitivity["evidence_location"] == "epoch acceptance artifacts"
