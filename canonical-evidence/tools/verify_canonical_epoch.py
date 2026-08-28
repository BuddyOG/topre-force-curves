#!/usr/bin/env python3
"""Fail-closed verifier for the frozen Step-2 canonical evidence epoch.

This verifier intentionally uses only the Python standard library.  It does not
consult Git, the live repository, Excel, the importer executable, or any network
resource.  All checks are performed against the sealed package bytes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from typing import Any, Iterable
import zipfile


EXPECTED_PACKAGE_ID = "canonical-evidence-epoch-6e86ac19-step2"
EXPECTED_EPOCH_ID = "canonical-evidence-2026-08-15-6e86ac19"
EXPECTED_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
EXPECTED_TREE = "e43d25a3fed8c5177467bba96a5abbdd5a3442b0"
EXPECTED_WORKBOOK_SHA256 = (
    "02e85a2fbdc8e025f1445ab8cb7bd830501f755b79d0a755d6ee31e53bca45a4"
)
EXPECTED_EVIDENCE_EPOCH_HASH = (
    "7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a"
)
EXPECTED_INPUT_SHA256SUMS_SHA256 = (
    "a6c2a5dcf4f6fdc5d518309536fe29d317ae1884cea0ca7a2c512ba0e905fb46"
)
EXPECTED_DECISIONS_SHA256 = (
    "e6d438b672408cd3e711d907e58424af1f73c13650674526900ce24ceeea9bf4"
)
EXPECTED_GENERATED_MANIFEST_SHA256 = (
    "b50d04604e639e19e9ace5ccc5426ceb9deffe75768a34ff61838dfc1a1c880c"
)
EXPECTED_WORKBOOK_SNAPSHOT_SHA256 = (
    "fee2cc5b217e8ce2600d5e8d778f6dc5eca2abbe15d93a4f983b316ca6e940ea"
)
EXPECTED_IMPORTER_ZIP_SHA256 = (
    "b1ccdaba5c4ec76b7a8516c4e8c8109c26f2cb58b0f60f49a5c5fcf9a031b284"
)
EXPECTED_IMPORTER_ZIP_BYTES = 8_283_858
EXPECTED_IMPORTER_EXE_SHA256 = (
    "351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e"
)
EXPECTED_IMPORTER_SOURCE_MANIFEST_SHA256 = (
    "0cc31a5a4ac68108377384337d1fba662ac5c22fb9c14ee37ecc75dba74d21dd"
)
EXPECTED_IMPORTER_SOURCE_MANIFEST_BYTES = 2_704
EXPECTED_CACHE_DIRECTORY = f"repo-{EXPECTED_COMMIT}"

EXPECTED_COUNTS = {
    "repository_paths": 189,
    "raw_paths": 184,
    "unique_acquisitions": 180,
    "semantic_records": 76,
    "independent_measurement_cohorts": 75,
    "workbook_rows": 79,
    "workbook_tested_yes": 65,
    "workbook_tested_no": 14,
    "legacy_metadata_records": 11,
    "historically_pruned_runs": 9,
    "shared_evidence_alias_groups": 1,
    "curve_packs": 76,
}

REQUIRED_IMPORTER_VALIDATION_FILES = {
    "epoch_inputs/validation/audit_test_imp_1_1_4.py",
    "epoch_inputs/validation/test_imp_1_1_4_epoch_audit.json",
    "epoch_inputs/validation/test_imp_1_1_4_epoch_audit.md",
    "epoch_inputs/validation/test_imp_1_1_4_per_cohort.csv",
    "epoch_inputs/validation/test_imp_1_1_4_per_run.csv",
}

REQUIRED_ACCEPTANCE_FILES = {
    "acceptance/EPOCH_ACCEPTANCE.json",
    "acceptance/EPOCH_ACCEPTANCE.md",
    "acceptance/FRESH_WORKBOOK_SNAPSHOT.json",
    "acceptance/TEST_RESULTS.json",
    "acceptance/GIT_TREE_AUDIT.json",
}

REQUIRED_AUTHORITY_FILES = {
    "authority/test-imp-1.1.4-windows-x64.zip",
    "authority/SOURCE-SHA256SUMS-1.1.4.txt",
}

REQUIRED_ACTIVE_REGISTRIES = {
    "generator/domelab_pipeline/config/exclusions.json",
    "generator/domelab_pipeline/config/review_register.json",
    "generator/domelab_pipeline/config/adjudications.json",
}

EVIDENCE_ROOT = "evidence"
RAW_CACHE_ROOT = f"raw_cache/{EXPECTED_CACHE_DIRECTORY}"


class VerificationError(RuntimeError):
    """Raised when a required artifact cannot be parsed safely."""


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []

    def check(self, name: str, condition: bool, detail: Any = None) -> bool:
        item: dict[str, Any] = {
            "name": name,
            "status": "PASS" if bool(condition) else "FAIL",
        }
        if detail is not None:
            item["detail"] = detail
        self.checks.append(item)
        return bool(condition)

    def fail(self, name: str, detail: Any = None) -> None:
        self.check(name, False, detail)

    @property
    def passed(self) -> bool:
        return all(item["status"] == "PASS" for item in self.checks)

    def report(self, package_root: Path) -> dict[str, Any]:
        failed = [item for item in self.checks if item["status"] == "FAIL"]
        return {
            "verifier": "canonical-evidence-epoch-verifier-v1",
            "package_root": str(package_root),
            "package_id": EXPECTED_PACKAGE_ID,
            "repo_commit": EXPECTED_COMMIT,
            "repo_tree": EXPECTED_TREE,
            "status": "PASS" if not failed else "FAIL",
            "check_count": len(self.checks),
            "failure_count": len(failed),
            "checks": self.checks,
        }


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, VerificationError) as exc:
        raise VerificationError(f"cannot parse JSON {path}: {exc}") from exc


def load_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        fields = list(reader.fieldnames or [])
        if not fields or len(fields) != len(set(fields)) or any(not f for f in fields):
            raise VerificationError(f"invalid or duplicate CSV header in {path}")
        rows = list(reader)
        if any(None in row for row in rows):
            raise VerificationError(f"ragged CSV row in {path}")
        return fields, rows
    except (OSError, UnicodeError, csv.Error, VerificationError) as exc:
        raise VerificationError(f"cannot parse CSV {path}: {exc}") from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_oid(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 -- Git SHA-1 identity


def _is_reparse_point(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & reparse_flag)


def validate_relpath(raw: str, *, label: str = "path") -> str:
    if not isinstance(raw, str) or not raw:
        raise VerificationError(f"{label} must be a non-empty string")
    if "\\" in raw or "\x00" in raw:
        raise VerificationError(f"unsafe {label}: {raw!r}")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or pure.drive or raw != pure.as_posix():
        raise VerificationError(f"non-canonical {label}: {raw!r}")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise VerificationError(f"unsafe {label}: {raw!r}")
    return raw


def scan_package(root: Path, audit: Audit) -> set[str]:
    files: set[str] = set()
    casefold_paths: dict[str, str] = {}
    stack = [root]
    security_errors: list[str] = []
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            security_errors.append(f"cannot scan {current}: {exc}")
            continue
        for entry in entries:
            path = Path(entry.path)
            try:
                st = entry.stat(follow_symlinks=False)
            except OSError as exc:
                security_errors.append(f"cannot stat {path}: {exc}")
                continue
            rel = path.relative_to(root).as_posix()
            try:
                validate_relpath(rel, label="package path")
            except VerificationError as exc:
                security_errors.append(str(exc))
                continue
            if entry.is_symlink() or stat.S_ISLNK(st.st_mode) or _is_reparse_point(st):
                security_errors.append(f"symlink/junction/reparse point forbidden: {rel}")
                continue
            if stat.S_ISDIR(st.st_mode):
                stack.append(path)
            elif stat.S_ISREG(st.st_mode):
                folded = rel.casefold()
                prior = casefold_paths.get(folded)
                if prior is not None and prior != rel:
                    security_errors.append(
                        f"case-insensitive path collision: {prior!r} and {rel!r}"
                    )
                casefold_paths[folded] = rel
                files.add(rel)
            else:
                security_errors.append(f"non-regular filesystem entry forbidden: {rel}")
    audit.check(
        "filesystem contains no symlinks, junctions, reparse points, path collisions, or special files",
        not security_errors,
        security_errors or {"regular_file_count": len(files)},
    )
    return files


def verify_sha256_inventory(root: Path, actual_files: set[str], audit: Audit) -> None:
    index_path = root / "SHA256SUMS.csv"
    try:
        fields, rows = load_csv(index_path)
    except VerificationError as exc:
        audit.fail("top-level SHA256SUMS.csv parses", str(exc))
        return
    audit.check(
        "SHA256SUMS.csv has exact schema",
        fields == ["path", "bytes", "sha256"],
        fields,
    )
    parsed: dict[str, tuple[int, str]] = {}
    errors: list[str] = []
    row_paths: list[str] = []
    for number, row in enumerate(rows, start=2):
        try:
            rel = validate_relpath(row.get("path", ""), label="checksum path")
            size = int(row.get("bytes", ""))
            digest = row.get("sha256", "").lower()
            if size < 0 or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                raise ValueError("invalid size or SHA-256")
            if rel == "SHA256SUMS.csv":
                raise ValueError("checksum file cannot self-hash")
            if rel in parsed:
                raise ValueError("duplicate path")
            parsed[rel] = (size, digest)
            row_paths.append(rel)
        except (ValueError, VerificationError) as exc:
            errors.append(f"row {number}: {exc}")
    audit.check("SHA256SUMS.csv rows are safe and unique", not errors, errors or len(parsed))
    audit.check(
        "SHA256SUMS.csv is byte-path sorted",
        row_paths == sorted(row_paths, key=lambda value: value.encode("utf-8")),
    )
    expected_files = actual_files - {"SHA256SUMS.csv"}
    audit.check(
        "SHA256SUMS.csv has exact package coverage (no missing or extra files)",
        set(parsed) == expected_files,
        {
            "missing": sorted(expected_files - set(parsed)),
            "extra": sorted(set(parsed) - expected_files),
            "indexed": len(parsed),
        },
    )
    mismatches: list[dict[str, Any]] = []
    for rel, (expected_size, expected_sha) in parsed.items():
        path = root / Path(*PurePosixPath(rel).parts)
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root.resolve(strict=True))
            actual_size = path.stat().st_size
            actual_sha = sha256_file(path)
            if actual_size != expected_size or actual_sha != expected_sha:
                mismatches.append(
                    {
                        "path": rel,
                        "expected_bytes": expected_size,
                        "actual_bytes": actual_size,
                        "expected_sha256": expected_sha,
                        "actual_sha256": actual_sha,
                    }
                )
        except (OSError, ValueError) as exc:
            mismatches.append({"path": rel, "error": str(exc)})
    audit.check(
        "every indexed package file matches byte count and SHA-256",
        not mismatches,
        mismatches or {"verified_files": len(parsed)},
    )


def require_paths(root: Path, paths: Iterable[str], audit: Audit, name: str) -> None:
    missing = sorted(rel for rel in paths if not (root / Path(*PurePosixPath(rel).parts)).is_file())
    audit.check(name, not missing, {"missing": missing})


def _load_json_checked(root: Path, rel: str, audit: Audit) -> Any | None:
    path = root / Path(*PurePosixPath(rel).parts)
    try:
        return load_json(path)
    except VerificationError as exc:
        audit.fail(f"{rel} parses as duplicate-key-free JSON", str(exc))
        return None


def _load_csv_checked(
    root: Path, rel: str, audit: Audit
) -> tuple[list[str], list[dict[str, str]]] | None:
    path = root / Path(*PurePosixPath(rel).parts)
    try:
        return load_csv(path)
    except VerificationError as exc:
        audit.fail(f"{rel} parses as a rectangular CSV", str(exc))
        return None


def bool_csv(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered not in {"true", "false"}:
        raise VerificationError(f"invalid CSV boolean: {value!r}")
    return lowered == "true"


def _unique_by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = row.get(key)
        if not isinstance(value, str) or not value or value in result:
            raise VerificationError(f"missing/duplicate {key}: {value!r}")
        result[value] = row
    return result


def git_tree_oid(rows: list[dict[str, str]]) -> str:
    root: dict[str, Any] = {}
    for row in rows:
        rel = validate_relpath(row["path"], label="Git inventory path")
        parts = list(PurePosixPath(rel).parts)
        node = root
        for part in parts[:-1]:
            existing = node.get(part)
            if existing is None:
                existing = {"__kind__": "tree", "__children__": {}}
                node[part] = existing
            if existing.get("__kind__") != "tree":
                raise VerificationError(f"Git path prefix collision at {rel!r}")
            node = existing["__children__"]
        leaf = parts[-1]
        if leaf in node:
            raise VerificationError(f"duplicate Git inventory path: {rel!r}")
        mode = row.get("mode", "")
        oid = row.get("git_blob_oid", "").lower()
        if mode not in {"100644", "100755", "120000"}:
            raise VerificationError(f"unsupported Git mode {mode!r} for {rel!r}")
        if len(oid) != 40 or any(c not in "0123456789abcdef" for c in oid):
            raise VerificationError(f"invalid blob OID for {rel!r}")
        node[leaf] = {"__kind__": "blob", "mode": mode, "oid": oid}

    def encode_tree(children: dict[str, Any]) -> str:
        materialized: list[tuple[str, bool, str, str]] = []
        for name, item in children.items():
            name_bytes = name.encode("utf-8")
            if b"/" in name_bytes or b"\x00" in name_bytes:
                raise VerificationError(f"invalid Git tree entry name: {name!r}")
            if item["__kind__"] == "tree":
                oid = encode_tree(item["__children__"])
                materialized.append((name, True, "40000", oid))
            else:
                materialized.append((name, False, item["mode"], item["oid"]))
        materialized.sort(
            key=lambda item: item[0].encode("utf-8") + (b"/" if item[1] else b"")
        )
        payload = b"".join(
            mode.encode("ascii")
            + b" "
            + name.encode("utf-8")
            + b"\x00"
            + bytes.fromhex(oid)
            for name, _is_tree, mode, oid in materialized
        )
        header = f"tree {len(payload)}\0".encode("ascii")
        return hashlib.sha1(header + payload).hexdigest()  # noqa: S324 -- Git identity

    return encode_tree(root)


def verify_manifest_identity(root: Path, manifest: Any, audit: Audit) -> None:
    if not isinstance(manifest, dict):
        audit.fail("EPOCH_MANIFEST.json is an object")
        return
    audit.check("package identity is pinned", manifest.get("package_id") == EXPECTED_PACKAGE_ID)
    audit.check("package manifest version is 1", manifest.get("manifest_version") == 1)
    repo = manifest.get("frozen_repository", {})
    audit.check("frozen commit is pinned", repo.get("commit_oid") == EXPECTED_COMMIT)
    audit.check("frozen Git tree is pinned", repo.get("tree_oid") == EXPECTED_TREE)
    audit.check("Git object format is SHA-1", repo.get("git_object_format") == "sha1")
    audit.check("raw cache root is pinned", repo.get("cache_root") == RAW_CACHE_ROOT)
    scope = manifest.get("scope", {})
    audit.check("package scope stops after Step 2", scope.get("completed_step") == 2)
    audit.check(
        "Step 3 is explicitly deferred and not executed",
        scope.get("step3_status") == "deferred_not_executed"
        and scope.get("force_curve_bench_release_eligible") is False,
    )
    counts = manifest.get("expected_counts", {})
    audit.check("package pins all canonical counts", counts == EXPECTED_COUNTS, counts)
    identity = manifest.get("identity", {})
    audit.check(
        "package pins workbook SHA-256",
        identity.get("workbook_sha256") == EXPECTED_WORKBOOK_SHA256,
    )
    audit.check(
        "package pins presentation-independent evidence epoch hash",
        identity.get("evidence_epoch_hash") == EXPECTED_EVIDENCE_EPOCH_HASH,
    )
    audit.check(
        "package pins input and generated membership manifests",
        identity.get("epoch_inputs_sha256sums_sha256")
        == EXPECTED_INPUT_SHA256SUMS_SHA256
        and identity.get("retained_decisions_sha256") == EXPECTED_DECISIONS_SHA256
        and identity.get("generated_manifest_sha256") == EXPECTED_GENERATED_MANIFEST_SHA256,
    )
    importer = manifest.get("intake_authority", {})
    audit.check(
        "package pins test-imp 1.1.4 Windows authority",
        importer.get("application_version") == "1.1.4"
        and importer.get("policy_version") == "intake-qc-v1.4"
        and importer.get("metrics_version") == "metrics-v4.2"
        and importer.get("zip_path") == "authority/test-imp-1.1.4-windows-x64.zip"
        and importer.get("zip_bytes") == EXPECTED_IMPORTER_ZIP_BYTES
        and importer.get("zip_sha256") == EXPECTED_IMPORTER_ZIP_SHA256
        and importer.get("source_manifest_path")
        == "authority/SOURCE-SHA256SUMS-1.1.4.txt"
        and importer.get("source_manifest_bytes") == EXPECTED_IMPORTER_SOURCE_MANIFEST_BYTES
        and importer.get("source_manifest_sha256")
        == EXPECTED_IMPORTER_SOURCE_MANIFEST_SHA256,
    )


def verify_repository_cache(root: Path, manifest: Any, audit: Audit) -> dict[str, dict[str, str]]:
    repo_prov = _load_json_checked(root, "epoch_inputs/manifest/repo_provenance.json", audit)
    repo_csv = _load_csv_checked(
        root, "epoch_inputs/manifest/repository_file_inventory.csv", audit
    )
    raw_json = _load_json_checked(root, "epoch_inputs/manifest/raw_file_inventory.json", audit)
    raw_csv = _load_csv_checked(root, "epoch_inputs/manifest/raw_file_inventory.csv", audit)
    if not all(item is not None for item in (repo_prov, repo_csv, raw_json, raw_csv)):
        return {}
    _repo_fields, repo_rows = repo_csv  # type: ignore[misc]
    _raw_fields, raw_csv_rows = raw_csv  # type: ignore[misc]
    raw_rows = raw_json.get("files", []) if isinstance(raw_json, dict) else []
    audit.check("repository inventory contains 189 paths", len(repo_rows) == 189, len(repo_rows))
    audit.check("raw JSON inventory contains 184 paths", len(raw_rows) == 184, len(raw_rows))
    audit.check("raw CSV inventory contains 184 paths", len(raw_csv_rows) == 184, len(raw_csv_rows))
    commit_values = {
        repo_prov.get("sha") if isinstance(repo_prov, dict) else None,
        raw_json.get("repo_commit") if isinstance(raw_json, dict) else None,
        manifest.get("frozen_repository", {}).get("commit_oid") if isinstance(manifest, dict) else None,
    }
    audit.check("repository inputs bind to one frozen commit", commit_values == {EXPECTED_COMMIT})
    try:
        repo_by_path = _unique_by(repo_rows, "path")
        raw_by_path = _unique_by(raw_rows, "path")
        raw_csv_by_path = _unique_by(raw_csv_rows, "path")
    except VerificationError as exc:
        audit.fail("repository/raw inventories have unique paths", str(exc))
        return {}
    csv_subset = {
        path
        for path, row in repo_by_path.items()
        if str(row.get("is_raw_csv", "")).strip().lower() == "true"
    }
    audit.check("raw inventory is exact raw-CSV subset", set(raw_by_path) == csv_subset)
    audit.check("raw JSON and CSV inventories have identical paths", set(raw_csv_by_path) == set(raw_by_path))
    inventory_mismatches: list[Any] = []
    raw_field_names = [
        "path",
        "set",
        "bytes",
        "sha256",
        "git_blob_oid",
        "git_object_format",
        "category",
        "mode",
        "git_object_type",
        "acquisition_id",
        "evidence_group_id",
    ]
    for path, raw in raw_by_path.items():
        csv_row = raw_csv_by_path.get(path, {})
        repo_row = repo_by_path.get(path, {})
        for field in raw_field_names:
            raw_value = raw.get(field)
            if field == "bytes":
                raw_value = str(raw_value)
            if str(csv_row.get(field, "")) != str(raw_value):
                inventory_mismatches.append([path, f"raw_json_vs_csv:{field}"])
        for field in ("bytes", "sha256", "git_blob_oid", "mode", "acquisition_id", "evidence_group_id"):
            if str(repo_row.get(field, "")) != str(raw.get(field, "")):
                inventory_mismatches.append([path, f"repository_vs_raw:{field}"])
    audit.check(
        "repository/raw JSON/raw CSV identity fields close exactly",
        not inventory_mismatches,
        inventory_mismatches[:25],
    )
    raw_cache_root = root / "raw_cache"
    raw_cache_entries: list[str] = []
    expected_cache_is_directory = False
    if raw_cache_root.is_dir():
        raw_cache_entries = sorted(path.name for path in raw_cache_root.iterdir())
        expected_cache_is_directory = (raw_cache_root / EXPECTED_CACHE_DIRECTORY).is_dir()
    audit.check(
        "raw_cache contains exactly the single frozen cache directory",
        raw_cache_entries == [EXPECTED_CACHE_DIRECTORY] and expected_cache_is_directory,
        {
            "expected": [EXPECTED_CACHE_DIRECTORY],
            "actual": raw_cache_entries,
            "expected_entry_is_directory": expected_cache_is_directory,
        },
    )
    cache_root = raw_cache_root / EXPECTED_CACHE_DIRECTORY
    actual_cache: set[str] = set()
    if cache_root.is_dir():
        for path in cache_root.rglob("*"):
            if path.is_file():
                actual_cache.add(path.relative_to(cache_root).as_posix())
    audit.check(
        "raw cache has exact 189-path repository inventory",
        actual_cache == set(repo_by_path),
        {
            "missing": sorted(set(repo_by_path) - actual_cache),
            "extra": sorted(actual_cache - set(repo_by_path)),
        },
    )
    byte_errors: list[Any] = []
    total_bytes = 0
    for rel, row in repo_by_path.items():
        try:
            validate_relpath(rel, label="repository path")
            path = cache_root / Path(*PurePosixPath(rel).parts)
            data = path.read_bytes()
            total_bytes += len(data)
            actual_sha = sha256_bytes(data)
            actual_oid = git_blob_oid(data)
            if (
                len(data) != int(row["bytes"])
                or actual_sha != row["sha256"].lower()
                or actual_oid != row["git_blob_oid"].lower()
                or row.get("git_object_format") != "sha1"
                or row.get("git_object_type") != "blob"
            ):
                byte_errors.append(
                    {
                        "path": rel,
                        "bytes": [row.get("bytes"), len(data)],
                        "sha256": [row.get("sha256"), actual_sha],
                        "git_blob_oid": [row.get("git_blob_oid"), actual_oid],
                    }
                )
        except (OSError, ValueError, KeyError, VerificationError) as exc:
            byte_errors.append({"path": rel, "error": str(exc)})
    audit.check(
        "all 189 cache files match inventory bytes, SHA-256, and Git blob OID",
        not byte_errors,
        byte_errors[:25] or {"files": len(repo_rows), "bytes": total_bytes},
    )
    try:
        calculated_tree = git_tree_oid(repo_rows)
    except VerificationError as exc:
        calculated_tree = None
        audit.fail("Git root tree can be reconstructed from inventory", str(exc))
    audit.check(
        "reconstructed Git root tree OID matches frozen commit tree",
        calculated_tree == EXPECTED_TREE,
        {"expected": EXPECTED_TREE, "actual": calculated_tree},
    )
    repo_inventory_path = root / "epoch_inputs/manifest/repository_file_inventory.csv"
    raw_inventory_path = root / "epoch_inputs/manifest/raw_file_inventory.csv"
    audit.check(
        "repo provenance binds repository inventory bytes",
        repo_prov.get("repository_file_inventory_sha256") == sha256_file(repo_inventory_path),
    )
    audit.check(
        "repo provenance binds raw inventory bytes",
        repo_prov.get("raw_file_inventory_sha256") == sha256_file(raw_inventory_path),
    )
    return repo_by_path


def verify_epoch_input_inventory(root: Path, audit: Audit) -> None:
    input_root = root / "epoch_inputs"
    index_path = input_root / "SHA256SUMS.csv"
    audit.check(
        "epoch input SHA index has exact frozen identity",
        sha256_file(index_path) == EXPECTED_INPUT_SHA256SUMS_SHA256,
    )
    parsed = _load_csv_checked(root, "epoch_inputs/SHA256SUMS.csv", audit)
    if parsed is None:
        return
    fields, rows = parsed
    audit.check(
        "epoch input SHA index has exact schema",
        fields == ["path", "sha256", "size_bytes"],
        fields,
    )
    declared: dict[str, tuple[str, int]] = {}
    errors: list[Any] = []
    for row in rows:
        try:
            rel = validate_relpath(row.get("path", ""), label="epoch input path")
            digest = row.get("sha256", "").lower()
            size = int(row.get("size_bytes", ""))
            if rel == "SHA256SUMS.csv" or rel in declared:
                raise ValueError("self-reference or duplicate")
            if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or size < 0:
                raise ValueError("invalid SHA-256 or size")
            declared[rel] = (digest, size)
        except (ValueError, VerificationError) as exc:
            errors.append([row, str(exc)])
    actual = {
        path.relative_to(input_root).as_posix()
        for path in input_root.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS.csv"
    }
    audit.check(
        "epoch input SHA index has exact 30-file coverage",
        not errors and len(declared) == 30 and set(declared) == actual,
        errors
        or {"missing": sorted(actual - set(declared)), "extra": sorted(set(declared) - actual)},
    )
    mismatches: list[Any] = []
    for rel, (expected_sha, expected_size) in declared.items():
        path = input_root / Path(*PurePosixPath(rel).parts)
        if path.stat().st_size != expected_size or sha256_file(path) != expected_sha:
            mismatches.append(rel)
    audit.check(
        "all 30 epoch input files match the frozen index",
        not mismatches,
        mismatches or {"verified_files": len(declared)},
    )
    validation = _load_json_checked(root, "epoch_inputs/validation/validation_report.json", audit)
    if isinstance(validation, dict):
        checks = validation.get("checks", {})
        audit.check(
            "epoch input validation report passes every declared gate",
            validation.get("validation_report_version") == 2
            and validation.get("result") == "PASS"
            and validation.get("epoch_id") == EXPECTED_EPOCH_ID
            and isinstance(checks, dict)
            and bool(checks)
            and all(value is True for value in checks.values()),
            {"check_count": len(checks), "failed": sorted(key for key, value in checks.items() if value is not True)},
        )
        seal = validation.get("importer_audit_seal", {})
        seal_errors: list[Any] = []
        artifacts = seal.get("artifacts", []) if isinstance(seal, dict) else []
        expected_artifact_paths = {
            "validation/audit_test_imp_1_1_4.py",
            "validation/test_imp_1_1_4_epoch_audit.json",
            "validation/test_imp_1_1_4_epoch_audit.md",
            "validation/test_imp_1_1_4_per_run.csv",
            "validation/test_imp_1_1_4_per_cohort.csv",
        }
        for item in artifacts:
            rel = item.get("path")
            if rel not in expected_artifact_paths:
                seal_errors.append([rel, "unexpected path"])
                continue
            path = input_root / Path(*PurePosixPath(rel).parts)
            if (
                path.stat().st_size != item.get("size_bytes")
                or sha256_file(path) != item.get("sha256")
            ):
                seal_errors.append([rel, "hash/size mismatch"])
        if {item.get("path") for item in artifacts} != expected_artifact_paths:
            seal_errors.append(["five-file audit coverage"])
        audit.check(
            "validation report binds all five final importer audit artifacts",
            not seal_errors
            and seal.get("result") == "PASS"
            and seal.get("repo_commit") == EXPECTED_COMMIT,
            seal_errors,
        )
        active_seal_value = validation.get("active_registry_and_staging_seal", {})
        active_seal = active_seal_value if isinstance(active_seal_value, dict) else {}
        active_path_map = {
            "source/generator/domelab_pipeline/config/exclusions.json": (
                "generator/domelab_pipeline/config/exclusions.json"
            ),
            "source/generator/domelab_pipeline/config/review_register.json": (
                "generator/domelab_pipeline/config/review_register.json"
            ),
            "source/generator/domelab_pipeline/config/retained_run_decisions.json": (
                "generator/domelab_pipeline/config/retained_run_decisions.json"
            ),
            "epoch_outputs/staging_canonical_6e86ac19/curve_pack_provenance.json": (
                "evidence/curve_pack_provenance.json"
            ),
            "epoch_outputs/staging_canonical_6e86ac19/generated_manifest.json": (
                "evidence/generated_manifest.json"
            ),
        }
        active_errors: list[Any] = []
        active_artifacts = (
            active_seal.get("artifacts", []) if isinstance(active_seal, dict) else []
        )
        for item in active_artifacts:
            source_rel = item.get("path") if isinstance(item, dict) else None
            package_rel = active_path_map.get(source_rel)
            if package_rel is None:
                active_errors.append([source_rel, "unexpected path"])
                continue
            path = root / Path(*PurePosixPath(package_rel).parts)
            try:
                if (
                    path.stat().st_size != item.get("size_bytes")
                    or sha256_file(path) != item.get("sha256")
                ):
                    active_errors.append([source_rel, "hash/size mismatch"])
            except OSError as exc:
                active_errors.append([source_rel, str(exc)])
        decisions = _load_json_checked(root, "evidence/intake_retention_decisions.json", audit)
        if {item.get("path") for item in active_artifacts if isinstance(item, dict)} != set(
            active_path_map
        ):
            active_errors.append(["five-file active registry/staging coverage"])
        audit.check(
            "validation report binds active registries and final evidence staging",
            not active_errors
            and active_seal.get("repo_commit") == EXPECTED_COMMIT
            and active_seal.get("evidence_epoch_hash") == EXPECTED_EVIDENCE_EPOCH_HASH
            and isinstance(decisions, dict)
            and active_seal.get("owner_decision_inputs_hash")
            == decisions.get("owner_decision_inputs_hash"),
            active_errors,
        )


def verify_metadata_and_history(root: Path, audit: Audit) -> None:
    workbook_path = root / "epoch_inputs/source_workbook/untested-domes_v2.xlsx"
    snapshot = _load_json_checked(root, "epoch_inputs/source_workbook/workbook_snapshot.json", audit)
    registry = _load_json_checked(root, "epoch_inputs/metadata/dome_metadata_registry.json", audit)
    dataset = _load_json_checked(root, "epoch_inputs/manifest/dataset_manifest.step2.json", audit)
    staged_registry = _load_json_checked(root, "evidence/metadata_registry.staged.json", audit)
    history = _load_json_checked(root, "epoch_inputs/history/exclusions_and_retests.json", audit)
    staged_history = _load_json_checked(root, "evidence/evidence_history.staged.json", audit)
    input_history = _load_json_checked(root, "epoch_inputs/history/evidence_event_ledger.json", audit)
    try:
        workbook_sha = sha256_file(workbook_path)
        workbook_size = workbook_path.stat().st_size
    except OSError as exc:
        audit.fail("authoritative workbook is readable", str(exc))
        return
    audit.check("authoritative workbook hash is exact", workbook_sha == EXPECTED_WORKBOOK_SHA256)
    if not all(item is not None for item in (snapshot, registry, dataset)):
        return
    source_info = registry.get("source_workbook", {})
    audit.check(
        "metadata registry binds authoritative workbook bytes",
        source_info.get("sha256") == workbook_sha and source_info.get("bytes") == workbook_size,
    )
    try:
        sheet = snapshot["sheets"][0]
        values = sheet["values"]
        header = values[0]
        value_rows = values[1:]
    except (KeyError, IndexError, TypeError) as exc:
        audit.fail("workbook value snapshot has expected table", str(exc))
        return
    expected_columns = [
        "display_name",
        "manufacturer",
        "brand",
        "style",
        "variant",
        "nominal_weight_g",
        "tested",
    ]
    audit.check(
        "workbook snapshot identifies Untested Domes A1:G80",
        snapshot.get("sheet_count") == 1
        and sheet.get("name") == "Untested Domes"
        and sheet.get("used_address") == "A1:G80",
    )
    audit.check("workbook columns are exact", header == expected_columns)
    snapshot_rows = [dict(zip(header, row, strict=True)) for row in value_rows]
    yes_rows = [row for row in snapshot_rows if row.get("tested") == "YES"]
    no_rows = [row for row in snapshot_rows if row.get("tested") == "NO"]
    audit.check("workbook has 79 metadata rows", len(snapshot_rows) == 79)
    audit.check("workbook has 65 tested YES rows", len(yes_rows) == 65)
    audit.check("workbook has 14 tested NO rows", len(no_rows) == 14)
    registry_rows = registry.get("rows", [])
    stripped_registry = [
        {column: row.get(column) for column in expected_columns} for row in registry_rows
    ]
    audit.check(
        "metadata registry is an exact row-for-row workbook transcription",
        stripped_registry == snapshot_rows,
    )
    audit.check("staged metadata registry equals input registry", staged_registry == registry)
    tests = dataset.get("tests", [])
    try:
        tests_by_set = _unique_by(tests, "set")
    except VerificationError as exc:
        audit.fail("dataset has unique semantic set names", str(exc))
        return
    aliases = registry.get("set_name_aliases", {})
    metadata_errors: list[Any] = []
    for row in yes_rows:
        workbook_name = row["display_name"]
        set_name = aliases.get(workbook_name, workbook_name)
        test = tests_by_set.get(set_name)
        if not test:
            metadata_errors.append([workbook_name, "missing tested dataset record"])
            continue
        metadata = test.get("metadata", {})
        for field in expected_columns:
            expected = True if field == "tested" else row[field]
            if metadata.get(field) != expected:
                metadata_errors.append(
                    [set_name, field, {"expected": expected, "actual": metadata.get(field)}]
                )
        if metadata.get("metadata_source") != "authoritative_workbook":
            metadata_errors.append([set_name, "metadata_source"])
        if metadata.get("status") != "verified":
            metadata_errors.append([set_name, "status"])
    no_names = {aliases.get(row["display_name"], row["display_name"]) for row in no_rows}
    metadata_errors.extend([name, "NO workbook row appears in dataset"] for name in sorted(no_names & set(tests_by_set)))
    legacy_sets = registry.get("legacy_metadata_sets", [])
    if len(legacy_sets) != 11 or len(set(legacy_sets)) != 11:
        metadata_errors.append(["legacy_metadata_sets", len(legacy_sets)])
    for set_name in legacy_sets:
        test = tests_by_set.get(set_name)
        if not test or test.get("metadata", {}).get("metadata_source") != "predecessor_manifest":
            metadata_errors.append([set_name, "legacy source mismatch"])
    audit.check(
        "65 workbook-authoritative and 11 legacy metadata records close exactly",
        not metadata_errors and len(tests) == 76,
        metadata_errors[:25] or {"workbook": 65, "legacy": 11, "semantic_records": len(tests)},
    )
    if isinstance(history, dict):
        pruned = history.get("historical_pruned_run_exclusions", [])
        retests = history.get("retest_supersessions", [])
        audit.check(
            "history records nine path-and-hash-bound pruned runs",
            len(pruned) == 9
            and len({item.get("path") for item in pruned}) == 9
            and all(item.get("current_epoch_status") == "absent_from_frozen_commit" for item in pruned),
        )
        audit.check(
            "history records four retest supersession events",
            len(retests) == 4 and len({item.get("event_id") for item in retests}) == 4,
        )
    audit.check("staged evidence history equals input event ledger", staged_history == input_history)


def verify_workbook_acceptance_proof(root: Path, audit: Audit) -> None:
    bundled = root / "epoch_inputs/source_workbook/workbook_snapshot.json"
    fresh = root / "acceptance/FRESH_WORKBOOK_SNAPSHOT.json"
    try:
        bundled_hash = sha256_file(bundled)
        fresh_hash = sha256_file(fresh)
        bundled_bytes = bundled.read_bytes()
        fresh_bytes = fresh.read_bytes()
    except OSError as exc:
        audit.fail("fresh workbook extraction proof is readable", str(exc))
        return
    audit.check(
        "fresh artifact-tool workbook extraction is byte-identical to bundled snapshot",
        bundled_hash == EXPECTED_WORKBOOK_SNAPSHOT_SHA256
        and fresh_hash == EXPECTED_WORKBOOK_SNAPSHOT_SHA256
        and bundled_bytes == fresh_bytes,
        {"expected_sha256": EXPECTED_WORKBOOK_SNAPSHOT_SHA256, "fresh_sha256": fresh_hash},
    )
    snapshot = _load_json_checked(root, "acceptance/FRESH_WORKBOOK_SNAPSHOT.json", audit)
    try:
        sheet = snapshot["sheets"][0]
        values = sheet["values"]
        yes = sum(row[6] == "YES" for row in values[1:])
        no = sum(row[6] == "NO" for row in values[1:])
        valid = (
            snapshot.get("sheet_count") == 1
            and sheet.get("name") == "Untested Domes"
            and sheet.get("used_address") == "A1:G80"
            and len(values) == 80
            and yes == 65
            and no == 14
        )
    except (KeyError, IndexError, TypeError):
        valid = False
    audit.check("fresh workbook proof has exact sheet/range/status counts", valid)


def verify_importer_authority(root: Path, audit: Audit) -> None:
    require_paths(root, REQUIRED_AUTHORITY_FILES, audit, "frozen importer authority files are present")
    zip_path = root / "authority/test-imp-1.1.4-windows-x64.zip"
    source_manifest = root / "authority/SOURCE-SHA256SUMS-1.1.4.txt"
    try:
        zip_size = zip_path.stat().st_size
        zip_hash = sha256_file(zip_path)
        source_size = source_manifest.stat().st_size
        source_hash = sha256_file(source_manifest)
    except OSError as exc:
        audit.fail("frozen importer authority files are readable", str(exc))
        return
    audit.check(
        "test-imp 1.1.4 Windows ZIP has exact byte identity",
        zip_size == EXPECTED_IMPORTER_ZIP_BYTES and zip_hash == EXPECTED_IMPORTER_ZIP_SHA256,
        {"bytes": zip_size, "sha256": zip_hash},
    )
    audit.check(
        "test-imp 1.1.4 source manifest has exact byte identity",
        source_size == EXPECTED_IMPORTER_SOURCE_MANIFEST_BYTES
        and source_hash == EXPECTED_IMPORTER_SOURCE_MANIFEST_SHA256,
        {"bytes": source_size, "sha256": source_hash},
    )
    zip_errors: list[Any] = []
    expected_names = {
        "BUILD-INFO.txt",
        "CHANGELOG.txt",
        "METHOD.md",
        "README.txt",
        "SHA256SUMS.txt",
        "test-imp.exe",
    }
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            infos = archive.infolist()
            names: list[str] = []
            for info in infos:
                try:
                    name = validate_relpath(info.filename, label="importer ZIP member")
                except VerificationError as exc:
                    zip_errors.append(str(exc))
                    continue
                if info.is_dir():
                    zip_errors.append(f"unexpected directory in importer ZIP: {name}")
                names.append(name)
            if len(names) != len(set(names)):
                zip_errors.append("duplicate importer ZIP member")
            if set(names) != expected_names:
                zip_errors.append(
                    {"expected_members": sorted(expected_names), "actual_members": sorted(names)}
                )
            bad_member = archive.testzip()
            if bad_member is not None:
                zip_errors.append(f"CRC failure: {bad_member}")
            if "test-imp.exe" in names:
                exe_hash = sha256_bytes(archive.read("test-imp.exe"))
                if exe_hash != EXPECTED_IMPORTER_EXE_SHA256:
                    zip_errors.append(["test-imp.exe", EXPECTED_IMPORTER_EXE_SHA256, exe_hash])
            if "SHA256SUMS.txt" in names:
                checksum_text = archive.read("SHA256SUMS.txt").decode("utf-8")
                declared: dict[str, str] = {}
                for line in checksum_text.splitlines():
                    if not line.strip():
                        continue
                    digest, separator, member = line.partition("  ")
                    if not separator:
                        zip_errors.append(f"malformed internal checksum line: {line!r}")
                        continue
                    try:
                        validate_relpath(member, label="internal importer checksum path")
                    except VerificationError as exc:
                        zip_errors.append(str(exc))
                        continue
                    if member in declared:
                        zip_errors.append(f"duplicate internal checksum path: {member}")
                    declared[member] = digest.lower()
                expected_declared = expected_names - {"SHA256SUMS.txt"}
                if set(declared) != expected_declared:
                    zip_errors.append("internal importer checksum coverage mismatch")
                for member, digest in declared.items():
                    actual = sha256_bytes(archive.read(member))
                    if digest != actual:
                        zip_errors.append([member, digest, actual])
    except (OSError, zipfile.BadZipFile, UnicodeError, KeyError) as exc:
        zip_errors.append(str(exc))
    audit.check(
        "frozen importer ZIP has safe exact contents and internally valid hashes",
        not zip_errors,
        zip_errors,
    )


def verify_active_registries(root: Path, audit: Audit) -> None:
    errors: list[Any] = []
    for rel in sorted(REQUIRED_ACTIVE_REGISTRIES):
        item = _load_json_checked(root, rel, audit)
        if not isinstance(item, dict) or item.get("entries") != []:
            errors.append([rel, None if not isinstance(item, dict) else item.get("entries")])
        if isinstance(item, dict) and item.get("repo_commit", EXPECTED_COMMIT) != EXPECTED_COMMIT:
            errors.append([rel, "commit mismatch"])
    audit.check("all active exclusion/review/adjudication registries are empty", not errors, errors)
    exclusion = _load_json_checked(root, "evidence/exclusion_manifest.json", audit)
    audit.check(
        "generated exclusion manifest is empty and release-eligible",
        isinstance(exclusion, dict)
        and exclusion.get("entries") == []
        and exclusion.get("release_eligible") is True
        and exclusion.get("repo_commit") == EXPECTED_COMMIT,
    )


def _canonical_object_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)


def verify_generator_snapshot(root: Path, audit: Audit) -> None:
    generator = root / "generator"
    package_dir = generator / "domelab_pipeline"
    generator_files = {
        path.relative_to(generator).as_posix()
        for path in generator.rglob("*")
        if path.is_file()
    }
    forbidden = sorted(
        rel
        for rel in generator_files
        if rel.startswith("staging/")
        or "/__pycache__/" in f"/{rel}"
        or rel.startswith(".pytest_cache/")
        or PurePosixPath(rel).suffix.lower() in {".pyc", ".pyo"}
        or PurePosixPath(rel).name.startswith("test_results.")
        or PurePosixPath(rel).name in {"run_tests.bat", "run_tests.sh"}
    )
    audit.check("generator snapshot excludes caches, old staging, and old test reports", not forbidden, forbidden)
    html = sorted(
        rel
        for rel in generator_files
        if PurePosixPath(rel).suffix.lower() in {".html", ".htm"}
    )
    audit.check(
        "generator HTML is limited to two unexecuted release-reference dependencies",
        html
        == [
            "domelab_pipeline/release_reference/dome-lab-parts.release.html",
            "domelab_pipeline/release_reference/index.release.html",
        ],
        html,
    )
    source_identity = {
        path.name: sha256_file(path)
        for path in sorted(package_dir.glob("*.py"), key=lambda value: value.name.encode("utf-8"))
    }
    reference_dir = package_dir / "release_reference"
    reference_identity = {
        path.name: sha256_file(path)
        for path in sorted(reference_dir.iterdir(), key=lambda value: value.name.encode("utf-8"))
        if path.is_file()
    }
    schema = _load_json_checked(root, "evidence/schema_meta.staged.json", audit)
    if isinstance(schema, dict):
        hashes = schema.get("provenance_hashes", {})
        audit.check(
            "generator module snapshot reproduces generated source identity",
            _canonical_object_hash(source_identity) == hashes.get("generator_source_hash"),
        )
        audit.check(
            "release-reference snapshot reproduces generated reference identity",
            _canonical_object_hash(reference_identity) == hashes.get("release_reference_hash"),
        )
    exact_pairs = [
        (
            "generator/domelab_pipeline/config/dataset_manifest.json",
            "epoch_inputs/manifest/dataset_manifest.step2.json",
        ),
        (
            "generator/domelab_pipeline/config/dome_metadata_registry.json",
            "epoch_inputs/metadata/dome_metadata_registry.json",
        ),
        (
            "generator/domelab_pipeline/config/evidence_history.json",
            "epoch_inputs/history/evidence_event_ledger.json",
        ),
        (
            "generator/domelab_pipeline/config/retained_run_decisions.json",
            "evidence/intake_retention_decisions.json",
        ),
        (
            "generator/domelab_pipeline/release_reference/repository_file_inventory.csv",
            "epoch_inputs/manifest/repository_file_inventory.csv",
        ),
        (
            "generator/domelab_pipeline/release_reference/repo_provenance.json",
            "epoch_inputs/manifest/repo_provenance.json",
        ),
    ]
    mismatches: list[Any] = []
    for left_rel, right_rel in exact_pairs:
        left = root / Path(*PurePosixPath(left_rel).parts)
        right = root / Path(*PurePosixPath(right_rel).parts)
        try:
            if left.read_bytes() != right.read_bytes():
                mismatches.append([left_rel, right_rel])
        except OSError as exc:
            mismatches.append([left_rel, right_rel, str(exc)])
    audit.check("generator config/reference inputs are byte-identical to sealed authorities", not mismatches, mismatches)


def _identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("raw_path") or row.get("path"),
        row.get("sha256"),
        row.get("git_blob_oid"),
        row.get("acquisition_id"),
    )


def verify_dataset_alias_and_retention(root: Path, audit: Audit) -> dict[str, dict[str, Any]]:
    dataset = _load_json_checked(root, "epoch_inputs/manifest/dataset_manifest.step2.json", audit)
    acquisitions = _load_json_checked(root, "epoch_inputs/manifest/acquisition_registry.json", audit)
    raw_manifest = _load_json_checked(root, "evidence/raw_path_manifest.json", audit)
    decisions = _load_json_checked(root, "evidence/intake_retention_decisions.json", audit)
    if not all(isinstance(item, dict) for item in (dataset, acquisitions, raw_manifest, decisions)):
        return {}
    tests = dataset.get("tests", [])
    expected_runs = [
        dict(run, set=test.get("set"), test_id=test.get("test_id"))
        for test in tests
        for run in test.get("expected_runs", [])
    ]
    raw_rows = raw_manifest.get("rows", [])
    acquisition_rows = acquisitions.get("acquisitions", [])
    decision_sets = decisions.get("sets", [])
    decision_runs = [
        dict(run, set=group.get("set"))
        for group in decision_sets
        for run in group.get("runs", [])
    ]
    audit.check("dataset contains 76 semantic records", len(tests) == 76)
    cohorts = {test.get("measurement_cohort_id") for test in tests}
    audit.check("dataset contains 75 independent measurement cohorts", len(cohorts) == 75)
    audit.check("dataset expected-run manifest contains 184 paths", len(expected_runs) == 184)
    audit.check("raw path manifest contains 184 paths", len(raw_rows) == 184)
    audit.check("acquisition registry contains 180 acquisitions", len(acquisition_rows) == 180)
    audit.check("retention authority contains 76 sets and 184 runs", len(decision_sets) == 76 and len(decision_runs) == 184)
    try:
        expected_by_path = _unique_by(expected_runs, "path")
        raw_by_path = _unique_by(raw_rows, "path")
        decisions_by_path = _unique_by(decision_runs, "raw_path")
        acquisition_by_id = _unique_by(acquisition_rows, "acquisition_id")
    except VerificationError as exc:
        audit.fail("dataset/raw/acquisition/decision keys are unique", str(exc))
        return {}
    audit.check(
        "dataset, raw path manifest, and retention authority have identical path sets",
        set(expected_by_path) == set(raw_by_path) == set(decisions_by_path),
    )
    closure_errors: list[Any] = []
    for path, expected in expected_by_path.items():
        raw = raw_by_path.get(path, {})
        decision = decisions_by_path.get(path, {})
        for field in ("sha256", "git_blob_oid", "acquisition_id"):
            if expected.get(field) != raw.get(field) or expected.get(field) != decision.get(field):
                closure_errors.append([path, field])
        expected_bytes = expected.get("bytes")
        if expected_bytes != raw.get("bytes") or expected_bytes != decision.get("raw_bytes"):
            closure_errors.append([path, "bytes"])
        acquisition = acquisition_by_id.get(expected.get("acquisition_id"), {})
        if (
            acquisition.get("sha256") != expected.get("sha256")
            or acquisition.get("git_blob_oid") != expected.get("git_blob_oid")
            or acquisition.get("size_bytes") != expected_bytes
            or path not in acquisition.get("raw_path_aliases", [])
        ):
            closure_errors.append([path, "acquisition registry"])
    audit.check(
        "dataset/raw/acquisition/retention identity fields close exactly",
        not closure_errors,
        closure_errors[:25],
    )
    retention_errors: list[Any] = []
    for group in decision_sets:
        if (
            group.get("status") != "accepted"
            or group.get("retained_count") != len(group.get("runs", []))
            or group.get("retained_count", 0) < 2
            or group.get("mixed_cohort") is not None
            or group.get("ramp_review_summary", {}).get("review_required") is not False
        ):
            retention_errors.append([group.get("set"), "set status/count/review"])
        for run in group.get("runs", []):
            if (
                run.get("retained") is not True
                or run.get("intake_individually_acceptable") is not True
                or run.get("matches_replicate_band") is not True
                or run.get("ramp_review_required") is not False
                or run.get("decision_reasons") != ["retained"]
            ):
                retention_errors.append([group.get("set"), run.get("raw_path")])
    summary = decisions.get("ramp_review_summary", {})
    if (
        decisions.get("artifact_role") != "canonical_retention_authority"
        or decisions.get("canonical_membership_active") is not True
        or decisions.get("membership_applied_to_outputs") is not True
        or decisions.get("release_eligible") is not True
        or summary != {"review_required": False, "run_count": 0, "set_count": 0}
        or decisions.get("raw_evidence_summary", {}).get("path_count") != 184
        or decisions.get("raw_evidence_summary", {}).get("unique_acquisition_count") != 180
    ):
        retention_errors.append(["top-level retention authority"])
    audit.check(
        "all 184 paths are retained with no mixed-population or ramp-review warning",
        not retention_errors,
        retention_errors[:25],
    )
    aliases = dataset.get("evidence_aliases", [])
    duplicate_sha: dict[str, list[str]] = {}
    for path, row in raw_by_path.items():
        duplicate_sha.setdefault(row.get("sha256"), []).append(path)
    duplicate_sha = {sha: paths for sha, paths in duplicate_sha.items() if len(paths) > 1}
    alias_errors: list[Any] = []
    if len(aliases) != 1:
        alias_errors.append(["alias group count", len(aliases)])
    else:
        alias = aliases[0]
        if alias.get("group_id") != "egrp_topre_hhkb_pro2_45g__topre_slider_black":
            alias_errors.append(["group id"])
        if set(alias.get("semantic_test_ids", [])) != {"bt_0015", "bt_0023"}:
            alias_errors.append(["semantic test ids"])
        if len(alias.get("run_pairs", [])) != 4:
            alias_errors.append(["run pair count"])
        declared_duplicate_sha: dict[str, set[str]] = {}
        for pair in alias.get("run_pairs", []):
            members = pair.get("members", [])
            shas = {member.get("sha256") for member in members}
            oids = {member.get("git_blob_oid") for member in members}
            acquisitions_in_pair = {member.get("acquisition_id", pair.get("acquisition_id")) for member in members}
            paths = {member.get("path") for member in members}
            sets = {member.get("set") for member in members}
            if (
                len(members) != 2
                or len(shas) != 1
                or len(oids) != 1
                or pair.get("acquisition_id") not in acquisitions_in_pair
                or sets != {"Topre_HHKB_Pro2_45g", "Topre_Slider_Black"}
                or pair.get("independent_observation_count") != 1
            ):
                alias_errors.append(["malformed run pair", pair.get("acquisition_id")])
            if shas:
                declared_duplicate_sha[next(iter(shas))] = paths
        if {sha: set(paths) for sha, paths in duplicate_sha.items()} != declared_duplicate_sha:
            alias_errors.append(["duplicate raw evidence differs from declared alias pairs"])
        alias_tests = [test for test in tests if test.get("test_id") in {"bt_0015", "bt_0023"}]
        if (
            len(alias_tests) != 2
            or len({test.get("measurement_cohort_id") for test in alias_tests}) != 1
            or len({test.get("independence_key") for test in alias_tests}) != 1
            or {test.get("metadata", {}).get("evidence_alias_role") for test in alias_tests}
            != {"part_assembly_semantic", "dome_semantic"}
        ):
            alias_errors.append(["semantic alias cohort/roles"])
    audit.check(
        "HHKB/black-slider alias is two semantics over four shared acquisitions",
        not alias_errors and len(duplicate_sha) == 4,
        alias_errors or {"shared_acquisitions": len(duplicate_sha)},
    )
    return decisions_by_path


def verify_generated_evidence(
    root: Path, decisions_by_path: dict[str, dict[str, Any]], audit: Audit
) -> None:
    evidence_root = root / EVIDENCE_ROOT
    generated = _load_json_checked(root, "evidence/generated_manifest.json", audit)
    schema_meta = _load_json_checked(root, "evidence/schema_meta.staged.json", audit)
    records = _load_json_checked(root, "evidence/bench_tests.staged.json", audit)
    per_run = _load_json_checked(root, "evidence/per_run_full_precision.json", audit)
    raw_manifest = _load_json_checked(root, "evidence/raw_path_manifest.json", audit)
    curve_provenance = _load_json_checked(root, "evidence/curve_pack_provenance.json", audit)
    if not evidence_root.is_dir():
        audit.fail("evidence directory exists")
        return
    evidence_files = {
        path.relative_to(evidence_root).as_posix()
        for path in evidence_root.rglob("*")
        if path.is_file()
    }
    html_files = sorted(
        path for path in evidence_files if PurePosixPath(path).suffix.lower() in {".html", ".htm"}
    )
    audit.check("evidence-only generation emitted no HTML", not html_files, html_files)
    if isinstance(generated, dict):
        audit.check(
            "generated manifest has exact frozen SHA-256",
            sha256_file(evidence_root / "generated_manifest.json")
            == EXPECTED_GENERATED_MANIFEST_SHA256,
        )
        audit.check(
            "retained decision manifest has exact frozen SHA-256",
            sha256_file(evidence_root / "intake_retention_decisions.json")
            == EXPECTED_DECISIONS_SHA256,
        )
        expected_generated_files = evidence_files - {"generated_manifest.json"}
        audit.check(
            "generated_manifest has exact evidence-file coverage",
            set(generated) == expected_generated_files,
            {
                "missing": sorted(expected_generated_files - set(generated)),
                "extra": sorted(set(generated) - expected_generated_files),
            },
        )
        hash_errors = []
        for rel, expected_hash in generated.items():
            try:
                validate_relpath(rel, label="generated artifact path")
                actual_hash = sha256_file(evidence_root / Path(*PurePosixPath(rel).parts))
                if actual_hash != expected_hash:
                    hash_errors.append([rel, expected_hash, actual_hash])
            except (OSError, VerificationError) as exc:
                hash_errors.append([rel, str(exc)])
        audit.check(
            "generated_manifest hashes every evidence artifact exactly",
            not hash_errors,
            hash_errors[:25] or {"verified_artifacts": len(generated)},
        )
    if isinstance(schema_meta, dict):
        epoch = schema_meta.get("evidence_epoch", {})
        provenance = schema_meta.get("provenance_hashes", {})
        intake = schema_meta.get("intake_policy", {})
        audit.check(
            "schema metadata carries exact canonical identities and counts",
            schema_meta.get("repo_commit") == EXPECTED_COMMIT
            and epoch.get("identity") == EXPECTED_EVIDENCE_EPOCH_HASH
            and provenance.get("evidence_epoch_hash") == EXPECTED_EVIDENCE_EPOCH_HASH
            and epoch.get("semantic_record_count") == 76
            and epoch.get("independent_measurement_cohort_count") == 75
            and epoch.get("raw_path_count") == 184
            and epoch.get("unique_raw_evidence_count") == 180,
        )
        audit.check(
            "schema metadata marks Step 3 deferred/nonrelease",
            epoch.get("force_curve_bench_step3_status") == "deferred_not_executed"
            and epoch.get("force_curve_bench_release_eligible") is False,
        )
        audit.check(
            "schema metadata has no canonical intake warning",
            intake.get("warning") is None
            and intake.get("ramp_review_summary")
            == {"review_required": False, "run_count": 0, "set_count": 0},
        )
    if not isinstance(records, list) or not isinstance(per_run, list) or not isinstance(raw_manifest, dict):
        audit.fail("authoritative aggregate/per-run/raw artifacts have expected types")
        return
    audit.check("authoritative aggregate results contain 76 records", len(records) == 76)
    audit.check("full-precision per-run results contain 184 records", len(per_run) == 184)
    try:
        records_by_set = _unique_by(records, "set")
        per_run_by_path = _unique_by(per_run, "raw_path")
        raw_by_path = _unique_by(raw_manifest.get("rows", []), "path")
    except VerificationError as exc:
        audit.fail("aggregate/per-run/raw artifacts have unique identities", str(exc))
        return
    audit.check(
        "full-precision per-run/raw/retention artifacts have identical path sets",
        set(per_run_by_path) == set(raw_by_path) == set(decisions_by_path),
    )
    per_run_errors: list[Any] = []
    for path, decision in decisions_by_path.items():
        row = per_run_by_path.get(path, {})
        raw = raw_by_path.get(path, {})
        for field in ("sha256", "git_blob_oid", "acquisition_id"):
            if row.get(field) != decision.get(field) or raw.get(field) != decision.get(field):
                per_run_errors.append([path, field])
        if row.get("retained_canonical") is not True or row.get("retained_output") is not True:
            per_run_errors.append([path, "retained flags"])
    audit.check("per-run identities and canonical membership close exactly", not per_run_errors, per_run_errors[:25])
    aggregate_errors: list[Any] = []
    for set_name, record in records_by_set.items():
        paths = record.get("provenance", {}).get("raw_paths", [])
        shas = record.get("provenance", {}).get("raw_sha256", [])
        oids = record.get("provenance", {}).get("raw_git_blob_oids", [])
        acqs = record.get("provenance", {}).get("acquisition_ids", [])
        if not (len(paths) == len(shas) == len(oids) == len(acqs) == record.get("runs_used")):
            aggregate_errors.append([set_name, "provenance vector lengths"])
            continue
        for path, sha, oid, acq in zip(paths, shas, oids, acqs, strict=True):
            decision = decisions_by_path.get(path)
            if not decision or decision.get("set") != set_name or _identity(decision) != (path, sha, oid, acq):
                aggregate_errors.append([set_name, path, "aggregate provenance mismatch"])
        if record.get("provenance", {}).get("config_hash") != EXPECTED_EVIDENCE_EPOCH_HASH:
            aggregate_errors.append([set_name, "evidence epoch hash"])
    audit.check("all 76 aggregate records close to retained per-run evidence", not aggregate_errors, aggregate_errors[:25])
    # The two semantic records intentionally share metrics but retain distinct metadata.
    hhkb = records_by_set.get("Topre_HHKB_Pro2_45g", {})
    slider = records_by_set.get("Topre_Slider_Black", {})
    metric_fields = [
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
        "runs_used",
        "dispersion",
    ]
    audit.check(
        "shared HHKB/black-slider semantic aggregates have identical metrics",
        bool(hhkb)
        and bool(slider)
        and all(hhkb.get(field) == slider.get(field) for field in metric_fields)
        and hhkb.get("kind") != slider.get("kind"),
    )
    if isinstance(curve_provenance, dict):
        packs = curve_provenance.get("packs", [])
        pack_errors: list[Any] = []
        if (
            curve_provenance.get("repo_commit") != EXPECTED_COMMIT
            or curve_provenance.get("evidence_epoch_hash") != EXPECTED_EVIDENCE_EPOCH_HASH
            or curve_provenance.get("authoritative_metrics_artifact") != "bench_tests.staged.json"
            or curve_provenance.get("pack_values_are_derived_and_lossy") is not True
        ):
            pack_errors.append(["top-level curve provenance"])
        try:
            packs_by_set = _unique_by(packs, "set")
        except VerificationError as exc:
            packs_by_set = {}
            pack_errors.append([str(exc)])
        if set(packs_by_set) != set(records_by_set):
            pack_errors.append(["curve/aggregate set mismatch"])
        for set_name, item in packs_by_set.items():
            rel = item.get("path")
            if not isinstance(rel, str):
                pack_errors.append([set_name, "missing path"])
                continue
            try:
                validate_relpath(rel, label="curve pack path")
                pack_path = evidence_root / Path(*PurePosixPath(rel).parts)
                pack = load_json(pack_path)
                record = records_by_set.get(set_name, {})
                if (
                    sha256_file(pack_path) != item.get("sha256")
                    or pack.get("set") != set_name
                    or pack.get("runs_used") != record.get("runs_used")
                    or pack.get("authoritative_metrics") is not False
                    or pack.get("derived_lossy_display_pack") is not True
                    or item.get("raw_paths") != record.get("provenance", {}).get("raw_paths")
                    or item.get("raw_sha256") != record.get("provenance", {}).get("raw_sha256")
                    or item.get("raw_git_blob_oids")
                    != record.get("provenance", {}).get("raw_git_blob_oids")
                    or item.get("acquisition_ids")
                    != record.get("provenance", {}).get("acquisition_ids")
                ):
                    pack_errors.append([set_name, "pack/provenance closure"])
            except (OSError, VerificationError) as exc:
                pack_errors.append([set_name, str(exc)])
        audit.check(
            "all 76 lossy curve packs close to authoritative aggregate provenance",
            not pack_errors and len(packs) == 76,
            pack_errors[:25] or {"curve_packs": len(packs)},
        )
    for rel in ("evidence/run_retention.csv", "evidence/per_run_full_precision.csv", "evidence/acquisition_qc.csv"):
        parsed = _load_csv_checked(root, rel, audit)
        if parsed is None:
            continue
        _fields, rows = parsed
        paths = {row.get("raw_path") for row in rows}
        audit.check(
            f"{rel} closes over all 184 retained paths",
            len(rows) == 184 and paths == set(decisions_by_path),
        )


def verify_importer_validation(root: Path, audit: Audit) -> None:
    require_paths(
        root,
        REQUIRED_IMPORTER_VALIDATION_FILES,
        audit,
        "all five independent importer validation artifacts are present",
    )
    importer = _load_json_checked(
        root, "epoch_inputs/validation/test_imp_1_1_4_epoch_audit.json", audit
    )
    if not isinstance(importer, dict):
        return
    fleet = importer.get("fleet_audit", {})
    generator = importer.get("generator_comparison", {})
    stability = importer.get("repo_and_cache_stability", {})
    release = importer.get("importer_release_identity", {})
    checks = fleet.get("checks", {})
    audit.check(
        "independent test-imp 1.1.4 fleet audit passes exact canonical counts",
        importer.get("result") == "PASS"
        and all(checks.values())
        and checks.get("semantic_path_count_184") is True
        and checks.get("unique_acquisition_count_180") is True
        and checks.get("semantic_cohort_count_76") is True
        and checks.get("independent_measurement_cohort_count_75") is True,
    )
    audit.check(
        "independent importer/generator comparison passes within 1e-12",
        generator.get("status") == "pass"
        and generator.get("per_run_full_precision", {}).get("status") == "pass"
        and generator.get("retained_run_decisions", {}).get("status") == "pass"
        and generator.get("dataset_manifest", {}).get("status") == "pass"
        and generator.get("max_scalar_delta", float("inf")) <= 1e-12,
    )
    bindings = generator.get("artifact_bindings", {})
    evidence = root / "evidence"
    binding_errors: list[Any] = []
    expected_bindings = {
        "generated_manifest": ("generated_manifest.json", "sha256"),
        "curve_pack_provenance": ("curve_pack_provenance.json", "sha256"),
    }
    for key, (filename, hash_key) in expected_bindings.items():
        expected_hash = bindings.get(key, {}).get(hash_key)
        try:
            actual_hash = sha256_file(evidence / filename)
        except OSError as exc:
            binding_errors.append([filename, str(exc)])
            continue
        if expected_hash != actual_hash:
            binding_errors.append([filename, expected_hash, actual_hash])
    direct_bindings = {
        "output_decisions_sha256": "intake_retention_decisions.json",
        "per_run_sha256": "per_run_full_precision.json",
    }
    for key, filename in direct_bindings.items():
        try:
            actual_hash = sha256_file(evidence / filename)
        except OSError as exc:
            binding_errors.append([filename, str(exc)])
            continue
        if bindings.get(key) != actual_hash:
            binding_errors.append([filename, bindings.get(key), actual_hash])
    audit.check("independent importer audit binds exact packaged generator artifacts", not binding_errors, binding_errors)
    audit.check(
        "independent audit observed stable clean frozen repo/cache",
        stability.get("all_checks_pass") is True and all(stability.get("checks", {}).values()),
    )
    audit.check(
        "importer 1.1.4 release identity passed its independent acceptance",
        release.get("all_checks_pass") is True
        and release.get("executable", {}).get("sha256")
        == "351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e",
    )
    cohort_csv = _load_csv_checked(
        root, "epoch_inputs/validation/test_imp_1_1_4_per_cohort.csv", audit
    )
    run_csv = _load_csv_checked(
        root, "epoch_inputs/validation/test_imp_1_1_4_per_run.csv", audit
    )
    if cohort_csv is not None:
        audit.check("independent importer cohort table has 76 rows", len(cohort_csv[1]) == 76)
    if run_csv is not None:
        audit.check("independent importer run table has 184 rows", len(run_csv[1]) == 184)


def verify_acceptance(root: Path, audit: Audit) -> None:
    require_paths(root, REQUIRED_ACCEPTANCE_FILES, audit, "required acceptance artifacts are present")
    acceptance = _load_json_checked(root, "acceptance/EPOCH_ACCEPTANCE.json", audit)
    tests = _load_json_checked(root, "acceptance/TEST_RESULTS.json", audit)
    tree_audit = _load_json_checked(root, "acceptance/GIT_TREE_AUDIT.json", audit)
    if isinstance(acceptance, dict):
        audit.check(
            "acceptance record passes Step 2 and defers Step 3",
            acceptance.get("status") == "PASS"
            and acceptance.get("scope") == "step2_only"
            and acceptance.get("repo_commit") == EXPECTED_COMMIT
            and acceptance.get("repo_tree") == EXPECTED_TREE
            and acceptance.get("step3_status") == "deferred_not_executed",
        )
    if isinstance(tests, dict):
        audit.check(
            "packaged test record reports all required Step-2 gates passing",
            tests.get("status") == "PASS"
            and tests.get("repo_commit") == EXPECTED_COMMIT
            and not tests.get("required_failures"),
        )
    if isinstance(tree_audit, dict):
        audit.check(
            "independent Git-tree audit binds all 189 cache objects",
            tree_audit.get("status") == "PASS"
            and tree_audit.get("repo_commit") == EXPECTED_COMMIT
            and tree_audit.get("expected_tree_oid") == EXPECTED_TREE
            and tree_audit.get("calculated_tree_oid") == EXPECTED_TREE
            and tree_audit.get("verified_paths") == 189
            and tree_audit.get("mismatch_count") == 0,
        )


def verify_package(package_root: Path) -> dict[str, Any]:
    audit = Audit()
    try:
        root = package_root.resolve(strict=True)
    except OSError as exc:
        audit.fail("package root exists", str(exc))
        return audit.report(package_root)
    audit.check("package root is a directory", root.is_dir())
    actual_files = scan_package(root, audit)
    required_top_level = {
        "EPOCH_MANIFEST.json",
        "README.md",
        "SHA256SUMS.csv",
        "tools/verify_canonical_epoch.py",
    }
    require_paths(root, required_top_level, audit, "required top-level package files are present")
    require_paths(
        root,
        REQUIRED_IMPORTER_VALIDATION_FILES
        | REQUIRED_ACCEPTANCE_FILES
        | REQUIRED_AUTHORITY_FILES
        | REQUIRED_ACTIVE_REGISTRIES,
        audit,
        "required package components are present",
    )
    verify_sha256_inventory(root, actual_files, audit)
    manifest = _load_json_checked(root, "EPOCH_MANIFEST.json", audit)
    if manifest is None:
        return audit.report(root)
    verify_manifest_identity(root, manifest, audit)
    verify_epoch_input_inventory(root, audit)
    verify_repository_cache(root, manifest, audit)
    verify_metadata_and_history(root, audit)
    verify_workbook_acceptance_proof(root, audit)
    verify_importer_authority(root, audit)
    verify_active_registries(root, audit)
    verify_generator_snapshot(root, audit)
    decisions_by_path = verify_dataset_alias_and_retention(root, audit)
    verify_generated_evidence(root, decisions_by_path, audit)
    verify_importer_validation(root, audit)
    verify_acceptance(root, audit)
    return audit.report(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "package_root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="canonical evidence epoch package root (default: parent of tools/)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="emit compact rather than indented JSON",
    )
    args = parser.parse_args(argv)
    report = verify_package(args.package_root)
    print(json.dumps(report, indent=None if args.compact else 2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
