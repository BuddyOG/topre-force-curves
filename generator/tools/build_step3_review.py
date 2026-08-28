#!/usr/bin/env python3
"""Build or verify the isolated Force Curve Bench Step-3 review package.

This contract is intentionally separate from the historical 917 review
envelope.  It packages only the fc-3.4 review viewer, the frozen subjective
pilot sidecar, a byte-for-byte copy of the already sealed Step-2 canonical
evidence package, and a small source overlay needed to inspect the Step-3
presentation work.  It never deploys or promotes a viewer.

The package is fail-closed:

* the exact, hash-pinned verifier inside the canonical package must pass before
  and after copying;
* the viewer must declare the fixed review/data authority split and exact fleet
  identity;
* every regular file is covered by the root manifest and extra files fail;
* links, junctions, path collisions, unexpected documents, and stale viewer
  identities are rejected; and
* an existing output path is never replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable


MANIFEST_NAME = "STEP3_REVIEW_MANIFEST.json"
MANIFEST_VERSION = 1
PACKAGE_ID = "force-curve-bench-fc-3.4-review.2-6e86ac19"
WARNING = "STEP 3 REVIEW CANDIDATE — NOT DEPLOYED OR RELEASE ELIGIBLE"
INVENTORY_SCOPE = f"all regular files except {MANIFEST_NAME}"

BENCH_BUILD = "fc-3.4-review.2"
REPO_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
EVIDENCE_IDENTITY = (
    "7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a"
)
CANONICAL_PACKAGE_ID = "canonical-evidence-epoch-6e86ac19-step2"
CANONICAL_VERIFIER_SHA256 = (
    "36faf29111351a66e71b9d0f1a61c1d14cad4603181806c45f538e52fbad017e"
)
CANONICAL_PREFIX = "canonical-evidence"
CANONICAL_VERIFIER = "tools/verify_canonical_epoch.py"
CANONICAL_WORKBOOK_EXCEPTION = (
    f"{CANONICAL_PREFIX}/epoch_inputs/source_workbook/untested-domes_v2.xlsx"
)

PRESENTATION_ROLE = "review_candidate"
DATA_ARTIFACT_ROLE = "canonical_retention_authority"
AXIS_BASE_MAX_MM = 4.0
AXIS_RELEASE_MAX_MM = 4.5
PILOT_ID = "subjective-pilot-v1"
PILOT_WORKBOOK_SHA256 = (
    "d4bbaad6831ccab1003bcc7e2974ef7100ee32e083fa88f27d468e64d7a323d0"
)
PILOT_CHECKSUMS_SHA256 = (
    "edf9e1fcf463b6d281c5bd76d9fdc6891192d0e4f4fca46fa1fdd01d2579f7fd"
)
PILOT_SOURCE_IDENTITY_SHA256 = (
    "8ebabff34ba0118a7868825d9c9a1d9eef24588b299e677d1dda0d4c88599704"
)
EXPECTED_COUNTS = {
    "records": 76,
    "sets": 76,
    "retained_run_bindings": 184,
    "unique_acquisitions": 180,
    "independent_measurement_cohorts": 75,
    "shared_evidence_alias_groups": 1,
}

VTEST_RECORD_FIELDS = {
    "id": "test_id",
    "k": "kind",
    "n": "name",
    "set": "set",
    "source_set": "set",
    "runs": "runs_used",
    "brand": "brand",
    "mfr": "manufacturer",
    "wt": "nominal_weight_g",
    "ver": "variant",
    "sty": "style",
    "pre": "precompression_mm",
    "sl": "slider",
    "rg": "silencing_ring",
    "h1": "housing",
    "dv": "travel_dev_mm",
    "cohort": "measurement_cohort_id",
    "alias_group": "evidence_alias_group",
    "alias_role": "evidence_alias_role",
    "quality_flags": "quality_flags",
    "null_reasons": "null_reasons",
    "cg": "collapse_force_gf",
    "cx": "collapse_travel_mm",
    "sn": "snap_pct",
    "en": "full_stroke_press_work_gf_mm",
    "tv": "travel_mm",
    "vF": "valley_force_gf",
    "vx": "valley_travel_mm",
    "pcw": "precollapse_work_gf_mm",
    "dg": "drop_gf",
    "dxd": "drop_travel_mm",
    "dr": "drop_rate_gf_per_mm",
    "ndr": "norm_drop_rate_per_mm",
    "sd": "steepest_drop_0p10mm_gf_per_mm",
    "rp": "ramp_10_90_gf_per_mm",
}

PERCEPTION_COMPONENTS = {
    "collapse_force_gf": "cg",
    "ramp_10_90_gf_per_mm": "rp",
    "precollapse_work_gf_mm": "pcw",
    "drop_gf": "dg",
    "steepest_drop_0p10mm_gf_per_mm": "sd",
    "drop_rate_gf_per_mm": "dr",
    "snap_pct": "sn",
}

# Trust root for the presentation-only perception model.  The verifier does
# not import or execute live/package source while validating an immutable
# package: it independently checks this exact contract and recomputes every
# embedded score from the sealed canonical records.
PERCEPTION_MODEL_CONTRACT = {
    "version": "perception-rank-v1",
    "artifact_role": "pilot_derived_presentation_index",
    "validation_status": "exploratory_single_rater_fixed_order_panel",
    "pilot_id": PILOT_ID,
    "pilot_workbook_sha256": PILOT_WORKBOOK_SHA256,
    "objective_evidence_identity": EVIDENCE_IDENTITY,
    "objective_repo_commit": REPO_COMMIT,
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

TOP_LEVEL_FIELDS = {
    "manifest_version",
    "package_id",
    "artifact_role",
    "presentation_role",
    "release_eligible",
    "warning",
    "bench_build",
    "repo_commit",
    "evidence_identity",
    "data_authority",
    "counts",
    "viewer",
    "subjective_pilot",
    "canonical_evidence",
    "source_snapshot",
    "sealed_document_exception",
    "inventory_scope",
    "files",
}
FILE_FIELDS = {"path", "bytes", "sha256"}

# This is a deliberately small overlay on the complete generator snapshot in
# canonical-evidence/generator.  It contains only Step-3 presentation, pilot,
# runtime-test, and packaging material; it excludes the historical 917 tools.
SOURCE_SNAPSHOT_FILES = (
    "generator/domelab_pipeline/packs.py",
    "generator/domelab_pipeline/perception.py",
    "generator/domelab_pipeline/prose.py",
    "generator/domelab_pipeline/release_reference/index.release.html",
    "generator/js/package-lock.json",
    "generator/js/package.json",
    "generator/tests/test_review_redteam_gates.py",
    "generator/tests/test_step3_review_packager.py",
    "generator/tests/test_viewer_review_build.py",
    "generator/tests/viewer_curve_battery.js",
    "generator/tests/viewer_offline_battery.js",
    "generator/tests/viewer_online_battery.js",
    "generator/tests/viewer_review_redteam_runtime.js",
    "generator/tests/viewer_review_runtime.js",
    "generator/tools/build_step3_review.py",
    "generator/tools/build_subjective_pilot.py",
)
SOURCE_README_PATH = "source-snapshot/README.md"
SOURCE_README = """# Step-3 source overlay

This directory is the minimal source overlay for the fc-3.4 review viewer and
its subjective-pilot sidecar.  The complete frozen Step-2 generator baseline is
in `../canonical-evidence/generator/`.  Apply these paths over that baseline to
inspect the current presentation changes.  Historical 917 review-envelope
tools are intentionally not part of this overlay and remain historical.
"""

STALE_VIEWER_PATTERNS = {
    "ambiguous Topre reference": re.compile(
        r"canonStats\(\s*[\"']Topre_45g[\"']\s*\)"
    ),
    "removed spreadsheet link": re.compile(r"ec-parts-dataset\.xlsx", re.I),
    "pre-fleet review wording": re.compile(r"not the retest fleet", re.I),
    "obsolete fc-3.1 build": re.compile(r"fc-3\.1-review", re.I),
    "obsolete fc-3.2 build": re.compile(r"fc-3\.2-review", re.I),
    "obsolete fc-3.3 build": re.compile(r"fc-3\.3-review", re.I),
    "obsolete public article": re.compile(
        r"unrealkeyboards\.com/blogs/topre-mods/topre-dome-force-curves", re.I
    ),
    "unpinned main-branch link": re.compile(r"/blob/main/|const\s+BRANCH\s*=\s*[\"']main"),
    "retired picker link": re.compile(r"href\s*=\s*[\"']dome-lab-parts\.html[\"']", re.I),
}

REQUIRED_PERCEPTION_LANGUAGE = (
    'data-m="profileWeight">Weight profile</button>',
    'data-m="profileTactility">Tactility profile</button>',
    'data-m="indexScatter">Weight vs tactility</button>',
    "Pilot-derived Weight Index",
    "Pilot-derived Tactility-sharpness Index",
    "Weight Index (0\u2013100)",
    "Tactility-sharpness Index (0\u2013100)",
    "Not calibrated",
    "Not available",
    "Weight Index</b> is this dome’s weight percentile compared with the other domes tested.",
    "Tactility Index</b> is this dome’s tactility percentile compared with the other domes tested.",
    "not predicted 1\u201310 ratings",
)

FORBIDDEN_ACTIVE_VIEWER_MARKERS = (
    "80 is not twice 40",
    "INDEX_SCALE_NOTE",
    "forceWallDelta",
    "wallDelta",
    "force_wall_reference",
)

REQUIRED_EXPORT_MARKERS = (
    'function drawExportWatermark(g,w,h)',
    'const text="UNREAL KEYBOARDS"',
    'g.fillStyle="rgba(28,36,34,.055)"',
    'drawExportWatermark(g,w,h);',
)

# The scatter is a presentation of the already sealed perception scores, never
# a new model or a projection of uncalibrated part assemblies.  These markers
# couple the packager to the executable comparison path rather than accepting
# axis prose alone.
REQUIRED_INDEX_SCATTER_SOURCE_PATTERNS = {
    "scatter draw routine": re.compile(r"\bfunction\s+drawIndexScatter\s*\("),
    "scatter hover target buffer": re.compile(r"\bSCATTER_PTS\b"),
    "scatter mode dispatch": re.compile(
        r"chartMode\s*===\s*[\"']indexScatter[\"']"
    ),
    "scatter calibrated/null-safe predicate": re.compile(
        r"\bfunction\s+isIndexScatterEligible\s*\([^)]*\)\s*\{"
        r"[^{}]*dome_baseline[^{}]*isNum\([^)]*(?:weightIndex|\.wi)\)"
        r"[^{}]*isNum\([^)]*(?:tactilityIndex|\.ti)\)[^{}]*\}",
        re.S,
    ),
}

VISIBLE_LOW_ASSOCIATION_PATTERNS = {
    "full-stroke press-work label": re.compile(
        r"\bfull[-\u2011\u2013 ]stroke\s+press[- ]work\b", re.I
    ),
    "press-work-to-force-wall label": re.compile(
        r"\bpress[- ]work[- ]to[- ]force[- ]wall\b", re.I
    ),
    "full-press-work label": re.compile(r"\bfull[- ]press[- ]work\b", re.I),
    "normalized-drop-rate label": re.compile(
        r"\b(?:normalized|norm\.)\s+drop\s+rate\b", re.I
    ),
    "retired press-work comparison": re.compile(r"\bpress\s+work\s+vs\s+snap\b", re.I),
    "retired NDR comparison": re.compile(r"\bdrop\s+rate\s+vs\s+NDR\b", re.I),
    "retired scatter mode": re.compile(r"data-m\s*=\s*[\"']scatter(?:2)?[\"']", re.I),
}


class Step3ReviewError(RuntimeError):
    """The requested package is incomplete, contradictory, or unsafe."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise Step3ReviewError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, Step3ReviewError) as error:
        raise Step3ReviewError(f"cannot read strict UTF-8 JSON {path}: {error}") from error


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(payload)


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _path_is_within(path: Path, root: Path) -> bool:
    """Case-safe containment for an output that does not exist yet."""
    try:
        common = os.path.commonpath(
            [os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))]
        )
    except ValueError:
        return False
    return common == os.path.normcase(os.path.abspath(root))


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except AttributeError:
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _resolve_directory(path: str | os.PathLike[str], label: str) -> Path:
    candidate = Path(path)
    if candidate.is_symlink() or _is_reparse_point(candidate) or not candidate.is_dir():
        raise Step3ReviewError(
            f"{label} must be an existing non-link directory: {candidate}"
        )
    try:
        return candidate.resolve(strict=True)
    except OSError as error:
        raise Step3ReviewError(f"cannot resolve {label} {candidate}: {error}") from error


def _normalize_relative(raw: Any, label: str = "path") -> str:
    if not isinstance(raw, str) or not raw:
        raise Step3ReviewError(f"{label} must be a nonempty string")
    if "\\" in raw or ":" in raw or "\x00" in raw or raw.startswith("/"):
        raise Step3ReviewError(f"unsafe {label}: {raw!r}")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or pure.as_posix() != raw:
        raise Step3ReviewError(f"non-canonical {label}: {raw!r}")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise Step3ReviewError(f"unsafe {label}: {raw!r}")
    return raw


def _scan_regular_files(root: Path) -> dict[str, Path]:
    """Return an exhaustive safe inventory, rejecting all link-like entries."""
    root = _resolve_directory(root, "package tree")
    files: dict[str, Path] = {}
    folded: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        kept: list[str] = []
        for name in sorted(dirnames):
            child = directory_path / name
            relative = _normalize_relative(child.relative_to(root).as_posix())
            if child.is_symlink() or _is_reparse_point(child) or not child.is_dir():
                raise Step3ReviewError(f"linked or non-directory entry is forbidden: {relative}")
            kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            child = directory_path / name
            relative = _normalize_relative(child.relative_to(root).as_posix())
            if child.is_symlink() or _is_reparse_point(child) or not child.is_file():
                raise Step3ReviewError(f"linked or non-regular file is forbidden: {relative}")
            key = relative.casefold()
            if key in folded:
                raise Step3ReviewError(
                    f"case-insensitive path collision: {folded[key]!r} and {relative!r}"
                )
            folded[key] = relative
            files[relative] = child
    return files


def _regular_file_within(root: Path, relative: str, label: str) -> Path:
    relative = _normalize_relative(relative, label)
    path = root / Path(*PurePosixPath(relative).parts)
    if path.is_symlink() or _is_reparse_point(path) or not path.is_file():
        raise Step3ReviewError(f"{label} must be a regular non-link file: {path}")
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise Step3ReviewError(f"{label} escapes its root: {path}") from error
    return path


def _extract_json_const(source: str, name: str) -> Any:
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=", source)
    if not match:
        raise Step3ReviewError(f"viewer has no generated {name} constant")
    start = match.end()
    while start < len(source) and source[start].isspace():
        start += 1
    try:
        value, end = json.JSONDecoder(object_pairs_hook=_reject_duplicate_keys).raw_decode(
            source, start
        )
    except (json.JSONDecodeError, Step3ReviewError) as error:
        raise Step3ReviewError(f"viewer {name} is not strict JSON: {error}") from error
    if source[end:].lstrip()[:1] != ";":
        raise Step3ReviewError(f"viewer {name} JSON is not terminated by a semicolon")
    return value


def _read_utf8(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise Step3ReviewError(f"cannot read {label} as UTF-8: {path}: {error}") from error


def _reject_stale_viewer(source: str, label: str) -> None:
    found = [name for name, pattern in STALE_VIEWER_PATTERNS.items() if pattern.search(source)]
    if found:
        raise Step3ReviewError(f"{label} contains stale viewer material: {found}")


def _require_bool(value: Any, expected: bool, label: str) -> None:
    if type(value) is not bool or value is not expected:
        raise Step3ReviewError(f"{label} must be exactly {expected!r}, got {value!r}")


def _canonical_manifest_contract(root: Path) -> dict[str, Any]:
    manifest = _read_json(_regular_file_within(root, "EPOCH_MANIFEST.json", "epoch manifest"))
    if not isinstance(manifest, dict):
        raise Step3ReviewError("canonical EPOCH_MANIFEST.json must be an object")
    if manifest.get("package_id") != CANONICAL_PACKAGE_ID:
        raise Step3ReviewError("wrong canonical package_id")
    frozen = manifest.get("frozen_repository")
    identity = manifest.get("identity")
    counts = manifest.get("expected_counts")
    scope = manifest.get("scope")
    if not isinstance(frozen, dict) or frozen.get("commit_oid") != REPO_COMMIT:
        raise Step3ReviewError("canonical package does not pin the required repository commit")
    if not isinstance(identity, dict) or identity.get("evidence_epoch_hash") != EVIDENCE_IDENTITY:
        raise Step3ReviewError("canonical package has the wrong evidence identity")
    if not isinstance(counts, dict) or any(
        (
            counts.get("semantic_records") != EXPECTED_COUNTS["records"],
            counts.get("curve_packs") != EXPECTED_COUNTS["sets"],
            counts.get("raw_paths") != EXPECTED_COUNTS["retained_run_bindings"],
            counts.get("unique_acquisitions") != EXPECTED_COUNTS["unique_acquisitions"],
        )
    ):
        raise Step3ReviewError("canonical package has unexpected 76/76/184/180 counts")
    if not isinstance(scope, dict) or scope.get("completed_step") != 2:
        raise Step3ReviewError("canonical package is not the sealed Step-2 scope")
    return manifest


def _run_canonical_verifier(root: Path) -> dict[str, Any]:
    verifier = _regular_file_within(root, CANONICAL_VERIFIER, "canonical verifier")
    digest = _sha256(verifier)
    if digest != CANONICAL_VERIFIER_SHA256:
        raise Step3ReviewError(
            f"canonical verifier SHA-256 mismatch: {digest}"
        )
    try:
        run = subprocess.run(
            [sys.executable, os.fspath(verifier), os.fspath(root), "--compact"],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=300,
            check=False,
        )
    except (OSError, UnicodeError, subprocess.SubprocessError) as error:
        raise Step3ReviewError(f"cannot run canonical verifier: {error}") from error
    try:
        report = json.loads(run.stdout, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, Step3ReviewError) as error:
        raise Step3ReviewError(
            f"canonical verifier did not emit one strict JSON report: {error}; "
            f"stderr={run.stderr[-1000:]!r}"
        ) from error
    if (
        run.returncode != 0
        or not isinstance(report, dict)
        or report.get("status") != "PASS"
        or report.get("package_id") != CANONICAL_PACKAGE_ID
        or report.get("repo_commit") != REPO_COMMIT
    ):
        raise Step3ReviewError(
            "sealed canonical verifier failed or reported the wrong identity: "
            f"returncode={run.returncode}, report={report!r}, stderr={run.stderr[-1000:]!r}"
        )
    return report


def _verify_canonical_package(root: Path) -> dict[str, Any]:
    root = _resolve_directory(root, "sealed canonical Step-2 package")
    manifest = _canonical_manifest_contract(root)
    report = _run_canonical_verifier(root)
    retained_path = manifest.get("canonical_artifacts", {}).get("retained_run_manifest")
    aggregate_path = manifest.get("canonical_artifacts", {}).get("aggregate_results")
    if not isinstance(retained_path, str):
        raise Step3ReviewError("canonical manifest has no retained-run artifact path")
    if not isinstance(aggregate_path, str):
        raise Step3ReviewError("canonical manifest has no aggregate-results artifact path")
    retained = _regular_file_within(root, retained_path, "canonical retained-run manifest")
    aggregate = _regular_file_within(root, aggregate_path, "canonical aggregate results")
    return {
        "root": root,
        "manifest": manifest,
        "report": report,
        "retained": retained,
        "aggregate": aggregate,
    }


def _validate_schema(schema_path: Path) -> dict[str, Any]:
    schema = _read_json(schema_path)
    if not isinstance(schema, dict) or schema.get("repo_commit") != REPO_COMMIT:
        raise Step3ReviewError("schema metadata does not pin the required commit")
    evidence = schema.get("evidence_epoch")
    intake = schema.get("intake_policy")
    if not isinstance(evidence, dict) or evidence.get("identity") != EVIDENCE_IDENTITY:
        raise Step3ReviewError("schema metadata has the wrong canonical evidence identity")
    schema_counts = {
        "records": evidence.get("semantic_record_count"),
        "sets": evidence.get("semantic_set_count"),
        "retained_run_bindings": evidence.get("raw_path_count"),
        "unique_acquisitions": evidence.get("unique_raw_evidence_count"),
        "independent_measurement_cohorts": evidence.get(
            "independent_measurement_cohort_count"
        ),
        "shared_evidence_alias_groups": evidence.get(
            "shared_evidence_alias_group_count"
        ),
    }
    if schema_counts != EXPECTED_COUNTS:
        raise Step3ReviewError(f"schema metadata count mismatch: {schema_counts}")
    if not isinstance(intake, dict) or intake.get("artifact_role") != DATA_ARTIFACT_ROLE:
        raise Step3ReviewError("schema metadata does not declare canonical retention authority")
    _require_bool(intake.get("canonical_membership_active"), True, "canonical membership")
    _require_bool(intake.get("membership_applied_to_outputs"), True, "applied membership")
    _require_bool(intake.get("release_eligible"), True, "canonical data release eligibility")
    provenance = schema.get("provenance_hashes")
    if not isinstance(provenance, dict) or any(
        not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get(field, "")))
        for field in ("generator_source_hash", "release_reference_hash")
    ):
        raise Step3ReviewError("schema metadata lacks Step-3 source provenance hashes")
    return schema


def _canonical_records(aggregate_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    records = _read_json(aggregate_path)
    if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
        raise Step3ReviewError("canonical aggregate results must be an array of objects")
    if len(records) != EXPECTED_COUNTS["records"]:
        raise Step3ReviewError("canonical aggregate results do not contain 76 records")
    by_id = {record.get("test_id"): record for record in records}
    if len(by_id) != EXPECTED_COUNTS["records"] or None in by_id:
        raise Step3ReviewError("canonical aggregate result IDs are missing or duplicated")
    if len({record.get("set") for record in records}) != EXPECTED_COUNTS["sets"]:
        raise Step3ReviewError("canonical aggregate source sets are missing or duplicated")
    return records, by_id


def _canonical_retained_contract(decision_path: Path) -> dict[str, Any]:
    decision = _read_json(decision_path)
    if not isinstance(decision, dict):
        raise Step3ReviewError("canonical retained-run manifest must be an object")
    if decision.get("artifact_role") != DATA_ARTIFACT_ROLE:
        raise Step3ReviewError("retained-run manifest is not canonical data authority")
    _require_bool(decision.get("release_eligible"), True, "retained-run release eligibility")
    sets = decision.get("sets")
    if not isinstance(sets, list) or not all(isinstance(entry, dict) for entry in sets):
        raise Step3ReviewError("retained-run manifest sets must be an array of objects")
    by_set: dict[str, list[dict[str, Any]]] = {}
    all_paths: list[str] = []
    acquisition_ids: set[str] = set()
    turnaround: dict[str, tuple[float, float]] = {}
    ramp_review_count = 0
    for entry in sets:
        set_name = entry.get("set")
        if not isinstance(set_name, str) or not set_name or set_name in by_set:
            raise Step3ReviewError("retained-run manifest set names are missing or duplicated")
        runs = entry.get("runs")
        if not isinstance(runs, list) or not all(isinstance(run, dict) for run in runs):
            raise Step3ReviewError(f"retained-run manifest has malformed runs for {set_name}")
        retained = [run for run in runs if run.get("retained") is True]
        if entry.get("status") != "accepted" or len(retained) != entry.get("retained_count"):
            raise Step3ReviewError(f"canonical retained membership is inconsistent for {set_name}")
        if len(retained) < 2:
            raise Step3ReviewError(f"canonical set has fewer than two retained runs: {set_name}")
        maxima: list[float] = []
        for run in retained:
            raw_path = _normalize_relative(run.get("raw_path"), "canonical raw path")
            if not raw_path.startswith(set_name + "/"):
                raise Step3ReviewError(f"canonical raw path is bound to the wrong set: {raw_path}")
            if PurePosixPath(raw_path).name != run.get("run"):
                raise Step3ReviewError(f"canonical run basename mismatch: {raw_path}")
            acquisition_id = run.get("acquisition_id")
            if not isinstance(acquisition_id, str) or not acquisition_id.startswith("acq_sha256:"):
                raise Step3ReviewError(f"canonical run lacks acquisition identity: {raw_path}")
            observations = run.get("intake_qc", {}).get("observations", {})
            maximum = observations.get("maximum_travel_mm")
            if type(maximum) not in (int, float) or not math.isfinite(float(maximum)):
                raise Step3ReviewError(f"canonical run lacks recorded turnaround: {raw_path}")
            if type(run.get("ramp_review_required")) is not bool:
                raise Step3ReviewError(f"canonical run lacks boolean RAMP review state: {raw_path}")
            ramp_review_count += int(run["ramp_review_required"])
            maxima.append(float(maximum))
            all_paths.append(raw_path)
            acquisition_ids.add(acquisition_id)
        by_set[set_name] = retained
        turnaround[set_name] = (min(maxima), max(maxima))
    if len(by_set) != EXPECTED_COUNTS["sets"]:
        raise Step3ReviewError("retained-run manifest does not contain 76 sets")
    if len(all_paths) != EXPECTED_COUNTS["retained_run_bindings"]:
        raise Step3ReviewError("retained-run manifest does not contain 184 retained bindings")
    if len(acquisition_ids) != EXPECTED_COUNTS["unique_acquisitions"]:
        raise Step3ReviewError("retained-run manifest does not contain 180 unique acquisitions")
    if ramp_review_count != 0:
        raise Step3ReviewError("frozen canonical fleet unexpectedly contains RAMP reviews")
    return {
        "decision": decision,
        "by_set": by_set,
        "paths": sorted(all_paths),
        "turnaround": turnaround,
        "ramp_review_count": ramp_review_count,
    }


def _embedded_contract(
    embedded: Any,
    retained: dict[str, Any],
) -> float:
    if not isinstance(embedded, dict) or set(embedded) != set(retained["by_set"]):
        raise Step3ReviewError("EMBEDDED set membership differs from canonical retained membership")
    domain_max = 0.0
    for set_name, value in embedded.items():
        if not isinstance(value, dict) or set(value) != {"n", "p", "r"}:
            raise Step3ReviewError(f"EMBEDDED entry has the wrong shape: {set_name}")
        if value["n"] != len(retained["by_set"][set_name]):
            raise Step3ReviewError(f"EMBEDDED run count differs from canonical data: {set_name}")
        for branch_name in ("p", "r"):
            branch = value[branch_name]
            if not isinstance(branch, dict) or set(branch) != {"x0", "df"}:
                raise Step3ReviewError(f"EMBEDDED {set_name}/{branch_name} has the wrong shape")
            x0, deltas = branch["x0"], branch["df"]
            if type(x0) is not int or not isinstance(deltas, list) or not deltas:
                raise Step3ReviewError(f"EMBEDDED {set_name}/{branch_name} is empty or malformed")
            if any(type(delta) is not int for delta in deltas):
                raise Step3ReviewError(f"EMBEDDED {set_name}/{branch_name} has non-integer deltas")
            endpoint = (x0 + len(deltas) - 1) / 200
            if not math.isfinite(endpoint) or endpoint < 0:
                raise Step3ReviewError(f"EMBEDDED {set_name}/{branch_name} has an invalid domain")
            domain_max = max(domain_max, endpoint)
    return domain_max


def _compare_vtests(
    rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    retained: dict[str, Any],
) -> None:
    by_id = {record["test_id"]: record for record in records}
    if {row.get("id") for row in rows} != set(by_id):
        raise Step3ReviewError("VTESTS record IDs differ from canonical aggregate results")
    for row in rows:
        record = by_id[row["id"]]
        mismatches: dict[str, dict[str, Any]] = {}
        for viewer_field, record_field in VTEST_RECORD_FIELDS.items():
            expected = record.get(record_field)
            if viewer_field == "quality_flags" and expected is None:
                expected = []
            elif viewer_field == "null_reasons" and expected is None:
                expected = {}
            if row.get(viewer_field) != expected:
                mismatches[viewer_field] = {
                    "expected": expected,
                    "actual": row.get(viewer_field),
                }
        base_expected = bool(record.get("is_baseline"))
        if type(row.get("base")) is not bool or row.get("base") is not base_expected:
            mismatches["base"] = {"expected": base_expected, "actual": row.get("base")}
        review_count = len(record.get("intake_review_notices", []))
        if row.get("intake_review_count") != review_count:
            mismatches["intake_review_count"] = {
                "expected": review_count,
                "actual": row.get("intake_review_count"),
            }
        bounds = retained["turnaround"][record["set"]]
        if row.get("tl_min") != bounds[0] or row.get("tl_max") != bounds[1]:
            mismatches["turnaround"] = {
                "expected": list(bounds),
                "actual": [row.get("tl_min"), row.get("tl_max")],
            }
        if mismatches:
            raise Step3ReviewError(
                f"VTESTS record differs from sealed canonical evidence: {row['id']}: {mismatches}"
            )
    if len({row.get("cohort") for row in rows}) != 75:
        raise Step3ReviewError("VTESTS does not preserve the 75 independent measurement cohorts")
    alias_groups = {row.get("alias_group") for row in rows if row.get("alias_group") is not None}
    if len(alias_groups) != 1:
        raise Step3ReviewError("VTESTS does not preserve the one shared-evidence alias group")


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


def _perception_percentile(value: Any, reference: list[float]) -> float | None:
    """Independent implementation of perception-rank-v1's frozen percentile."""
    if not _finite_number(value):
        return None
    numeric = float(value)
    left = 0
    while left < len(reference) and reference[left] < numeric:
        left += 1
    right = left
    while right < len(reference) and reference[right] == numeric:
        right += 1
    denominator = len(reference) - 1
    if right > left:
        return 100.0 * ((left + right - 1) / 2.0) / denominator
    if left == 0:
        return 0.0
    if left == len(reference):
        return 100.0

    lower_value = reference[left - 1]
    upper_value = reference[left]
    lower_left = reference.index(lower_value)
    lower_right = len(reference) - list(reversed(reference)).index(lower_value)
    upper_left = reference.index(upper_value)
    upper_right = len(reference) - list(reversed(reference)).index(upper_value)
    lower_pct = 100.0 * ((lower_left + lower_right - 1) / 2.0) / denominator
    upper_pct = 100.0 * ((upper_left + upper_right - 1) / 2.0) / denominator
    fraction = (numeric - lower_value) / (upper_value - lower_value)
    return lower_pct + fraction * (upper_pct - lower_pct)


def _expected_perception_scores(
    records: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    eligible = [
        record
        for record in records
        if record.get("kind") == "dome_baseline"
        and isinstance(record.get("provenance"), dict)
        and record["provenance"].get("release_eligible") is True
    ]
    for record in eligible:
        provenance = record["provenance"]
        if provenance.get("repo_commit") != REPO_COMMIT:
            raise Step3ReviewError(
                "perception reference does not pin the frozen repository commit"
            )
        if provenance.get("config_hash") != EVIDENCE_IDENTITY:
            raise Step3ReviewError(
                "perception reference does not pin the frozen evidence identity"
            )
    cohort_records: dict[str, dict[str, Any]] = {}
    for record in eligible:
        cohort = record.get("measurement_cohort_id")
        if not isinstance(cohort, str) or not cohort:
            raise Step3ReviewError(
                "perception reference requires measurement-cohort identities"
            )
        previous = cohort_records.get(cohort)
        if previous is None:
            cohort_records[cohort] = record
            continue
        for field in PERCEPTION_COMPONENTS:
            if not _same_nullable_number(previous.get(field), record.get(field)):
                raise Step3ReviewError(
                    f"perception reference cohort has divergent {field}: {cohort}"
                )
    expected_count = PERCEPTION_MODEL_CONTRACT["reference_count"]
    if len(cohort_records) != expected_count:
        raise Step3ReviewError(
            "perception reference count mismatch: "
            f"expected {expected_count}, found {len(cohort_records)}"
        )

    reference: dict[str, list[float]] = {}
    for field in PERCEPTION_COMPONENTS:
        values = [record.get(field) for record in cohort_records.values()]
        if not all(_finite_number(value) for value in values):
            raise Step3ReviewError(
                f"perception reference metric has missing values: {field}"
            )
        reference[field] = sorted(float(value) for value in values)

    expected: dict[str, dict[str, Any]] = {}
    for record in records:
        test_id = record.get("test_id")
        if not isinstance(test_id, str) or not test_id:
            raise Step3ReviewError("perception scoring requires canonical test IDs")
        calibrated = record.get("kind") == "dome_baseline"
        components = {
            viewer_key: (
                _perception_percentile(record.get(field), reference[field])
                if calibrated
                else None
            )
            for field, viewer_key in PERCEPTION_COMPONENTS.items()
        }
        expected[test_id] = {
            "wi": components[PERCEPTION_MODEL_CONTRACT["weight"]["primary_viewer_key"]],
            "ti": components[
                PERCEPTION_MODEL_CONTRACT["tactility"]["primary_viewer_key"]
            ],
            "pp": components,
        }
    return expected


def _validate_perception_contract(
    source: str,
    model: Any,
    rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    if model != PERCEPTION_MODEL_CONTRACT:
        raise Step3ReviewError("PERCEPTION_MODEL differs from perception-rank-v1 contract")
    missing_language = [
        marker for marker in REQUIRED_PERCEPTION_LANGUAGE if marker not in source
    ]
    if missing_language:
        raise Step3ReviewError(
            f"viewer lacks required visible perception profile/index language: {missing_language}"
        )
    forbidden = [
        label
        for label, pattern in VISIBLE_LOW_ASSOCIATION_PATTERNS.items()
        if pattern.search(source)
    ]
    if forbidden:
        raise Step3ReviewError(
            f"viewer exposes retired low-association metric labels/modes: {forbidden}"
        )

    missing_scatter_source = [
        label
        for label, pattern in REQUIRED_INDEX_SCATTER_SOURCE_PATTERNS.items()
        if not pattern.search(source)
    ]
    if missing_scatter_source:
        raise Step3ReviewError(
            "viewer lacks required Weight Index vs Tactility-sharpness Index "
            f"scatter behavior: {missing_scatter_source}"
        )
    scatter_domain = re.search(
        r"\bconst\s+INDEX_SCATTER_DOMAIN\s*=\s*"
        r"(?:Object\.freeze\(\s*)?\[\s*0(?:\.0)?\s*,\s*100(?:\.0)?\s*\]"
        r"(?:\s*\))?\s*;",
        source,
    )
    if scatter_domain is None or source.count("INDEX_SCATTER_DOMAIN") < 2:
        raise Step3ReviewError(
            "viewer perception scatter must use the shared exact 0-100 domain "
            "for both Weight Index and Tactility-sharpness Index axes"
        )

    expected = _expected_perception_scores(records)
    if {row.get("id") for row in rows} != set(expected):
        raise Step3ReviewError("perception-score record IDs differ from canonical evidence")
    for row in rows:
        actual = {field: row.get(field) for field in ("wi", "ti", "pp")}
        if actual != expected[row["id"]]:
            raise Step3ReviewError(
                "viewer perception score differs from sealed canonical evidence: "
                f"{row['id']}: expected={expected[row['id']]!r}, actual={actual!r}"
            )

    calibrated = [row for row in rows if row.get("k") == "dome_baseline"]
    if len(calibrated) != PERCEPTION_MODEL_CONTRACT["reference_count"]:
        raise Step3ReviewError(
            "perception scatter calibration population differs from the frozen "
            f"68-dome reference: {len(calibrated)}"
        )
    for row in calibrated:
        for field in ("wi", "ti"):
            value = row.get(field)
            if not _finite_number(value) or not 0.0 <= float(value) <= 100.0:
                raise Step3ReviewError(
                    "perception scatter score is not a finite 0-100 calibrated "
                    f"dome value: {row.get('id')}: {field}={value!r}"
                )
    for row in rows:
        if row.get("k") != "dome_baseline" and any(
            row.get(field) is not None for field in ("wi", "ti")
        ):
            raise Step3ReviewError(
                "perception scatter must not calibrate part-assembly records: "
                f"{row.get('id')}"
            )


def _validate_viewer(
    viewer_path: Path,
    schema_path: Path,
    aggregate_path: Path,
    decision_path: Path,
) -> dict[str, Any]:
    source = _read_utf8(viewer_path, "review viewer")
    _reject_stale_viewer(source, "review viewer")
    forbidden = [marker for marker in FORBIDDEN_ACTIVE_VIEWER_MARKERS if marker in source]
    if forbidden:
        raise Step3ReviewError(
            f"review viewer retains removed comparison/scale-note markers: {forbidden}"
        )
    missing_export = [marker for marker in REQUIRED_EXPORT_MARKERS if marker not in source]
    if missing_export:
        raise Step3ReviewError(
            f"review viewer lacks required PNG watermark behavior: {missing_export}"
        )
    watermark_call = source.index('drawExportWatermark(g,w,h);')
    scene_call = source.index('drawScene(g,w,h,{export:true,theme:"light"});')
    if watermark_call > scene_call:
        raise Step3ReviewError("PNG watermark must be drawn behind the exported chart")
    build = _extract_json_const(source, "VIEWER_BUILD")
    perception_model = _extract_json_const(source, "PERCEPTION_MODEL")
    rows = _extract_json_const(source, "VTESTS")
    canonical_runs = _extract_json_const(source, "CANONICAL_RUNS")
    fallback_paths = _extract_json_const(source, "FALLBACK_CSVS")
    embedded = _extract_json_const(source, "EMBEDDED")
    ramp_reviews = _extract_json_const(source, "INTAKE_RAMP_REVIEWS_BY_SET")
    if not isinstance(build, dict):
        raise Step3ReviewError("VIEWER_BUILD must be an object")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise Step3ReviewError("VTESTS must be an array of objects")
    schema = _validate_schema(schema_path)
    records, _records_by_id = _canonical_records(aggregate_path)
    retained = _canonical_retained_contract(decision_path)
    embedded_domain = _embedded_contract(embedded, retained)
    canonical_walls = [
        float(record["travel_mm"])
        for record in records
        if type(record.get("travel_mm")) in (int, float)
        and math.isfinite(float(record["travel_mm"]))
    ]
    if not canonical_walls:
        raise Step3ReviewError("canonical aggregate results have no detected force-wall onset")
    force_wall_domain = max(canonical_walls)
    if force_wall_domain > AXIS_RELEASE_MAX_MM:
        raise Step3ReviewError(
            f"released force-wall onset {force_wall_domain!r} exceeds the {AXIS_RELEASE_MAX_MM:.1f} mm axis limit"
        )
    expected_scalars = {
        "mode": "review",
        "bench_build": BENCH_BUILD,
        "presentation_role": PRESENTATION_ROLE,
        "repo_commit": REPO_COMMIT,
        "data_identity": EVIDENCE_IDENTITY,
        "canonical_evidence_identity": EVIDENCE_IDENTITY,
        "data_artifact_role": DATA_ARTIFACT_ROLE,
        "subjective_pilot_id": PILOT_ID,
        "subjective_pilot_workbook_sha256": PILOT_WORKBOOK_SHA256,
        "perception_score_version": PERCEPTION_MODEL_CONTRACT["version"],
        "record_count": EXPECTED_COUNTS["records"],
        "set_count": EXPECTED_COUNTS["sets"],
        "retained_run_count": EXPECTED_COUNTS["retained_run_bindings"],
        "semantic_run_binding_count": EXPECTED_COUNTS["retained_run_bindings"],
        "unique_acquisition_count": EXPECTED_COUNTS["unique_acquisitions"],
        "independent_measurement_cohort_count": EXPECTED_COUNTS[
            "independent_measurement_cohorts"
        ],
        "shared_evidence_alias_group_count": EXPECTED_COUNTS[
            "shared_evidence_alias_groups"
        ],
        "metrics": schema.get("metrics_version"),
        "intake": schema.get("intake_policy", {}).get("version"),
        "intake_parity_target": schema.get("intake_policy", {}).get(
            "implementation_parity_target"
        ),
        "method_identity": schema.get("calc_version"),
        "data_epoch": "canonical-6e86ac1",
        "data_epoch_prefix": "canonical-",
        "axis_data_floor_mm": AXIS_BASE_MAX_MM,
        "force_wall_domain_max_mm": force_wall_domain,
        "ramp_review_run_count": 0,
        "ramp_review_set_count": 0,
    }
    mismatches = {
        key: {"expected": expected, "actual": build.get(key)}
        for key, expected in expected_scalars.items()
        if build.get(key) != expected
    }
    if mismatches:
        raise Step3ReviewError(f"VIEWER_BUILD identity mismatch: {mismatches}")
    _require_bool(build.get("release_eligible"), False, "viewer release eligibility")
    _require_bool(build.get("ramp_review_required"), False, "viewer RAMP review state")
    _require_bool(
        build.get("canonical_data_release_eligible"),
        True,
        "viewer canonical-data release eligibility",
    )
    curve_domain = build.get("curve_domain_max_mm")
    if type(curve_domain) not in (int, float) or not math.isfinite(float(curve_domain)):
        raise Step3ReviewError("VIEWER_BUILD curve domain must be finite")
    recorded_domain = max(bounds[1] for bounds in retained["turnaround"].values())
    if float(curve_domain) != recorded_domain:
        raise Step3ReviewError(
            f"VIEWER_BUILD curve domain {curve_domain!r} differs from recorded data {recorded_domain!r}"
        )
    if embedded_domain > float(curve_domain):
        raise Step3ReviewError(
            f"EMBEDDED domain {embedded_domain!r} exceeds VIEWER_BUILD {curve_domain!r}"
        )
    if len(rows) != EXPECTED_COUNTS["records"]:
        raise Step3ReviewError(f"VTESTS has {len(rows)} rows instead of 76")
    if len({row.get("id") for row in rows}) != EXPECTED_COUNTS["records"]:
        raise Step3ReviewError("VTESTS record IDs are missing or duplicated")
    if len({row.get("source_set") for row in rows}) != EXPECTED_COUNTS["sets"]:
        raise Step3ReviewError("VTESTS source-set count is not 76")
    if "documentation/subjective-pilot/index.html" not in source:
        raise Step3ReviewError("viewer has no packaged subjective-pilot link")
    _compare_vtests(rows, records, retained)
    _validate_perception_contract(source, perception_model, rows, records)
    expected_runs = {
        set_name: [PurePosixPath(run["raw_path"]).name for run in runs]
        for set_name, runs in retained["by_set"].items()
    }
    if canonical_runs != expected_runs:
        raise Step3ReviewError("CANONICAL_RUNS differs from sealed retained membership")
    if fallback_paths != retained["paths"]:
        raise Step3ReviewError("FALLBACK_CSVS differs from sealed retained raw paths")
    if ramp_reviews != {}:
        raise Step3ReviewError("viewer contains RAMP reviews absent from the frozen fleet")
    if any(
        type(record.get("travel_mm")) in (int, float)
        and float(record["travel_mm"]) > float(curve_domain)
        for record in records
    ):
        raise Step3ReviewError("viewer curve domain does not cover every force-wall marker")
    return {
        "source": source,
        "build": build,
        "perception_model": perception_model,
        "rows": rows,
        "schema_data": schema,
    }


def _validate_pilot(root: Path) -> dict[str, Any]:
    root = _resolve_directory(root, "subjective-pilot sidecar")
    files = _scan_regular_files(root)
    checksum_name = "SHA256SUMS.json"
    if checksum_name not in files or "source_identity.json" not in files or "index.html" not in files:
        raise Step3ReviewError("subjective pilot lacks its checksum, identity, or index")
    if _sha256(files[checksum_name]) != PILOT_CHECKSUMS_SHA256:
        raise Step3ReviewError("subjective-pilot SHA256SUMS.json trust-root mismatch")
    if _sha256(files["source_identity.json"]) != PILOT_SOURCE_IDENTITY_SHA256:
        raise Step3ReviewError("subjective-pilot source_identity.json trust-root mismatch")
    sums = _read_json(files[checksum_name])
    identity = _read_json(files["source_identity.json"])
    if not isinstance(sums, dict) or sums.get("pilot_id") != PILOT_ID:
        raise Step3ReviewError("subjective-pilot checksum identity mismatch")
    rows = sums.get("files")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise Step3ReviewError("subjective-pilot checksum files must be an array")
    declared: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for row in rows:
        if set(row) != FILE_FIELDS:
            raise Step3ReviewError("subjective-pilot checksum row has the wrong fields")
        relative = _normalize_relative(row.get("path"), "subjective-pilot checksum path")
        size, digest = row.get("bytes"), row.get("sha256")
        if type(size) is not int or size < 0 or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            raise Step3ReviewError("subjective-pilot checksum row has an invalid identity")
        if relative in declared or relative == checksum_name:
            raise Step3ReviewError("subjective-pilot checksum paths are duplicated or recursive")
        declared[relative] = (size, str(digest))
        order.append(relative)
    if order != sorted(order, key=lambda value: value.encode("utf-8")):
        raise Step3ReviewError("subjective-pilot checksum paths are not byte-path sorted")
    if set(files) != set(declared) | {checksum_name}:
        raise Step3ReviewError("subjective-pilot checksum inventory has missing or extra files")
    for relative, (size, digest) in declared.items():
        path = files[relative]
        if path.stat().st_size != size or _sha256(path) != digest:
            raise Step3ReviewError(f"subjective-pilot checksum mismatch: {relative}")
    if not isinstance(identity, dict):
        raise Step3ReviewError("subjective-pilot source identity must be an object")
    expected_identity = {
        "artifact_role": "exploratory_subjective_pilot",
        "release_eligible": False,
        "pilot_id": PILOT_ID,
        "objective_repo_commit": REPO_COMMIT,
        "objective_evidence_identity": EVIDENCE_IDENTITY,
        "workbook_included": False,
        "workbook_sha256": PILOT_WORKBOOK_SHA256,
    }
    mismatches = {
        key: {"expected": value, "actual": identity.get(key)}
        for key, value in expected_identity.items()
        if identity.get(key) != value
    }
    if mismatches:
        raise Step3ReviewError(f"subjective-pilot identity mismatch: {mismatches}")
    _require_bool(identity.get("release_eligible"), False, "subjective-pilot release eligibility")
    _require_bool(identity.get("workbook_included"), False, "subjective-pilot workbook inclusion")
    return {"root": root, "files": files, "identity": identity}


def _validate_staging(staging: Path, canonical: dict[str, Any]) -> dict[str, Any]:
    staging = _resolve_directory(staging, "Step-3 staging")
    viewer = _regular_file_within(staging, "packs/viewer.staged.html", "staged viewer")
    schema = _regular_file_within(staging, "schema_meta.staged.json", "staged schema metadata")
    decisions = _regular_file_within(
        staging, "intake_retention_decisions.json", "staged retained-run manifest"
    )
    if decisions.read_bytes() != canonical["retained"].read_bytes():
        raise Step3ReviewError("staged canonical retained-run manifest differs from sealed Step-2")
    validated = _validate_viewer(
        viewer,
        schema,
        canonical["aggregate"],
        canonical["retained"],
    )
    return {"root": staging, "viewer": viewer, "schema": schema, **validated}


def _validate_source_files(source_root: Path) -> dict[str, Path]:
    source_root = _resolve_directory(source_root, "current source root")
    result: dict[str, Path] = {}
    for relative in SOURCE_SNAPSHOT_FILES:
        result[relative] = _regular_file_within(
            source_root, relative, "Step-3 source overlay file"
        )
    template = _read_utf8(
        result["generator/domelab_pipeline/release_reference/index.release.html"],
        "viewer source template",
    )
    _reject_stale_viewer(template, "viewer source template")
    return result


def _source_provenance_hashes(generator_root: Path) -> dict[str, str]:
    package = _resolve_directory(generator_root / "domelab_pipeline", "generator package")
    release = _resolve_directory(package / "release_reference", "release-reference directory")
    python_files = {
        path.name: _sha256(path)
        for path in sorted(package.iterdir(), key=lambda item: item.name)
        if path.is_file() and not path.is_symlink() and path.suffix == ".py"
    }
    release_files = {
        path.name: _sha256(path)
        for path in sorted(release.iterdir(), key=lambda item: item.name)
        if path.is_file() and not path.is_symlink()
    }
    if not python_files or "index.release.html" not in release_files:
        raise Step3ReviewError("generator source snapshot is incomplete")
    return {
        "generator_source_hash": _canonical_hash(python_files),
        "release_reference_hash": _canonical_hash(release_files),
    }


def _reconstructed_source_provenance(package_root: Path) -> dict[str, str]:
    baseline = _resolve_directory(
        package_root / CANONICAL_PREFIX / "generator/domelab_pipeline",
        "sealed generator baseline",
    )
    overlay = _resolve_directory(
        package_root / "source-snapshot/generator/domelab_pipeline",
        "Step-3 source overlay",
    )
    baseline_release = _resolve_directory(
        baseline / "release_reference", "sealed release-reference baseline"
    )
    overlay_release = _resolve_directory(
        overlay / "release_reference", "Step-3 release-reference overlay"
    )

    python_paths = {
        path.name: path
        for path in baseline.iterdir()
        if path.is_file() and not path.is_symlink() and path.suffix == ".py"
    }
    for path in overlay.iterdir():
        if path.is_file() and not path.is_symlink() and path.suffix == ".py":
            python_paths[path.name] = path
    release_paths = {
        path.name: path
        for path in baseline_release.iterdir()
        if path.is_file() and not path.is_symlink()
    }
    for path in overlay_release.iterdir():
        if path.is_file() and not path.is_symlink():
            release_paths[path.name] = path
    return {
        "generator_source_hash": _canonical_hash(
            {name: _sha256(path) for name, path in sorted(python_paths.items())}
        ),
        "release_reference_hash": _canonical_hash(
            {name: _sha256(path) for name, path in sorted(release_paths.items())}
        ),
    }


def _check_document_policy(paths: Iterable[str]) -> None:
    forbidden: list[str] = []
    for relative in paths:
        suffix = PurePosixPath(relative).suffix.lower()
        if suffix not in {".xls", ".xlsx", ".pdf"}:
            continue
        if relative == CANONICAL_WORKBOOK_EXCEPTION:
            continue
        forbidden.append(relative)
    if forbidden:
        raise Step3ReviewError(
            f"new spreadsheet/PDF files are forbidden in the Step-3 review: {sorted(forbidden)}"
        )


def _inventory(root: Path, files: dict[str, Path]) -> list[dict[str, Any]]:
    return [
        {"path": relative, "bytes": files[relative].stat().st_size, "sha256": _sha256(files[relative])}
        for relative in sorted(files, key=lambda value: value.encode("utf-8"))
        if relative != MANIFEST_NAME
    ]


def _add_plan(
    plan: dict[str, Path | bytes],
    folded: dict[str, str],
    destination: str,
    source: Path | bytes,
) -> None:
    destination = _normalize_relative(destination, "planned destination")
    key = destination.casefold()
    if destination in plan or key in folded:
        raise Step3ReviewError(
            f"duplicate planned destination {destination!r}; conflicts with {folded.get(key)!r}"
        )
    plan[destination] = source
    folded[key] = destination


def _copy_plan(plan: dict[str, Path | bytes], destination: Path) -> None:
    for relative in sorted(plan, key=lambda value: value.encode("utf-8")):
        target = destination / Path(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        source = plan[relative]
        if isinstance(source, bytes):
            target.write_bytes(source)
        else:
            shutil.copyfile(source, target)


def _manifest_for(
    root: Path,
    canonical: dict[str, Any],
    viewer: dict[str, Any],
    pilot: dict[str, Any],
) -> dict[str, Any]:
    files = _scan_regular_files(root)
    files.pop(MANIFEST_NAME, None)
    source_paths = sorted([
        f"source-snapshot/{relative}" for relative in SOURCE_SNAPSHOT_FILES
    ] + [SOURCE_README_PATH], key=lambda value: value.encode("utf-8"))
    return {
        "manifest_version": MANIFEST_VERSION,
        "package_id": PACKAGE_ID,
        "artifact_role": "force_curve_bench_step3_review",
        "presentation_role": PRESENTATION_ROLE,
        "release_eligible": False,
        "warning": WARNING,
        "bench_build": BENCH_BUILD,
        "repo_commit": REPO_COMMIT,
        "evidence_identity": EVIDENCE_IDENTITY,
        "data_authority": {
            "artifact_role": DATA_ARTIFACT_ROLE,
            "release_eligible": True,
            "canonical_membership_active": True,
        },
        "counts": EXPECTED_COUNTS,
        "viewer": {"path": "index.html", "sha256": _sha256(root / "index.html")},
        "subjective_pilot": {
            "path": "documentation/subjective-pilot",
            "pilot_id": PILOT_ID,
            "workbook_included": False,
            "workbook_sha256": PILOT_WORKBOOK_SHA256,
            "source_identity_sha256": _sha256(
                root / "documentation/subjective-pilot/source_identity.json"
            ),
            "checksums_sha256": _sha256(
                root / "documentation/subjective-pilot/SHA256SUMS.json"
            ),
        },
        "canonical_evidence": {
            "path": CANONICAL_PREFIX,
            "package_id": CANONICAL_PACKAGE_ID,
            "verifier_path": f"{CANONICAL_PREFIX}/{CANONICAL_VERIFIER}",
            "verifier_sha256": CANONICAL_VERIFIER_SHA256,
            "epoch_manifest_sha256": _sha256(root / CANONICAL_PREFIX / "EPOCH_MANIFEST.json"),
            "verification_status": canonical["report"]["status"],
        },
        "source_snapshot": {
            "path": "source-snapshot",
            "baseline": "canonical-evidence/generator",
            "contract": "minimal_step3_overlay",
            "files": source_paths,
            "generator_source_hash": viewer["schema_data"]["provenance_hashes"][
                "generator_source_hash"
            ],
            "release_reference_hash": viewer["schema_data"]["provenance_hashes"][
                "release_reference_hash"
            ],
        },
        "sealed_document_exception": CANONICAL_WORKBOOK_EXCEPTION,
        "inventory_scope": INVENTORY_SCOPE,
        "files": _inventory(root, files),
    }


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (root / MANIFEST_NAME).write_bytes(payload)


def _verify_root_manifest(root: Path, actual: dict[str, Path]) -> dict[str, Any]:
    manifest_path = actual.get(MANIFEST_NAME)
    if manifest_path is None:
        raise Step3ReviewError(f"package lacks {MANIFEST_NAME}")
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, dict) or set(manifest) != TOP_LEVEL_FIELDS:
        raise Step3ReviewError(
            f"root manifest has wrong fields: {sorted(manifest) if isinstance(manifest, dict) else type(manifest)}"
        )
    expected_top = {
        "manifest_version": MANIFEST_VERSION,
        "package_id": PACKAGE_ID,
        "artifact_role": "force_curve_bench_step3_review",
        "presentation_role": PRESENTATION_ROLE,
        "release_eligible": False,
        "warning": WARNING,
        "bench_build": BENCH_BUILD,
        "repo_commit": REPO_COMMIT,
        "evidence_identity": EVIDENCE_IDENTITY,
        "counts": EXPECTED_COUNTS,
        "inventory_scope": INVENTORY_SCOPE,
        "sealed_document_exception": CANONICAL_WORKBOOK_EXCEPTION,
    }
    mismatches = {
        key: {"expected": value, "actual": manifest.get(key)}
        for key, value in expected_top.items()
        if manifest.get(key) != value
    }
    if mismatches:
        raise Step3ReviewError(f"root manifest identity mismatch: {mismatches}")
    _require_bool(manifest.get("release_eligible"), False, "root release eligibility")
    authority = manifest.get("data_authority")
    if authority != {
        "artifact_role": DATA_ARTIFACT_ROLE,
        "release_eligible": True,
        "canonical_membership_active": True,
    }:
        raise Step3ReviewError("root manifest canonical data-authority contract is wrong")
    rows = manifest.get("files")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise Step3ReviewError("root manifest files must be an array of objects")
    declared: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    for row in rows:
        if set(row) != FILE_FIELDS:
            raise Step3ReviewError("root inventory row has the wrong fields")
        relative = _normalize_relative(row.get("path"), "root inventory path")
        size, digest = row.get("bytes"), row.get("sha256")
        if (
            type(size) is not int
            or size < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise Step3ReviewError(f"invalid root inventory identity for {relative}")
        if relative == MANIFEST_NAME or relative in declared:
            raise Step3ReviewError(f"recursive or duplicate root inventory path: {relative}")
        declared[relative] = (size, digest)
        order.append(relative)
    if order != sorted(order, key=lambda value: value.encode("utf-8")):
        raise Step3ReviewError("root inventory is not byte-path sorted")
    actual_without_manifest = set(actual) - {MANIFEST_NAME}
    if set(declared) != actual_without_manifest:
        raise Step3ReviewError(
            "root inventory has missing or extra files: "
            f"unlisted={sorted(actual_without_manifest - set(declared))}, "
            f"missing={sorted(set(declared) - actual_without_manifest)}"
        )
    for relative, (size, digest) in declared.items():
        path = actual[relative]
        if path.stat().st_size != size or _sha256(path) != digest:
            raise Step3ReviewError(f"root inventory hash mismatch: {relative}")
    return manifest


def _verify_package_layout(actual: dict[str, Path], manifest: dict[str, Any]) -> None:
    required = {
        MANIFEST_NAME,
        "index.html",
        "documentation/subjective-pilot/index.html",
        f"{CANONICAL_PREFIX}/EPOCH_MANIFEST.json",
        f"{CANONICAL_PREFIX}/{CANONICAL_VERIFIER}",
        SOURCE_README_PATH,
    }
    missing = sorted(required - set(actual))
    if missing:
        raise Step3ReviewError(f"required Step-3 package files are missing: {missing}")
    allowed_roots = {
        MANIFEST_NAME,
        "index.html",
        "documentation",
        CANONICAL_PREFIX,
        "source-snapshot",
    }
    roots = {path.split("/", 1)[0] for path in actual}
    if roots != allowed_roots:
        raise Step3ReviewError(
            f"Step-3 package has wrong top-level entries: {sorted(roots)}"
        )
    source_expected = {
        f"source-snapshot/{relative}" for relative in SOURCE_SNAPSHOT_FILES
    } | {SOURCE_README_PATH}
    source_actual = {path for path in actual if path.startswith("source-snapshot/")}
    if source_actual != source_expected:
        raise Step3ReviewError(
            "source snapshot has missing or extra files: "
            f"missing={sorted(source_expected - source_actual)}, "
            f"extra={sorted(source_actual - source_expected)}"
        )
    if manifest.get("source_snapshot", {}).get("files") != sorted(
        source_expected, key=lambda value: value.encode("utf-8")
    ):
        raise Step3ReviewError("root manifest source-snapshot declaration is not exact")
    _check_document_policy(actual)


def verify_step3_review(package_root: str | os.PathLike[str]) -> dict[str, Any]:
    """Verify a completed Step-3 review package without consulting live sources."""
    root = _resolve_directory(package_root, "Step-3 review package")
    actual = _scan_regular_files(root)
    manifest = _verify_root_manifest(root, actual)
    _verify_package_layout(actual, manifest)

    canonical = _verify_canonical_package(root / CANONICAL_PREFIX)
    canonical_meta = manifest.get("canonical_evidence")
    expected_canonical_meta = {
        "path": CANONICAL_PREFIX,
        "package_id": CANONICAL_PACKAGE_ID,
        "verifier_path": f"{CANONICAL_PREFIX}/{CANONICAL_VERIFIER}",
        "verifier_sha256": CANONICAL_VERIFIER_SHA256,
        "epoch_manifest_sha256": _sha256(root / CANONICAL_PREFIX / "EPOCH_MANIFEST.json"),
        "verification_status": "PASS",
    }
    if canonical_meta != expected_canonical_meta:
        raise Step3ReviewError("root manifest canonical-evidence declaration is wrong")

    pilot = _validate_pilot(root / "documentation/subjective-pilot")
    expected_pilot_meta = {
        "path": "documentation/subjective-pilot",
        "pilot_id": PILOT_ID,
        "workbook_included": False,
        "workbook_sha256": PILOT_WORKBOOK_SHA256,
        "source_identity_sha256": _sha256(
            root / "documentation/subjective-pilot/source_identity.json"
        ),
        "checksums_sha256": _sha256(
            root / "documentation/subjective-pilot/SHA256SUMS.json"
        ),
    }
    if manifest.get("subjective_pilot") != expected_pilot_meta:
        raise Step3ReviewError("root manifest subjective-pilot declaration is wrong")

    sealed_schema = root / CANONICAL_PREFIX / "evidence/schema_meta.staged.json"
    viewer = _validate_viewer(
        root / "index.html",
        sealed_schema,
        canonical["aggregate"],
        canonical["retained"],
    )
    if manifest.get("viewer") != {
        "path": "index.html",
        "sha256": _sha256(root / "index.html"),
    }:
        raise Step3ReviewError("root manifest viewer declaration is wrong")
    template = _read_utf8(
        root
        / "source-snapshot/generator/domelab_pipeline/release_reference/index.release.html",
        "packaged viewer source template",
    )
    _reject_stale_viewer(template, "packaged viewer source template")
    reconstructed = _reconstructed_source_provenance(root)
    expected_source_files = sorted(
        [f"source-snapshot/{relative}" for relative in SOURCE_SNAPSHOT_FILES]
        + [SOURCE_README_PATH],
        key=lambda value: value.encode("utf-8"),
    )
    expected_source_meta = {
        "path": "source-snapshot",
        "baseline": "canonical-evidence/generator",
        "contract": "minimal_step3_overlay",
        "files": expected_source_files,
        **reconstructed,
    }
    if manifest.get("source_snapshot") != expected_source_meta:
        raise Step3ReviewError(
            "source overlay does not reconstruct the declared generator provenance"
        )
    return {
        "status": "PASS",
        "verification_scope": "package_integrity_and_identity_only",
        "ui_browser_acceptance": "NOT_EVALUATED",
        "package_root": str(root),
        "package_id": PACKAGE_ID,
        "bench_build": viewer["build"]["bench_build"],
        "repo_commit": REPO_COMMIT,
        "evidence_identity": EVIDENCE_IDENTITY,
        "file_count": len(actual),
        "canonical_verification": canonical["report"]["status"],
        "subjective_pilot": pilot["identity"]["pilot_id"],
        "perception_model": viewer["perception_model"]["version"],
    }


def build_step3_review(
    *,
    staging: str | os.PathLike[str],
    canonical_evidence: str | os.PathLike[str],
    source_root: str | os.PathLike[str],
    output: str | os.PathLike[str],
    subjective_pilot: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Build, self-verify, and atomically place a new review package."""
    output_path = Path(os.path.abspath(os.fspath(output)))
    if _lexists(output_path):
        raise Step3ReviewError(f"refusing to replace existing output: {output_path}")

    canonical = _verify_canonical_package(Path(canonical_evidence))
    staged = _validate_staging(Path(staging), canonical)
    source_root_path = _resolve_directory(source_root, "current source root")
    pilot_path = (
        Path(subjective_pilot)
        if subjective_pilot is not None
        else source_root_path / "documentation/subjective-pilot"
    )
    pilot = _validate_pilot(pilot_path)
    sources = _validate_source_files(source_root_path)
    input_roots = {
        "Step-3 staging": staged["root"],
        "sealed canonical evidence": canonical["root"],
        "current source": source_root_path,
        "subjective pilot": pilot["root"],
    }
    for label, input_root in input_roots.items():
        if _path_is_within(output_path, input_root):
            raise Step3ReviewError(
                f"output must not be inside {label}: {output_path}"
            )

    current_provenance = _source_provenance_hashes(source_root_path / "generator")
    staged_provenance = staged["schema_data"]["provenance_hashes"]
    for field, actual in current_provenance.items():
        if staged_provenance.get(field) != actual:
            raise Step3ReviewError(
                f"staged viewer source provenance is stale for {field}: "
                f"staged={staged_provenance.get(field)!r}, current={actual!r}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    parent = _resolve_directory(output_path.parent, "output parent")
    output_path = parent / output_path.name
    if _lexists(output_path):
        raise Step3ReviewError(f"refusing to replace existing output: {output_path}")

    plan: dict[str, Path | bytes] = {}
    folded: dict[str, str] = {}
    _add_plan(plan, folded, "index.html", staged["viewer"])
    for relative, path in pilot["files"].items():
        _add_plan(plan, folded, f"documentation/subjective-pilot/{relative}", path)
    for relative, path in _scan_regular_files(canonical["root"]).items():
        _add_plan(plan, folded, f"{CANONICAL_PREFIX}/{relative}", path)
    for relative, path in sources.items():
        _add_plan(plan, folded, f"source-snapshot/{relative}", path)
    _add_plan(plan, folded, SOURCE_README_PATH, SOURCE_README.encode("utf-8"))
    _check_document_policy(plan)

    candidate = Path(tempfile.mkdtemp(prefix=".step3-review-", dir=parent))
    try:
        _copy_plan(plan, candidate)
        copied_canonical = _verify_canonical_package(candidate / CANONICAL_PREFIX)
        manifest = _manifest_for(candidate, copied_canonical, staged, pilot)
        _write_manifest(candidate, manifest)
        report = verify_step3_review(candidate)
        if _lexists(output_path):
            raise Step3ReviewError(f"output appeared during build; refusing replacement: {output_path}")
        os.replace(candidate, output_path)
        return {**report, "package_root": str(output_path)}
    except Exception:
        if candidate.exists():
            shutil.rmtree(candidate)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build a new non-deployed review package")
    build.add_argument("--staging", required=True, type=Path)
    build.add_argument("--canonical-evidence", required=True, type=Path)
    build.add_argument("--source-root", required=True, type=Path)
    build.add_argument("--subjective-pilot", type=Path)
    build.add_argument("--output", required=True, type=Path)
    verify = subparsers.add_parser("verify", help="verify an existing review package")
    verify.add_argument("package_root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build_step3_review(
                staging=args.staging,
                canonical_evidence=args.canonical_evidence,
                source_root=args.source_root,
                subjective_pilot=args.subjective_pilot,
                output=args.output,
            )
        else:
            report = verify_step3_review(args.package_root)
    except Step3ReviewError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
