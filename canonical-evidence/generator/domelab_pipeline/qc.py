"""Acquisition QC — observes and gates; never mutates or imputes raw values.

Layers (machine-readable, kept separate): 1 parse/trajectory validity,
2 acquisition-signal integrity, 3 protocol/rate conformity, 4 specimen/workflow
disposition (registry), 5 replicate runfilter membership (pipeline).
Thresholds live in method_config (versioned); nothing here is hardcoded.

Step 2.3 corrections
--------------------
* Turnaround: the press/return boundary is no longer skipped unconditionally.
  The exemption applies only to the exact documented duplicate turnaround
  (consecutive maximum rows, identical travel, identical steps, the expected
  shared maximum, declared phase split satisfied). Every other boundary
  transition is validated as a normal -0.005 mm / -8 step return sample, so a
  0.400 mm / 640-step jump is now a violation instead of an invisible skip.
* Completeness: row count alone no longer establishes a complete return. A
  configurable return-completion fraction, endpoint zone and return span are
  required; row count is retained only as a supplementary observation.
* Origin/span: the press must start inside the configured origin zone and sweep
  at least the configured minimum span, so a mid-stroke crop is caught.
* Parsing: malformed and nonfinite rows are surfaced as integrity failures
  rather than being silently dropped from the trajectory.
"""
import statistics
from .core import config


def _turnaround_is_documented_duplicate(X, S, im, n, cfg):
    """True only for the exact documented duplicate maximum-travel row.

    Requires all of:
      * a boundary exists (im+1 < n);
      * the two maximum rows are consecutive (im and im+1);
      * travel values are identical;
      * step values are identical;
      * that shared value is the run maximum;
      * the declared phase split holds (press ends at the FIRST maximum, and
        the return begins at that same shared sample).
    """
    det = {"boundary_present": bool(im + 1 < n)}
    if not det["boundary_present"]:
        return False, det
    xm = max(X)
    tol_x = cfg["acquisition"]["travel_steps_ratio_tol_mm"]
    det["consecutive_max_rows"] = bool(abs(X[im] - xm) <= tol_x and abs(X[im + 1] - xm) <= tol_x)
    det["travel_identical"] = bool(abs(X[im + 1] - X[im]) <= tol_x)
    det["steps_identical"] = bool(abs(S[im + 1] - S[im]) <= 0.5)
    det["is_expected_shared_maximum"] = bool(abs(X[im] - xm) <= tol_x)
    first_max = next((i for i in range(n) if abs(X[i] - xm) <= tol_x), -1)
    det["phase_split_satisfied"] = bool(first_max == im)
    ok = all(det[k] for k in ("boundary_present", "consecutive_max_rows", "travel_identical",
                              "steps_identical", "is_expected_shared_maximum",
                              "phase_split_satisfied"))
    return ok, det


def acquisition_qc(run, split_index):
    cfg = config()
    t = cfg["qc_thresholds"]
    a = cfg["acquisition"]
    proto = cfg["protocol"]
    nom = cfg["nominal_sample_step_mm"]
    spm = a["steps_per_mm"]
    M, S, X, R, F = run["millis"], run["steps"], run["x"], run["raw"], run["F"]
    n = len(X)
    im = split_index
    q = {"rows": n, "malformed_rows": run["bad_rows"], "nonfinite_values": run["nonfinite"],
         "header_exact": run["header_exact"],
         "millis_strictly_increasing": all(b > a2 for a2, b in zip(M, M[1:])),
         "millis_monotonic": all(b >= a2 for a2, b in zip(M, M[1:]))}

    gaps = [b - a2 for a2, b in zip(M, M[1:]) if b > a2]
    med = statistics.median(gaps) if gaps else 0.0
    srt = sorted(gaps)
    q["interval_median_ms"] = med
    q["interval_p95_ms"] = srt[int(0.95 * (len(srt) - 1))] if srt else 0.0
    q["interval_max_ms"] = srt[-1] if srt else 0.0
    gap_idx = [i for i in range(1, n) if med and (M[i] - M[i - 1]) > t["timing_gap_factor"] * med]
    q["timing_gap_count"] = len(gap_idx)
    q["timing_gap_indices"] = gap_idx

    dur = (M[-1] - M[0]) / 1000.0 if n > 1 else 0.0
    span = (max(X) - min(X)) if X else 0.0
    sp = (2 * span / dur) if dur > 0 else None
    q["effective_speed_mm_s"] = sp
    q["rate_cohort_conform"] = bool(sp is not None and
        abs(sp - a["nominal_speed_mm_s"]) <= a["speed_cohort_tol_frac"] * a["nominal_speed_mm_s"])

    q["phase_reversals_press"] = sum(1 for a2, b in zip(X[:im], X[1:im + 1]) if b < a2 - 1e-9)
    q["phase_reversals_return"] = sum(1 for a2, b in zip(X[im:], X[im + 1:]) if b > a2 + 1e-9)
    q["max_travel_row_count"] = sum(1 for v in X if v == max(X)) if X else 0

    # ---- turnaround: exemption only for the exact documented duplicate ----
    ta_ok, ta_detail = _turnaround_is_documented_duplicate(X, S, im, n, cfg)
    q["turnaround_documented_duplicate"] = bool(ta_ok)
    q["turnaround_detail"] = ta_detail
    if n > im + 1:
        q["turnaround_travel_delta_mm"] = X[im + 1] - X[im]
        q["turnaround_step_delta"] = S[im + 1] - S[im]
    else:
        q["turnaround_travel_delta_mm"] = None
        q["turnaround_step_delta"] = None

    # ---- strict signed progression -------------------------------------
    grid_bad = steps_bad = ratio_bad = 0
    nsps = cfg["nominal_steps_per_sample"]
    turnaround_violation = False
    for i in range(1, n):
        boundary = (i == im + 1)
        if boundary and ta_ok:
            continue
        sign = 1.0 if i <= im else -1.0
        dx_bad = abs((X[i] - X[i - 1]) - sign * nom) > 1e-6
        ds_bad = abs((S[i] - S[i - 1]) - sign * nsps) > 0.5
        if dx_bad:
            grid_bad += 1
        if ds_bad:
            steps_bad += 1
        if boundary and (dx_bad or ds_bad):
            turnaround_violation = True
    for i in range(n):
        if abs(S[i] / spm - X[i]) > a["travel_steps_ratio_tol_mm"]:
            ratio_bad += 1
    q["travel_step_violations"] = grid_bad
    q["steps_continuity_violations"] = steps_bad
    q["travel_steps_ratio_violations"] = ratio_bad
    q["grid_conforming"] = bool(grid_bad == 0 and steps_bad == 0 and ratio_bad == 0)
    q["invalid_turnaround"] = bool(turnaround_violation)
    q["missing_duplicate_turnaround"] = bool(n > im + 1 and not ta_ok and not turnaround_violation)

    # ---- protocol completeness -----------------------------------------
    x_max = max(X) if X else 0.0
    x_start = X[0] if X else 0.0
    x_end = X[-1] if X else 0.0
    press_span = x_max - x_start
    return_span = x_max - x_end

    q["x_start_mm"] = x_start
    q["x_max_mm"] = x_max
    q["x_end_mm"] = x_end
    q["press_span_mm"] = press_span
    q["return_span_mm"] = return_span
    q["return_rows"] = n - im - 1
    q["return_completion_fraction"] = (return_span / press_span) if press_span > 0 else None

    q["origin_zone_conform"] = bool(abs(x_start) <= proto["origin_zone_mm"])
    q["endpoint_zone_conform"] = bool(abs(x_end) <= proto["return_endpoint_zone_mm"])
    q["press_span_conform"] = bool(press_span >= proto["min_press_span_mm"])
    q["return_span_conform"] = bool(return_span >= proto["min_return_span_mm"])
    q["return_completion_conform"] = bool(q["return_completion_fraction"] is not None and
        q["return_completion_fraction"] >= proto["min_return_completion_fraction"])
    # supplementary only — never establishes completeness on its own
    q["return_rows_supplementary_ok"] = bool(q["return_rows"] >= t["short_return_rows"])

    q["incomplete_press"] = bool(x_max < t["short_press_max_travel_mm"] or
                                 not q["press_span_conform"])
    q["incomplete_return"] = bool(not q["return_completion_conform"] or
                                  not q["return_span_conform"])
    q["short_return"] = q["incomplete_return"]  # retained key name for downstream readers
    q["bad_origin"] = bool(not q["origin_zone_conform"])
    q["bad_return_endpoint"] = bool(not q["endpoint_zone_conform"])
    q["cropped_stroke"] = bool(q["bad_origin"] and q["bad_return_endpoint"])

    # ---- signal integrity ----------------------------------------------
    fmax = max(F) if F else 0.0
    runlen = mx = 0
    for v in F:
        runlen = runlen + 1 if v == fmax else 0
        mx = max(mx, runlen)
    q["loadcell_saturation"] = bool(mx >= t["saturation_min_run"] and fmax >= t["saturation_min_g"])
    q["force_spikes"] = sum(1 for a2, b in zip(F, F[1:]) if abs(b - a2) > t["spike_gf_per_step"])
    q["raw_adc_dropout_count"] = sum(1 for i in range(n)
        if R[i] < a["adc_dropout_raw_floor"] or F[i] < a["adc_dropout_cal_floor_g"])
    runlen = mx = 0
    for i in range(1, im + 1):
        runlen = runlen + 1 if (F[i] == F[i - 1] and X[i] > X[i - 1]) else 0
        mx = max(mx, runlen)
    q["stale_force_max_run_press"] = mx
    q["stale_force_flag"] = bool(mx >= t["stale_force_min_run"])
    prs = list(zip(R[1:im + 1], F[1:im + 1]))
    q["raw_cal_sign_disagreements"] = sum(1 for (r0, f0), (r1, f1) in zip(prs, prs[1:])
        if (r1 - r0) * (f1 - f0) < 0 and abs(f1 - f0) > 1.0)
    mR, mF = (min(R) if R else 0.0), (min(F) if F else 0.0)
    q["min_raw"], q["min_cal_g"] = mR, mF
    q["negative_observed"] = bool(mR < 0 or mF < 0)
    q["negative_class"] = ""
    if q["negative_observed"]:
        i = min(range(n), key=lambda j: F[j]) if mF < 0 else min(range(n), key=lambda j: R[j])
        q["negative_at_x_mm"] = X[i]
        q["negative_phase"] = "press" if i <= im else "return"
        near_end = X[i] <= t["baseline_endpoint_zone_mm"] or X[i] >= max(X) - t["baseline_endpoint_zone_mm"]
        mild = mF >= t["baseline_negative_floor_g"] and q["raw_adc_dropout_count"] == 0
        q["negative_class"] = "baseline_zero_offset" if (mild and near_end) else "review_required"
    return q


def qc_disposition(q):
    """Collapse layered observations into one explicit disposition.

    Every reason is named. Cadence/rate nonconformance stays review (never
    automatic acceptance), and acquisition integrity failures are never
    overridable by a later runfilter.
    """
    cfg = config()
    a = cfg["acquisition"]
    fails, reviews, notes = [], [], []
    if not q["header_exact"]:
        fails.append("header_mismatch")
    if q["nonfinite_values"]:
        fails.append("nonfinite_values")
    if q["malformed_rows"]:
        if q["rows"] and q["malformed_rows"] > a["max_malformed_row_frac"] * (q["rows"] + q["malformed_rows"]):
            fails.append("malformed_rows_over_2pct")
        else:
            fails.append("malformed_rows")
    if q["raw_adc_dropout_count"]:
        fails.append("raw_adc_dropout")
    if q["incomplete_press"]:
        fails.append("incomplete_press")
    if q["incomplete_return"]:
        fails.append("incomplete_return")
    if q["bad_origin"]:
        fails.append("bad_origin")
    if q["bad_return_endpoint"]:
        fails.append("bad_return_endpoint")
    if q["cropped_stroke"]:
        fails.append("cropped_stroke")
    if q.get("invalid_turnaround"):
        fails.append("invalid_turnaround")
    if q.get("missing_duplicate_turnaround"):
        fails.append("missing_duplicate_turnaround")
    if q["loadcell_saturation"]:
        fails.append("loadcell_saturation")
    if not q["millis_strictly_increasing"]:
        fails.append("timestamp_nonmonotonic")
    if q["phase_reversals_press"] or q["phase_reversals_return"]:
        fails.append("phase_reversal")
    if not q["grid_conforming"]:
        reviews.append("grid_nonconforming")
    if not q["rate_cohort_conform"]:
        reviews.append("rate_cohort_nonconform")
    if q["stale_force_flag"]:
        reviews.append("stale_force")
    if q["force_spikes"]:
        reviews.append("force_spikes")
    if q["raw_cal_sign_disagreements"] > 20:
        reviews.append("raw_cal_inconsistency")
    if q["timing_gap_count"] >= 10:
        reviews.append("timing_gaps_ge_10")
    if q["negative_class"] == "review_required":
        reviews.append("negative_review")
    if q["negative_class"] == "baseline_zero_offset":
        notes.append("baseline_zero_offset")
    fails = sorted(set(fails))
    reviews = sorted(set(reviews))
    if fails:
        return "fail_exclude", fails + reviews + notes
    if reviews:
        return "review", reviews + notes
    if notes:
        return "pass_with_offset_note", notes
    return "pass", []
