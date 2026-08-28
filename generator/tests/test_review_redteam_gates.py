"""Independent release gates for the isolated force-curve review build.

These checks deliberately overlap no implementation-owned test file.  They
exercise the generated artifact as a consumer would: exact record identity,
applied intake membership, public method language, curve parity, and hostile
null/duplicate-record runtime states.
"""
from __future__ import annotations

import html as html_module
import importlib.util
import json
import os
import re
import subprocess
import sys
import types

import pytest

from domelab_pipeline.intake_policy import canonical_hash
from domelab_pipeline.packs import VT_METRIC, _extract_blob
from domelab_pipeline.parity import _node_modules
from domelab_pipeline.pipeline import generate, load_config_bundle


HERE = os.path.dirname(os.path.abspath(__file__))

VIEWER_METRICS = {
    "cg": "collapse_force_gf",
    "cx": "collapse_travel_mm",
    "vF": "valley_force_gf",
    "vx": "valley_travel_mm",
    "sn": "snap_pct",
    "tv": "travel_mm",
    "en": "full_stroke_press_work_gf_mm",
    "pcw": "precollapse_work_gf_mm",
    "dg": "drop_gf",
    "dxd": "drop_travel_mm",
    "dr": "drop_rate_gf_per_mm",
    "ndr": "norm_drop_rate_per_mm",
    "sd": "steepest_drop_0p10mm_gf_per_mm",
    "rp": "ramp_10_90_gf_per_mm",
}

PROFILE_METRICS = {
    "cg": "collapse_force_gf",
    "rp": "ramp_10_90_gf_per_mm",
    "pcw": "precollapse_work_gf_mm",
    "dg": "drop_gf",
    "sd": "steepest_drop_0p10mm_gf_per_mm",
    "dr": "drop_rate_gf_per_mm",
    "sn": "snap_pct",
}


@pytest.fixture(scope="module")
def redteam_candidate(cache, commit):
    staged, records, per_run, _ = generate(
        cache, commit, "unused", write=False, run_parity=False
    )
    return staged, records, per_run


def _blob(source: str, name: str):
    return _extract_blob(source, name)[2]


def _method_text(source: str) -> str:
    match = re.search(r'<div class="method">(.*?)</div>', source, flags=re.S)
    assert match, "generated viewer has no public Method block"
    without_tags = re.sub(r"<[^>]+>", " ", match.group(1))
    return " ".join(html_module.unescape(without_tags).split())


def _node_env() -> dict[str, str]:
    env = dict(os.environ)
    env["NODE_PATH"] = _node_modules()
    env["PYTHONUTF8"] = "1"
    return env


def test_retired_legacy_gui_cannot_fall_through_to_old_exporter(
    importer_path, monkeypatch, active_intake_identity
):
    """Exercise the GUI entry point without creating a real desktop window."""
    assert importer_path
    spec = importlib.util.spec_from_file_location(
        "bench_import_redteam_retirement", importer_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["bench_import_redteam_retirement"] = module
    spec.loader.exec_module(module)

    events: list[object] = []

    class FakeRoot:
        def withdraw(self):
            events.append("withdraw")

        def destroy(self):
            events.append("destroy")

    fake_tkinter = types.ModuleType("tkinter")
    fake_tkinter.Tk = FakeRoot
    fake_tkinter.ttk = types.SimpleNamespace()
    fake_tkinter.filedialog = types.SimpleNamespace()
    fake_tkinter.messagebox = types.SimpleNamespace(
        showerror=lambda title, message: events.append((title, message))
    )
    monkeypatch.setitem(sys.modules, "tkinter", fake_tkinter)

    assert module.gui() is None
    assert events[0] == "withdraw"
    assert events[-1] == "destroy"
    assert len(events) == 3
    title, message = events[1]
    assert title == "Bench importer retired"
    assert message == module.RETIRED_IMPORTER_MESSAGE
    assert active_intake_identity["parity_target"] in message
    assert active_intake_identity["policy_version"] in message
    assert "No output was written" in message


def test_all_fourteen_viewer_scalars_are_exact_and_record_bound(redteam_candidate):
    staged, records, _ = redteam_candidate
    source = staged["packs/viewer.staged.html"]
    rows = _blob(source, "VTESTS")
    by_id = {row["id"]: row for row in rows}

    assert len(by_id) == len(rows) == len(records)
    assert set(by_id) == {record["test_id"] for record in records}
    for record in records:
        row = by_id[record["test_id"]]
        assert row["source_set"] == row["set"] == record["set"]
        assert row["runs"] == record["runs_used"]
        for viewer_key, record_key in VIEWER_METRICS.items():
            assert row[viewer_key] == record[record_key], (
                record["test_id"],
                viewer_key,
                row[viewer_key],
                record[record_key],
            )


def test_perception_indices_and_profile_percentiles_are_independently_recomputed(
    redteam_candidate,
):
    staged, records, _ = redteam_candidate
    source = staged["packs/viewer.staged.html"]
    rows = _blob(source, "VTESTS")
    model = _blob(source, "PERCEPTION_MODEL")
    canonical = {record["test_id"]: record for record in records}
    domes = [row for row in rows if row["k"] == "dome_baseline"]
    parts = [row for row in rows if row["k"] == "part_assembly"]

    assert model["version"] == "perception-rank-v1"
    assert model["reference_count"] == len(domes) == 68
    assert model["weight"]["primary_metric"] == "collapse_force_gf"
    assert model["tactility"]["primary_metric"] == "drop_gf"
    assert model["outside_reference_range"] == "clamp_0_100"
    assert model["missing"] == "not_available_no_imputation"

    # Independent average-rank implementation. This verifies the embedded
    # values rather than using the generator's percentile helper as its oracle.
    expected = {}
    for viewer_key, record_key in PROFILE_METRICS.items():
        values = [canonical[row["id"]][record_key] for row in domes]
        assert all(isinstance(value, (int, float)) for value in values)
        for row, value in zip(domes, values):
            below = sum(other < value for other in values)
            equal = sum(other == value for other in values)
            average_zero_rank = below + (equal - 1) / 2
            expected.setdefault(row["id"], {})[viewer_key] = (
                100 * average_zero_rank / (len(values) - 1)
            )

    for row in domes:
        assert set(row["pp"]) == set(PROFILE_METRICS)
        for key, value in expected[row["id"]].items():
            assert row["pp"][key] == pytest.approx(value, abs=1e-12)
        assert row["wi"] == row["pp"]["cg"]
        assert row["ti"] == row["pp"]["dg"]

    for row in parts:
        assert row["wi"] is None and row["ti"] is None
        assert set(row["pp"]) == set(PROFILE_METRICS)
        assert all(value is None for value in row["pp"].values())


def test_picker_display_pack_is_derived_from_records_not_self_referential(
    redteam_candidate,
):
    """Close the gap left by picker runtime checks that read TESTS as expected.

    The picker is excluded from this review envelope, but its generator remains
    in the reproducibility source.  Compare the generated compact/rounded TESTS
    pack to the full-precision records outside the JavaScript runtime so a
    consistently wrong TESTS value cannot bless its own display and snapshot.
    """
    staged, records, _ = redteam_candidate
    rows = json.loads(staged["packs/picker_tests.json"])
    by_id = {row["id"]: row for row in rows}

    assert len(by_id) == len(rows) == len(records)
    assert set(by_id) == {record["test_id"] for record in records}
    for record in records:
        row = by_id[record["test_id"]]
        assert row["set"] == record["set"]
        assert row["runs"] == record["runs_used"]
        for picker_key, (record_key, rounder) in VT_METRIC.items():
            assert row[picker_key] == rounder(record[record_key]), (
                record["test_id"],
                picker_key,
                row[picker_key],
                record[record_key],
            )


def test_every_generated_surface_uses_the_same_applied_membership(redteam_candidate):
    staged, records, per_run = redteam_candidate
    source = staged["packs/viewer.staged.html"]
    decision = json.loads(staged["intake_retention_decisions.json"])
    metadata = json.loads(staged["schema_meta.staged.json"])
    policy_version = metadata["intake_policy"]["version"]
    accepted = {
        entry["set"]: [run["raw_path"] for run in entry["runs"] if run["retained"]]
        for entry in decision["sets"]
        if entry["status"] == "accepted"
    }

    assert accepted
    assert all(len(paths) >= 2 for paths in accepted.values())
    assert all(
        not any(run["retained"] for run in entry["runs"])
        for entry in decision["sets"]
        if entry["status"] != "accepted"
    )
    assert {record["set"] for record in records} == set(accepted)
    for record in records:
        assert record["provenance"]["raw_paths"] == accepted[record["set"]]
        assert record["runs_used"] == len(accepted[record["set"]])
        assert record["calc_version"] == metadata["calc_version"]
        assert policy_version in record["calc_version"]
        assert "runfilter-v1.1" not in record["calc_version"]

    canonical_runs = _blob(source, "CANONICAL_RUNS")
    embedded = _blob(source, "EMBEDDED")
    build = _blob(source, "VIEWER_BUILD")
    expected_basenames = {
        set_name: [path.rsplit("/", 1)[-1] for path in paths]
        for set_name, paths in accepted.items()
    }
    expected_paths = sorted(path for paths in accepted.values() for path in paths)

    assert canonical_runs == expected_basenames
    assert set(embedded) == set(accepted)
    assert all(embedded[name]["n"] == len(paths) for name, paths in accepted.items())
    # The v2 viewer derives the legacy flat fallback list from the authoritative
    # per-set membership instead of embedding a second copy that can diverge.
    assert (
        "const FALLBACK_CSVS=Object.entries(CANONICAL_RUNS)"
        ".flatMap(([set,files])=>files.map(f=>set+\"/\"+f));"
    ) in source
    fallback = sorted(
        f"{set_name}/{basename}"
        for set_name, basenames in canonical_runs.items()
        for basename in basenames
    )
    assert fallback == expected_paths
    assert build["set_count"] == len(accepted)
    assert build["record_count"] == len(records)
    assert build["retained_run_count"] == len(expected_paths)

    active_rows = [row for row in per_run if row["set"] in accepted]
    for row in active_rows:
        expected = row["raw_path"] in accepted[row["set"]]
        assert row["retained_output"] is expected
        assert row["retained_review_candidate"] is False
        # Step 2 is frozen canonical data authority. Step 3 changes only the
        # outer presentation role of the viewer.
        assert row["retained_canonical"] is True
        assert row["legacy_membership_evaluated"] is False
        assert row["retained_conventional"] is None
        assert row["retained_legacy"] is None
        assert row["intake_retained"] is expected
        assert row["output_membership_authority"] == (
            f"{policy_version} canonical retention authority"
        )


def test_canonical_data_and_review_presentation_roles_remain_separate(redteam_candidate):
    staged, _, _ = redteam_candidate
    source = staged["packs/viewer.staged.html"]
    decision = json.loads(staged["intake_retention_decisions.json"])
    metadata = json.loads(staged["schema_meta.staged.json"])["intake_policy"]
    build = _blob(source, "VIEWER_BUILD")

    assert decision["artifact_role"] == "canonical_retention_authority"
    assert decision["membership_applied_to_outputs"] is True
    assert decision["canonical_membership_active"] is True
    assert decision["release_eligible"] is True
    assert metadata["release_eligible"] is True
    assert metadata["warning"] is None
    assert build["mode"] == "review"
    assert build["presentation_role"] == "review_candidate"
    assert build["release_eligible"] is False
    assert build["data_artifact_role"] == "canonical_retention_authority"
    assert build["canonical_data_release_eligible"] is True
    assert "complete frozen retest fleet" in source
    assert "not deployed" in source

    bundle = load_config_bundle()
    expected_owner_hash = canonical_hash(
        {
            "exclusions": bundle["exclusions"],
            "adjudications": bundle["adjudications"],
            "review_register": bundle["review_register"],
        }
    )
    assert decision["owner_decision_inputs_hash"] == expected_owner_hash


def test_public_method_does_not_conflate_trace_markers_or_stale_authorities(
    redteam_candidate,
):
    source = redteam_candidate[0]["packs/viewer.staged.html"]
    metadata = json.loads(redteam_candidate[0]["schema_meta.staged.json"])
    method = _method_text(source)
    lower = method.lower()

    stale_article = "https://unrealkeyboards.com/blogs/topre-mods/topre-dome-force-curves"
    assert stale_article not in source
    assert "documentation:" in lower
    assert "included with this release" in lower
    assert 'href="documentation/index.html"' in source
    assert metadata["intake_policy"]["version"] in method
    assert "runfilter-v1.1" not in method
    assert "under one gram" not in lower

    # A curve assembled by averaging force samples is not the object from which
    # the canonical scalar events are detected.  The public method must say so.
    assert "averaged visualization trace" in lower
    assert "scalar" in lower and ("landmark" in lower or "marker" in lower)
    assert "arithmetic mean" in lower and "per-run" in lower
    assert "need not" in lower and "averaged" in lower
    assert "same analyzer that draws the chart" not in source.lower()


def test_remote_data_paths_are_generated_and_commit_pinned(redteam_candidate, commit):
    source = redteam_candidate[0]["packs/viewer.staged.html"]
    build = _blob(source, "VIEWER_BUILD")
    assert build["repo_commit"] == commit
    assert re.fullmatch(r"[0-9a-f]{40}", build["repo_commit"])
    assert "VIEWER_BUILD.repo_commit" in source
    assert "api.github.com" not in source
    assert 'const BRANCH = "main"' not in source
    assert "/blob/main/" not in source
    assert "/main/" not in source


def test_full_fleet_online_offline_curve_arrays_match(
    redteam_candidate, cache, tmp_path
):
    staged, records, _ = redteam_candidate
    viewer = tmp_path / "viewer.review.html"
    viewer.write_text(staged["packs/viewer.staged.html"], encoding="utf-8")
    plan = {}
    for record in records:
        plan.setdefault(
            record["set"],
            {
                "files": [
                    os.path.join(cache, path)
                    for path in record["provenance"]["raw_paths"]
                ],
                "n": record["runs_used"],
            },
        )
    plan_path = tmp_path / "curve-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    run = subprocess.run(
        [
            "node",
            os.path.join(HERE, "viewer_curve_battery.js"),
            str(viewer),
            str(plan_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_node_env(),
        timeout=45,
    )
    assert run.stdout, run.stderr
    payload = json.loads(run.stdout[run.stdout.index("{") :])
    assert run.returncode == 0, payload.get("failures") or run.stderr
    assert payload["failed"] == 0
    assert payload["sets"] == len(plan)


def test_null_and_duplicate_identity_runtime_is_fail_closed(
    redteam_candidate, tmp_path
):
    viewer = tmp_path / "viewer.review.html"
    viewer.write_text(
        redteam_candidate[0]["packs/viewer.staged.html"], encoding="utf-8"
    )
    harness = os.path.join(HERE, "viewer_review_redteam_runtime.js")
    run = subprocess.run(
        ["node", harness, str(viewer)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=_node_env(),
        timeout=30,
    )
    assert run.stdout, run.stderr
    payload = json.loads(run.stdout.strip().splitlines()[-1])
    assert run.returncode == 0, {**payload, "stderr": run.stderr}
    assert all(payload.values()), payload
