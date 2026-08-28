"""Focused adversarial tests for the isolated Step-3 review package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from domelab_pipeline import perception
from tools import build_step3_review as step3


def _write(path: Path, payload: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_fake_verifier(path: Path) -> None:
    _write(
        path,
        """#!/usr/bin/env python3
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
passed = not (root / "INVALID").exists()
print(json.dumps({
    "status": "PASS" if passed else "FAIL",
    "package_id": "canonical-evidence-epoch-6e86ac19-step2",
    "repo_commit": "6e86ac1955a0c566c7aae521705e51371992ba8a",
}))
raise SystemExit(0 if passed else 1)
""",
    )


def _set_name(number: int) -> str:
    return "Topre_R1_45g" if number == 75 else f"Fixture_Set_{number:02d}"


def _run_count(number: int) -> int:
    # 152 base bindings + 30 third runs + two extra Topre R1 runs = 184.
    if number == 75:
        return 4
    return 3 if number <= 30 else 2


def _aggregate_records():
    records = []
    part_numbers = {1, 68, 69, 70, 71, 72, 73, 74}
    for number in range(1, 77):
        set_name = _set_name(number)
        shared = number in (1, 2)
        records.append(
            {
                "test_id": f"bt_{number:04d}",
                "set": set_name,
                "kind": "part_assembly" if number in part_numbers else "dome_baseline",
                "name": set_name,
                "runs_used": _run_count(number),
                "brand": "Fixture",
                "manufacturer": "Fixture Labs",
                "nominal_weight_g": 40 + number,
                "variant": f"V{number}",
                "style": None,
                "precompression_mm": 0.0,
                "slider": "slider::topre",
                "silencing_ring": None,
                "housing": "housing::topre",
                "is_baseline": False,
                "travel_dev_mm": None,
                "measurement_cohort_id": "mc_shared" if shared else f"mc_{number:02d}",
                "evidence_alias_group": "egrp_shared" if shared else None,
                "evidence_alias_role": (
                    ("primary" if number == 1 else "semantic_alias") if shared else None
                ),
                "quality_flags": [],
                "null_reasons": {},
                "intake_review_notices": [],
                "provenance": {
                    "release_eligible": True,
                    "repo_commit": step3.REPO_COMMIT,
                    "config_hash": step3.EVIDENCE_IDENTITY,
                },
                "collapse_force_gf": 30.0 + number / 10,
                "collapse_travel_mm": 1.0 + number / 1000,
                "snap_pct": 10.0 + number / 100,
                "full_stroke_press_work_gf_mm": 100.0 + number / 10,
                "travel_mm": 3.9025 if number == 75 else 3.5 + number / 1000,
                "valley_force_gf": 20.0 + number / 10,
                "valley_travel_mm": 2.0 + number / 1000,
                "precollapse_work_gf_mm": 40.0 + number / 10,
                "drop_gf": 8.0 + number / 100,
                "drop_travel_mm": 1.5 + number / 1000,
                "drop_rate_gf_per_mm": 4.0 + number / 100,
                "norm_drop_rate_per_mm": 0.1 + number / 10000,
                "steepest_drop_0p10mm_gf_per_mm": 8.0 + number / 100,
                "ramp_10_90_gf_per_mm": 20.0 + number / 10,
            }
        )
    return records


def _decision_manifest():
    sets = []
    acquisition_number = 0
    for number in range(1, 77):
        set_name = _set_name(number)
        runs = []
        for run_number in range(1, _run_count(number) + 1):
            acquisition_number += 1
            # Four shared-evidence bindings produce 180 unique acquisitions.
            acquisition_identity = (
                acquisition_number - 180 if acquisition_number > 180 else acquisition_number
            )
            runs.append(
                {
                    "run": f"DataLog_{run_number}.csv",
                    "raw_path": f"{set_name}/DataLog_{run_number}.csv",
                    "retained": True,
                    "acquisition_id": f"acq_sha256:{acquisition_identity:064x}",
                    "ramp_review_required": False,
                    "intake_qc": {
                        "observations": {
                            "maximum_travel_mm": 4.2 + run_number / 1000
                        }
                    },
                }
            )
        sets.append(
            {
                "set": set_name,
                "status": "accepted",
                "retained_count": len(runs),
                "runs": runs,
            }
        )
    return {
        "artifact_role": step3.DATA_ARTIFACT_ROLE,
        "canonical_membership_active": True,
        "membership_applied_to_outputs": True,
        "release_eligible": True,
        "repo_commit": step3.REPO_COMMIT,
        "sets": sets,
    }


def _canonical_tree(root: Path) -> Path:
    decision = _decision_manifest()
    manifest = {
        "package_id": step3.CANONICAL_PACKAGE_ID,
        "frozen_repository": {"commit_oid": step3.REPO_COMMIT},
        "identity": {"evidence_epoch_hash": step3.EVIDENCE_IDENTITY},
        "expected_counts": {
            "semantic_records": 76,
            "curve_packs": 76,
            "raw_paths": 184,
            "unique_acquisitions": 180,
        },
        "scope": {"completed_step": 2},
        "canonical_artifacts": {
            "retained_run_manifest": "evidence/intake_retention_decisions.json",
            "aggregate_results": "evidence/bench_tests.staged.json",
        },
    }
    schema = {
        "repo_commit": step3.REPO_COMMIT,
        "evidence_epoch": {
            "identity": step3.EVIDENCE_IDENTITY,
            "semantic_record_count": 76,
            "semantic_set_count": 76,
            "independent_measurement_cohort_count": 75,
            "raw_path_count": 184,
            "unique_raw_evidence_count": 180,
            "shared_evidence_alias_group_count": 1,
        },
        "metrics_version": "metrics-v4.2",
        "calc_version": "fixture-method-v1",
        "intake_policy": {
            **{key: decision[key] for key in (
                "artifact_role",
                "canonical_membership_active",
                "membership_applied_to_outputs",
                "release_eligible",
            )},
            "version": "intake-qc-v1.4",
            "implementation_parity_target": "test-imp 1.1.4",
        },
        "provenance_hashes": {
            "generator_source_hash": "1" * 64,
            "release_reference_hash": "2" * 64,
        },
    }
    _write(root / "EPOCH_MANIFEST.json", json.dumps(manifest))
    _write(root / "evidence/intake_retention_decisions.json", json.dumps(decision))
    _write(root / "evidence/schema_meta.staged.json", json.dumps(schema))
    _write(root / "evidence/bench_tests.staged.json", json.dumps(_aggregate_records()))
    _write(root / "generator/domelab_pipeline/packs.py", "# sealed packs baseline\n")
    _write(root / "generator/domelab_pipeline/prose.py", "# sealed prose baseline\n")
    _write(
        root / "generator/domelab_pipeline/release_reference/index.release.html",
        "<!doctype html><title>sealed baseline</title>\n",
    )
    _write(
        root / "epoch_inputs/source_workbook/untested-domes_v2.xlsx",
        b"sealed workbook fixture",
    )
    _write_fake_verifier(root / step3.CANONICAL_VERIFIER)
    return root


def _viewer_build(**overrides):
    build = {
        "mode": "review",
        "bench_build": step3.BENCH_BUILD,
        "presentation_role": step3.PRESENTATION_ROLE,
        "release_eligible": False,
        "repo_commit": step3.REPO_COMMIT,
        "data_identity": step3.EVIDENCE_IDENTITY,
        "canonical_evidence_identity": step3.EVIDENCE_IDENTITY,
        "data_artifact_role": step3.DATA_ARTIFACT_ROLE,
        "canonical_data_release_eligible": True,
        "subjective_pilot_id": step3.PILOT_ID,
        "subjective_pilot_workbook_sha256": step3.PILOT_WORKBOOK_SHA256,
        "perception_score_version": perception.MODEL["version"],
        "record_count": 76,
        "set_count": 76,
        "retained_run_count": 184,
        "semantic_run_binding_count": 184,
        "unique_acquisition_count": 180,
        "independent_measurement_cohort_count": 75,
        "shared_evidence_alias_group_count": 1,
        "metrics": "metrics-v4.2",
        "intake": "intake-qc-v1.4",
        "intake_parity_target": "test-imp 1.1.4",
        "method_identity": "fixture-method-v1",
        "data_epoch": "canonical-6e86ac1",
        "data_epoch_prefix": "canonical-",
        "axis_data_floor_mm": 4.0,
        "force_wall_domain_max_mm": 3.9025,
        "curve_domain_max_mm": 4.204,
        "ramp_review_required": False,
        "ramp_review_run_count": 0,
        "ramp_review_set_count": 0,
    }
    build.update(overrides)
    return build


def _viewer_rows():
    records = _aggregate_records()
    perception_by_id = {
        row["test_id"]: row
        for row in perception.build_perception_pack(records)["records"]
    }
    decision_by_set = {
        entry["set"]: entry for entry in _decision_manifest()["sets"]
    }
    rows = []
    for record in records:
        row = {
            viewer_field: record.get(record_field)
            for viewer_field, record_field in step3.VTEST_RECORD_FIELDS.items()
        }
        row["base"] = bool(record.get("is_baseline"))
        row["intake_review_count"] = len(record.get("intake_review_notices", []))
        maxima = [
            run["intake_qc"]["observations"]["maximum_travel_mm"]
            for run in decision_by_set[record["set"]]["runs"]
        ]
        row["tl_min"], row["tl_max"] = min(maxima), max(maxima)
        scores = perception_by_id[record["test_id"]]
        row["wi"] = scores["weight_index"]
        row["ti"] = scores["tactility_index"]
        row["pp"] = scores["component_percentiles"]
        rows.append(row)
    return rows


def _comparison_html() -> str:
    return (
        '<button data-m="profileWeight">Weight profile</button>'
        '<button data-m="profileTactility">Tactility profile</button>'
        '<button data-m="indexScatter">Weight vs tactility</button>'
        '<span>Weight Index (0\u2013100)</span>'
        '<span>Tactility-sharpness Index (0\u2013100)</span>'
        '<span>Not calibrated</span><span>Not available</span>'
        '<p><b>Pilot-derived indices.</b> <b>Weight Index</b> is this dome’s weight '
        'percentile compared with the other domes tested. <b>Tactility Index</b> is '
        'this dome’s tactility percentile compared with the other domes tested. '
        'Pilot-derived Weight Index and Pilot-derived '
        'Tactility-sharpness Index are not predicted 1\u201310 ratings.</p>'
        '<script>const INDEX_SCATTER_DOMAIN=[0,100];const SCATTER_PTS=[];'
        'function isIndexScatterEligible(t){return t.k==="dome_baseline"&&'
        'isNum(t.wi)&&isNum(t.ti);}'
        'function drawIndexScatter(){const [indexMin,indexMax]=INDEX_SCATTER_DOMAIN;'
        'return [indexMin,indexMax];}'
        'function drawFixtureMode(){if(chartMode==="indexScatter")'
        'drawIndexScatter();}</script>'
    )


def _staging_tree(
    root: Path,
    canonical: Path,
    *,
    build=None,
    rows=None,
    extra_html="",
    source_provenance=None,
    canonical_runs_override=None,
    fallback_override=None,
    embedded_override=None,
    perception_model_override=None,
    profile_html=None,
) -> Path:
    decision = _decision_manifest()
    canonical_runs = {
        entry["set"]: [run["run"] for run in entry["runs"]]
        for entry in decision["sets"]
    }
    fallback = sorted(
        run["raw_path"] for entry in decision["sets"] for run in entry["runs"]
    )
    embedded = {
        entry["set"]: {
            "n": len(entry["runs"]),
            "p": {"x0": 0, "df": [0] * 841},
            "r": {"x0": 0, "df": [0] * 841},
        }
        for entry in decision["sets"]
    }
    if canonical_runs_override is not None:
        canonical_runs = canonical_runs_override
    if fallback_override is not None:
        fallback = fallback_override
    if embedded_override is not None:
        embedded = embedded_override
    perception_model = (
        perception.MODEL
        if perception_model_override is None
        else perception_model_override
    )
    if profile_html is None:
        profile_html = _comparison_html()
    viewer = (
        "<!doctype html><a href=\"documentation/subjective-pilot/index.html\">pilot</a>"
        + profile_html
        + "<script>const VIEWER_BUILD = "
        + json.dumps(build or _viewer_build(), sort_keys=True, separators=(",", ":"))
        + "; const PERCEPTION_MODEL = "
        + json.dumps(perception_model, sort_keys=True, separators=(",", ":"))
        + "; const VTESTS = "
        + json.dumps(rows or _viewer_rows(), sort_keys=True, separators=(",", ":"))
        + "; const CANONICAL_RUNS = "
        + json.dumps(canonical_runs, sort_keys=True, separators=(",", ":"))
        + "; const FALLBACK_CSVS = "
        + json.dumps(fallback, sort_keys=True, separators=(",", ":"))
        + "; const EMBEDDED = "
        + json.dumps(embedded, sort_keys=True, separators=(",", ":"))
        + "; const INTAKE_RAMP_REVIEWS_BY_SET = {};"
        + 'function drawExportWatermark(g,w,h){const text="UNREAL KEYBOARDS";'
        + 'g.fillStyle="rgba(28,36,34,.055)";g.fillText(text,w/2,h/2);}'
        + "function exportPNG(){g.fillStyle=CANVAS_THEME.light.exportBg;"
        + "g.fillRect(0,0,w,exportH);drawExportWatermark(g,w,h);"
        + 'drawScene(g,w,h,{export:true,theme:"light"});}</script>'
        + extra_html
    )
    _write(root / "packs/viewer.staged.html", viewer)
    schema = json.loads(
        (canonical / "evidence/schema_meta.staged.json").read_text(encoding="utf-8")
    )
    if source_provenance is not None:
        schema["provenance_hashes"].update(source_provenance)
    _write(root / "schema_meta.staged.json", json.dumps(schema))
    _write(
        root / "intake_retention_decisions.json",
        (canonical / "evidence/intake_retention_decisions.json").read_bytes(),
    )
    return root


def _reseal_pilot(root: Path) -> None:
    files = []
    for path in sorted(
        (path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS.json"),
        key=lambda path: path.relative_to(root).as_posix().encode("utf-8"),
    ):
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    _write(
        root / "SHA256SUMS.json",
        json.dumps(
            {
                "pilot_id": step3.PILOT_ID,
                "inventory_scope": "all regular files in this directory except SHA256SUMS.json",
                "files": files,
            },
            sort_keys=True,
        ),
    )


def _pilot_tree(root: Path) -> Path:
    identity = {
        "artifact_role": "exploratory_subjective_pilot",
        "release_eligible": False,
        "pilot_id": step3.PILOT_ID,
        "objective_repo_commit": step3.REPO_COMMIT,
        "objective_evidence_identity": step3.EVIDENCE_IDENTITY,
        "workbook_included": False,
        "workbook_sha256": step3.PILOT_WORKBOOK_SHA256,
    }
    _write(root / "source_identity.json", json.dumps(identity))
    _write(root / "index.html", "<!doctype html><title>subjective pilot</title>")
    _write(root / "README.md", "# Subjective pilot\n")
    _reseal_pilot(root)
    return root


def _source_tree(root: Path) -> Path:
    for relative in step3.SOURCE_SNAPSHOT_FILES:
        payload = "# fixture source\n"
        if relative.endswith("index.release.html"):
            payload = "<!doctype html><title>fc-3.4 viewer template</title>\n"
        elif relative.endswith("package.json"):
            payload = "{}\n"
        _write(root / relative, payload)
    return root


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    canonical = _canonical_tree(tmp_path / "canonical")
    monkeypatch.setattr(
        step3,
        "CANONICAL_VERIFIER_SHA256",
        _sha256(canonical / step3.CANONICAL_VERIFIER),
    )
    source = _source_tree(tmp_path / "source")
    pilot = _pilot_tree(source / "documentation/subjective-pilot")
    monkeypatch.setattr(
        step3,
        "PILOT_CHECKSUMS_SHA256",
        _sha256(pilot / "SHA256SUMS.json"),
    )
    monkeypatch.setattr(
        step3,
        "PILOT_SOURCE_IDENTITY_SHA256",
        _sha256(pilot / "source_identity.json"),
    )
    source_provenance = step3._source_provenance_hashes(source / "generator")
    staging = _staging_tree(
        tmp_path / "staging",
        canonical,
        source_provenance=source_provenance,
    )
    return {
        "canonical": canonical,
        "staging": staging,
        "source": source,
        "pilot": pilot,
        "output": tmp_path / "review",
    }


def _build(workspace):
    return step3.build_step3_review(
        staging=workspace["staging"],
        canonical_evidence=workspace["canonical"],
        source_root=workspace["source"],
        output=workspace["output"],
    )


def _restage(workspace, **overrides):
    return _staging_tree(
        workspace["staging"],
        workspace["canonical"],
        source_provenance=step3._source_provenance_hashes(
            workspace["source"] / "generator"
        ),
        **overrides,
    )


def test_builds_and_reverifies_exhaustive_nonrelease_package(workspace):
    report = _build(workspace)
    root = workspace["output"]
    assert report["status"] == "PASS"
    assert report["package_id"] == "force-curve-bench-fc-3.4-review.2-6e86ac19"
    assert report["bench_build"] == "fc-3.4-review.2"
    assert report["perception_model"] == "perception-rank-v1"
    assert (root / "index.html").read_bytes() == (
        workspace["staging"] / "packs/viewer.staged.html"
    ).read_bytes()
    assert (
        root
        / "canonical-evidence/epoch_inputs/source_workbook/untested-domes_v2.xlsx"
    ).is_file()
    assert not (
        root / "source-snapshot/generator/tools/build_review_envelope.py"
    ).exists()
    assert (
        root / "source-snapshot/generator/domelab_pipeline/perception.py"
    ).is_file()

    manifest = json.loads((root / step3.MANIFEST_NAME).read_text(encoding="utf-8"))
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != step3.MANIFEST_NAME
    }
    assert {row["path"] for row in manifest["files"]} == actual
    assert manifest["presentation_role"] == "review_candidate"
    assert manifest["release_eligible"] is False
    assert manifest["data_authority"]["release_eligible"] is True
    assert manifest["counts"]["independent_measurement_cohorts"] == 75
    assert manifest["counts"]["shared_evidence_alias_groups"] == 1
    assert "force_wall_reference" not in manifest
    assert report["verification_scope"] == "package_integrity_and_identity_only"
    assert report["ui_browser_acceptance"] == "NOT_EVALUATED"
    assert step3.verify_step3_review(root)["status"] == "PASS"


def test_refuses_an_existing_output_without_touching_it(workspace):
    workspace["output"].mkdir()
    marker = workspace["output"] / "keep.txt"
    _write(marker, "keep\n")
    with pytest.raises(step3.Step3ReviewError, match="refusing to replace"):
        _build(workspace)
    assert marker.read_text(encoding="utf-8") == "keep\n"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bench_build", "fc-3.1-review.2"),
        ("presentation_role", "canonical_release"),
        ("release_eligible", True),
        ("data_artifact_role", "review_candidate"),
        ("canonical_data_release_eligible", False),
        ("data_identity", "0" * 64),
        ("perception_score_version", "perception-rank-v0"),
        ("record_count", 75),
        ("retained_run_count", 183),
        ("unique_acquisition_count", 184),
        ("independent_measurement_cohort_count", 76),
        ("shared_evidence_alias_group_count", 0),
        ("metrics", "metrics-v4.1"),
        ("intake", "intake-qc-v1.2"),
        ("intake_parity_target", "test-imp 1.1.2"),
        ("method_identity", "stale-method"),
        ("data_epoch", "preview-9175069"),
        ("axis_data_floor_mm", 4.5),
        ("ramp_review_required", True),
    ],
)
def test_rejects_wrong_viewer_contract(workspace, field, value):
    _restage(workspace, build=_viewer_build(**{field: value}))
    with pytest.raises(step3.Step3ReviewError):
        _build(workspace)


@pytest.mark.parametrize(
    "field",
    [
        "force_wall_reference_set",
        "force_wall_reference_label",
        "force_wall_reference_test_id",
    ],
)
def test_rejects_force_wall_reference_metadata(workspace, field):
    _restage(workspace, build=_viewer_build(**{field: "retired"}))
    with pytest.raises(step3.Step3ReviewError):
        _build(workspace)


@pytest.mark.parametrize(
    "stale",
    [
        'canonStats("Topre_45g")',
        "ec-parts-dataset.xlsx",
        "not the retest fleet",
        "fc-3.1-review.2",
        "fc-3.2-review.1",
        "fc-3.3-review.1",
        'href="dome-lab-parts.html"',
    ],
)
def test_rejects_stale_generated_viewer_material(workspace, stale):
    _restage(workspace, extra_html=stale)
    with pytest.raises(step3.Step3ReviewError, match="stale viewer material"):
        _build(workspace)


def test_rejects_stale_source_template(workspace):
    _write(
        workspace["source"]
        / "generator/domelab_pipeline/release_reference/index.release.html",
        "<!doctype html>not the retest fleet",
    )
    with pytest.raises(step3.Step3ReviewError, match="viewer source template"):
        _build(workspace)


def test_rejects_tampered_vtest_scalar(workspace):
    rows = _viewer_rows()
    rows[0]["cg"] += 1.0
    _restage(workspace, rows=rows)
    with pytest.raises(step3.Step3ReviewError, match="differs from sealed canonical evidence"):
        _build(workspace)


@pytest.mark.parametrize("field", ["wi", "ti"])
def test_rejects_tampered_perception_index(workspace, field):
    rows = _viewer_rows()
    dome = next(row for row in rows if row["k"] == "dome_baseline")
    dome[field] += 0.125
    _restage(workspace, rows=rows)
    with pytest.raises(step3.Step3ReviewError, match="perception score differs"):
        _build(workspace)


@pytest.mark.parametrize("component", ["cg", "rp", "pcw", "dg", "sd", "dr", "sn"])
def test_rejects_tampered_perception_component_percentile(workspace, component):
    rows = _viewer_rows()
    dome = next(row for row in rows if row["k"] == "dome_baseline")
    dome["pp"][component] += 0.125
    _restage(workspace, rows=rows)
    with pytest.raises(step3.Step3ReviewError, match="perception score differs"):
        _build(workspace)


def test_rejects_calibrated_score_on_part_assembly(workspace):
    rows = _viewer_rows()
    part = next(row for row in rows if row["k"] == "part_assembly")
    assert part["wi"] is None and part["ti"] is None
    assert set(part["pp"].values()) == {None}
    part["wi"] = 0.0
    _restage(workspace, rows=rows)
    with pytest.raises(step3.Step3ReviewError, match="perception score differs"):
        _build(workspace)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        (None, "version", "perception-rank-v0"),
        (None, "reference_count", 67),
        ("weight", "primary_metric", "ramp_10_90_gf_per_mm"),
        ("tactility", "pilot_mean_spearman_rho", 0.99),
    ],
)
def test_rejects_tampered_perception_model(workspace, section, field, value):
    model = json.loads(json.dumps(perception.MODEL))
    target = model if section is None else model[section]
    target[field] = value
    _restage(workspace, perception_model_override=model)
    with pytest.raises(step3.Step3ReviewError, match="PERCEPTION_MODEL"):
        _build(workspace)


def test_rejects_viewer_without_visible_perception_profile_language(workspace):
    _restage(workspace, profile_html="")
    with pytest.raises(step3.Step3ReviewError, match="visible perception profile/index"):
        _build(workspace)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (
            "Weight Index</b> is this dome’s weight percentile compared with the "
            "other domes tested.",
            "Weight Index</b> = a 0–100 score.",
        ),
        (
            "Tactility Index</b> is this dome’s tactility percentile compared with "
            "the other domes tested.",
            "Tactility-sharpness Index</b> = a 0–100 score.",
        ),
        ("not predicted 1\u201310 ratings", "predicted 1\u201310 ratings"),
        ("Not calibrated", "No score"),
        ("Not available", "Missing"),
    ],
)
def test_rejects_missing_plain_english_perception_safeguards(workspace, old, new):
    profile_html = _comparison_html()
    assert old in profile_html
    _restage(workspace, profile_html=profile_html.replace(old, new, 1))
    with pytest.raises(step3.Step3ReviewError, match="visible perception profile/index"):
        _build(workspace)


@pytest.mark.parametrize(
    "consumer_note",
    ["80 is not twice 40.", "INDEX_SCALE_NOTE"],
)
def test_rejects_repeated_index_math_notes_in_viewer(workspace, consumer_note):
    _restage(workspace, extra_html=f"<p>{consumer_note}</p>")
    with pytest.raises(step3.Step3ReviewError):
        _build(workspace)


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        (
            'data-m="indexScatter">Weight vs tactility</button>',
            'data-m="indexScatter">Indices</button>',
            "visible perception profile/index",
        ),
        ("Weight Index (0\u2013100)", "Weight score", "visible perception profile/index"),
        (
            "Tactility-sharpness Index (0\u2013100)",
            "Tactility score",
            "visible perception profile/index",
        ),
        ("function drawIndexScatter", "function drawOther", "scatter behavior"),
        ("SCATTER_PTS", "OTHER_PTS", "scatter behavior"),
        ('chartMode==="indexScatter"', 'chartMode==="curves"', "scatter behavior"),
        ("isIndexScatterEligible", "isAnyScatterEligible", "scatter behavior"),
        (
            "const INDEX_SCATTER_DOMAIN=[0,100]",
            "const INDEX_SCATTER_DOMAIN=[0,90]",
            "exact 0-100 domain",
        ),
        (
            "const [indexMin,indexMax]=INDEX_SCATTER_DOMAIN",
            "const [indexMin,indexMax]=[0,100]",
            "exact 0-100 domain",
        ),
    ],
)
def test_rejects_missing_or_tampered_index_scatter_contract(
    workspace, old, new, error
):
    profile_html = _comparison_html()
    assert old in profile_html
    _restage(workspace, profile_html=profile_html.replace(old, new, 1))
    with pytest.raises(step3.Step3ReviewError, match=error):
        _build(workspace)


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        ("dome_baseline", "wi", None),
        ("dome_baseline", "ti", 100.001),
        ("part_assembly", "wi", 0.0),
        ("part_assembly", "ti", 50.0),
    ],
)
def test_rejects_scatter_scores_that_are_missing_out_of_range_or_uncalibrated(
    workspace, kind, field, value
):
    rows = _viewer_rows()
    record = next(row for row in rows if row["k"] == kind)
    record[field] = value
    _restage(workspace, rows=rows)
    with pytest.raises(step3.Step3ReviewError, match="perception score differs"):
        _build(workspace)


@pytest.mark.parametrize(
    "retired_label",
    [
        "Full-stroke press work",
        "Full press work",
        "Press work to force-wall",
        "Norm. drop rate",
        "Normalized drop rate",
        "Press work vs Snap",
        "Drop rate vs NDR",
        'data-m="scatter"',
        'data-m="scatter2"',
    ],
)
def test_rejects_visible_low_association_metric_labels_and_modes(
    workspace, retired_label
):
    _restage(workspace, extra_html=f"<p>{retired_label}</p>")
    with pytest.raises(step3.Step3ReviewError, match="retired low-association"):
        _build(workspace)


@pytest.mark.parametrize("field", ["mfr", "cohort", "alias_group", "alias_role"])
def test_rejects_tampered_vtest_metadata_and_evidence_relationships(workspace, field):
    rows = _viewer_rows()
    rows[0][field] = "fabricated"
    _restage(workspace, rows=rows)
    with pytest.raises(step3.Step3ReviewError, match="differs from sealed canonical evidence"):
        _build(workspace)


def test_rejects_changed_canonical_runs_blob(workspace):
    source = (workspace["staging"] / "packs/viewer.staged.html").read_text(encoding="utf-8")
    runs = step3._extract_json_const(source, "CANONICAL_RUNS")
    runs[_set_name(1)] = runs[_set_name(1)][1:]
    _restage(workspace, canonical_runs_override=runs)
    with pytest.raises(step3.Step3ReviewError, match="CANONICAL_RUNS"):
        _build(workspace)


def test_rejects_changed_fallback_raw_path_blob(workspace):
    source = (workspace["staging"] / "packs/viewer.staged.html").read_text(encoding="utf-8")
    paths = step3._extract_json_const(source, "FALLBACK_CSVS")
    paths[0] = "Fabricated/DataLog_1.csv"
    _restage(workspace, fallback_override=paths)
    with pytest.raises(step3.Step3ReviewError, match="FALLBACK_CSVS"):
        _build(workspace)


def test_rejects_changed_embedded_membership_or_run_count(workspace):
    source = (workspace["staging"] / "packs/viewer.staged.html").read_text(encoding="utf-8")
    embedded = step3._extract_json_const(source, "EMBEDDED")
    embedded[_set_name(1)]["n"] += 1
    _restage(workspace, embedded_override=embedded)
    with pytest.raises(step3.Step3ReviewError, match="EMBEDDED run count"):
        _build(workspace)


def test_rejects_internally_resealed_but_reauthored_subjective_pilot(workspace):
    _write(workspace["pilot"] / "README.md", "# Reauthored subjective claims\n")
    _reseal_pilot(workspace["pilot"])
    with pytest.raises(step3.Step3ReviewError, match="trust-root mismatch"):
        _build(workspace)


@pytest.mark.parametrize("input_key", ["staging", "canonical", "source", "pilot"])
def test_rejects_output_inside_every_input_root(workspace, input_key):
    workspace["output"] = workspace[input_key] / "nested-review-output"
    with pytest.raises(step3.Step3ReviewError, match="output must not be inside"):
        _build(workspace)
    assert not workspace["output"].exists()


def test_rejects_staging_generated_from_stale_source(workspace):
    _write(
        workspace["source"] / "generator/domelab_pipeline/packs.py",
        "# changed after staging\n",
    )
    with pytest.raises(step3.Step3ReviewError, match="source provenance is stale"):
        _build(workspace)


def test_rejects_new_pdf_even_when_subjective_inventory_lists_it(workspace, monkeypatch):
    _write(workspace["pilot"] / "obsolete.pdf", b"not a real PDF")
    _reseal_pilot(workspace["pilot"])
    # Isolate the outer document policy from the independent pilot trust-root
    # check; production never changes this pin.
    monkeypatch.setattr(
        step3,
        "PILOT_CHECKSUMS_SHA256",
        _sha256(workspace["pilot"] / "SHA256SUMS.json"),
    )
    with pytest.raises(step3.Step3ReviewError, match="spreadsheet/PDF"):
        _build(workspace)


def test_rejects_tampered_or_extra_packaged_files(workspace):
    _build(workspace)
    root = workspace["output"]
    _write(root / "extra.txt", "not declared\n")
    with pytest.raises(step3.Step3ReviewError, match="missing or extra"):
        step3.verify_step3_review(root)


def test_rejects_tampering_inside_copied_canonical_evidence(workspace):
    _build(workspace)
    retained = (
        workspace["output"]
        / "canonical-evidence/evidence/intake_retention_decisions.json"
    )
    _write(retained, "{}\n")
    with pytest.raises(step3.Step3ReviewError, match="hash mismatch"):
        step3.verify_step3_review(workspace["output"])


def test_canonical_verifier_must_pass_before_any_output_is_built(workspace):
    _write(workspace["canonical"] / "INVALID", "fail\n")
    with pytest.raises(step3.Step3ReviewError, match="canonical verifier failed"):
        _build(workspace)
    assert not workspace["output"].exists()


def test_rejects_stage_decision_that_differs_from_sealed_step2(workspace):
    _write(workspace["staging"] / "intake_retention_decisions.json", "{}\n")
    with pytest.raises(step3.Step3ReviewError, match="differs from sealed Step-2"):
        _build(workspace)


def test_root_manifest_itself_cannot_claim_release_eligibility(workspace):
    _build(workspace)
    path = workspace["output"] / step3.MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["release_eligible"] = True
    _write(path, json.dumps(manifest))
    with pytest.raises(step3.Step3ReviewError, match="root manifest identity mismatch"):
        step3.verify_step3_review(workspace["output"])
