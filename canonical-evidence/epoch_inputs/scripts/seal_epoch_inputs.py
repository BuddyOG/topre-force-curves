#!/usr/bin/env python3
"""Fail-closed, deterministic final seal for the Step-2 epoch inputs.

``build_epoch_inputs.py`` intentionally produces the base (version 1)
validation report.  After the independent test-imp audit has been rerun, this
script verifies the audit, active owner-decision inputs, and regenerated
evidence-only staging tree.  It then emits the version 2 validation report and
an exhaustive checksum index for the epoch-input directory.

Only ``validation/validation_report.json`` and ``SHA256SUMS.csv`` are written.
The raw cache, Git repository, generator configuration, staging tree, and
independent audit artifacts are always read-only inputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable


AUDIT_ARTIFACTS = (
    "validation/audit_test_imp_1_1_4.py",
    "validation/test_imp_1_1_4_epoch_audit.json",
    "validation/test_imp_1_1_4_epoch_audit.md",
    "validation/test_imp_1_1_4_per_run.csv",
    "validation/test_imp_1_1_4_per_cohort.csv",
)

ACTIVE_ARTIFACTS = (
    "source/generator/domelab_pipeline/config/exclusions.json",
    "source/generator/domelab_pipeline/config/review_register.json",
    "source/generator/domelab_pipeline/config/retained_run_decisions.json",
    "epoch_outputs/staging_canonical_{short_commit}/curve_pack_provenance.json",
    "epoch_outputs/staging_canonical_{short_commit}/generated_manifest.json",
)

SEAL_CHECK_NAMES = (
    "final_importer_audit_schema_v2",
    "final_importer_audit_matches_frozen_epoch",
    "final_importer_audit_result_pass",
    "final_importer_audit_artifacts_hash_bound",
    "active_exclusions_registry_matches_frozen_epoch",
    "active_review_register_matches_frozen_epoch",
    "retained_decisions_owner_inputs_match_active_registries",
    "final_importer_audit_binds_regenerated_canonical_staging",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class SealError(RuntimeError):
    """The epoch cannot be sealed because a required binding failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SealError(message)


def _read_bytes(path: Path, label: str) -> bytes:
    _require(path.exists(), f"missing {label}: {path}")
    _require(path.is_file(), f"{label} is not a regular file: {path}")
    _require(not path.is_symlink(), f"{label} must not be a symlink: {path}")
    return path.read_bytes()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    raw = _read_bytes(path, label)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SealError(f"invalid UTF-8 JSON in {label}: {path}: {exc}") from exc
    _require(isinstance(value, dict), f"{label} must contain a JSON object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path, label: str) -> str:
    return _sha256_bytes(_read_bytes(path, label))


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(payload.encode("utf-8"))


def _artifact(path: Path, relative_path: str) -> dict[str, Any]:
    raw = _read_bytes(path, relative_path)
    return {
        "path": relative_path,
        "sha256": _sha256_bytes(raw),
        "size_bytes": len(raw),
    }


def _require_exact_artifact_list(
    declared: Any,
    expected_paths: Iterable[str],
    root: Path,
    label: str,
) -> None:
    expected = tuple(expected_paths)
    _require(isinstance(declared, list), f"{label}.artifacts must be a list")
    _require(
        [entry.get("path") for entry in declared if isinstance(entry, dict)]
        == list(expected),
        f"{label}.artifacts paths/order do not match the canonical list",
    )
    for entry, relative in zip(declared, expected):
        _require(isinstance(entry, dict), f"{label} artifact is not an object")
        actual = _artifact(root / relative, relative)
        _require(
            entry == actual,
            f"{label} hash/size mismatch for {relative}",
        )


def _require_all_checks(section: dict[str, Any], label: str) -> None:
    checks = section.get("checks")
    _require(isinstance(checks, dict) and checks, f"{label}.checks is missing or empty")
    failed = sorted(key for key, value in checks.items() if value is not True)
    _require(not failed, f"{label}.checks contains failures: {failed}")


def _validation_base(report: dict[str, Any]) -> dict[str, Any]:
    """Return the builder-owned v1 portion of either a v1 or v2 report."""
    _require(
        report.get("validation_report_version") in (1, 2),
        "validation_report_version must be 1 or 2 before sealing",
    )
    checks = report.get("checks")
    _require(isinstance(checks, dict) and checks, "base validation checks are missing")
    base_checks = {
        key: value for key, value in checks.items() if key not in SEAL_CHECK_NAMES
    }
    failed = sorted(key for key, value in base_checks.items() if value is not True)
    _require(not failed, f"base validation checks contain failures: {failed}")
    _require(report.get("result") == "PASS", "base validation result is not PASS")
    return {
        "validation_report_version": 1,
        "epoch_id": report.get("epoch_id"),
        "checks": base_checks,
        "counts": report.get("counts"),
        "case_only_mapping": report.get("case_only_mapping"),
        "shared_evidence_rule": report.get("shared_evidence_rule"),
        "warnings": report.get("warnings"),
        "open_questions": report.get("open_questions"),
        "result": report.get("result"),
    }


def _verify_prior_v2_seals(
    report: dict[str, Any],
    epoch_inputs: Path,
    work_root: Path,
    commit: str,
) -> None:
    """Make idempotent resealing fail if an already-sealed input was altered."""
    if report.get("validation_report_version") != 2:
        return
    importer = report.get("importer_audit_seal")
    active = report.get("active_registry_and_staging_seal")
    _require(isinstance(importer, dict), "existing v2 importer_audit_seal is missing")
    _require(isinstance(active, dict), "existing v2 active registry seal is missing")
    _require_exact_artifact_list(
        importer.get("artifacts"), AUDIT_ARTIFACTS, epoch_inputs, "existing importer seal"
    )
    active_paths = tuple(
        value.format(short_commit=commit[:8]) for value in ACTIVE_ARTIFACTS
    )
    _require_exact_artifact_list(
        active.get("artifacts"), active_paths, work_root, "existing active seal"
    )


def _verify_audit(
    epoch_inputs: Path,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validation = epoch_inputs / "validation"
    audit_path = validation / "test_imp_1_1_4_epoch_audit.json"
    audit = _read_json(audit_path, "test-imp audit JSON")
    epoch_id = manifest["epoch_id"]
    commit = manifest["repo_commit"]

    _require(audit.get("audit_schema_version") == 2, "test-imp audit schema is not v2")
    _require(audit.get("epoch_id") == epoch_id, "test-imp audit epoch_id mismatch")
    _require(audit.get("repo_commit") == commit, "test-imp audit repo_commit mismatch")
    _require(audit.get("result") == "PASS", "test-imp audit result is not PASS")

    for key in (
        "importer_release_identity",
        "predecessor_epoch_retest_impact",
        "raw_inputs",
        "repo_and_cache_stability",
    ):
        section = audit.get(key)
        _require(isinstance(section, dict), f"test-imp audit section missing: {key}")
        _require(section.get("all_checks_pass") is True, f"{key} is not passing")
        _require_all_checks(section, key)

    fleet = audit.get("fleet_audit")
    _require(isinstance(fleet, dict), "test-imp audit fleet_audit is missing")
    _require(
        fleet.get("all_structural_checks_pass") is True,
        "test-imp fleet structural checks are not passing",
    )
    _require_all_checks(fleet, "fleet_audit")

    generator = audit.get("generator_comparison")
    _require(isinstance(generator, dict), "generator_comparison is missing")
    _require(generator.get("status") == "pass", "generator comparison is not pass")
    for key in ("dataset_manifest", "per_run_full_precision", "retained_run_decisions"):
        section = generator.get(key)
        _require(
            isinstance(section, dict) and section.get("status") == "pass",
            f"generator comparison {key} is not pass",
        )
    bindings = generator.get("artifact_bindings")
    _require(
        isinstance(bindings, dict) and bindings.get("status") == "pass",
        "generator artifact bindings are not pass",
    )
    _require_all_checks(bindings, "generator artifact bindings")
    tolerance = generator.get("numeric_tolerance")
    maximum_delta = generator.get("max_scalar_delta")
    _require(
        isinstance(tolerance, (int, float))
        and not isinstance(tolerance, bool)
        and math.isfinite(float(tolerance))
        and float(tolerance) >= 0,
        "generator numeric tolerance is invalid",
    )
    _require(
        isinstance(maximum_delta, (int, float))
        and not isinstance(maximum_delta, bool)
        and math.isfinite(float(maximum_delta))
        and 0 <= float(maximum_delta) <= float(tolerance),
        "generator maximum scalar delta exceeds its tolerance",
    )

    manifest_path = epoch_inputs / "manifest" / "dataset_manifest.step2.json"
    audit_manifest = audit.get("inputs", {}).get("dataset_manifest", {})
    _require(
        audit_manifest.get("sha256") == _sha256_file(manifest_path, "Step-2 manifest"),
        "test-imp audit does not bind the current Step-2 manifest",
    )
    script_path = validation / "audit_test_imp_1_1_4.py"
    script_identity = audit.get("script", {})
    _require(
        script_identity.get("sha256") == _sha256_file(script_path, "audit script"),
        "test-imp audit script hash does not match the script that produced it",
    )

    counts = manifest["counts"]
    fleet_counts = fleet.get("counts", {})
    _require(
        fleet_counts.get("semantic_cohorts") == counts["semantic_records"],
        "test-imp semantic cohort count mismatch",
    )
    _require(
        fleet_counts.get("independent_measurement_cohorts")
        == counts["independent_measurement_cohorts"],
        "test-imp independent-cohort count mismatch",
    )
    _require(
        fleet_counts.get("semantic_paths") == counts["tracked_raw_paths"],
        "test-imp raw-path count mismatch",
    )
    _require(
        fleet_counts.get("unique_acquisitions") == counts["unique_acquisitions"],
        "test-imp acquisition count mismatch",
    )
    _require(
        fleet_counts.get("retained_semantic_paths") == counts["tracked_raw_paths"],
        "test-imp retained membership is not complete",
    )

    with (validation / "test_imp_1_1_4_per_run.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        run_rows = list(csv.DictReader(handle))
    _require(
        len(run_rows) == counts["tracked_raw_paths"],
        "test-imp per-run CSV row count mismatch",
    )
    _require(
        len({row.get("raw_path") for row in run_rows}) == len(run_rows),
        "test-imp per-run CSV paths are not unique",
    )
    _require(
        all(row.get("retained") == "True" for row in run_rows),
        "test-imp per-run CSV contains an unretained row",
    )
    with (validation / "test_imp_1_1_4_per_cohort.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        cohort_rows = list(csv.DictReader(handle))
    _require(
        len(cohort_rows) == counts["semantic_records"],
        "test-imp per-cohort CSV row count mismatch",
    )
    _require(
        all(row.get("status") == "accepted" for row in cohort_rows),
        "test-imp per-cohort CSV contains a non-accepted cohort",
    )

    markdown = _read_bytes(
        validation / "test_imp_1_1_4_epoch_audit.md", "test-imp audit Markdown"
    ).decode("utf-8")
    _require("Overall result: **PASS**" in markdown, "audit Markdown is not PASS")
    _require(commit in markdown, "audit Markdown does not name the frozen commit")

    artifacts = [
        _artifact(epoch_inputs / relative, relative) for relative in AUDIT_ARTIFACTS
    ]
    return audit, artifacts


def _verify_staging_tree(staging: Path, generated: dict[str, Any]) -> None:
    _require(staging.is_dir(), f"missing staging directory: {staging}")
    actual: dict[str, Path] = {}
    for path in staging.rglob("*"):
        _require(not path.is_symlink(), f"staging tree contains a symlink: {path}")
        if path.is_file():
            actual[path.relative_to(staging).as_posix()] = path
    expected_paths = set(generated)
    actual_paths = set(actual) - {"generated_manifest.json"}
    _require(
        actual_paths == expected_paths,
        "generated_manifest.json does not have exact staging-tree coverage",
    )
    for relative in sorted(expected_paths):
        declared = generated[relative]
        _require(
            isinstance(declared, str) and SHA256_RE.fullmatch(declared) is not None,
            f"generated manifest has an invalid digest for {relative}",
        )
        _require(
            _sha256_file(actual[relative], f"staged artifact {relative}") == declared,
            f"generated manifest hash mismatch for {relative}",
        )


def _verify_active_and_staging(
    work_root: Path,
    manifest: dict[str, Any],
    audit: dict[str, Any],
) -> tuple[str, str, list[dict[str, Any]]]:
    commit = manifest["repo_commit"]
    config = work_root / "source" / "generator" / "domelab_pipeline" / "config"
    exclusions = _read_json(config / "exclusions.json", "active exclusions registry")
    review = _read_json(config / "review_register.json", "active review register")
    adjudications = _read_json(config / "adjudications.json", "active adjudications")
    decisions_path = config / "retained_run_decisions.json"
    decisions = _read_json(decisions_path, "canonical retained-run decisions")
    generator_manifest = _read_json(config / "dataset_manifest.json", "generator manifest")

    _require(
        generator_manifest.get("repo_commit") == commit,
        "generator dataset_manifest.repo_commit mismatch",
    )
    _require(
        exclusions.get("repo_commit") == commit,
        "active exclusions registry repo_commit mismatch",
    )
    _require(
        review.get("repo_commit") == commit,
        "active review register repo_commit mismatch",
    )
    _require(
        decisions.get("repo_commit") == commit,
        "canonical decisions repo_commit mismatch",
    )
    _require(
        decisions.get("artifact_role") == "canonical_retention_authority"
        and decisions.get("release_eligible") is True,
        "retained-run decisions are not the canonical release authority",
    )
    owner_hash = _canonical_hash(
        {
            "exclusions": exclusions,
            "adjudications": adjudications,
            "review_register": review,
        }
    )
    _require(
        decisions.get("owner_decision_inputs_hash") == owner_hash,
        "retained decisions owner_decision_inputs_hash mismatch",
    )

    staging = work_root / "epoch_outputs" / f"staging_canonical_{commit[:8]}"
    curve_path = staging / "curve_pack_provenance.json"
    generated_path = staging / "generated_manifest.json"
    output_decisions_path = staging / "intake_retention_decisions.json"
    per_run_path = staging / "per_run_full_precision.json"
    curve = _read_json(curve_path, "curve-pack provenance")
    generated = _read_json(generated_path, "generated manifest")
    _verify_staging_tree(staging, generated)

    _require(curve.get("repo_commit") == commit, "curve provenance commit mismatch")
    evidence_hash = curve.get("evidence_epoch_hash")
    _require(
        isinstance(evidence_hash, str) and SHA256_RE.fullmatch(evidence_hash) is not None,
        "curve provenance evidence_epoch_hash is invalid",
    )
    curve_sha = _sha256_file(curve_path, "curve-pack provenance")
    generated_sha = _sha256_file(generated_path, "generated manifest")
    decision_sha = _sha256_file(decisions_path, "canonical retained-run decisions")
    output_decision_sha = _sha256_file(output_decisions_path, "staged decisions")
    per_run_sha = _sha256_file(per_run_path, "staged full-precision results")
    _require(output_decision_sha == decision_sha, "staged decisions differ from authority")
    _require(
        generated.get("curve_pack_provenance.json") == curve_sha,
        "generated manifest does not bind curve provenance",
    )
    _require(
        generated.get("intake_retention_decisions.json") == decision_sha,
        "generated manifest does not bind canonical decisions",
    )
    _require(
        generated.get("per_run_full_precision.json") == per_run_sha,
        "generated manifest does not bind full-precision results",
    )

    generator = audit["generator_comparison"]
    bindings = generator["artifact_bindings"]
    audit_curve = bindings.get("curve_pack_provenance", {})
    audit_generated = bindings.get("generated_manifest", {})
    _require(
        audit_curve.get("sha256") == curve_sha
        and audit_curve.get("repo_commit") == commit
        and audit_curve.get("evidence_epoch_hash") == evidence_hash,
        "test-imp audit curve-provenance binding is stale",
    )
    _require(
        audit_generated.get("sha256") == generated_sha,
        "test-imp audit generated-manifest binding is stale",
    )
    _require(
        bindings.get("selected_canonical_decisions_sha256") == decision_sha
        and bindings.get("output_decisions_sha256") == decision_sha,
        "test-imp audit decision binding is stale",
    )
    _require(
        bindings.get("per_run_sha256") == per_run_sha,
        "test-imp audit full-precision binding is stale",
    )
    _require(
        generator["retained_run_decisions"].get("selected_sha256") == decision_sha,
        "test-imp retained-decision comparison is stale",
    )
    _require(
        generator["per_run_full_precision"].get("selected_sha256") == per_run_sha,
        "test-imp per-run comparison is stale",
    )
    _require(
        generator["dataset_manifest"].get("repo_commit") == commit,
        "test-imp generator-manifest comparison commit is stale",
    )

    active_paths = tuple(
        value.format(short_commit=commit[:8]) for value in ACTIVE_ARTIFACTS
    )
    artifacts = [_artifact(work_root / relative, relative) for relative in active_paths]
    return owner_hash, evidence_hash, artifacts


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _eligible_epoch_files(epoch_inputs: Path) -> list[Path]:
    paths: list[Path] = []
    for path in epoch_inputs.rglob("*"):
        _require(not path.is_symlink(), f"epoch_inputs contains a symlink: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(epoch_inputs)
        if path.name == "SHA256SUMS.csv":
            continue
        if path.suffix == ".pyc" or "__pycache__" in relative.parts or "node_modules" in relative.parts:
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: path.relative_to(epoch_inputs).as_posix().encode("utf-8"))


def _checksum_bytes(
    epoch_inputs: Path,
    validation_report_bytes: bytes,
) -> tuple[bytes, list[dict[str, Any]]]:
    report_path = epoch_inputs / "validation" / "validation_report.json"
    rows: list[dict[str, Any]] = []
    for path in _eligible_epoch_files(epoch_inputs):
        relative = path.relative_to(epoch_inputs).as_posix()
        raw = validation_report_bytes if path == report_path else _read_bytes(path, relative)
        rows.append(
            {
                "path": relative,
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=("path", "sha256", "size_bytes"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8"), rows


def _atomic_write(path: Path, value: bytes) -> None:
    _require(not path.is_symlink(), f"refusing to replace symlink: {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def seal_epoch_inputs(work_root: Path, *, check: bool = False) -> dict[str, Any]:
    work_root = Path(work_root).resolve()
    epoch_inputs = work_root / "epoch_inputs"
    _require(epoch_inputs.is_dir(), f"epoch_inputs directory is missing: {epoch_inputs}")
    manifest = _read_json(
        epoch_inputs / "manifest" / "dataset_manifest.step2.json",
        "Step-2 manifest",
    )
    commit = manifest.get("repo_commit")
    epoch_id = manifest.get("epoch_id")
    counts = manifest.get("counts")
    _require(isinstance(commit, str) and COMMIT_RE.fullmatch(commit) is not None, "invalid frozen commit")
    _require(isinstance(epoch_id, str) and epoch_id, "invalid epoch_id")
    _require(isinstance(counts, dict), "Step-2 manifest counts are missing")

    report_path = epoch_inputs / "validation" / "validation_report.json"
    existing_report = _read_json(report_path, "validation report")
    base = _validation_base(existing_report)
    _require(base["epoch_id"] == epoch_id, "base validation epoch_id mismatch")
    _require(base["counts"] == counts, "base validation counts mismatch")
    _verify_prior_v2_seals(existing_report, epoch_inputs, work_root, commit)

    audit, importer_artifacts = _verify_audit(epoch_inputs, manifest)
    owner_hash, evidence_hash, active_artifacts = _verify_active_and_staging(
        work_root, manifest, audit
    )
    seal_checks = {
        "final_importer_audit_schema_v2": True,
        "final_importer_audit_matches_frozen_epoch": True,
        "final_importer_audit_result_pass": True,
        "final_importer_audit_artifacts_hash_bound": True,
        "active_exclusions_registry_matches_frozen_epoch": True,
        "active_review_register_matches_frozen_epoch": True,
        "retained_decisions_owner_inputs_match_active_registries": True,
        "final_importer_audit_binds_regenerated_canonical_staging": True,
    }
    checks = {**base["checks"], **seal_checks}
    report = {
        "validation_report_version": 2,
        "epoch_id": epoch_id,
        "checks": checks,
        "counts": counts,
        "importer_audit_seal": {
            "audit_schema_version": audit["audit_schema_version"],
            "epoch_id": epoch_id,
            "repo_commit": commit,
            "result": audit["result"],
            "maximum_scalar_delta": audit["generator_comparison"]["max_scalar_delta"],
            "artifacts": importer_artifacts,
        },
        "active_registry_and_staging_seal": {
            "repo_commit": commit,
            "owner_decision_inputs_hash": owner_hash,
            "evidence_epoch_hash": evidence_hash,
            "artifacts": active_artifacts,
        },
        "case_only_mapping": base["case_only_mapping"],
        "shared_evidence_rule": base["shared_evidence_rule"],
        "warnings": base["warnings"],
        "open_questions": base["open_questions"],
        "result": "PASS",
    }
    report_bytes = _json_bytes(report)
    checksum_bytes, rows = _checksum_bytes(epoch_inputs, report_bytes)
    checksum_path = epoch_inputs / "SHA256SUMS.csv"

    if check:
        _require(
            _read_bytes(report_path, "validation report") == report_bytes,
            "validation_report.json is not the deterministic sealed output",
        )
        _require(
            _read_bytes(checksum_path, "checksum index") == checksum_bytes,
            "SHA256SUMS.csv is not the deterministic exhaustive index",
        )
    else:
        _atomic_write(report_path, report_bytes)
        _atomic_write(checksum_path, checksum_bytes)

    # Verify the emitted (or checked) index against every declared file.
    for row in rows:
        path = epoch_inputs / row["path"]
        raw = _read_bytes(path, row["path"])
        _require(len(raw) == row["size_bytes"], f"post-seal size mismatch: {row['path']}")
        _require(
            _sha256_bytes(raw) == row["sha256"],
            f"post-seal hash mismatch: {row['path']}",
        )
    return {
        "result": "PASS",
        "mode": "check" if check else "seal",
        "epoch_id": epoch_id,
        "repo_commit": commit,
        "evidence_epoch_hash": evidence_hash,
        "owner_decision_inputs_hash": owner_hash,
        "indexed_files": len(rows),
        "validation_report_sha256": _sha256_bytes(report_bytes),
        "sha256sums_sha256": _sha256_bytes(checksum_bytes),
    }


def main(argv: list[str] | None = None) -> int:
    default_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-root",
        type=Path,
        default=default_root,
        help="canonical epoch work root (defaults to the script's grandparent)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify byte-identical sealed outputs without writing",
    )
    args = parser.parse_args(argv)
    try:
        result = seal_epoch_inputs(args.work_root, check=args.check)
    except SealError as exc:
        print(f"SEAL FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
