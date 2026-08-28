"""Parity and adversarial contract tests for intake-qc-v1.4.

These tests intentionally exercise policy boundaries without importing the
separate test-imp source tree.  A real-fleet reciprocal comparison against
test-imp 1.1.4 is hash-bound by the versioned policy configuration.
"""
from __future__ import annotations

import copy
import json
import os

import pytest

from domelab_pipeline import intake_policy
from domelab_pipeline import intake_cli
from domelab_pipeline import pipeline
from domelab_pipeline.pipeline import generate, load_config_bundle


def _metrics(fc=60.0, xc=1.0, snap=55.0, ndr=1.5):
    return {
        "collapse_force_gf": fc,
        "collapse_travel_mm": xc,
        "valley_force_gf": fc * (1.0 - snap / 100.0),
        "valley_travel_mm": xc + 0.40,
        "snap_pct": snap,
        "travel_mm": 3.8,
        "full_stroke_press_work_gf_mm": 180.0,
        "precollapse_work_gf_mm": 35.0,
        "drop_gf": fc * snap / 100.0,
        "drop_travel_mm": 0.40,
        "drop_rate_gf_per_mm": fc * snap / 40.0,
        "norm_drop_rate_per_mm": ndr,
        "steepest_drop_0p10mm_gf_per_mm": 80.0,
        "ramp_10_90_gf_per_mm": 70.0,
    }


def _raw(dt_ms=34.0):
    press = [index * 0.005 for index in range(1, 801)]
    travel = press + [press[-1]] + list(reversed(press[:-1]))
    millis = [1000.0 + index * dt_ms for index in range(len(travel))]
    steps = [position * 1600.0 for position in travel]
    force = [20.0 + 20.0 * position for position in travel]
    return {
        "millis": millis,
        "steps": steps,
        "x": travel,
        "raw": [value * 3000.0 for value in force],
        "F": force,
        "bad_rows": 0,
        "nonfinite": 0,
        "header_exact": True,
    }


def _evaluate(raw=None, metrics=None, flags=None):
    policy = load_config_bundle()["intake_policy"]
    raw = raw or _raw()
    split = raw["x"].index(max(raw["x"]))
    return intake_policy.evaluate_run(
        raw, metrics or _metrics(), flags or [], split, policy
    )


def _cohort_run(
    path, fc, xc=1.0, snap=55.0, ndr=1.5, ramp=70.0, acceptable=True
):
    metrics = _metrics(fc, xc, snap, ndr)
    metrics["ramp_10_90_gf_per_mm"] = ramp
    return {
        "path": path,
        "rel_path": path,
        "sha256": (path.encode("utf-8").hex() + "0" * 64)[:64],
        "metrics": metrics,
        "intake_qc": {
            "individually_acceptable": acceptable,
            "mixed_cohort_eligible": acceptable,
            "integrity_failures": [] if acceptable else ["synthetic_failure"],
            "protocol_failures": [],
            "fatal_metric_flags": [],
            "advisories": [],
            "observations": {},
        },
    }


def _upstream(set_name, runs, rejected=()):
    rejected = set(rejected)
    return {
        (set_name, run["rel_path"].rsplit("/", 1)[-1]): (
            run["rel_path"] not in rejected,
            "ineligible upstream" if run["rel_path"] in rejected else "eligible upstream",
        )
        for run in runs
    }


def _cohort_decision(runs, *, excluded_by_registry=False):
    policy = load_config_bundle()["intake_policy"]
    return intake_policy.evaluate_cohort(
        "Demo",
        runs,
        _upstream("Demo", runs),
        policy,
        excluded_by_registry=excluded_by_registry,
    )


def _warned_manifest():
    return {
        "sets": [
            {
                "set": "Demo",
                "runs": [
                    {
                        "run": "DataLog_2.csv",
                        "retained": True,
                        "ramp_review_required": True,
                        "ramp_review": {
                            "ramp_gf_per_mm": 59.0,
                            "retained_median_gf_per_mm": 70.0,
                            "signed_deviation_pct": -15.714285714285714,
                            "absolute_deviation_pct": 15.714285714285714,
                            "threshold_pct": 10.0,
                        },
                    }
                ],
            }
        ]
    }


def test_policy_constants_and_hashes_are_exact_test_imp_114_authority():
    policy = load_config_bundle()["intake_policy"]
    assert policy["policy_version"] == "intake-qc-v1.4"
    assert policy["implementation_parity_target"] == "test-imp 1.1.4"
    binding = policy["authority_binding"]
    assert binding["test_imp_init_py_sha256"] == (
        "7a1c69b505288b267097d200480f587f0209a411fcb581aa5d5b6e30f495a88b"
    )
    assert binding["test_imp_config_py_sha256"] == (
        "5f310e7de398ee33380833448e0132ffa1fbc8ae5059a32897e51906fe4b8bd0"
    )
    assert binding["test_imp_analysis_py_sha256"] == (
        "75b8313b4a73cc31293fcd689e9e7b31ef0719bfd9c014b5e9063dada873506b"
    )
    assert binding["test_imp_model_py_sha256"] == (
        "940a0cff05427d138ae5f7716cbcf54b7211cf21564cb6ac45b9b4bdf9fefbf8"
    )
    assert binding["test_imp_cli_py_sha256"] == (
        "bf58bd81de7d67b09bb7c5bd622a408358909f2461c1e5c6e352afd89bcebb61"
    )
    assert binding["test_imp_method_md_sha256"] == (
        "72fa2e7d4313cb00c493a98ce3a765bc2b25dd69518493c4523ec8a7cc6ba97a"
    )
    assert binding["release_zip_name"] == "test-imp-1.1.4-windows-x64.zip"
    assert binding["release_zip_bytes"] == 8_283_858
    assert binding["release_zip_sha256"] == (
        "b1ccdaba5c4ec76b7a8516c4e8c8109c26f2cb58b0f60f49a5c5fcf9a031b284"
    )
    assert binding["test_imp_source_manifest_name"] == (
        "SOURCE-SHA256SUMS-1.1.4.txt"
    )
    assert binding["test_imp_source_manifest_sha256"] == (
        "0cc31a5a4ac68108377384337d1fba662ac5c22fb9c14ee37ecc75dba74d21dd"
    )
    assert binding["release_directory"] == "release-1.1.4"
    assert binding["release_exe_name"] == "test-imp.exe"
    assert binding["release_exe_sha256"] == (
        "351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e"
    )
    assert binding["release_sha256s_txt_name"] == "SHA256SUMS.txt"
    assert binding["release_sha256s_txt_sha256"] == (
        "a4b6827de92e01bde043265f2569439fe9daa19e18a453bed956e77d6584a7b3"
    )
    assert binding["acceptance_json_name"] == (
        "acceptance/importer_acceptance-1.1.4.json"
    )
    assert binding["acceptance_json_sha256"] == (
        "e1e4b3d56a7e05823440e6e1d4d64dc3bd80be7148d97c03feb81e665e15d9de"
    )
    assert policy["speed"]["preferred_full_cycle_mm_s"] == [0.1445, 0.1500]
    assert policy["speed"]["hard_full_cycle_mm_s"] == [0.1400, 0.1530]
    assert policy["speed"]["preferred_collapse_local_mm_s"] == [0.1445, 0.1520]
    assert policy["speed"]["hard_collapse_local_mm_s"] == [0.1400, 0.1550]
    assert policy["replicates"]["collapse_force_absolute_tolerance_gf"] == 1.0
    assert policy["replicates"]["collapse_force_relative_tolerance"] == 0.02
    assert policy["replicates"]["collapse_position_tolerance_mm"] == 0.05
    assert policy["replicates"]["minimum_retained_runs"] == 2
    assert policy["ramp_review"]["minimum_numeric_retained_runs"] == 3
    assert policy["ramp_review"]["relative_deviation"] == 0.10


@pytest.mark.parametrize("dt_ms", [33.0, 35.0])
def test_preferred_speed_miss_is_visible_but_not_excluding(dt_ms):
    decision = _evaluate(_raw(dt_ms))
    assert decision["individually_acceptable"], decision
    assert any("preferred" in reason for reason in decision["advisories"])
    assert not decision["protocol_failures"]


def test_speed_outside_hard_envelope_is_ineligible():
    decision = _evaluate(_raw(36.0))
    assert not decision["individually_acceptable"]
    assert "full_cycle_speed_outside_hard_envelope" in decision["protocol_failures"]


def test_collapse_approach_dwell_fails_even_with_intact_grid():
    raw = _raw()
    split = raw["x"].index(max(raw["x"]))
    dwell_index = min(
        range(1, split), key=lambda index: abs(raw["x"][index] - 0.90)
    )
    for index in range(dwell_index, len(raw["millis"])):
        raw["millis"][index] += 80.0
    decision = _evaluate(raw)
    assert not decision["individually_acceptable"]
    assert "collapse_approach_timing_dwell" in decision["protocol_failures"]


@pytest.mark.parametrize(
    "mutation,reason",
    [
        (lambda raw: raw.__setitem__("bad_rows", 1), "malformed_or_wrong_width_rows"),
        (lambda raw: raw["x"].__setitem__(100, raw["x"][99]), "grid_or_step_nonconforming"),
        (lambda raw: raw["F"].__setitem__(200, raw["F"][200] + 12), "force_signal_discontinuity"),
    ],
)
def test_integrity_failures_never_reach_retention(mutation, reason):
    raw = _raw()
    mutation(raw)
    decision = _evaluate(raw)
    assert not decision["individually_acceptable"]
    assert reason in decision["integrity_failures"]


def test_smooth_return_release_over_adjacent_limit_is_not_a_discontinuity():
    raw = _raw()
    split = raw["x"].index(max(raw["x"]))
    start = next(
        index
        for index in range(split + 1, len(raw["x"]))
        if raw["x"][index] == 2.0
    )
    offsets = [-6.0, -12.0, -18.0, *[float(value) for value in range(-17, 1)]]
    for index, offset in enumerate(offsets, start):
        raw["F"][index] += offset
    return_deltas = [
        abs(raw["F"][index] - raw["F"][index - 1])
        for index in range(split + 2, len(raw["F"]))
    ]
    assert max(return_deltas) > 5.0
    decision = _evaluate(raw)
    assert decision["individually_acceptable"], decision
    assert decision["observations"]["press_adjacent_step_spikes"] == 0
    assert decision["observations"]["press_return_local_residual_spikes"] == 0


def test_press_adjacent_jump_over_limit_remains_fatal():
    raw = _raw()
    index = raw["x"].index(0.3)
    offset = raw["F"][index - 1] + 6.0 - raw["F"][index]
    for position in range(index, len(raw["F"])):
        raw["F"][position] += offset
    decision = _evaluate(raw)
    assert not decision["individually_acceptable"]
    assert "force_signal_discontinuity" in decision["integrity_failures"]
    assert decision["observations"]["press_adjacent_step_spikes"] == 1
    assert decision["observations"]["press_return_local_residual_spikes"] == 0


def test_isolated_return_local_residual_remains_fatal():
    raw = _raw()
    split = raw["x"].index(max(raw["x"]))
    index = next(
        position
        for position in range(split + 1, len(raw["x"]))
        if raw["x"][position] == 2.0
    )
    raw["F"][index] += 6.0
    decision = _evaluate(raw)
    assert not decision["individually_acceptable"]
    assert "force_signal_discontinuity" in decision["integrity_failures"]
    assert decision["observations"]["press_adjacent_step_spikes"] == 0
    assert decision["observations"]["press_return_local_residual_spikes"] == 1


def test_exact_five_gf_discontinuity_boundaries_pass():
    press = _raw()
    press_index = press["x"].index(0.3)
    previous = float(round(press["F"][press_index - 1]))
    press["F"][press_index - 1] = previous
    offset = previous + 5.0 - press["F"][press_index]
    for position in range(press_index, len(press["F"])):
        press["F"][position] += offset
    press_decision = _evaluate(press)
    assert press["F"][press_index] - press["F"][press_index - 1] == 5.0
    assert press_decision["individually_acceptable"], press_decision

    returned = _raw()
    split = returned["x"].index(max(returned["x"]))
    return_index = next(
        position
        for position in range(split + 1, len(returned["x"]))
        if returned["x"][position] == 2.0
    )
    neighbor = float(
        round(0.5 * (returned["F"][return_index - 1] + returned["F"][return_index + 1]))
    )
    returned["F"][return_index - 1] = neighbor
    returned["F"][return_index] = neighbor + 5.0
    returned["F"][return_index + 1] = neighbor
    return_decision = _evaluate(returned)
    residual = abs(
        returned["F"][return_index]
        - 0.5 * (returned["F"][return_index - 1] + returned["F"][return_index + 1])
    )
    assert residual == 5.0
    assert return_decision["individually_acceptable"], return_decision


def test_metric_local_null_flag_does_not_exclude_but_unknown_flag_fails_closed():
    local = _evaluate(flags=["bottomout_not_found"])
    assert local["individually_acceptable"]
    unknown = _evaluate(flags=["future_unclassified_flag"])
    assert not unknown["individually_acceptable"]
    assert unknown["fatal_metric_flags"] == ["future_unclassified_flag"]


def test_two_supported_force_populations_stop_before_replication():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 38.0),
        _cohort_run("Demo/DataLog_2.csv", 38.2),
        _cohort_run("Demo/DataLog_3.csv", 66.0),
        _cohort_run("Demo/DataLog_4.csv", 65.8),
    ]
    policy = load_config_bundle()["intake_policy"]
    decision = intake_policy.evaluate_cohort(
        "Demo", runs, _upstream("Demo", runs), policy, excluded_by_registry=False
    )
    assert decision["status"] == "mixed_cohort_stop"
    assert decision["mixed_cohort"]["feature"] == "collapse_force"
    assert decision["retained_count"] == 0


def test_single_outlier_is_omitted_not_misclassified_as_second_dome():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0),
        _cohort_run("Demo/DataLog_2.csv", 60.2),
        _cohort_run("Demo/DataLog_3.csv", 68.0),
    ]
    policy = load_config_bundle()["intake_policy"]
    decision = intake_policy.evaluate_cohort(
        "Demo", runs, _upstream("Demo", runs), policy, excluded_by_registry=False
    )
    assert decision["status"] == "accepted"
    assert decision["mixed_cohort"] is None
    assert [run["retained"] for run in decision["runs"]] == [True, True, False]


def test_force_tolerance_is_max_one_gf_or_two_percent_and_equality_passes():
    runs = [
        _cohort_run("Heavy/DataLog_1.csv", 98.0),
        _cohort_run("Heavy/DataLog_2.csv", 100.0),
        _cohort_run("Heavy/DataLog_3.csv", 102.0),
    ]
    policy = load_config_bundle()["intake_policy"]
    decision = intake_policy.evaluate_cohort(
        "Heavy", runs, _upstream("Heavy", runs), policy, excluded_by_registry=False
    )
    assert decision["tolerances"]["collapse_force_gf"] == 2.0
    assert decision["status"] == "accepted"
    assert all(run["retained"] for run in decision["runs"])


def test_one_match_is_flagged_for_retest_and_omitted():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0),
        _cohort_run("Demo/DataLog_2.csv", 80.0),
        _cohort_run("Demo/DataLog_3.csv", 100.0),
    ]
    policy = load_config_bundle()["intake_policy"]
    decision = intake_policy.evaluate_cohort(
        "Demo", runs, _upstream("Demo", runs), policy, excluded_by_registry=False
    )
    assert decision["status"] == "retest_insufficient_replicates"
    assert decision["preliminary_matching_count"] == 1
    assert decision["retained_count"] == 0
    assert not any(run["retained"] for run in decision["runs"])


def test_ramp_review_is_advisory_and_does_not_change_retained_membership():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=59.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_4.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_5.csv", 60.0, ramp=70.0),
    ]
    decision = _cohort_decision(runs)
    assert decision["status"] == "accepted"
    assert decision["retained_count"] == 5
    assert all(run["retained"] for run in decision["runs"])
    warned = [run for run in decision["runs"] if run["ramp_review_required"]]
    assert [run["run"] for run in warned] == ["DataLog_2.csv"]
    assert warned[0]["ramp_review"] == {
        "ramp_gf_per_mm": 59.0,
        "retained_median_gf_per_mm": 70.0,
        "signed_deviation_pct": pytest.approx(-15.714285714285714),
        "absolute_deviation_pct": pytest.approx(15.714285714285714),
        "threshold_pct": 10.0,
    }
    assert decision["ramp_review_summary"] == {
        "numeric_retained_count": 5,
        "retained_median_gf_per_mm": 70.0,
        "review_count": 1,
        "review_required": True,
    }


def test_ramp_review_matches_test_imp_observed_five_run_pattern():
    observed_ramps = [74.46, 59.87, 70.23, 69.44, 66.33]
    runs = [
        _cohort_run(f"Demo/DataLog_{index}.csv", 60.0, ramp=ramp)
        for index, ramp in enumerate(observed_ramps, 1)
    ]
    decision = _cohort_decision(runs)
    assert decision["retained_count"] == 5
    warned = [run for run in decision["runs"] if run["ramp_review_required"]]
    assert [run["run"] for run in warned] == ["DataLog_2.csv"]
    assert warned[0]["ramp_review"]["ramp_gf_per_mm"] == 59.87
    assert warned[0]["ramp_review"]["retained_median_gf_per_mm"] == 69.44
    assert warned[0]["ramp_review"]["signed_deviation_pct"] == pytest.approx(
        -13.78168202764978
    )


def test_ramp_values_and_reviews_are_not_fc_xc_membership_inputs():
    baseline = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_2.csv", 60.1, ramp=70.0),
        _cohort_run("Demo/DataLog_3.csv", 60.2, ramp=70.0),
        _cohort_run("Demo/DataLog_4.csv", 68.0, ramp=70.0),
    ]
    reviewed = copy.deepcopy(baseline)
    for run, ramp in zip(reviewed, [50.0, 70.0, 90.0, 1000.0]):
        run["metrics"]["ramp_10_90_gf_per_mm"] = ramp
    baseline_decision = _cohort_decision(baseline)
    reviewed_decision = _cohort_decision(reviewed)
    membership_fields = (
        "status",
        "candidate_count",
        "preliminary_matching_count",
        "retained_count",
        "center",
        "tolerances",
        "mixed_cohort",
    )
    assert {
        field: baseline_decision[field] for field in membership_fields
    } == {
        field: reviewed_decision[field] for field in membership_fields
    }
    per_run_membership_fields = (
        "matches_replicate_band",
        "retained",
        "collapse_force_deviation_gf",
        "collapse_position_deviation_mm",
        "decision_reasons",
    )
    assert [
        {field: run[field] for field in per_run_membership_fields}
        for run in baseline_decision["runs"]
    ] == [
        {field: run[field] for field in per_run_membership_fields}
        for run in reviewed_decision["runs"]
    ]
    assert baseline_decision["ramp_review_summary"]["review_count"] == 0
    assert reviewed_decision["ramp_review_summary"]["review_count"] == 2


@pytest.mark.parametrize("ramp", [63.0, 77.0])
def test_ramp_review_exact_ten_percent_boundary_passes(ramp):
    values = [70.0, 70.0, 70.0, ramp]
    runs = [
        _cohort_run(f"Demo/DataLog_{index}.csv", 60.0, ramp=value)
        for index, value in enumerate(values, 1)
    ]
    decision = _cohort_decision(runs)
    assert decision["ramp_review_summary"]["retained_median_gf_per_mm"] == 70.0
    assert decision["ramp_review_summary"]["review_count"] == 0
    assert not any(run["ramp_review_required"] for run in decision["runs"])


def test_ramp_review_tiny_amount_over_ten_percent_warns():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_4.csv", 60.0, ramp=77.0000001),
    ]
    decision = _cohort_decision(runs)
    assert decision["ramp_review_summary"]["review_count"] == 1
    assert decision["runs"][-1]["ramp_review_required"] is True


def test_ramp_review_ignores_null_nonfinite_and_boolean_values():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=None),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=float("nan")),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=True),
        _cohort_run("Demo/DataLog_4.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_5.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_6.csv", 60.0, ramp=85.0),
    ]
    decision = _cohort_decision(runs)
    assert decision["ramp_review_summary"]["numeric_retained_count"] == 3
    assert decision["ramp_review_summary"]["review_count"] == 1
    assert decision["runs"][-1]["ramp_review_required"] is True
    assert all(
        run["ramp_review"] is None for run in decision["runs"][:3]
    )


def test_ramp_review_requires_three_finite_numeric_retained_values():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=100.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=None),
    ]
    decision = _cohort_decision(runs)
    assert decision["ramp_review_summary"] == {
        "numeric_retained_count": 2,
        "retained_median_gf_per_mm": None,
        "review_count": 0,
        "review_required": False,
    }


def test_ramp_review_can_flag_multiple_retained_runs_around_conventional_median():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=50.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=90.0),
    ]
    decision = _cohort_decision(runs)
    assert decision["ramp_review_summary"]["retained_median_gf_per_mm"] == 70.0
    assert decision["ramp_review_summary"]["review_count"] == 2
    assert [run["ramp_review_required"] for run in decision["runs"]] == [
        True,
        False,
        True,
    ]


def test_ramp_review_does_not_define_percentage_against_nonpositive_median():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=-1.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=0.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=1.0),
    ]
    decision = _cohort_decision(runs)
    assert decision["ramp_review_summary"] == {
        "numeric_retained_count": 3,
        "retained_median_gf_per_mm": 0.0,
        "review_count": 0,
        "review_required": False,
    }


def test_ramp_review_excludes_nonretained_run_from_median_and_warning():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=70.0),
        _cohort_run("Demo/DataLog_4.csv", 60.0, ramp=1000.0, acceptable=False),
    ]
    decision = _cohort_decision(runs)
    assert decision["retained_count"] == 3
    assert decision["ramp_review_summary"]["numeric_retained_count"] == 3
    assert decision["ramp_review_summary"]["review_count"] == 0
    assert decision["runs"][-1]["retained"] is False
    assert decision["runs"][-1]["ramp_review"] is None


def test_ramp_review_is_suppressed_for_mixed_population_stop():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0, snap=40.0, ndr=1.0, ramp=50.0),
        _cohort_run("Demo/DataLog_2.csv", 60.0, snap=41.0, ndr=1.0, ramp=70.0),
        _cohort_run("Demo/DataLog_3.csv", 60.0, snap=60.0, ndr=2.0, ramp=90.0),
        _cohort_run("Demo/DataLog_4.csv", 60.0, snap=61.0, ndr=2.0, ramp=110.0),
    ]
    decision = _cohort_decision(runs)
    assert decision["status"] == "mixed_cohort_stop"
    assert decision["mixed_cohort"]["feature"] == "collapse_shape"
    assert decision["ramp_review_summary"] == {
        "numeric_retained_count": 0,
        "retained_median_gf_per_mm": None,
        "review_count": 0,
        "review_required": False,
    }
    assert not any(run["ramp_review_required"] for run in decision["runs"])


def test_manifest_ramp_review_summary_counts_sets_and_runs():
    reviewed = _cohort_decision(
        [
            _cohort_run("Demo/DataLog_1.csv", 60.0, ramp=50.0),
            _cohort_run("Demo/DataLog_2.csv", 60.0, ramp=70.0),
            _cohort_run("Demo/DataLog_3.csv", 60.0, ramp=90.0),
        ]
    )
    manifest = intake_policy.build_decision_manifest(
        artifact_role=intake_policy.PREVIEW_ROLE,
        repo_commit="0" * 40,
        dataset_manifest={},
        metrics_method_config={},
        exclusions={},
        adjudications={},
        review_register={},
        policy=load_config_bundle()["intake_policy"],
        sets=[reviewed],
    )
    assert manifest["decision_manifest_version"] == 2
    assert manifest["ramp_review_summary"] == {
        "set_count": 1,
        "run_count": 2,
        "review_required": True,
    }


def test_intake_cli_cancels_without_separate_ramp_review_acknowledgement(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "intake.json"
    monkeypatch.setattr(
        intake_cli,
        "compute_intake_decision_manifest",
        lambda cache, commit, role: _warned_manifest(),
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    code = intake_cli.main(
        [
            "--cache",
            "cache",
            "--commit",
            "0" * 40,
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert code == intake_cli.EXIT_RAMP_REVIEW_REQUIRED
    assert not output.exists()
    assert "RAMP REPEATABILITY WARNING" in captured.err
    assert "No intake decision draft was written" in captured.err


def test_intake_cli_explicit_ramp_review_ack_writes_unchanged_evidence(
    tmp_path, monkeypatch, capsys
):
    manifest = _warned_manifest()
    output = tmp_path / "intake.json"
    monkeypatch.setattr(
        intake_cli,
        "compute_intake_decision_manifest",
        lambda cache, commit, role: manifest,
    )
    code = intake_cli.main(
        [
            "--cache",
            "cache",
            "--commit",
            "0" * 40,
            "--output",
            str(output),
            "--ack-ramp-review",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(output.read_text(encoding="utf-8")) == manifest
    assert "acknowledged by explicit command-line option" in captured.err


def test_intake_cli_exact_interactive_ramp_review_phrase_writes_draft(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "intake.json"
    monkeypatch.setattr(
        intake_cli,
        "compute_intake_decision_manifest",
        lambda cache, commit, role: _warned_manifest(),
    )
    monkeypatch.setattr("builtins.input", lambda prompt: "RAMP REVIEW")
    code = intake_cli.main(
        [
            "--cache",
            "cache",
            "--commit",
            "0" * 40,
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert output.exists()
    assert "RAMP REVIEW acknowledged" in captured.err


def test_intake_cli_without_ramp_reviews_needs_no_acknowledgement(
    tmp_path, monkeypatch, capsys
):
    manifest = {"sets": [{"set": "Demo", "runs": []}]}
    output = tmp_path / "intake.json"
    monkeypatch.setattr(
        intake_cli,
        "compute_intake_decision_manifest",
        lambda cache, commit, role: manifest,
    )
    monkeypatch.setattr(
        "builtins.input",
        lambda prompt: (_ for _ in ()).throw(AssertionError("unexpected prompt")),
    )
    code = intake_cli.main(
        [
            "--cache",
            "cache",
            "--commit",
            "0" * 40,
            "--output",
            str(output),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert output.exists()
    assert "RAMP REPEATABILITY WARNING" not in captured.err


def test_pre_runfilter_ineligibility_is_never_re_admitted():
    runs = [
        _cohort_run("Demo/DataLog_1.csv", 60.0),
        _cohort_run("Demo/DataLog_2.csv", 60.1),
    ]
    policy = load_config_bundle()["intake_policy"]
    decision = intake_policy.evaluate_cohort(
        "Demo",
        runs,
        _upstream("Demo", runs, rejected={"Demo/DataLog_1.csv"}),
        policy,
        excluded_by_registry=False,
    )
    assert decision["status"] == "retest_insufficient_replicates"
    assert decision["retained_count"] == 0
    assert "pre_runfilter_ineligible" in decision["runs"][0]["decision_reasons"]


def test_obsolete_qc_disposition_is_diagnostic_not_an_intake_veto():
    run = _cohort_run("Demo/DataLog_1.csv", 60.0)
    run["qc_disposition"] = "fail_exclude"
    run["qc_disposition_flags"] = ["obsolete_qc_divergence_fixture"]
    bundle = {
        "review_register": {"entries": []},
        "intake_policy": load_config_bundle()["intake_policy"],
    }
    upstream = pipeline._explicit_intake_upstream(
        bundle, {"Demo": [run]}, adjudications={}
    )
    assert upstream[("Demo", "DataLog_1.csv")][0] is True
    assert "legacy QC disposition is diagnostic only" in upstream[("Demo", "DataLog_1.csv")][1]


def test_nonempty_qc_bound_adjudication_is_rejected_before_legacy_verifier(
    monkeypatch,
):
    bundle = {
        "adjudications": {"entries": [{"legacy": "divergence fixture"}]},
        "intake_policy": load_config_bundle()["intake_policy"],
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("old QC-bound adjudication verifier was invoked")

    monkeypatch.setattr(pipeline.registries, "verify_adjudications", forbidden)
    with pytest.raises(RuntimeError, match="must be empty under intake-qc-v1.4"):
        pipeline._legacy_adjudications_for_role(
            bundle,
            run_index={},
            method_hash="0" * 64,
            artifact_role=intake_policy.REVIEW_ROLE,
        )


def test_valid_legacy_adjudication_remains_available_in_development_preview():
    method_hash = "a" * 64
    raw_hash = "b" * 64
    entry = {
        "set": "Demo",
        "run": "DataLog_1.csv",
        "raw_path": "Demo/DataLog_1.csv",
        "sha256": raw_hash,
        "method_hash": method_hash,
        "overrides_disposition": "review",
        "qc_reasons": ["legacy_review_reason"],
        "barrier_flags": [],
        "eligible": True,
        "authority": "owner",
        "date": "2026-08-12",
        "rationale": "development-preview compatibility fixture",
    }
    bundle = {"adjudications": {"entries": [entry]}}
    run_index = {
        ("Demo", "DataLog_1.csv"): {
            "raw_path": "Demo/DataLog_1.csv",
            "sha256": raw_hash,
            "qc_disposition": "review",
            "qc_reasons": ["legacy_review_reason"],
            "barrier_flags": [],
        }
    }
    verified = pipeline._legacy_adjudications_for_role(
        bundle, run_index, method_hash, intake_policy.PREVIEW_ROLE
    )
    assert verified[("Demo", "DataLog_1.csv")]["eligible"] is True


def test_review_register_is_path_and_hash_bound_and_load_bearing():
    run = _cohort_run("Demo/DataLog_1.csv", 60.0)
    bundle = {
        "review_register": {
            "entries": [
                {
                    "set": "Demo",
                    "raw_path": "Demo/DataLog_1.csv",
                    "sha256": run["sha256"],
                    "canonically_eligible": False,
                }
            ]
        }
    }
    upstream = pipeline._explicit_intake_upstream(
        bundle, {"Demo": [run]}, adjudications={}
    )
    assert upstream[("Demo", "DataLog_1.csv")][0] is False
    bad = copy.deepcopy(bundle)
    bad["review_register"]["entries"][0]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="hash mismatch"):
        pipeline._explicit_intake_upstream(bad, {"Demo": [run]}, adjudications={})


def test_retired_topre_55g_no_retest_decision_is_preserved_as_history_only():
    bundle = load_config_bundle()
    assert bundle["review_register"]["entries"] == []
    event = next(
        item for item in bundle["evidence_history"]["events"]
        if item["event_id"] == "evt_oem_topre_collection_transition"
    )
    prior = event["prior_topre_55g_no_retest_decision"]
    assert prior["decision_scope"] == "retired generic cohort Topre_55g"
    assert prior["decision_was_satisfied_by_this_commit"] is False
    assert event["identity_mapping"] is None
    assert "Topre_55g" not in {
        item["set"] for item in bundle["retained_run_decisions"]["sets"]
    }


def test_registry_exclusion_wins_over_matching_runs():
    runs = [
        _cohort_run("Excluded/DataLog_1.csv", 60.0),
        _cohort_run("Excluded/DataLog_2.csv", 60.1),
    ]
    policy = load_config_bundle()["intake_policy"]
    decision = intake_policy.evaluate_cohort(
        "Excluded",
        runs,
        _upstream("Excluded", runs),
        policy,
        excluded_by_registry=True,
    )
    assert decision["status"] == "excluded_by_registry"
    assert decision["retained_count"] == 0


def test_declared_decision_manifest_rejects_any_manual_membership_edit():
    declared = load_config_bundle()["retained_run_decisions"]
    edited = copy.deepcopy(declared)
    accepted = next(entry for entry in edited["sets"] if entry["status"] == "accepted")
    accepted["runs"][0]["retained"] = not accepted["runs"][0]["retained"]
    with pytest.raises(RuntimeError, match="stale or has been hand-edited"):
        intake_policy.verify_declared_manifest(edited, declared)


def test_canonical_role_applies_membership_and_is_release_eligible():
    declared = load_config_bundle()["retained_run_decisions"]
    assert declared["artifact_role"] == intake_policy.CANONICAL_ROLE
    assert declared["membership_applied_to_outputs"] is True
    assert declared["canonical_membership_active"] is True
    assert declared["release_eligible"] is True
    membership = intake_policy.applied_membership_by_set(
        declared, {entry["set"] for entry in declared["sets"]}
    )
    assert len(membership) == 76
    assert all(all(runs.values()) for runs in membership.values())


def test_canonical_generation_includes_accepted_fleet_and_labels_every_artifact(cache, commit):
    staged, records, per_run, _ = generate(
        cache, commit, os.path.join(cache, "not-written"), write=False,
        run_parity=False, evidence_only=True,
    )
    assert "intake_retention_decisions.json" in staged
    assert len(records) == 76
    expected_run_count = sum(
        len(entry["expected_runs"])
        for entry in load_config_bundle()["dataset_manifest"]["tests"]
    )
    assert len(per_run) == expected_run_count
    assert all(record["provenance"]["artifact_role"] == intake_policy.CANONICAL_ROLE for record in records)
    assert all(record["provenance"]["release_eligible"] is True for record in records)
    assert all(row["release_eligible"] is True for row in per_run)
    assert all(row["retained_canonical"] == row["retained_output"] for row in per_run)
    assert all(row["legacy_membership_evaluated"] is False for row in per_run)
    assert all(row["retained_conventional"] is None for row in per_run)
    assert all(row["retained_legacy"] is None for row in per_run)
    assert not any(row["retained_review_candidate"] for row in per_run)
    meta = json.loads(staged["schema_meta.staged.json"])["intake_policy"]
    assert meta["warning"] is None
    assert meta["membership_applied_to_outputs"] is True
    assert meta["release_eligible"] is True
    exclusion = json.loads(staged["exclusion_manifest.json"])
    assert exclusion["artifact_role"] == intake_policy.CANONICAL_ROLE
    assert exclusion["release_eligible"] is True
    diagnostics = json.loads(staged["eligibility_decisions.json"])
    assert all(item["artifact_role"] == intake_policy.CANONICAL_ROLE for item in diagnostics)
    assert all(item["release_eligible"] is True for item in diagnostics)
    assert not staged["diff_vs_release.md"].startswith("# REVIEW CANDIDATE")


def test_canonical_generation_never_executes_legacy_runfilter(cache, commit, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("legacy batch_filter executed under intake authority")

    monkeypatch.setattr(pipeline, "batch_filter", forbidden)
    staged, records, _, _ = generate(
        cache, commit, os.path.join(cache, "not-written"), write=False,
        run_parity=False, evidence_only=True,
    )
    assert records
    assert "intake_retention_decisions.json" in staged


def test_canonical_generation_never_invokes_legacy_canonical_eligibility(
    cache, commit, monkeypatch
):
    def forbidden(*args, **kwargs):
        raise AssertionError("legacy canonical_eligibility executed under intake authority")

    monkeypatch.setattr(pipeline, "canonical_eligibility", forbidden)
    staged, records, _, _ = generate(
        cache, commit, os.path.join(cache, "not-written"), write=False,
        run_parity=False, evidence_only=True,
    )
    assert records
    diagnostics = json.loads(staged["eligibility_decisions.json"])
    assert all(item["canonical_eligible"] is None for item in diagnostics)
    assert all(item["decision_role"] == "legacy_qc_diagnostic" for item in diagnostics)
