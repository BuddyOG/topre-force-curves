"""Canonical acquisition/intake policy shared with test-imp 1.1.4.

The generator historically had a permissive QC layer followed by a fixed
``+/-1 gf, +/-0.10 mm`` runfilter.  New acquisitions use the independently
versioned ``intake-qc-v1.4`` contract instead.  This module is deliberately
data-independent: all thresholds come from ``config/intake_policy.json`` and
all outputs are deterministic functions of raw rows, per-run metrics, and the
exact owner-decision gate (registry/manifest exclusions, path-and-hash-bound
review blocks). Legacy QC and its adjudication schema are not inputs under
applied review/canonical roles.

There are two decision-manifest roles:

``development_preview``
    Recomputed and verified, but does not replace the frozen canonical
    membership.  It is useful for a decision-only comparison.

``review_candidate``
    Applies the recomputed decisions to isolated review outputs, while
    carrying ``release_eligible=false`` and ``canonical_membership_active=false``.
    This exercises omissions and changed run membership end to end without
    presenting the result as a canonical release.

``canonical_retention_authority``
    Recomputed and verified, then consumed as the run-membership authority.
    Every included set must pass the mixed-cohort stop and retain at least two
    runs.  This role is intended for the later, explicitly frozen retest fleet.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from typing import Any, Iterable


MANIFEST_VERSION = 2
PREVIEW_ROLE = "development_preview"
REVIEW_ROLE = "review_candidate"
CANONICAL_ROLE = "canonical_retention_authority"
ALLOWED_ROLES = frozenset({PREVIEW_ROLE, REVIEW_ROLE, CANONICAL_ROLE})


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _median(values: Iterable[float]) -> float:
    return statistics.median(list(values))


def _finite_metrics(metrics: dict[str, Any], fields: Iterable[str]) -> bool:
    for field in fields:
        value = metrics.get(field)
        if (
            value is None
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            return False
    return True


def _finite_number(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _normal_interval_fraction(
    millis: list[float],
    travel: list[float],
    split_index: int,
    normal_bounds: list[float],
    lower_x: float | None = None,
    upper_x: float | None = None,
) -> tuple[float | None, list[float]]:
    intervals: list[float] = []
    for index in range(1, split_index + 1):
        midpoint = 0.5 * (travel[index - 1] + travel[index])
        if lower_x is not None and midpoint < lower_x:
            continue
        if upper_x is not None and midpoint > upper_x:
            continue
        intervals.append(millis[index] - millis[index - 1])
    if not intervals:
        return None, intervals
    low, high = normal_bounds
    return sum(low <= value <= high for value in intervals) / len(intervals), intervals


def _collapse_local_speed(
    millis: list[float],
    travel: list[float],
    split_index: int,
    collapse_x: float | None,
    half_width: float,
) -> float | None:
    if collapse_x is None:
        return None
    speeds: list[float] = []
    for index in range(1, split_index + 1):
        midpoint = 0.5 * (travel[index - 1] + travel[index])
        elapsed = millis[index] - millis[index - 1]
        if collapse_x - half_width <= midpoint <= collapse_x + half_width and elapsed > 0:
            speeds.append(1000.0 * (travel[index] - travel[index - 1]) / elapsed)
    return _median(speeds) if speeds else None


def _longest_bad_cadence(
    millis: list[float],
    travel: list[float],
    split_index: int,
    bounds: list[float],
) -> int:
    low, high = bounds
    longest = current = 0
    for index in range(1, split_index + 1):
        elapsed = millis[index] - millis[index - 1]
        speed = (
            1000.0 * (travel[index] - travel[index - 1]) / elapsed
            if elapsed > 0
            else 0.0
        )
        current = current + 1 if not low <= speed <= high else 0
        longest = max(longest, current)
    return longest


def evaluate_run(
    raw: dict[str, Any],
    metrics: dict[str, Any],
    quality_flags: list[str],
    split_index: int | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate one parsed run using the exact intake-qc-v1.4 gate order.

    Reason identifiers are stable machine codes.  Numeric observations are
    carried separately so prose changes cannot alter the decision identity.
    """
    parse = policy["parse"]
    trajectory = policy["trajectory"]
    integrity_cfg = policy["integrity"]
    speed_cfg = policy["speed"]
    millis = raw["millis"]
    steps = raw["steps"]
    travel = raw["x"]
    raw_force = raw["raw"]
    force = raw["F"]
    integrity: list[str] = []
    protocol: list[str] = []
    advisories: list[str] = []
    observations: dict[str, Any] = {
        "numeric_rows": len(travel),
        "malformed_rows": raw["bad_rows"],
        "nonfinite_rows": raw["nonfinite"],
        "header_exact": raw["header_exact"],
    }

    if not raw["header_exact"]:
        integrity.append("header_mismatch")
    if raw["bad_rows"]:
        integrity.append("malformed_or_wrong_width_rows")
    if raw["nonfinite"]:
        integrity.append("nonfinite_rows")
    if len(travel) < parse["minimum_numeric_rows"] or split_index is None:
        integrity.append("insufficient_numeric_rows")
        return _finish_run(
            metrics, quality_flags, integrity, protocol, advisories, observations, policy
        )

    imax = split_index
    n = len(travel)
    timestamp_strict = all(b > a for a, b in zip(millis, millis[1:]))
    observations["timestamps_strictly_increasing"] = timestamp_strict
    if not timestamp_strict:
        integrity.append("timestamp_nonmonotonic")
    intervals = [b - a for a, b in zip(millis, millis[1:])]
    interval_median = _median(intervals) if intervals else None
    timing_gaps = sum(
        1
        for elapsed in intervals
        if interval_median
        and elapsed > integrity_cfg["timing_gap_factor"] * interval_median
    )
    observations["interval_median_ms"] = interval_median
    observations["timing_gap_count"] = timing_gaps
    if timing_gaps >= integrity_cfg["timing_gap_fail_count"]:
        protocol.append("timing_gap_limit")
    elif timing_gaps:
        advisories.append("isolated_timing_gaps")
    if interval_median is None:
        protocol.append("median_sample_interval_unavailable")
    else:
        low, high = speed_cfg["preferred_interval_ms"]
        if not low <= interval_median <= high:
            advisories.append("preferred_sample_interval_miss")

    maximum = max(travel)
    grid_tol = trajectory["grid_tolerance_mm"]
    max_rows = [i for i, value in enumerate(travel) if abs(value - maximum) <= grid_tol]
    documented_turnaround = (
        len(max_rows) == 2
        and max_rows[0] == imax
        and max_rows[1] == imax + 1
        and abs(steps[imax] - steps[imax + 1]) <= trajectory["step_tolerance"]
    )
    observations["documented_duplicate_turnaround"] = documented_turnaround
    if not documented_turnaround:
        integrity.append("invalid_duplicate_turnaround")

    grid_errors = step_errors = 0
    for index in range(1, n):
        if index == imax + 1 and documented_turnaround:
            continue
        sign = 1.0 if index <= imax else -1.0
        if (
            abs(
                (travel[index] - travel[index - 1])
                - sign * trajectory["nominal_step_mm"]
            )
            > grid_tol
        ):
            grid_errors += 1
        if (
            abs(
                (steps[index] - steps[index - 1])
                - sign * trajectory["nominal_step_count"]
            )
            > trajectory["step_tolerance"]
        ):
            step_errors += 1
    ratio_errors = sum(
        1
        for step, position in zip(steps, travel)
        if abs(step / trajectory["steps_per_mm"] - position) > grid_tol
    )
    observations.update(
        grid_errors=grid_errors,
        step_errors=step_errors,
        travel_step_ratio_errors=ratio_errors,
    )
    if grid_errors or step_errors or ratio_errors:
        integrity.append("grid_or_step_nonconforming")
    if any(b < a - grid_tol for a, b in zip(travel[:imax], travel[1 : imax + 1])):
        integrity.append("press_displacement_reversal")
    if any(b > a + grid_tol for a, b in zip(travel[imax:], travel[imax + 1 :])):
        integrity.append("return_displacement_reversal")

    start, end = travel[0], travel[-1]
    press_span, return_span = maximum - start, maximum - end
    completion = return_span / press_span if press_span > 0 else 0.0
    observations.update(
        start_travel_mm=start,
        maximum_travel_mm=maximum,
        end_travel_mm=end,
        press_span_mm=press_span,
        return_span_mm=return_span,
        return_completion_fraction=completion,
    )
    if (
        abs(start) > trajectory["origin_zone_mm"]
        or press_span < trajectory["minimum_press_span_mm"]
    ):
        integrity.append("incomplete_or_cropped_press")
    if (
        abs(end) > trajectory["return_endpoint_zone_mm"]
        or return_span < trajectory["minimum_return_span_mm"]
        or completion < trajectory["minimum_return_completion_fraction"]
    ):
        integrity.append("incomplete_or_cropped_return")

    if any(
        raw_value < integrity_cfg["adc_dropout_raw_floor"]
        or force_value < integrity_cfg["adc_dropout_force_floor_gf"]
        for raw_value, force_value in zip(raw_force, force)
    ):
        integrity.append("raw_adc_dropout")
    negative_indices = [
        index
        for index, (raw_value, force_value) in enumerate(zip(raw_force, force))
        if raw_value < 0 or force_value < 0
    ]
    if negative_indices:
        severe = [
            index
            for index in negative_indices
            if force[index] < integrity_cfg["baseline_negative_floor_gf"]
            or index <= imax
            or travel[index] > integrity_cfg["baseline_zone_mm"]
        ]
        if severe:
            integrity.append("negative_reading_outside_unloaded_return_endpoint")
        else:
            advisories.append("unloaded_return_endpoint_zero_offset")

    max_force = max(force)
    longest_max = current = 0
    for value in force:
        current = current + 1 if value == max_force else 0
        longest_max = max(longest_max, current)
    if (
        max_force >= integrity_cfg["saturation_min_force_gf"]
        and longest_max >= integrity_cfg["saturation_min_run"]
    ):
        integrity.append("load_cell_saturation")

    stale = current = 0
    for index in range(1, imax + 1):
        current = current + 1 if force[index] == force[index - 1] else 0
        stale = max(stale, current)
    observations["stale_force_press_steps"] = stale
    if stale >= integrity_cfg["stale_force_max_run"]:
        integrity.append("stale_force_samples")

    force_shape_limit = min(
        integrity_cfg["mechanical_region_end_mm"], metrics.get("travel_mm") or 3.4
    )
    # intake-qc-v1.3 made the adjacent-step gate phase-aware: a natural,
    # multi-sample dome release may be steeper than 5 gf per return step
    # without being an acquisition discontinuity.  The local-residual gate
    # remains bidirectional so an isolated corrupt return sample is fatal.
    press_adjacent_spikes = sum(
        1
        for index in range(1, imax + 1)
        if integrity_cfg["mechanical_region_start_mm"]
        <= max(travel[index - 1], travel[index])
        <= force_shape_limit
        and abs(force[index] - force[index - 1])
        > integrity_cfg["press_adjacent_force_spike_gf_per_step"]
    )
    both_phase_local_residuals = sum(
        1
        for index in range(1, n - 1)
        if integrity_cfg["mechanical_region_start_mm"]
        <= travel[index]
        <= force_shape_limit
        and abs(force[index] - 0.5 * (force[index - 1] + force[index + 1]))
        > integrity_cfg["both_phase_local_force_residual_gf"]
    )
    observations.update(
        press_adjacent_step_spikes=press_adjacent_spikes,
        press_return_local_residual_spikes=both_phase_local_residuals,
    )
    if press_adjacent_spikes or both_phase_local_residuals:
        integrity.append("force_signal_discontinuity")

    duration = (millis[-1] - millis[0]) / 1000.0
    effective_speed = (
        2.0 * (maximum - min(travel)) / duration if duration > 0 else None
    )
    collapse_speed = _collapse_local_speed(
        millis,
        travel,
        imax,
        metrics.get("collapse_travel_mm"),
        speed_cfg["collapse_local_half_width_mm"],
    )
    observations["effective_speed_mm_s"] = effective_speed
    observations["collapse_local_speed_mm_s"] = collapse_speed
    if effective_speed is None:
        protocol.append("full_cycle_speed_unavailable")
    else:
        low, high = speed_cfg["hard_full_cycle_mm_s"]
        if not low <= effective_speed <= high:
            protocol.append("full_cycle_speed_outside_hard_envelope")
        else:
            low, high = speed_cfg["preferred_full_cycle_mm_s"]
            if not low <= effective_speed <= high:
                advisories.append("preferred_full_cycle_speed_miss")
    if collapse_speed is None:
        protocol.append("collapse_local_speed_unavailable")
    else:
        low, high = speed_cfg["hard_collapse_local_mm_s"]
        if not low <= collapse_speed <= high:
            protocol.append("collapse_local_speed_outside_hard_envelope")
        else:
            low, high = speed_cfg["preferred_collapse_local_mm_s"]
            if not low <= collapse_speed <= high:
                advisories.append("preferred_collapse_local_speed_miss")

    longest_bad = _longest_bad_cadence(
        millis, travel, imax, speed_cfg["instantaneous_press_mm_s"]
    )
    observations["longest_nonstandard_cadence_steps"] = longest_bad
    if longest_bad >= speed_cfg["sustained_bad_cadence_steps"]:
        protocol.append("sustained_nonstandard_cadence")

    press_fraction, _ = _normal_interval_fraction(
        millis, travel, imax, speed_cfg["normal_interval_ms"]
    )
    observations["normal_press_interval_fraction"] = press_fraction
    if press_fraction is None:
        protocol.append("normal_press_interval_fraction_unavailable")
    elif press_fraction < speed_cfg["minimum_normal_press_fraction"]:
        protocol.append("normal_press_interval_fraction_below_minimum")

    collapse_x = metrics.get("collapse_travel_mm")
    if collapse_x is not None:
        approach_fraction, approach_intervals = _normal_interval_fraction(
            millis,
            travel,
            imax,
            speed_cfg["normal_interval_ms"],
            collapse_x - speed_cfg["collapse_approach_window_mm"],
            collapse_x,
        )
        observations["normal_collapse_approach_fraction"] = approach_fraction
        if approach_fraction is None:
            protocol.append("normal_collapse_approach_fraction_unavailable")
        elif approach_fraction < speed_cfg["minimum_normal_collapse_approach_fraction"]:
            protocol.append("normal_collapse_approach_fraction_below_minimum")
        if interval_median and any(
            elapsed > speed_cfg["collapse_approach_dwell_factor"] * interval_median
            for elapsed in approach_intervals
        ):
            protocol.append("collapse_approach_timing_dwell")

    valley_x = metrics.get("valley_travel_mm")
    if collapse_x is not None and valley_x is not None:
        drop_fraction, _ = _normal_interval_fraction(
            millis,
            travel,
            imax,
            speed_cfg["normal_interval_ms"],
            collapse_x,
            valley_x,
        )
        observations["normal_collapse_to_valley_fraction"] = drop_fraction
        if drop_fraction is None:
            protocol.append("normal_collapse_to_valley_fraction_unavailable")
        elif drop_fraction < speed_cfg["minimum_normal_drop_fraction"]:
            protocol.append("normal_collapse_to_valley_fraction_below_minimum")

    return _finish_run(
        metrics, quality_flags, integrity, protocol, advisories, observations, policy
    )


def _finish_run(
    metrics: dict[str, Any],
    quality_flags: list[str],
    integrity: list[str],
    protocol: list[str],
    advisories: list[str],
    observations: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    local_flags = set(policy["metric_flag_classification"]["metric_local_flags"])
    fatal_flags = sorted(set(quality_flags) - local_flags)
    individually_acceptable = (
        not integrity
        and not protocol
        and not fatal_flags
        and _finite_metrics(metrics, policy["core_acceptance_metrics"])
    )
    mixed_eligible = (
        not integrity
        and not protocol
        and not fatal_flags
        and _finite_metrics(metrics, policy["mixed_cohort_metrics"])
    )
    return {
        "individually_acceptable": individually_acceptable,
        "mixed_cohort_eligible": mixed_eligible,
        "integrity_failures": sorted(set(integrity)),
        "protocol_failures": sorted(set(protocol)),
        "fatal_metric_flags": fatal_flags,
        "advisories": sorted(set(advisories)),
        "observations": observations,
    }


def _compact(
    runs: list[dict[str, Any]],
    metric: str,
    absolute: float,
    relative: float = 0.0,
) -> bool:
    values = [float(run["metrics"][metric]) for run in runs]
    center = _median(values)
    return max(values) - min(values) <= max(absolute, abs(center) * relative)


def _supported_splits(runs: list[dict[str, Any]]):
    count = len(runs)
    for index in range(1, count):
        left, right = runs[:index], runs[index:]
        if count > 2 and (len(left) < 2 or len(right) < 2):
            continue
        yield left, right


def detect_mixed_cohort(
    runs: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any] | None:
    """Return deterministic split evidence or ``None``.

    The implementation intentionally matches test-imp 1.1.4: only runs that
    clear structural/protocol/fatal-landmark gates participate, and a
    singleton is not a second supported population when n > 2.
    """
    cfg = policy["mixed_cohort"]
    candidates = [run for run in runs if run["intake_qc"]["mixed_cohort_eligible"]]
    if len(candidates) < 2:
        return None

    by_force = sorted(candidates, key=lambda run: float(run["metrics"]["collapse_force_gf"]))
    overall_fc = _median(float(run["metrics"]["collapse_force_gf"]) for run in by_force)
    force_threshold = max(
        cfg["collapse_force_absolute_gap_gf"],
        abs(overall_fc) * cfg["collapse_force_relative_gap"],
    )
    for left, right in _supported_splits(by_force):
        gap = min(float(run["metrics"]["collapse_force_gf"]) for run in right) - max(
            float(run["metrics"]["collapse_force_gf"]) for run in left
        )
        if (
            gap >= force_threshold
            and _compact(
                left,
                "collapse_force_gf",
                cfg["within_group_collapse_force_absolute_gf"],
                cfg["within_group_collapse_force_relative"],
            )
            and _compact(
                right,
                "collapse_force_gf",
                cfg["within_group_collapse_force_absolute_gf"],
                cfg["within_group_collapse_force_relative"],
            )
        ):
            return _mixed_evidence("collapse_force", gap, left, right)

    by_position = sorted(
        candidates, key=lambda run: float(run["metrics"]["collapse_travel_mm"])
    )
    for left, right in _supported_splits(by_position):
        gap = min(float(run["metrics"]["collapse_travel_mm"]) for run in right) - max(
            float(run["metrics"]["collapse_travel_mm"]) for run in left
        )
        if (
            gap >= cfg["collapse_position_gap_mm"]
            and _compact(
                left,
                "collapse_travel_mm",
                cfg["within_group_collapse_position_mm"],
            )
            and _compact(
                right,
                "collapse_travel_mm",
                cfg["within_group_collapse_position_mm"],
            )
        ):
            return _mixed_evidence("collapse_position", gap, left, right)

    by_snap = sorted(candidates, key=lambda run: float(run["metrics"]["snap_pct"]))
    for left, right in _supported_splits(by_snap):
        gap = min(float(run["metrics"]["snap_pct"]) for run in right) - max(
            float(run["metrics"]["snap_pct"]) for run in left
        )
        left_ndr = _median(float(run["metrics"]["norm_drop_rate_per_mm"]) for run in left)
        right_ndr = _median(float(run["metrics"]["norm_drop_rate_per_mm"]) for run in right)
        ndr_relative_gap = abs(right_ndr - left_ndr) / max(
            abs(_median([left_ndr, right_ndr])), 1e-9
        )
        if (
            gap >= cfg["snap_gap_percentage_points"]
            and ndr_relative_gap >= cfg["normalized_drop_rate_relative_gap"]
        ):
            evidence = _mixed_evidence("collapse_shape", gap, left, right)
            evidence["normalized_drop_rate_relative_gap"] = ndr_relative_gap
            return evidence
    return None


def _mixed_evidence(
    feature: str,
    gap: float,
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "feature": feature,
        "gap": gap,
        "group_a": [run["rel_path"] for run in left],
        "group_b": [run["rel_path"] for run in right],
    }


def ramp_repeatability_reviews(
    runs: list[dict[str, Any]],
    retained_paths: set[str],
    mixed: dict[str, Any] | None,
    policy: dict[str, Any],
) -> dict[str, Any]:
    """Return the nonfatal intake-qc-v1.4 retained-cohort RAMP review.

    This is intentionally downstream of all per-run and Fc/xc retention
    gates.  Null/nonfinite RAMP values do not count toward the three-value
    minimum and never receive a warning.  The equality guard matches
    test-imp 1.1.4 exactly and prevents floating representation from turning
    a mathematical 10% boundary into a strict-greater-than warning.
    """
    result: dict[str, Any] = {
        "numeric_retained_count": 0,
        "retained_median_gf_per_mm": None,
        "reviews": {},
    }
    if mixed is not None:
        return result

    candidates: list[tuple[str, float]] = []
    for run in runs:
        path = run["rel_path"]
        ramp = run["metrics"].get("ramp_10_90_gf_per_mm")
        if path in retained_paths and _finite_number(ramp):
            candidates.append((path, float(ramp)))

    result["numeric_retained_count"] = len(candidates)
    cfg = policy["ramp_review"]
    if len(candidates) < cfg["minimum_numeric_retained_runs"]:
        return result

    median_ramp = _median(value for _, value in candidates)
    result["retained_median_gf_per_mm"] = median_ramp
    if not math.isfinite(median_ramp) or median_ramp <= 0.0:
        return result

    relative_threshold = cfg["relative_deviation"]
    limit = abs(median_ramp) * relative_threshold
    reviews: dict[str, dict[str, float]] = {}
    for path, ramp in candidates:
        delta = ramp - median_ramp
        absolute_delta = abs(delta)
        boundary_equal = math.isclose(
            absolute_delta,
            limit,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        if absolute_delta > limit and not boundary_equal:
            signed_pct = 100.0 * delta / abs(median_ramp)
            reviews[path] = {
                "ramp_gf_per_mm": ramp,
                "retained_median_gf_per_mm": median_ramp,
                "signed_deviation_pct": signed_pct,
                "absolute_deviation_pct": abs(signed_pct),
                "threshold_pct": 100.0 * relative_threshold,
            }
    result["reviews"] = reviews
    return result


def evaluate_cohort(
    set_name: str,
    runs: list[dict[str, Any]],
    upstream: dict[tuple[str, str], tuple[bool, str]],
    policy: dict[str, Any],
    *,
    excluded_by_registry: bool,
    excluded_by_manifest: bool = False,
) -> dict[str, Any]:
    """Compute the complete set/run retention decision.

    ``upstream`` is the explicit owner-decision gate assembled from exact
    review-register blocks. Registry and dataset exclusions are set-level
    arguments. Legacy ``qc_disposition`` is intentionally absent and remains
    diagnostic-only; QC-bound adjudications exist only in development-preview
    compatibility mode.
    """
    replicate = policy["replicates"]
    mixed = (
        None
        if excluded_by_registry or excluded_by_manifest
        else detect_mixed_cohort(runs, policy)
    )
    candidates: list[dict[str, Any]] = []
    for run in runs:
        run_name = run["rel_path"].rsplit("/", 1)[-1]
        upstream_ok, _ = upstream[(set_name, run_name)]
        if upstream_ok and run["intake_qc"]["individually_acceptable"]:
            candidates.append(run)

    center_fc = center_xc = fc_tolerance = None
    prelim: dict[str, bool] = {run["rel_path"]: False for run in runs}
    deviation: dict[str, tuple[float | None, float | None]] = {
        run["rel_path"]: (None, None) for run in runs
    }
    if candidates:
        center_fc = _median(float(run["metrics"]["collapse_force_gf"]) for run in candidates)
        center_xc = _median(float(run["metrics"]["collapse_travel_mm"]) for run in candidates)
        fc_tolerance = max(
            replicate["collapse_force_absolute_tolerance_gf"],
            replicate["collapse_force_relative_tolerance"] * abs(center_fc),
        )
        for run in candidates:
            fc_dev = abs(float(run["metrics"]["collapse_force_gf"]) - center_fc)
            xc_dev = abs(float(run["metrics"]["collapse_travel_mm"]) - center_xc)
            deviation[run["rel_path"]] = (fc_dev, xc_dev)
            prelim[run["rel_path"]] = (
                fc_dev <= fc_tolerance
                and xc_dev <= replicate["collapse_position_tolerance_mm"]
            )

    preliminary_count = sum(prelim.values())
    if excluded_by_registry:
        status = "excluded_by_registry"
    elif excluded_by_manifest:
        status = "excluded_by_dataset_manifest"
    elif mixed is not None:
        status = "mixed_cohort_stop"
    elif preliminary_count < replicate["minimum_retained_runs"]:
        status = "retest_insufficient_replicates"
    else:
        status = "accepted"

    retained_paths = {
        path for path, matches in prelim.items() if status == "accepted" and matches
    }
    ramp_review = ramp_repeatability_reviews(
        runs, retained_paths, mixed, policy
    )
    ramp_reviews = ramp_review["reviews"]

    run_decisions = []
    for run in runs:
        run_name = run["rel_path"].rsplit("/", 1)[-1]
        upstream_ok, upstream_reason = upstream[(set_name, run_name)]
        fc_dev, xc_dev = deviation[run["rel_path"]]
        matches = prelim[run["rel_path"]]
        retained = status == "accepted" and matches
        reasons: list[str] = []
        if excluded_by_registry:
            reasons.append("excluded_by_registry")
        if excluded_by_manifest:
            reasons.append("excluded_by_dataset_manifest")
        if not upstream_ok:
            reasons.append("pre_runfilter_ineligible")
        if not run["intake_qc"]["individually_acceptable"]:
            reasons.append("intake_run_ineligible")
        if mixed is not None:
            reasons.append("mixed_cohort_stop")
        if fc_dev is not None and fc_tolerance is not None and fc_dev > fc_tolerance:
            reasons.append("collapse_force_outside_replicate_band")
        if (
            xc_dev is not None
            and xc_dev > replicate["collapse_position_tolerance_mm"]
        ):
            reasons.append("collapse_position_outside_replicate_band")
        if matches and status == "retest_insufficient_replicates":
            reasons.append("minimum_two_matching_runs_not_met")
        if retained:
            reasons.append("retained")
        run_decisions.append(
            {
                "run": run_name,
                "raw_path": run["rel_path"],
                "sha256": run["sha256"],
                "pre_runfilter_eligible": upstream_ok,
                "pre_runfilter_decision": upstream_reason,
                "intake_individually_acceptable": run["intake_qc"][
                    "individually_acceptable"
                ],
                "matches_replicate_band": matches,
                "retained": retained,
                "ramp_review_required": run["rel_path"] in ramp_reviews,
                "ramp_review": ramp_reviews.get(run["rel_path"]),
                "collapse_force_deviation_gf": fc_dev,
                "collapse_position_deviation_mm": xc_dev,
                "decision_reasons": reasons,
                "intake_qc": run["intake_qc"],
            }
        )

    return {
        "set": set_name,
        "status": status,
        "excluded_by_registry": excluded_by_registry,
        "excluded_by_dataset_manifest": excluded_by_manifest,
        "candidate_count": len(candidates),
        "preliminary_matching_count": preliminary_count,
        "retained_count": sum(run["retained"] for run in run_decisions),
        "ramp_review_summary": {
            "numeric_retained_count": ramp_review["numeric_retained_count"],
            "retained_median_gf_per_mm": ramp_review["retained_median_gf_per_mm"],
            "review_count": len(ramp_reviews),
            "review_required": bool(ramp_reviews),
        },
        "center": {"collapse_force_gf": center_fc, "collapse_position_mm": center_xc},
        "tolerances": {
            "collapse_force_gf": fc_tolerance,
            "collapse_position_mm": replicate["collapse_position_tolerance_mm"],
        },
        "mixed_cohort": mixed,
        "runs": run_decisions,
    }


def build_decision_manifest(
    *,
    artifact_role: str,
    repo_commit: str,
    dataset_manifest: dict[str, Any],
    metrics_method_config: dict[str, Any],
    exclusions: dict[str, Any],
    adjudications: dict[str, Any],
    review_register: dict[str, Any],
    policy: dict[str, Any],
    sets: list[dict[str, Any]],
) -> dict[str, Any]:
    if artifact_role not in ALLOWED_ROLES:
        raise RuntimeError(f"unsupported intake decision artifact role: {artifact_role!r}")
    ordered_sets = sorted(sets, key=lambda entry: entry["set"])
    ramp_review_count = sum(
        entry["ramp_review_summary"]["review_count"] for entry in ordered_sets
    )
    ramp_review_set_count = sum(
        entry["ramp_review_summary"]["review_required"] for entry in ordered_sets
    )
    return {
        "decision_manifest_version": MANIFEST_VERSION,
        "artifact_role": artifact_role,
        "canonical_membership_active": artifact_role == CANONICAL_ROLE,
        "membership_applied_to_outputs": artifact_role in (REVIEW_ROLE, CANONICAL_ROLE),
        "release_eligible": artifact_role == CANONICAL_ROLE,
        "policy_version": policy["policy_version"],
        "policy_hash": canonical_hash(policy),
        "metrics_method_config_hash": canonical_hash(metrics_method_config),
        "repo_commit": repo_commit,
        "dataset_manifest_hash": canonical_hash(dataset_manifest),
        "owner_decision_inputs_hash": canonical_hash(
            {
                "exclusions": exclusions,
                "adjudications": adjudications,
                "review_register": review_register,
            }
        ),
        "ramp_review_summary": {
            "set_count": ramp_review_set_count,
            "run_count": ramp_review_count,
            "review_required": bool(ramp_review_count),
        },
        "sets": ordered_sets,
    }


def verify_declared_manifest(
    declared: dict[str, Any], computed: dict[str, Any]
) -> None:
    """Fail closed unless the checked-in decision artifact is byte-semantic equal."""
    if declared.get("artifact_role") not in ALLOWED_ROLES:
        raise RuntimeError("intake decision manifest has an unsupported artifact_role")
    if declared != computed:
        keys = sorted(set(declared) | set(computed))
        differing = [key for key in keys if declared.get(key) != computed.get(key)]
        raise RuntimeError(
            "intake decision manifest is stale or has been hand-edited; "
            "recompute and review it before generation (differing top-level fields: "
            + ", ".join(differing)
            + ")"
        )


def applied_membership_by_set(
    manifest: dict[str, Any], included_sets: set[str]
) -> dict[str, dict[str, bool]]:
    """Validate/return path membership for a review/canonical applied role.

    Failed cohorts are intentionally omitted and carried in the decision
    artifact for retest; they do not abort generation of unrelated accepted
    sets.  Structural contradictions still fail closed.
    """
    if manifest["artifact_role"] not in (REVIEW_ROLE, CANONICAL_ROLE):
        raise RuntimeError("development preview cannot be applied as output membership")
    result: dict[str, dict[str, bool]] = {}
    for entry in manifest["sets"]:
        name = entry["set"]
        result[name] = {run["raw_path"]: run["retained"] for run in entry["runs"]}
        retained_count = sum(result[name].values())
        if name in included_sets and entry["status"] == "accepted" and retained_count < 2:
            raise RuntimeError(
                f"accepted intake decision retained fewer than two runs for {name}"
            )
        if name in included_sets and entry["status"] != "accepted" and retained_count:
            raise RuntimeError(
                f"retest/omitted intake decision retains runs for {name}: {entry['status']}"
            )
    return result
