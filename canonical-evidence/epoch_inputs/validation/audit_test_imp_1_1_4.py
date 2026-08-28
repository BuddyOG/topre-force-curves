#!/usr/bin/env python3
"""Independent, deterministic test-imp 1.1.4 audit for the canonical epoch.

This script treats a raw *path* as a semantic evidence record and an exact
SHA-256 as a physical acquisition identity.  Consequently, byte-identical
Git aliases may be exposed under more than one interpretation, but are counted
only once when reporting independent observations.

The audit is read-only with respect to the raw cache, source repository, and
generator configuration.  It writes only the JSON/CSV/Markdown reports beside
this script.  It imports the hash-verified final test-imp 1.1.4 source directly;
it does not reimplement the intake rules.
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
import subprocess
import sys
import tomllib
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


EXPECTED_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
PREDECESSOR_COMMIT = "8816ffbf80ce7fd349a1a73893ce63cd5b7ad3d2"
RETEST_IMPACT_SET = "Topre_R2_45g"
EXPECTED_IMPORTER_VERSION = "1.1.4"
EXPECTED_METRICS_VERSION = "metrics-v4.2"
EXPECTED_POLICY_VERSION = "intake-qc-v1.4"
EXPECTED_EXE_SHA256 = (
    "351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e"
)
EXPECTED_ZIP_SHA256 = (
    "b1ccdaba5c4ec76b7a8516c4e8c8109c26f2cb58b0f60f49a5c5fcf9a031b284"
)
EXPECTED_VERSION_OUTPUT = (
    "test-imp.exe 1.1.4 (metrics-v4.2; intake-qc-v1.4)"
)
NUMERIC_TOLERANCE = 1e-12

METRIC_FIELDS = (
    "collapse_force_gf",
    "collapse_travel_mm",
    "valley_force_gf",
    "valley_travel_mm",
    "snap_pct",
    "travel_mm",
    "full_stroke_press_work_gf_mm",
    "precollapse_work_gf_mm",
    "drop_gf",
    "drop_travel_mm",
    "drop_rate_gf_per_mm",
    "norm_drop_rate_per_mm",
    "steepest_drop_0p10mm_gf_per_mm",
    "ramp_10_90_gf_per_mm",
)

AUDIT_FIELDS = (
    "force_wall_travel_mm",
    "force_wall_found",
    "steepest_drop_start_mm",
    "steepest_drop_end_mm",
    "ramp_baseline_force_gf",
    "ramp_x10_mm",
    "ramp_x90_mm",
    "ramp_x10_cross_count",
    "ramp_x90_cross_count",
    "ramp_x10_eligible_cross_count",
    "ramp_x90_eligible_cross_count",
    "ramp_band_sample_count",
    "ramp_band_complete",
)

INTAKE_OBSERVATION_FIELDS = (
    "effective_speed_mm_s",
    "collapse_local_speed_mm_s",
    "interval_median_ms",
    "timing_gap_count",
)

HASH_LINE = re.compile(r"^([0-9A-Fa-f]{64})  (.+)$")


class AuditError(RuntimeError):
    """A deterministic audit precondition or comparison failed."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_blob_oid(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def posix_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def full_cache_tree_identity(root: Path) -> dict[str, Any]:
    """Hash every materialized file into a deterministic path/content tree."""
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        data = path.read_bytes()
        rows.append(
            {
                "path": posix_relative(path, root),
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "git_blob_oid": git_blob_oid(data),
            }
        )
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "file_count": len(rows),
        "tree_sha256": sha256_bytes(canonical),
        "rows": rows,
    }


def run_git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )


def live_repo_snapshot(repo: Path) -> dict[str, Any]:
    head = run_git(repo, "rev-parse", "HEAD")
    branch = run_git(repo, "branch", "--show-current")
    status = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    upstream = run_git(repo, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    upstream_counts = None
    if upstream.returncode == 0:
        pieces = upstream.stdout.strip().split()
        if len(pieces) == 2:
            upstream_counts = {"ahead": int(pieces[0]), "behind": int(pieces[1])}
    return {
        "path": str(repo),
        "head": head.stdout.strip(),
        "branch": branch.stdout.strip(),
        "status_porcelain_v1": status.stdout.splitlines(),
        "upstream_counts": upstream_counts,
        "commands_ok": all(
            completed.returncode == 0 for completed in (head, branch, status, upstream)
        ),
        "stderr": {
            "head": head.stderr.strip(),
            "branch": branch.stderr.strip(),
            "status": status.stderr.strip(),
            "upstream": upstream.stderr.strip(),
        },
    }


def parse_hash_manifest(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = HASH_LINE.fullmatch(line)
        if not match:
            raise AuditError(f"malformed hash line {path}:{number}: {line!r}")
        rows.append({"sha256": match.group(1).lower(), "path": match.group(2)})
    return rows


def verify_hash_manifest(path: Path, root: Path) -> dict[str, Any]:
    entries = parse_hash_manifest(path)
    mismatches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        rel = entry["path"]
        if rel in seen:
            mismatches.append({"path": rel, "reason": "duplicate_manifest_path"})
            continue
        seen.add(rel)
        target = root / Path(PurePosixPath(rel))
        if not target.is_file():
            mismatches.append({"path": rel, "reason": "missing"})
            continue
        observed = sha256_file(target)
        if observed != entry["sha256"]:
            mismatches.append(
                {
                    "path": rel,
                    "reason": "sha256_mismatch",
                    "expected": entry["sha256"],
                    "observed": observed,
                }
            )
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "entry_count": len(entries),
        "entries_unique": len(seen) == len(entries),
        "mismatches": mismatches,
        "all_entries_match": not mismatches,
        "entries": entries,
    }


def release_identity(importer_root: Path) -> dict[str, Any]:
    source_manifest = importer_root / "SOURCE-SHA256SUMS-1.1.4.txt"
    rolling_source_manifest = importer_root / "SOURCE-SHA256SUMS.txt"
    release_root = importer_root / "release-1.1.4"
    release_manifest = release_root / "SHA256SUMS.txt"
    exe = release_root / "test-imp.exe"
    archive = importer_root / "test-imp-1.1.4-windows-x64.zip"
    acceptance = importer_root / "acceptance" / "importer_acceptance-1.1.4.json"

    source_check = verify_hash_manifest(source_manifest, importer_root)
    release_check = verify_hash_manifest(release_manifest, release_root)
    rolling_identical = (
        source_manifest.read_bytes() == rolling_source_manifest.read_bytes()
    )

    with (importer_root / "pyproject.toml").open("rb") as handle:
        pyproject_version = tomllib.load(handle)["project"]["version"]

    completed = subprocess.run(
        [str(exe), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    version_output = completed.stdout.strip()

    zip_mismatches: list[dict[str, Any]] = []
    zip_entries: list[dict[str, Any]] = []
    release_entries = {entry["path"]: entry["sha256"] for entry in release_check["entries"]}
    # The checksum file cannot list its own digest, but it is itself included
    # in the ZIP and must match the released checksum file byte-for-byte.
    zip_expected_entries = {
        **release_entries,
        "SHA256SUMS.txt": sha256_file(release_manifest),
    }
    with zipfile.ZipFile(archive) as zipped:
        names = [info.filename for info in zipped.infolist() if not info.is_dir()]
        if set(names) != set(zip_expected_entries):
            zip_mismatches.append(
                {
                    "reason": "entry_set_mismatch",
                    "missing": sorted(set(zip_expected_entries) - set(names)),
                    "extra": sorted(set(names) - set(zip_expected_entries)),
                }
            )
        for name in sorted(names):
            data = zipped.read(name)
            digest = sha256_bytes(data)
            zip_entries.append({"path": name, "bytes": len(data), "sha256": digest})
            if zip_expected_entries.get(name) != digest:
                zip_mismatches.append(
                    {
                        "reason": "entry_sha256_mismatch",
                        "path": name,
                        "expected": zip_expected_entries.get(name),
                        "observed": digest,
                    }
                )

    exe_sha = sha256_file(exe)
    zip_sha = sha256_file(archive)
    acceptance_identity = None
    if acceptance.is_file():
        acceptance_doc = read_json(acceptance)
        acceptance_identity = {
            "path": str(acceptance),
            "sha256": sha256_file(acceptance),
            "importer_identity": acceptance_doc.get("importer_identity"),
            "release": acceptance_doc.get("release"),
            "native_tests": acceptance_doc.get("native_tests"),
            "generator_parity": acceptance_doc.get("generator_parity"),
        }

    checks = {
        "source_manifest_all_entries_match": source_check["all_entries_match"],
        "rolling_source_manifest_byte_identical": rolling_identical,
        "release_manifest_all_entries_match": release_check["all_entries_match"],
        "exe_sha256_pinned": exe_sha == EXPECTED_EXE_SHA256,
        "zip_sha256_pinned": zip_sha == EXPECTED_ZIP_SHA256,
        "zip_payload_matches_release_manifest": not zip_mismatches,
        "exe_version_output_exact": (
            completed.returncode == 0 and version_output == EXPECTED_VERSION_OUTPUT
        ),
        "pyproject_version_exact": pyproject_version == EXPECTED_IMPORTER_VERSION,
    }
    return {
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "source_manifest": source_check,
        "rolling_source_manifest": {
            "path": str(rolling_source_manifest),
            "sha256": sha256_file(rolling_source_manifest),
            "byte_identical_to_versioned": rolling_identical,
        },
        "release_manifest": release_check,
        "executable": {
            "path": str(exe),
            "bytes": exe.stat().st_size,
            "sha256": exe_sha,
            "expected_sha256": EXPECTED_EXE_SHA256,
            "version_return_code": completed.returncode,
            "version_stdout": version_output,
            "version_stderr": completed.stderr.strip(),
        },
        "zip": {
            "path": str(archive),
            "bytes": archive.stat().st_size,
            "sha256": zip_sha,
            "expected_sha256": EXPECTED_ZIP_SHA256,
            "entries": zip_entries,
            "mismatches": zip_mismatches,
        },
        "pyproject_version": pyproject_version,
        "acceptance_evidence": acceptance_identity,
    }


def import_final_source(importer_root: Path) -> tuple[Any, Any, Any]:
    importer_root = importer_root.resolve()
    sys.path.insert(0, str(importer_root))
    import test_imp  # type: ignore
    from test_imp import config as importer_config  # type: ignore
    from test_imp.analysis import assess_cohort  # type: ignore

    module_path = Path(test_imp.__file__).resolve()
    if importer_root not in module_path.parents:
        raise AuditError(f"wrong test_imp source imported: {module_path}")
    identity = {
        "module_path": str(module_path),
        "application_version": test_imp.__version__,
        "metrics_version": test_imp.__metrics_version__,
        "policy_version": test_imp.__policy_version__,
    }
    expected = {
        "application_version": EXPECTED_IMPORTER_VERSION,
        "metrics_version": EXPECTED_METRICS_VERSION,
        "policy_version": EXPECTED_POLICY_VERSION,
    }
    if identity | {} != {"module_path": str(module_path), **expected}:
        raise AuditError(f"unexpected importer source identity: {identity}")
    return assess_cohort, importer_config, identity


def flatten_manifest_tests(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for test in manifest["tests"]:
        for run in test["expected_runs"]:
            rows.append(
                {
                    "test_id": test["test_id"],
                    "set": test["set"],
                    "measurement_cohort_id": test.get("measurement_cohort_id"),
                    "acquisition_group_id": test.get("acquisition_group_id"),
                    "independence_key": test.get("independence_key"),
                    **run,
                }
            )
    return rows


def verify_raw_inputs(
    epoch_inputs: Path,
    work_root: Path,
    manifest: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    commit = manifest.get("repo_commit")
    raw_root = work_root / "raw_cache" / f"repo-{commit}"
    raw_inventory = read_json(epoch_inputs / "manifest" / "raw_file_inventory.json")
    raw_inventory_csv_path = epoch_inputs / "manifest" / "raw_file_inventory.csv"
    repository_inventory_path = (
        epoch_inputs / "manifest" / "repository_file_inventory.csv"
    )
    repo_provenance_path = epoch_inputs / "manifest" / "repo_provenance.json"
    repo_provenance = read_json(repo_provenance_path)
    acquisition_registry = read_json(
        epoch_inputs / "manifest" / "acquisition_registry.json"
    )
    manifest_rows = flatten_manifest_tests(manifest)
    inventory_rows = [row for row in raw_inventory["files"] if row.get("is_raw_csv")]

    by_manifest_path: dict[str, dict[str, Any]] = {}
    duplicate_manifest_paths: list[str] = []
    for row in manifest_rows:
        if row["path"] in by_manifest_path:
            duplicate_manifest_paths.append(row["path"])
        by_manifest_path[row["path"]] = row
    by_inventory_path = {row["path"]: row for row in inventory_rows}
    cache_paths = sorted(
        posix_relative(path, raw_root)
        for path in raw_root.rglob("*.csv")
        if path.is_file()
    )

    with repository_inventory_path.open("r", encoding="utf-8", newline="") as handle:
        repository_inventory_rows = list(csv.DictReader(handle))
    repository_by_path = {row["path"]: row for row in repository_inventory_rows}
    full_cache = full_cache_tree_identity(raw_root)
    full_cache_by_path = {row["path"]: row for row in full_cache["rows"]}
    full_cache_mismatches: list[dict[str, Any]] = []
    for rel in sorted(set(repository_by_path) | set(full_cache_by_path)):
        inventory = repository_by_path.get(rel)
        observed = full_cache_by_path.get(rel)
        if inventory is None or observed is None:
            full_cache_mismatches.append(
                {
                    "path": rel,
                    "reason": "full_cache_path_membership_mismatch",
                    "in_inventory": inventory is not None,
                    "in_cache": observed is not None,
                }
            )
            continue
        expected_bytes = int(inventory["bytes"])
        for field, expected in (
            ("bytes", expected_bytes),
            ("sha256", inventory["sha256"]),
            ("git_blob_oid", inventory["git_blob_oid"]),
        ):
            if observed[field] != expected:
                full_cache_mismatches.append(
                    {
                        "path": rel,
                        "field": field,
                        "expected": expected,
                        "observed": observed[field],
                    }
                )

    path_mismatches: list[dict[str, Any]] = []
    all_paths = sorted(set(by_manifest_path) | set(by_inventory_path) | set(cache_paths))
    for rel in all_paths:
        if rel not in by_manifest_path:
            path_mismatches.append({"path": rel, "reason": "not_in_dataset_manifest"})
        if rel not in by_inventory_path:
            path_mismatches.append({"path": rel, "reason": "not_in_raw_inventory"})
        if rel not in cache_paths:
            path_mismatches.append({"path": rel, "reason": "not_in_raw_cache"})

    content_mismatches: list[dict[str, Any]] = []
    observed_rows: list[dict[str, Any]] = []
    for rel in sorted(by_manifest_path):
        target = raw_root / Path(PurePosixPath(rel))
        if not target.is_file():
            continue
        data = target.read_bytes()
        observed_sha = sha256_bytes(data)
        observed_oid = git_blob_oid(data)
        observed_size = len(data)
        expected = by_manifest_path[rel]
        inventory = by_inventory_path.get(rel, {})
        comparisons = {
            "manifest_sha256": expected.get("sha256") == observed_sha,
            "inventory_sha256": inventory.get("sha256") == observed_sha,
            "manifest_git_blob_oid": expected.get("git_blob_oid") == observed_oid,
            "inventory_git_blob_oid": inventory.get("git_blob_oid") == observed_oid,
            "manifest_bytes": expected.get("bytes") == observed_size,
            "inventory_bytes": inventory.get("bytes") == observed_size,
            "acquisition_id": expected.get("acquisition_id")
            == f"acq_sha256:{observed_sha}",
        }
        if not all(comparisons.values()):
            content_mismatches.append(
                {
                    "path": rel,
                    "comparisons": comparisons,
                    "observed_sha256": observed_sha,
                    "observed_git_blob_oid": observed_oid,
                    "observed_bytes": observed_size,
                }
            )
        observed_rows.append(
            {
                **expected,
                "observed_sha256": observed_sha,
                "observed_git_blob_oid": observed_oid,
                "observed_bytes": observed_size,
            }
        )

    registry_by_sha = {row["sha256"]: row for row in acquisition_registry["acquisitions"]}
    paths_by_sha: dict[str, list[str]] = defaultdict(list)
    for row in observed_rows:
        paths_by_sha[row["observed_sha256"]].append(row["path"])

    registry_mismatches: list[dict[str, Any]] = []
    for digest, paths in sorted(paths_by_sha.items()):
        registered = registry_by_sha.get(digest)
        if registered is None:
            registry_mismatches.append(
                {"sha256": digest, "reason": "missing_acquisition_registry_entry"}
            )
            continue
        if sorted(paths) != sorted(registered["raw_path_aliases"]):
            registry_mismatches.append(
                {
                    "sha256": digest,
                    "reason": "alias_path_set_mismatch",
                    "observed": sorted(paths),
                    "registered": sorted(registered["raw_path_aliases"]),
                }
            )
        if registered.get("independent_observation_count") != 1:
            registry_mismatches.append(
                {
                    "sha256": digest,
                    "reason": "independent_observation_count_not_one",
                    "observed": registered.get("independent_observation_count"),
                }
            )
    for digest in sorted(set(registry_by_sha) - set(paths_by_sha)):
        registry_mismatches.append(
            {"sha256": digest, "reason": "registry_entry_has_no_manifest_path"}
        )

    alias_groups = [
        {
            "sha256": digest,
            "paths": sorted(paths),
            "path_count": len(paths),
            "independent_observation_count": 1,
        }
        for digest, paths in sorted(paths_by_sha.items())
        if len(paths) > 1
    ]

    checks = {
        "commit_exact": commit == EXPECTED_COMMIT,
        "raw_root_exists": raw_root.is_dir(),
        "manifest_paths_unique": not duplicate_manifest_paths,
        "path_bijection": not path_mismatches,
        "all_path_hash_oid_size_bindings_match": not content_mismatches,
        "acquisition_registry_exact": not registry_mismatches,
        "semantic_path_count_184": len(manifest_rows) == 184,
        "unique_acquisition_count_180": len(paths_by_sha) == 180,
        "alias_acquisition_count_4": len(alias_groups) == 4,
        "repository_inventory_sha256_pinned": (
            sha256_file(repository_inventory_path)
            == repo_provenance.get("repository_file_inventory_sha256")
        ),
        "raw_inventory_sha256_pinned": (
            sha256_file(raw_inventory_csv_path)
            == repo_provenance.get("raw_file_inventory_sha256")
        ),
        "full_cache_file_count_189": len(full_cache_by_path) == 189,
        "full_cache_matches_repository_inventory": not full_cache_mismatches,
    }
    return raw_root, {
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "counts": {
            "manifest_semantic_paths": len(manifest_rows),
            "inventory_paths": len(inventory_rows),
            "cache_csv_paths": len(cache_paths),
            "unique_acquisitions": len(paths_by_sha),
            "alias_acquisitions": len(alias_groups),
            "repository_inventory_paths": len(repository_inventory_rows),
            "full_cache_files": len(full_cache_by_path),
        },
        "repo_provenance": {
            "path": str(repo_provenance_path),
            "sha256": sha256_file(repo_provenance_path),
            "sha": repo_provenance.get("sha"),
            "branch": repo_provenance.get("branch"),
            "git_object_format": repo_provenance.get("git_object_format"),
        },
        "repository_inventory": {
            "path": str(repository_inventory_path),
            "sha256": sha256_file(repository_inventory_path),
            "file_count": len(repository_inventory_rows),
        },
        "full_cache_identity": {
            "file_count": full_cache["file_count"],
            "tree_sha256": full_cache["tree_sha256"],
        },
        "full_cache_mismatches": full_cache_mismatches,
        "duplicate_manifest_paths": duplicate_manifest_paths,
        "path_mismatches": path_mismatches,
        "content_mismatches": content_mismatches,
        "registry_mismatches": registry_mismatches,
        "alias_groups": alias_groups,
        "observed_rows": observed_rows,
    }


def metric_record(metrics: Any) -> dict[str, Any]:
    return {field: getattr(metrics, field) for field in METRIC_FIELDS + AUDIT_FIELDS}


def generator_advisory_codes(warnings: list[str]) -> list[str]:
    """Translate the source's human CLI warnings to generator policy codes."""
    codes: list[str] = []
    for warning in warnings:
        if "isolated timing gap(s); displacement grid remains intact" in warning:
            codes.append("isolated_timing_gaps")
        elif warning == "small unloaded return-endpoint zero offset":
            codes.append("unloaded_return_endpoint_zero_offset")
        elif warning.startswith("speed flag: median sample interval"):
            codes.append("preferred_sample_interval_miss")
        elif warning.startswith("speed flag: full-cycle speed"):
            codes.append("preferred_full_cycle_speed_miss")
        elif warning.startswith("speed flag: collapse-region speed"):
            codes.append("preferred_collapse_local_speed_miss")
        else:
            raise AuditError(f"unmapped test-imp warning: {warning!r}")
    return sorted(set(codes))


def decision_reason_codes(run: Any, cohort: Any, minimum_runs: int) -> list[str]:
    reasons: list[str] = []
    if not run.individually_acceptable:
        reasons.append("intake_run_ineligible")
    if cohort.mixed is not None:
        reasons.append("mixed_cohort_stop")
    if run.individually_acceptable:
        fc_dev = abs(float(run.metrics.collapse_force_gf) - cohort.center_fc_gf)
        xc_dev = abs(float(run.metrics.collapse_travel_mm) - cohort.center_xc_mm)
        if fc_dev > cohort.fc_tolerance_gf:
            reasons.append("collapse_force_outside_replicate_band")
        if xc_dev > cohort.xc_tolerance_mm:
            reasons.append("collapse_position_outside_replicate_band")
    status = cohort_status(cohort, minimum_runs)
    if run.retained and status == "retest_insufficient_replicates":
        reasons.append("minimum_two_matching_runs_not_met")
    if run.retained and status == "accepted":
        reasons.append("retained")
    return reasons


def cohort_status(cohort: Any, minimum_runs: int) -> str:
    if cohort.mixed is not None:
        return "mixed_cohort_stop"
    if len(cohort.retained) < minimum_runs:
        return "retest_insufficient_replicates"
    return "accepted"


def assess_fleet(
    manifest: dict[str, Any],
    raw_root: Path,
    assess_cohort: Any,
    importer_config: Any,
) -> dict[str, Any]:
    run_rows: list[dict[str, Any]] = []
    cohort_rows: list[dict[str, Any]] = []
    by_semantic_key: dict[tuple[str, str], dict[str, Any]] = {}

    for test in manifest["tests"]:
        expected_runs = test["expected_runs"]
        paths = [raw_root / Path(PurePosixPath(row["path"])) for row in expected_runs]
        cohort = assess_cohort(paths)
        status = cohort_status(cohort, importer_config.MIN_ACCEPTED_RUNS)
        expected_by_local = {
            str(path.resolve()): run for path, run in zip(paths, expected_runs)
        }
        ramp_median = None
        numeric_retained_ramps = [
            float(run.metrics.ramp_10_90_gf_per_mm)
            for run in cohort.retained
            if run.metrics.ramp_10_90_gf_per_mm is not None
            and math.isfinite(float(run.metrics.ramp_10_90_gf_per_mm))
        ]
        if len(numeric_retained_ramps) >= importer_config.RAMP_REVIEW_MIN_NUMERIC_RETAINED_RUNS:
            numeric_retained_ramps.sort()
            middle = len(numeric_retained_ramps) // 2
            ramp_median = (
                numeric_retained_ramps[middle]
                if len(numeric_retained_ramps) % 2
                else 0.5
                * (numeric_retained_ramps[middle - 1] + numeric_retained_ramps[middle])
            )

        mixed = None
        if cohort.mixed is not None:
            mixed = {
                "reason": cohort.mixed.reason,
                "group_a": [posix_relative(run.raw.path, raw_root) for run in cohort.mixed.group_a],
                "group_b": [posix_relative(run.raw.path, raw_root) for run in cohort.mixed.group_b],
            }

        cohort_row = {
            "test_id": test["test_id"],
            "set": test["set"],
            "measurement_cohort_id": test.get("measurement_cohort_id"),
            "acquisition_group_id": test.get("acquisition_group_id"),
            "independence_key": test.get("independence_key"),
            "candidate_count": len(cohort.runs),
            "individually_acceptable_count": sum(
                run.individually_acceptable for run in cohort.runs
            ),
            "preliminary_matching_count": len(cohort.retained),
            "retained_count": len(cohort.retained) if status == "accepted" else 0,
            "status": status,
            "mixed_cohort": mixed,
            "center_collapse_force_gf": cohort.center_fc_gf,
            "center_collapse_position_mm": cohort.center_xc_mm,
            "collapse_force_tolerance_gf": cohort.fc_tolerance_gf,
            "collapse_position_tolerance_mm": cohort.xc_tolerance_mm,
            "minimum_retained_runs": importer_config.MIN_ACCEPTED_RUNS,
            "minimum_retained_runs_pass": status == "accepted",
            "numeric_retained_ramp_count": len(numeric_retained_ramps),
            "retained_median_ramp_gf_per_mm": ramp_median,
            "ramp_review_count": len(cohort.ramp_reviews),
        }
        cohort_rows.append(cohort_row)

        for assessment in cohort.runs:
            expected = expected_by_local[str(assessment.raw.path.resolve())]
            fc_dev = (
                None
                if not assessment.individually_acceptable
                else abs(
                    float(assessment.metrics.collapse_force_gf)
                    - float(cohort.center_fc_gf)
                )
            )
            xc_dev = (
                None
                if not assessment.individually_acceptable
                else abs(
                    float(assessment.metrics.collapse_travel_mm)
                    - float(cohort.center_xc_mm)
                )
            )
            source_metrics = metric_record(assessment.metrics)
            effective_retained = assessment.retained and status == "accepted"
            ramp_review = None
            if assessment.ramp_review is not None:
                ramp_review = {
                    "ramp_gf_per_mm": assessment.ramp_review.ramp_gf_per_mm,
                    "retained_median_gf_per_mm": assessment.ramp_review.retained_median_gf_per_mm,
                    "signed_deviation_pct": assessment.ramp_review.signed_deviation_pct,
                    "absolute_deviation_pct": assessment.ramp_review.absolute_deviation_pct,
                    "threshold_pct": assessment.ramp_review.threshold_pct,
                }
            row = {
                "test_id": test["test_id"],
                "set": test["set"],
                "measurement_cohort_id": test.get("measurement_cohort_id"),
                "acquisition_group_id": test.get("acquisition_group_id"),
                "independence_key": test.get("independence_key"),
                "raw_path": expected["path"],
                "run": PurePosixPath(expected["path"]).name,
                "sha256": assessment.raw.sha256,
                "git_blob_oid": expected.get("git_blob_oid"),
                "acquisition_id": expected.get("acquisition_id"),
                "raw_bytes": assessment.raw.byte_count,
                **source_metrics,
                "quality_flags": sorted(set(assessment.metrics.flags)),
                "integrity_failures": assessment.integrity_failures,
                "protocol_failures": assessment.protocol_failures,
                "warnings": assessment.warnings,
                "expected_generator_advisories": generator_advisory_codes(
                    assessment.warnings
                ),
                "speed_flags": assessment.speed_flags,
                "fatal_metric_flags": assessment.fatal_metric_flags,
                "metric_local_flags": assessment.metric_local_flags,
                "mixed_cohort_eligible": assessment.mixed_cohort_eligible,
                "individually_acceptable": assessment.individually_acceptable,
                "matches_replicate_band": assessment.retained,
                "retained": effective_retained,
                "cohort_status": status,
                "collapse_force_deviation_gf": fc_dev,
                "collapse_position_deviation_mm": xc_dev,
                "decision_reasons": decision_reason_codes(
                    assessment, cohort, importer_config.MIN_ACCEPTED_RUNS
                ),
                "ramp_review_required": assessment.ramp_review is not None,
                "ramp_review": ramp_review,
                "effective_speed_mm_s": assessment.effective_speed_mm_s,
                "collapse_local_speed_mm_s": assessment.collapse_local_speed_mm_s,
                "interval_median_ms": assessment.interval_median_ms,
                "timing_gap_count": assessment.timing_gap_count,
            }
            run_rows.append(row)
            by_semantic_key[(test["set"], expected["path"])] = row

    alias_checks: list[dict[str, Any]] = []
    runs_by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in run_rows:
        runs_by_sha[row["sha256"]].append(row)
    for digest, aliases in sorted(runs_by_sha.items()):
        if len(aliases) < 2:
            continue
        reference = aliases[0]
        comparison_fields = list(METRIC_FIELDS + AUDIT_FIELDS) + [
            "quality_flags",
            "individually_acceptable",
            "matches_replicate_band",
            "retained",
            "cohort_status",
            "ramp_review_required",
            "ramp_review",
        ]
        mismatched = [
            field
            for field in comparison_fields
            if any(alias[field] != reference[field] for alias in aliases[1:])
        ]
        alias_checks.append(
            {
                "sha256": digest,
                "paths": [row["raw_path"] for row in aliases],
                "sets": [row["set"] for row in aliases],
                "semantic_record_count": len(aliases),
                "independent_observation_count": 1,
                "metric_and_decision_match": not mismatched,
                "mismatched_fields": mismatched,
            }
        )

    unique_run_by_sha = {row["sha256"]: row for row in run_rows}
    counts = {
        "semantic_cohorts": len(cohort_rows),
        "independent_measurement_cohorts": len(
            {row["measurement_cohort_id"] for row in cohort_rows}
        ),
        "semantic_paths": len(run_rows),
        "unique_acquisitions": len(unique_run_by_sha),
        "individually_acceptable_semantic_paths": sum(
            row["individually_acceptable"] for row in run_rows
        ),
        "individually_acceptable_unique_acquisitions": sum(
            row["individually_acceptable"] for row in unique_run_by_sha.values()
        ),
        "retained_semantic_paths": sum(row["retained"] for row in run_rows),
        "retained_unique_acquisitions": sum(
            row["retained"] for row in unique_run_by_sha.values()
        ),
        "omitted_failed_semantic_paths": sum(
            not row["individually_acceptable"] for row in run_rows
        ),
        "omitted_outlier_semantic_paths": sum(
            row["individually_acceptable"] and not row["matches_replicate_band"]
            for row in run_rows
        ),
        "mixed_cohorts": sum(row["mixed_cohort"] is not None for row in cohort_rows),
        "minimum_two_fail_cohorts": sum(
            not row["minimum_retained_runs_pass"]
            and row["mixed_cohort"] is None
            for row in cohort_rows
        ),
        "ramp_review_semantic_paths": sum(
            row["ramp_review_required"] for row in run_rows
        ),
        "ramp_review_unique_acquisitions": sum(
            row["ramp_review_required"] for row in unique_run_by_sha.values()
        ),
        "preferred_speed_flag_semantic_paths": sum(
            bool(row["speed_flags"]) for row in run_rows
        ),
        "hard_protocol_failure_semantic_paths": sum(
            bool(row["protocol_failures"]) for row in run_rows
        ),
        "integrity_failure_semantic_paths": sum(
            bool(row["integrity_failures"]) for row in run_rows
        ),
        "fatal_metric_failure_semantic_paths": sum(
            bool(row["fatal_metric_flags"]) for row in run_rows
        ),
        "metric_local_null_semantic_paths": sum(
            bool(row["metric_local_flags"]) for row in run_rows
        ),
    }
    checks = {
        "semantic_cohort_count_76": counts["semantic_cohorts"] == 76,
        "independent_measurement_cohort_count_75": (
            counts["independent_measurement_cohorts"] == 75
        ),
        "semantic_path_count_184": counts["semantic_paths"] == 184,
        "unique_acquisition_count_180": counts["unique_acquisitions"] == 180,
        "all_alias_metrics_and_decisions_match": all(
            row["metric_and_decision_match"] for row in alias_checks
        ),
        "all_cohorts_pass_minimum_two": not counts["minimum_two_fail_cohorts"],
        "no_mixed_cohort_stop": not counts["mixed_cohorts"],
    }
    return {
        "checks": checks,
        "all_structural_checks_pass": all(checks.values()),
        "counts": counts,
        "cohorts": cohort_rows,
        "runs": run_rows,
        "alias_semantics": {
            "rule": (
                "Each path is a semantic evidence record; identical SHA-256 values "
                "identify one physical acquisition and count once for independence."
            ),
            "checks": alias_checks,
        },
    }


def predecessor_retest_impact(
    work_root: Path,
    fleet: dict[str, Any],
    importer_config: Any,
) -> dict[str, Any]:
    """Describe the Topre R2 45g retest's epoch-to-epoch impact.

    This is an evidence comparison, not an intake gate or a causal diagnosis.
    The predecessor aggregate is bound to its staged full-precision record and
    independently rechecked against its retained per-run evidence.  The new
    aggregate is calculated directly from this audit's importer-derived runs.
    """

    predecessor_root = (
        work_root / "epoch_outputs" / f"staging_canonical_{PREDECESSOR_COMMIT[:7]}"
    )
    predecessor_bench_path = predecessor_root / "bench_tests.staged.json"
    predecessor_runs_path = predecessor_root / "per_run_full_precision.json"
    if not predecessor_bench_path.is_file() or not predecessor_runs_path.is_file():
        raise AuditError(
            "predecessor retest-impact evidence is unavailable: "
            f"{predecessor_bench_path}, {predecessor_runs_path}"
        )

    predecessor_bench = read_json(predecessor_bench_path)
    predecessor_records = (
        predecessor_bench
        if isinstance(predecessor_bench, list)
        else predecessor_bench.get("tests", [])
    )
    matching_records = [
        row for row in predecessor_records if row.get("set") == RETEST_IMPACT_SET
    ]
    if len(matching_records) != 1:
        raise AuditError(
            f"expected one predecessor {RETEST_IMPACT_SET!r} record, "
            f"found {len(matching_records)}"
        )
    predecessor_record = matching_records[0]

    predecessor_per_run = read_json(predecessor_runs_path)
    if not isinstance(predecessor_per_run, list):
        raise AuditError("predecessor per-run evidence must be a JSON array")
    predecessor_runs = [
        row
        for row in predecessor_per_run
        if row.get("set") == RETEST_IMPACT_SET
        and bool(row.get("retained_output", row.get("intake_retained", False)))
    ]
    candidate_runs = [
        row
        for row in fleet["runs"]
        if row.get("set") == RETEST_IMPACT_SET and row.get("retained")
    ]

    def arithmetic_mean(rows: list[dict[str, Any]], field: str) -> float | None:
        values = [row.get(field) for row in rows]
        if not values or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
            for value in values
        ):
            return None
        return sum(float(value) for value in values) / len(values)

    predecessor_metric_mismatches: list[dict[str, Any]] = []
    metrics: dict[str, dict[str, Any]] = {}
    for field in METRIC_FIELDS:
        predecessor_value = predecessor_record.get(field)
        predecessor_recalculated = arithmetic_mean(predecessor_runs, field)
        equal, check_delta = same_number(
            predecessor_value, predecessor_recalculated
        )
        if not equal:
            predecessor_metric_mismatches.append(
                {
                    "field": field,
                    "staged_aggregate": predecessor_value,
                    "recalculated_from_per_run": predecessor_recalculated,
                    "absolute_delta": check_delta,
                }
            )
        candidate_value = arithmetic_mean(candidate_runs, field)
        absolute_delta = None
        relative_delta_pct = None
        if (
            isinstance(predecessor_value, (int, float))
            and not isinstance(predecessor_value, bool)
            and isinstance(candidate_value, (int, float))
            and not isinstance(candidate_value, bool)
        ):
            absolute_delta = candidate_value - predecessor_value
            if predecessor_value != 0:
                relative_delta_pct = 100.0 * absolute_delta / predecessor_value
        metrics[field] = {
            "predecessor": predecessor_value,
            "candidate": candidate_value,
            "absolute_delta": absolute_delta,
            "relative_delta_pct": relative_delta_pct,
        }

    predecessor_by_path = {
        row["raw_path"]: row for row in predecessor_runs
    }
    candidate_by_path = {row["raw_path"]: row for row in candidate_runs}
    predecessor_ramps = sorted(
        float(row["ramp_10_90_gf_per_mm"])
        for row in predecessor_runs
        if row.get("ramp_10_90_gf_per_mm") is not None
    )
    candidate_ramps = sorted(
        float(row["ramp_10_90_gf_per_mm"])
        for row in candidate_runs
        if row.get("ramp_10_90_gf_per_mm") is not None
    )

    def median(values: list[float]) -> float | None:
        if not values:
            return None
        middle = len(values) // 2
        return (
            values[middle]
            if len(values) % 2
            else 0.5 * (values[middle - 1] + values[middle])
        )

    predecessor_ramp_median = median(predecessor_ramps)
    candidate_ramp_median = median(candidate_ramps)
    common_paths = sorted(set(predecessor_by_path) & set(candidate_by_path))
    replaced_paths = [
        {
            "raw_path": path,
            "predecessor_sha256": predecessor_by_path[path].get("sha256"),
            "candidate_sha256": candidate_by_path[path].get("sha256"),
        }
        for path in common_paths
        if predecessor_by_path[path].get("sha256")
        != candidate_by_path[path].get("sha256")
    ]
    predecessor_commit = (predecessor_record.get("provenance") or {}).get(
        "repo_commit"
    )
    checks = {
        "predecessor_commit_exact": predecessor_commit == PREDECESSOR_COMMIT,
        "predecessor_retained_count_three": len(predecessor_runs) == 3,
        "candidate_retained_count_two": len(candidate_runs) == 2,
        "predecessor_aggregate_recalculates_from_per_run": (
            not predecessor_metric_mismatches
        ),
        "all_fourteen_metrics_present": set(metrics) == set(METRIC_FIELDS),
    }
    return {
        "classification": "descriptive_retest_impact_not_qc_failure",
        "interpretation": (
            "Describes the measured change after replacement runs were committed. "
            "Magnitude does not change test-imp retention and does not establish a cause."
        ),
        "set": RETEST_IMPACT_SET,
        "predecessor": {
            "repo_commit": predecessor_commit,
            "retained_count": len(predecessor_runs),
            "raw_paths": sorted(predecessor_by_path),
            "raw_sha256": [
                predecessor_by_path[path].get("sha256")
                for path in sorted(predecessor_by_path)
            ],
            "bench_tests": {
                "path": str(predecessor_bench_path),
                "sha256": sha256_file(predecessor_bench_path),
            },
            "per_run_full_precision": {
                "path": str(predecessor_runs_path),
                "sha256": sha256_file(predecessor_runs_path),
            },
        },
        "candidate": {
            "repo_commit": EXPECTED_COMMIT,
            "retained_count": len(candidate_runs),
            "raw_paths": sorted(candidate_by_path),
            "raw_sha256": [
                candidate_by_path[path].get("sha256")
                for path in sorted(candidate_by_path)
            ],
        },
        "membership": {
            "retained_count_delta": len(candidate_runs) - len(predecessor_runs),
            "retired_paths": sorted(set(predecessor_by_path) - set(candidate_by_path)),
            "added_paths": sorted(set(candidate_by_path) - set(predecessor_by_path)),
            "replaced_paths": replaced_paths,
        },
        "ramp_review_context": {
            "rule": (
                "A retained numeric RAMP more than the relative threshold from "
                "the retained-run median is advisory only; the rule is evaluated "
                "only when the minimum numeric retained-run count is met."
            ),
            "minimum_numeric_retained_runs": (
                importer_config.RAMP_REVIEW_MIN_NUMERIC_RETAINED_RUNS
            ),
            "relative_threshold_pct": (
                100.0 * importer_config.RAMP_REVIEW_RELATIVE_DEVIATION
            ),
            "predecessor": {
                "numeric_retained_count": len(predecessor_ramps),
                "values_gf_per_mm": predecessor_ramps,
                "median_gf_per_mm": predecessor_ramp_median,
                "formal_rule_evaluated": len(predecessor_ramps)
                >= importer_config.RAMP_REVIEW_MIN_NUMERIC_RETAINED_RUNS,
                "review_count": sum(
                    bool(row.get("intake_ramp_review_required"))
                    for row in predecessor_runs
                ),
            },
            "candidate": {
                "numeric_retained_count": len(candidate_ramps),
                "values_gf_per_mm": candidate_ramps,
                "median_gf_per_mm": candidate_ramp_median,
                "formal_rule_evaluated": len(candidate_ramps)
                >= importer_config.RAMP_REVIEW_MIN_NUMERIC_RETAINED_RUNS,
                "review_count": sum(
                    bool(row.get("ramp_review_required")) for row in candidate_runs
                ),
            },
        },
        "metrics": metrics,
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "predecessor_metric_mismatches": predecessor_metric_mismatches,
    }


def same_number(expected: Any, observed: Any) -> tuple[bool, float | None]:
    if expected is None or observed is None:
        return expected is observed, None
    if isinstance(expected, bool) or isinstance(observed, bool):
        return expected is observed, None
    try:
        left = float(expected)
        right = float(observed)
    except (TypeError, ValueError):
        return expected == observed, None
    if not math.isfinite(left) or not math.isfinite(right):
        return left == right, None
    delta = abs(left - right)
    return delta <= NUMERIC_TOLERANCE, delta


def flatten_decisions(document: dict[str, Any]) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    sets: dict[str, Any] = {}
    runs: dict[tuple[str, str], dict[str, Any]] = {}
    for set_row in document.get("sets", []):
        set_name = set_row["set"]
        sets[set_name] = set_row
        for run in set_row.get("runs", []):
            runs[(set_name, run["raw_path"])] = run
    return sets, runs


def candidate_json_documents(root: Path, filename: str) -> Iterable[Path]:
    for path in root.rglob(filename):
        if "raw_cache" not in path.parts and path.is_file():
            yield path


def select_generator_document(
    candidates: Iterable[Path],
    expected_commit: str,
    expected_keys: set[tuple[str, str]],
    kind: str,
) -> tuple[Path | None, dict[str, Any] | list[Any] | None, list[dict[str, Any]]]:
    inspected: list[dict[str, Any]] = []
    matches: list[tuple[Path, Any]] = []
    for path in sorted(set(candidates)):
        try:
            doc = read_json(path)
        except Exception as exc:  # report malformed candidates, never hide them
            inspected.append({"path": str(path), "usable": False, "reason": repr(exc)})
            continue
        commit = doc.get("repo_commit") if isinstance(doc, dict) else None
        if kind == "decisions" and isinstance(doc, dict):
            _, rows = flatten_decisions(doc)
            keys = set(rows)
        elif kind == "per_run" and isinstance(doc, list):
            keys = {
                (str(row.get("set")), str(row.get("raw_path")))
                for row in doc
                if isinstance(row, dict)
            }
            commits = {
                row.get("repo_commit")
                for row in doc
                if isinstance(row, dict) and row.get("repo_commit")
            }
            if len(commits) == 1:
                commit = next(iter(commits))
        else:
            keys = set()
        path_match = keys == expected_keys
        commit_match = commit in (None, expected_commit) if kind == "per_run" else commit == expected_commit
        usable = path_match and commit_match
        inspected.append(
            {
                "path": str(path),
                "commit": commit,
                "key_count": len(keys),
                "path_set_exact": path_match,
                "commit_exact_or_embedded_elsewhere": commit_match,
                "usable": usable,
            }
        )
        if usable:
            matches.append((path, doc))
    if not matches:
        return None, None, inspected
    # Prefer the newest deterministic staged/canonical target, but fail closed
    # if equally current documents disagree in a later comparison.
    matches.sort(key=lambda item: (item[0].stat().st_mtime_ns, str(item[0])))
    return matches[-1][0], matches[-1][1], inspected


def compare_generator(
    work_root: Path,
    source_manifest: dict[str, Any],
    fleet: dict[str, Any],
) -> dict[str, Any]:
    expected_runs = {(row["set"], row["raw_path"]): row for row in fleet["runs"]}
    expected_keys = set(expected_runs)
    generator_root = work_root / "source" / "generator"
    config_root = generator_root / "domelab_pipeline" / "config"

    generator_manifest_path = config_root / "dataset_manifest.json"
    manifest_comparison: dict[str, Any] = {
        "path": str(generator_manifest_path),
        "status": "not_ready",
        "mismatches": [],
    }
    if generator_manifest_path.is_file():
        generator_manifest = read_json(generator_manifest_path)
        generator_rows = flatten_manifest_tests(generator_manifest)
        source_rows = flatten_manifest_tests(source_manifest)
        source_by_key = {(row["set"], row["path"]): row for row in source_rows}
        generator_by_key = {(row["set"], row["path"]): row for row in generator_rows}
        if generator_manifest.get("repo_commit") == EXPECTED_COMMIT:
            mismatches: list[dict[str, Any]] = []
            for key in sorted(set(source_by_key) | set(generator_by_key)):
                left = source_by_key.get(key)
                right = generator_by_key.get(key)
                if left is None or right is None:
                    mismatches.append(
                        {"key": list(key), "reason": "path_membership_mismatch"}
                    )
                    continue
                for field in ("sha256", "git_blob_oid", "acquisition_id", "bytes"):
                    if left.get(field) != right.get(field):
                        mismatches.append(
                            {
                                "key": list(key),
                                "field": field,
                                "expected": left.get(field),
                                "observed": right.get(field),
                            }
                        )
            manifest_comparison = {
                "path": str(generator_manifest_path),
                "status": "pass" if not mismatches else "fail",
                "repo_commit": generator_manifest.get("repo_commit"),
                "source_path_count": len(source_rows),
                "generator_path_count": len(generator_rows),
                "mismatches": mismatches,
            }
        else:
            manifest_comparison["observed_repo_commit"] = generator_manifest.get(
                "repo_commit"
            )
            manifest_comparison["reason"] = "generator manifest still targets another epoch"

    decision_candidates = list(candidate_json_documents(generator_root, "retained_run_decisions.json"))
    decision_candidates.extend(
        candidate_json_documents(generator_root, "retained_run_decisions*.json")
    )
    decision_path, decision_doc, decision_inspected = select_generator_document(
        decision_candidates, EXPECTED_COMMIT, expected_keys, "decisions"
    )
    decision_comparison: dict[str, Any] = {
        "status": "not_ready",
        "selected_path": None,
        "inspected_candidates": decision_inspected,
        "mismatches": [],
        "max_scalar_delta": None,
    }
    if decision_path is not None and isinstance(decision_doc, dict):
        generator_sets, generator_runs = flatten_decisions(decision_doc)
        expected_sets = {row["set"]: row for row in fleet["cohorts"]}
        mismatches: list[dict[str, Any]] = []
        max_delta = 0.0
        scalar_compared = 0
        for key in sorted(expected_keys):
            expected = expected_runs[key]
            observed = generator_runs[key]
            for field, observed_field in (
                ("sha256", "sha256"),
                ("individually_acceptable", "intake_individually_acceptable"),
                ("matches_replicate_band", "matches_replicate_band"),
                ("retained", "retained"),
                ("ramp_review_required", "ramp_review_required"),
            ):
                if expected[field] != observed.get(observed_field):
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": observed_field,
                            "expected": expected[field],
                            "observed": observed.get(observed_field),
                        }
                    )
            if expected["decision_reasons"] != observed.get("decision_reasons"):
                mismatches.append(
                    {
                        "key": list(key),
                        "field": "decision_reasons",
                        "expected": expected["decision_reasons"],
                        "observed": observed.get("decision_reasons"),
                    }
                )
            observed_qc = observed.get("intake_qc") or {}
            qc_exact_fields = (
                ("mixed_cohort_eligible", expected["mixed_cohort_eligible"]),
                ("fatal_metric_flags", sorted(expected["fatal_metric_flags"])),
                ("advisories", expected["expected_generator_advisories"]),
            )
            for qc_field, expected_value in qc_exact_fields:
                observed_value = observed_qc.get(qc_field)
                if isinstance(observed_value, list):
                    observed_value = sorted(observed_value)
                if expected_value != observed_value:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": f"intake_qc.{qc_field}",
                            "expected": expected_value,
                            "observed": observed_value,
                        }
                    )
            # Every frozen run is source-acceptable, so exact emptiness is a
            # strict cross-implementation check without translating human
            # failure prose to generator reason codes.
            for qc_field in ("integrity_failures", "protocol_failures"):
                if observed_qc.get(qc_field) != []:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": f"intake_qc.{qc_field}",
                            "expected": [],
                            "observed": observed_qc.get(qc_field),
                        }
                    )
            observations = observed_qc.get("observations") or {}
            for observation_field in INTAKE_OBSERVATION_FIELDS:
                equal, delta = same_number(
                    expected[observation_field], observations.get(observation_field)
                )
                if delta is not None:
                    scalar_compared += 1
                    max_delta = max(max_delta, delta)
                if not equal:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": f"intake_qc.observations.{observation_field}",
                            "expected": expected[observation_field],
                            "observed": observations.get(observation_field),
                            "absolute_delta": delta,
                        }
                    )
            for expected_field, observed_field in (
                ("collapse_force_deviation_gf", "collapse_force_deviation_gf"),
                ("collapse_position_deviation_mm", "collapse_position_deviation_mm"),
            ):
                equal, delta = same_number(expected[expected_field], observed.get(observed_field))
                if delta is not None:
                    scalar_compared += 1
                    max_delta = max(max_delta, delta)
                if not equal:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": observed_field,
                            "expected": expected[expected_field],
                            "observed": observed.get(observed_field),
                            "absolute_delta": delta,
                        }
                    )
            if expected["ramp_review"] != observed.get("ramp_review"):
                # Compare review evidence numerically field-by-field before
                # declaring a mismatch, since two compliant implementations
                # may differ only at floating representation scale.
                left = expected["ramp_review"]
                right = observed.get("ramp_review")
                if left is None or right is None:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": "ramp_review",
                            "expected": left,
                            "observed": right,
                        }
                    )
                else:
                    for review_field in left:
                        equal, delta = same_number(left[review_field], right.get(review_field))
                        if delta is not None:
                            scalar_compared += 1
                            max_delta = max(max_delta, delta)
                        if not equal:
                            mismatches.append(
                                {
                                    "key": list(key),
                                    "field": f"ramp_review.{review_field}",
                                    "expected": left[review_field],
                                    "observed": right.get(review_field),
                                    "absolute_delta": delta,
                                }
                            )

        for set_name, expected in sorted(expected_sets.items()):
            observed = generator_sets.get(set_name)
            if observed is None:
                mismatches.append({"set": set_name, "reason": "missing_set_decision"})
                continue
            if expected["status"] != observed.get("status"):
                mismatches.append(
                    {
                        "set": set_name,
                        "field": "status",
                        "expected": expected["status"],
                        "observed": observed.get("status"),
                    }
                )
            for exact_field in (
                "candidate_count",
                "preliminary_matching_count",
                "retained_count",
            ):
                if expected[exact_field] != observed.get(exact_field):
                    mismatches.append(
                        {
                            "set": set_name,
                            "field": exact_field,
                            "expected": expected[exact_field],
                            "observed": observed.get(exact_field),
                        }
                    )
            if (expected["mixed_cohort"] is None) != (
                observed.get("mixed_cohort") is None
            ):
                mismatches.append(
                    {
                        "set": set_name,
                        "field": "mixed_cohort",
                        "expected": expected["mixed_cohort"],
                        "observed": observed.get("mixed_cohort"),
                    }
                )
            observed_ramp = observed.get("ramp_review_summary") or {}
            for expected_field, observed_field in (
                ("numeric_retained_ramp_count", "numeric_retained_count"),
                ("ramp_review_count", "review_count"),
            ):
                if expected[expected_field] != observed_ramp.get(observed_field):
                    mismatches.append(
                        {
                            "set": set_name,
                            "field": f"ramp_review_summary.{observed_field}",
                            "expected": expected[expected_field],
                            "observed": observed_ramp.get(observed_field),
                        }
                    )
            expected_review_required = expected["ramp_review_count"] > 0
            if expected_review_required != observed_ramp.get("review_required"):
                mismatches.append(
                    {
                        "set": set_name,
                        "field": "ramp_review_summary.review_required",
                        "expected": expected_review_required,
                        "observed": observed_ramp.get("review_required"),
                    }
                )
            equal, delta = same_number(
                expected["retained_median_ramp_gf_per_mm"],
                observed_ramp.get("retained_median_gf_per_mm"),
            )
            if delta is not None:
                scalar_compared += 1
                max_delta = max(max_delta, delta)
            if not equal:
                mismatches.append(
                    {
                        "set": set_name,
                        "field": "ramp_review_summary.retained_median_gf_per_mm",
                        "expected": expected["retained_median_ramp_gf_per_mm"],
                        "observed": observed_ramp.get("retained_median_gf_per_mm"),
                        "absolute_delta": delta,
                    }
                )
            for expected_field, group, observed_field in (
                ("center_collapse_force_gf", "center", "collapse_force_gf"),
                ("center_collapse_position_mm", "center", "collapse_position_mm"),
                ("collapse_force_tolerance_gf", "tolerances", "collapse_force_gf"),
                ("collapse_position_tolerance_mm", "tolerances", "collapse_position_mm"),
            ):
                equal, delta = same_number(
                    expected[expected_field], (observed.get(group) or {}).get(observed_field)
                )
                if delta is not None:
                    scalar_compared += 1
                    max_delta = max(max_delta, delta)
                if not equal:
                    mismatches.append(
                        {
                            "set": set_name,
                            "field": f"{group}.{observed_field}",
                            "expected": expected[expected_field],
                            "observed": (observed.get(group) or {}).get(observed_field),
                            "absolute_delta": delta,
                        }
                    )
        decision_comparison = {
            "status": "pass" if not mismatches else "fail",
            "selected_path": str(decision_path),
            "selected_sha256": sha256_file(decision_path),
            "artifact_role": decision_doc.get("artifact_role"),
            "repo_commit": decision_doc.get("repo_commit"),
            "run_count": len(generator_runs),
            "set_count": len(generator_sets),
            "scalar_comparisons": scalar_compared,
            "max_scalar_delta": max_delta,
            "numeric_tolerance": NUMERIC_TOLERANCE,
            "mismatches": mismatches,
            "inspected_candidates": decision_inspected,
        }

    # Canonical epoch products live outside the copied generator source.  Scan
    # the epoch work root and accept only the document whose semantic key set
    # exactly equals the 184 frozen manifest keys; stale generator staging is
    # therefore visible in the inspection log but cannot be selected.
    per_run_candidates = list(
        candidate_json_documents(work_root, "per_run_full_precision.json")
    )
    per_run_path, per_run_doc, per_run_inspected = select_generator_document(
        per_run_candidates, EXPECTED_COMMIT, expected_keys, "per_run"
    )
    per_run_comparison: dict[str, Any] = {
        "status": "not_ready",
        "selected_path": None,
        "inspected_candidates": per_run_inspected,
        "mismatches": [],
        "max_scalar_delta": None,
    }
    if per_run_path is not None and isinstance(per_run_doc, list):
        observed_runs = {
            (str(row["set"]), str(row["raw_path"])): row for row in per_run_doc
        }
        mismatches: list[dict[str, Any]] = []
        max_delta = 0.0
        scalar_compared = 0
        for key in sorted(expected_keys):
            expected = expected_runs[key]
            observed = observed_runs[key]
            for field in ("sha256", "git_blob_oid", "acquisition_id"):
                if field in observed and expected[field] != observed[field]:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": field,
                            "expected": expected[field],
                            "observed": observed[field],
                        }
                    )
            for field in METRIC_FIELDS + AUDIT_FIELDS:
                equal, delta = same_number(expected[field], observed.get(field))
                if delta is not None:
                    scalar_compared += 1
                    max_delta = max(max_delta, delta)
                if not equal:
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": field,
                            "expected": expected[field],
                            "observed": observed.get(field),
                            "absolute_delta": delta,
                        }
                    )
            observed_flags = observed.get("quality_flags", [])
            if isinstance(observed_flags, str):
                observed_flags = [item for item in observed_flags.split(";") if item]
            if expected["quality_flags"] != sorted(set(observed_flags)):
                mismatches.append(
                    {
                        "key": list(key),
                        "field": "quality_flags",
                        "expected": expected["quality_flags"],
                        "observed": sorted(set(observed_flags)),
                    }
                )
            for expected_field, observed_field in (
                ("individually_acceptable", "intake_individually_acceptable"),
                ("matches_replicate_band", "intake_matches_replicate_band"),
                ("retained", "intake_retained"),
                ("cohort_status", "intake_set_status"),
                ("ramp_review_required", "intake_ramp_review_required"),
            ):
                if expected[expected_field] != observed.get(observed_field):
                    mismatches.append(
                        {
                            "key": list(key),
                            "field": observed_field,
                            "expected": expected[expected_field],
                            "observed": observed.get(observed_field),
                        }
                    )
        per_run_comparison = {
            "status": "pass" if not mismatches else "fail",
            "selected_path": str(per_run_path),
            "selected_sha256": sha256_file(per_run_path),
            "run_count": len(observed_runs),
            "metrics_per_run": len(METRIC_FIELDS),
            "audit_fields_per_run": len(AUDIT_FIELDS),
            "scalar_comparisons": scalar_compared,
            "max_scalar_delta": max_delta,
            "numeric_tolerance": NUMERIC_TOLERANCE,
            "mismatches": mismatches,
            "inspected_candidates": per_run_inspected,
        }

    artifact_bindings: dict[str, Any] = {
        "status": "not_ready",
        "checks": {},
    }
    if per_run_path is not None and decision_path is not None:
        output_root = per_run_path.parent
        generated_manifest_path = output_root / "generated_manifest.json"
        output_decisions_path = output_root / "intake_retention_decisions.json"
        curve_provenance_path = output_root / "curve_pack_provenance.json"
        if (
            generated_manifest_path.is_file()
            and output_decisions_path.is_file()
            and curve_provenance_path.is_file()
        ):
            generated_manifest = read_json(generated_manifest_path)
            curve_provenance = read_json(curve_provenance_path)
            selected_per_run_sha = sha256_file(per_run_path)
            selected_decision_sha = sha256_file(decision_path)
            output_decision_sha = sha256_file(output_decisions_path)
            binding_checks = {
                "generated_manifest_binds_per_run": generated_manifest.get(
                    "per_run_full_precision.json"
                )
                == selected_per_run_sha,
                "generated_manifest_binds_output_decisions": generated_manifest.get(
                    "intake_retention_decisions.json"
                )
                == output_decision_sha,
                "output_decisions_equal_selected_canonical_decisions": (
                    output_decision_sha == selected_decision_sha
                ),
                "curve_provenance_commit_exact": curve_provenance.get("repo_commit")
                == EXPECTED_COMMIT,
            }
            artifact_bindings = {
                "status": "pass" if all(binding_checks.values()) else "fail",
                "checks": binding_checks,
                "output_root": str(output_root),
                "generated_manifest": {
                    "path": str(generated_manifest_path),
                    "sha256": sha256_file(generated_manifest_path),
                },
                "per_run_sha256": selected_per_run_sha,
                "selected_canonical_decisions_sha256": selected_decision_sha,
                "output_decisions_sha256": output_decision_sha,
                "curve_pack_provenance": {
                    "path": str(curve_provenance_path),
                    "sha256": sha256_file(curve_provenance_path),
                    "repo_commit": curve_provenance.get("repo_commit"),
                    "evidence_epoch_hash": curve_provenance.get(
                        "evidence_epoch_hash"
                    ),
                },
            }

    statuses = [
        manifest_comparison["status"],
        decision_comparison["status"],
        per_run_comparison["status"],
        artifact_bindings["status"],
    ]
    overall = "pass" if statuses == ["pass", "pass", "pass", "pass"] else (
        "fail" if "fail" in statuses else "not_ready"
    )
    max_deltas = [
        value
        for value in (
            decision_comparison.get("max_scalar_delta"),
            per_run_comparison.get("max_scalar_delta"),
        )
        if value is not None
    ]
    return {
        "status": overall,
        "dataset_manifest": manifest_comparison,
        "retained_run_decisions": decision_comparison,
        "per_run_full_precision": per_run_comparison,
        "artifact_bindings": artifact_bindings,
        "max_scalar_delta": max(max_deltas) if max_deltas else None,
        "numeric_tolerance": NUMERIC_TOLERANCE,
    }


def write_run_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "test_id",
        "set",
        "measurement_cohort_id",
        "raw_path",
        "sha256",
        "git_blob_oid",
        "acquisition_id",
        "individually_acceptable",
        "matches_replicate_band",
        "retained",
        "cohort_status",
        "ramp_review_required",
        "effective_speed_mm_s",
        "collapse_local_speed_mm_s",
        "interval_median_ms",
        "timing_gap_count",
        *METRIC_FIELDS,
        *AUDIT_FIELDS,
        "quality_flags",
        "speed_flags",
        "integrity_failures",
        "protocol_failures",
        "decision_reasons",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for source in rows:
        row = {field: source.get(field) for field in fields}
        for field in (
            "quality_flags",
            "speed_flags",
            "integrity_failures",
            "protocol_failures",
            "decision_reasons",
        ):
            row[field] = ";".join(source.get(field) or [])
        writer.writerow(row)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="\n")


def write_cohort_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "test_id",
        "set",
        "measurement_cohort_id",
        "candidate_count",
        "individually_acceptable_count",
        "preliminary_matching_count",
        "retained_count",
        "status",
        "center_collapse_force_gf",
        "center_collapse_position_mm",
        "collapse_force_tolerance_gf",
        "collapse_position_tolerance_mm",
        "minimum_retained_runs",
        "minimum_retained_runs_pass",
        "numeric_retained_ramp_count",
        "retained_median_ramp_gf_per_mm",
        "ramp_review_count",
        "mixed_cohort",
    ]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for source in rows:
        row = {field: source.get(field) for field in fields}
        row["mixed_cohort"] = (
            "" if source.get("mixed_cohort") is None else json.dumps(source["mixed_cohort"], sort_keys=True)
        )
        writer.writerow(row)
    path.write_text(buffer.getvalue(), encoding="utf-8", newline="\n")


def markdown_report(result: dict[str, Any]) -> str:
    identity = result["importer_release_identity"]
    raw = result["raw_inputs"]
    fleet = result["fleet_audit"]
    generator = result["generator_comparison"]
    stability = result["repo_and_cache_stability"]
    retest = result["predecessor_epoch_retest_impact"]
    counts = fleet["counts"]
    lines = [
        "# Independent test-imp 1.1.4 epoch audit",
        "",
        f"Overall result: **{result['result']}**",
        "",
        "This audit imports the hash-verified final `test_imp` 1.1.4 source directly. "
        "It does not reimplement intake rules and does not modify the raw cache, Git repository, "
        "generator configuration, or viewer code.",
        "",
        "## Identity and raw evidence",
        "",
        f"- Frozen commit: `{EXPECTED_COMMIT}`",
        f"- test-imp identity: `{result['importer_source_identity']['application_version']}` / "
        f"`{result['importer_source_identity']['metrics_version']}` / "
        f"`{result['importer_source_identity']['policy_version']}`",
        f"- Executable SHA-256: `{identity['executable']['sha256']}`",
        f"- Release ZIP SHA-256: `{identity['zip']['sha256']}`",
        f"- Source manifest SHA-256: `{identity['source_manifest']['sha256']}` "
        f"({identity['source_manifest']['entry_count']} checked entries)",
        f"- Release manifest SHA-256: `{identity['release_manifest']['sha256']}` "
        f"({identity['release_manifest']['entry_count']} checked entries)",
        f"- Raw semantic paths: {raw['counts']['manifest_semantic_paths']}",
        f"- Unique physical acquisitions: {raw['counts']['unique_acquisitions']}",
        f"- Byte-identical alias acquisitions: {raw['counts']['alias_acquisitions']}",
        f"- Full materialized Git snapshot: {raw['counts']['full_cache_files']} files, tree SHA-256 "
        f"`{raw['full_cache_identity']['tree_sha256']}`",
        f"- Live repository stable and clean during audit: {stability['all_checks_pass']}",
        "",
        "The four aliases are the same four Topre acquisitions under two separate semantic "
        "records (`Topre_HHKB_Pro2_45g` and `Topre_Slider_Black`). They remain separate "
        "interpretations but count as four—not eight—independent observations.",
        "",
        "## Intake outcome",
        "",
        f"- Semantic cohorts: {counts['semantic_cohorts']} (independent measurement cohorts: "
        f"{counts['independent_measurement_cohorts']})",
        f"- Individually acceptable paths: {counts['individually_acceptable_semantic_paths']} / "
        f"{counts['semantic_paths']}",
        f"- Retained paths after Fc/xc rules: {counts['retained_semantic_paths']} / "
        f"{counts['semantic_paths']}",
        f"- Omitted for individual failure: {counts['omitted_failed_semantic_paths']}",
        f"- Omitted as Fc/xc outlier: {counts['omitted_outlier_semantic_paths']}",
        f"- Mixed-population stops: {counts['mixed_cohorts']}",
        f"- Minimum-two failures: {counts['minimum_two_fail_cohorts']}",
        f"- Preferred-speed advisory paths: {counts['preferred_speed_flag_semantic_paths']}",
        f"- Hard protocol-failure paths: {counts['hard_protocol_failure_semantic_paths']}",
        f"- RAMP review paths: {counts['ramp_review_semantic_paths']} semantic / "
        f"{counts['ramp_review_unique_acquisitions']} independent",
        f"- Metric-local-null paths: {counts['metric_local_null_semantic_paths']}",
        "",
        "## Generator comparison",
        "",
        f"- Status: **{generator['status']}**",
        f"- Dataset manifest: {generator['dataset_manifest']['status']}",
        f"- Retained-run decisions: {generator['retained_run_decisions']['status']}",
        f"- Per-run full-precision evidence: {generator['per_run_full_precision']['status']}",
        f"- Generated-manifest/decision/provenance bindings: {generator['artifact_bindings']['status']}",
        f"- Maximum scalar delta: {generator['max_scalar_delta']}",
        f"- Numeric tolerance: {generator['numeric_tolerance']}",
        "",
    ]
    impact_lines = [
        "## Predecessor-epoch Topre R2 45g retest impact",
        "",
        "This is a descriptive epoch-to-epoch comparison, not a QC failure and not a "
        "claim about why the measurements changed.",
        "",
        f"- Predecessor: `{retest['predecessor']['repo_commit']}` with "
        f"{retest['predecessor']['retained_count']} retained runs",
        f"- Candidate: `{retest['candidate']['repo_commit']}` with "
        f"{retest['candidate']['retained_count']} retained runs",
        f"- Retained-membership delta: {retest['membership']['retained_count_delta']}",
        f"- Retired path: {', '.join(retest['membership']['retired_paths']) or 'none'}",
        f"- Same-path replacement blobs: {len(retest['membership']['replaced_paths'])}",
        f"- Candidate RAMP values: "
        f"{retest['ramp_review_context']['candidate']['values_gf_per_mm']} gf/mm",
        f"- Formal RAMP review evaluated: "
        f"{retest['ramp_review_context']['candidate']['formal_rule_evaluated']} "
        f"(requires {retest['ramp_review_context']['minimum_numeric_retained_runs']} "
        "numeric retained runs; this two-run cohort therefore cannot emit that advisory)",
        "",
        "| Metric | Predecessor | Candidate | Absolute delta | Relative delta |",
        "|---|---:|---:|---:|---:|",
    ]
    for field in METRIC_FIELDS:
        values = retest["metrics"][field]
        relative = values["relative_delta_pct"]
        impact_lines.append(
            f"| `{field}` | {values['predecessor']!r} | {values['candidate']!r} | "
            f"{values['absolute_delta']!r} | "
            f"{'n/a' if relative is None else f'{relative:.6f}%'} |"
        )
    impact_lines.extend(
        [
            "",
            "The two candidate runs agree with each other under the importer replicate rules. "
            "The table intentionally preserves the material predecessor-to-candidate shifts; "
            "those shifts do not alter the importer decision.",
            "",
        ]
    )
    generator_heading_index = lines.index("## Generator comparison")
    lines[generator_heading_index:generator_heading_index] = impact_lines
    if generator["status"] == "not_ready":
        lines.extend(
            [
                "The independent importer result is complete. The generator comparison is marked "
                "`not_ready` until the generator manifest, retained decisions, and per-run evidence "
                "all target this frozen commit and expose the exact 184 semantic path keys. Rerun this "
                "same script after generation; it will select only commit/path-exact artifacts.",
                "",
            ]
        )
    mismatches = (
        raw["path_mismatches"]
        + raw["content_mismatches"]
        + raw["registry_mismatches"]
        + generator["dataset_manifest"].get("mismatches", [])
        + generator["retained_run_decisions"].get("mismatches", [])
        + generator["per_run_full_precision"].get("mismatches", [])
    )
    lines.extend(
        [
            "## Mismatch summary",
            "",
            f"- Total reported mismatches: {len(mismatches)}",
            "",
            "Detailed path-, hash-, decision-, metric-, cohort-, and alias-level evidence is in "
            "`test_imp_1_1_4_epoch_audit.json`; compact run and cohort tables are in the adjacent CSV files.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    script_path = Path(__file__).resolve()
    validation_dir = script_path.parent
    epoch_inputs = validation_dir.parent
    work_root = epoch_inputs.parent
    default_importer = work_root.parent / "test-imp-v1.1-work"

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--importer-root", type=Path, default=default_importer)
    parser.add_argument("--json", type=Path, default=validation_dir / "test_imp_1_1_4_epoch_audit.json")
    parser.add_argument("--runs-csv", type=Path, default=validation_dir / "test_imp_1_1_4_per_run.csv")
    parser.add_argument("--cohorts-csv", type=Path, default=validation_dir / "test_imp_1_1_4_per_cohort.csv")
    parser.add_argument("--markdown", type=Path, default=validation_dir / "test_imp_1_1_4_epoch_audit.md")
    args = parser.parse_args(argv)

    manifest_path = epoch_inputs / "manifest" / "dataset_manifest.step2.json"
    manifest = read_json(manifest_path)
    materialization_path = validation_dir / "raw_cache_materialization.json"
    materialization = read_json(materialization_path)
    live_repo = Path(materialization["repo_path"])
    repo_before = live_repo_snapshot(live_repo)
    release = release_identity(args.importer_root.resolve())
    assess_cohort, importer_config, source_identity = import_final_source(
        args.importer_root.resolve()
    )
    raw_root, raw_audit = verify_raw_inputs(epoch_inputs, work_root, manifest)
    fleet = assess_fleet(
        manifest, raw_root, assess_cohort, importer_config
    )
    retest_impact = predecessor_retest_impact(
        work_root, fleet, importer_config
    )
    generator = compare_generator(work_root, manifest, fleet)
    cache_after = full_cache_tree_identity(raw_root)
    repo_after = live_repo_snapshot(live_repo)
    stability_checks = {
        "live_repo_commands_ok": repo_before["commands_ok"] and repo_after["commands_ok"],
        "live_repo_head_exact_before": repo_before["head"] == EXPECTED_COMMIT,
        "live_repo_head_exact_after": repo_after["head"] == EXPECTED_COMMIT,
        "live_repo_stable_during_audit": repo_before == repo_after,
        "live_repo_clean_before": not repo_before["status_porcelain_v1"],
        "live_repo_clean_after": not repo_after["status_porcelain_v1"],
        "live_repo_synced_to_local_upstream_before": repo_before["upstream_counts"]
        == {"ahead": 0, "behind": 0},
        "live_repo_synced_to_local_upstream_after": repo_after["upstream_counts"]
        == {"ahead": 0, "behind": 0},
        "raw_cache_stable_during_audit": (
            raw_audit["full_cache_identity"]["file_count"] == cache_after["file_count"]
            and raw_audit["full_cache_identity"]["tree_sha256"]
            == cache_after["tree_sha256"]
        ),
    }
    stability = {
        "checks": stability_checks,
        "all_checks_pass": all(stability_checks.values()),
        "live_repo_before": repo_before,
        "live_repo_after": repo_after,
        "raw_cache_before": raw_audit["full_cache_identity"],
        "raw_cache_after": {
            "file_count": cache_after["file_count"],
            "tree_sha256": cache_after["tree_sha256"],
        },
    }

    base_pass = (
        release["all_checks_pass"]
        and raw_audit["all_checks_pass"]
        and fleet["all_structural_checks_pass"]
        and retest_impact["all_checks_pass"]
        and stability["all_checks_pass"]
    )
    if not base_pass or generator["status"] == "fail":
        overall = "FAIL"
    elif generator["status"] == "pass":
        overall = "PASS"
    else:
        overall = "PASS_IMPORTER_GENERATOR_PENDING"

    result = {
        "audit_schema_version": 2,
        "result": overall,
        "epoch_id": manifest.get("epoch_id"),
        "repo_commit": manifest.get("repo_commit"),
        "script": {
            "path": str(script_path),
            "sha256": sha256_file(script_path),
            "python": sys.version,
        },
        "inputs": {
            "dataset_manifest": {
                "path": str(manifest_path),
                "sha256": sha256_file(manifest_path),
            },
            "raw_root": str(raw_root),
            "importer_root": str(args.importer_root.resolve()),
        },
        "importer_source_identity": source_identity,
        "importer_release_identity": release,
        "raw_inputs": raw_audit,
        "repo_and_cache_stability": stability,
        "fleet_audit": fleet,
        "predecessor_epoch_retest_impact": retest_impact,
        "generator_comparison": generator,
    }
    write_json(args.json, result)
    write_run_csv(args.runs_csv, fleet["runs"])
    write_cohort_csv(args.cohorts_csv, fleet["cohorts"])
    args.markdown.write_text(markdown_report(result), encoding="utf-8", newline="\n")

    print(
        json.dumps(
            {
                "result": overall,
                "counts": fleet["counts"],
                "generator_status": generator["status"],
                "max_scalar_delta": generator["max_scalar_delta"],
                "reports": {
                    "json": str(args.json),
                    "runs_csv": str(args.runs_csv),
                    "cohorts_csv": str(args.cohorts_csv),
                    "markdown": str(args.markdown),
                },
            },
            indent=2,
        )
    )
    return 0 if overall != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
