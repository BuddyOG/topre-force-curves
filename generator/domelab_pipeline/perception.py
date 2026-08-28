"""Pilot-derived presentation indices for the Force Curve Bench review viewer.

These indices do not alter canonical mechanical evidence.  They monotonically
standardize the two mechanical metrics with the strongest rank association to
the frozen 25-dome, one-rater subjective pilot.  The remaining high-association
metrics stay visible as supporting descriptors rather than being double-counted
inside a collinear composite.
"""
from __future__ import annotations

import bisect
import math
from typing import Any


MODEL = {
    "version": "perception-rank-v1",
    "artifact_role": "pilot_derived_presentation_index",
    "validation_status": "exploratory_single_rater_fixed_order_panel",
    "pilot_id": "subjective-pilot-v1",
    "pilot_workbook_sha256": (
        "d4bbaad6831ccab1003bcc7e2974ef7100ee32e083fa88f27d468e64d7a323d0"
    ),
    "objective_evidence_identity": (
        "7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a"
    ),
    "objective_repo_commit": (
        "6e86ac1955a0c566c7aae521705e51371992ba8a"
    ),
    "reference_population": "release_eligible_dome_baseline_records_at_frozen_commit",
    "reference_unit": "dome_baseline_measurement_cohort",
    "reference_count": 68,
    "percentile_formula": "100 * (average_zero_based_rank) / (N - 1)",
    "ties": "average_occupied_rank",
    "between_reference_values": "linear_interpolation",
    "outside_reference_range": "clamp_0_100",
    "missing": "not_available_no_imputation",
    "direction": "higher_index_means_greater_panel_associated_perception",
    "display_decimals": 1,
    "weight": {
        "label": "Pilot-derived weight index",
        "primary_metric": "collapse_force_gf",
        "primary_viewer_key": "cg",
        "score_viewer_key": "wi",
        "pilot_mean_spearman_rho": 0.951744545758805,
        "pilot_session_spearman_rho": [
            0.9000956591423925,
            0.927118048775914,
            0.9164377659252297,
        ],
        "supporting_metrics": [
            "ramp_10_90_gf_per_mm",
            "precollapse_work_gf_mm",
        ],
        "rho_weighted_family_composite_spearman_rho": 0.9239451107508398,
        "selection_reason": (
            "Collapse force had the strongest observed rank association. "
            "Combining the correlated family reduced agreement with the pilot."
        ),
    },
    "tactility": {
        "label": "Pilot-derived tactility-sharpness index",
        "primary_metric": "drop_gf",
        "primary_viewer_key": "dg",
        "score_viewer_key": "ti",
        "pilot_mean_spearman_rho": 0.930200072898408,
        "pilot_session_spearman_rho": [
            0.9103861518456052,
            0.9295664914029365,
            0.9249624978666606,
        ],
        "supporting_metrics": [
            "steepest_drop_0p10mm_gf_per_mm",
            "drop_rate_gf_per_mm",
            "snap_pct",
        ],
        "rho_weighted_family_composite_spearman_rho": 0.9197873855152169,
        "selection_reason": (
            "Force drop had the strongest observed rank association. "
            "Combining the correlated family reduced agreement with the pilot."
        ),
    },
    "limitations": [
        "The pilot has one rater, 25 domes, three fixed-order sessions, and no independent validation panel.",
        "The indices are relative mechanical rankings, not predicted 1-10 ratings or universal perceptual units.",
        "The tactility pilot contains no linear/off observation; a low index does not classify a test as linear.",
        "Part-assembly records are not calibrated and receive no perception index.",
        "Force-wall onset is separate and is never an input to either index.",
    ],
}


COMPONENTS = {
    "collapse_force_gf": "cg",
    "ramp_10_90_gf_per_mm": "rp",
    "precollapse_work_gf_mm": "pcw",
    "drop_gf": "dg",
    "steepest_drop_0p10mm_gf_per_mm": "sd",
    "drop_rate_gf_per_mm": "dr",
    "snap_pct": "sn",
}


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _same_nullable_number(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    return _finite_number(left) and _finite_number(right) and left == right


def _mid_percentile(value: Any, reference: list[float]) -> float | None:
    if not _finite_number(value):
        return None
    left = bisect.bisect_left(reference, value)
    right = bisect.bisect_right(reference, value)
    denominator = len(reference) - 1
    if right > left:
        average_zero_rank = (left + right - 1) / 2.0
        return 100.0 * average_zero_rank / denominator
    if left == 0:
        return 0.0
    if left == len(reference):
        return 100.0

    lower_value, upper_value = reference[left - 1], reference[left]
    lower_left = bisect.bisect_left(reference, lower_value)
    lower_right = bisect.bisect_right(reference, lower_value)
    upper_left = bisect.bisect_left(reference, upper_value)
    upper_right = bisect.bisect_right(reference, upper_value)
    lower_pct = 100.0 * ((lower_left + lower_right - 1) / 2.0) / denominator
    upper_pct = 100.0 * ((upper_left + upper_right - 1) / 2.0) / denominator
    fraction = (value - lower_value) / (upper_value - lower_value)
    return lower_pct + fraction * (upper_pct - lower_pct)


def build_perception_pack(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a deterministic score contract and full-precision record scores."""
    eligible = [
        record for record in records
        if record.get("kind") == "dome_baseline"
        and record.get("provenance", {}).get("release_eligible") is True
    ]
    for record in eligible:
        provenance = record.get("provenance", {})
        if provenance.get("repo_commit") != MODEL["objective_repo_commit"]:
            raise RuntimeError(
                "perception index requires the frozen objective repository commit"
            )
        if provenance.get("config_hash") != MODEL["objective_evidence_identity"]:
            raise RuntimeError(
                "perception index requires the frozen objective evidence identity"
            )
    cohort_records: dict[str, dict[str, Any]] = {}
    for record in eligible:
        cohort = record.get("measurement_cohort_id")
        if not isinstance(cohort, str) or not cohort:
            raise RuntimeError("perception index requires measurement-cohort identities")
        previous = cohort_records.get(cohort)
        if previous is None:
            cohort_records[cohort] = record
            continue
        for field in COMPONENTS:
            if not _same_nullable_number(previous.get(field), record.get(field)):
                raise RuntimeError(
                    f"shared measurement cohort has divergent {field}: {cohort}"
                )

    if len(cohort_records) != MODEL["reference_count"]:
        raise RuntimeError(
            "perception reference count mismatch: "
            f"expected {MODEL['reference_count']}, found {len(cohort_records)}"
        )

    reference: dict[str, list[float]] = {}
    for field in COMPONENTS:
        values = [record.get(field) for record in cohort_records.values()]
        if not all(_finite_number(value) for value in values):
            raise RuntimeError(f"perception reference metric has missing values: {field}")
        reference[field] = sorted(float(value) for value in values)

    output_records: list[dict[str, Any]] = []
    for record in records:
        calibrated = record.get("kind") == "dome_baseline"
        components = {
            viewer_key: (
                _mid_percentile(record.get(field), reference[field])
                if calibrated else None
            )
            for field, viewer_key in COMPONENTS.items()
        }
        output_records.append({
            "test_id": record.get("test_id"),
            "set": record.get("set"),
            "measurement_cohort_id": record.get("measurement_cohort_id"),
            "calibration_status": "calibrated_dome_baseline" if calibrated else "not_calibrated_part_assembly",
            "weight_index": components[MODEL["weight"]["primary_viewer_key"]],
            "tactility_index": components[MODEL["tactility"]["primary_viewer_key"]],
            "component_percentiles": components,
        })

    return {
        "model": MODEL,
        "reference": {
            "measurement_cohort_count": len(cohort_records),
            "component_full_precision_values": reference,
        },
        "records": output_records,
    }
