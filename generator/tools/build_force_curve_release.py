#!/usr/bin/env python3
"""Build and verify the deterministic Force Curve Bench fc-3.5 site overlay.

The input ``base-release`` is the already published fc-3.4 + lib-6.1 site and
must pass the lib-6.1 site verifier before any output is created.  This tool
changes only the Force Curve Bench entry point, its two generated viewer
artifacts, and source/documentation/assets explicitly named by an overlay
policy.  The EC Parts Library, raw CSVs, canonical evidence, legacy entry
points, and the historical fc-3.4 manifest remain byte-identical.

The prior active site manifest is retained as an immutable predecessor record.
The resulting package receives a new active ``SITE_RELEASE_MANIFEST.json`` and
``SHA256SUMS`` inventory and is verified before and after atomic promotion.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Mapping

import build_parts_library_release as parts


SITE_MANIFEST_NAME = "SITE_RELEASE_MANIFEST.json"
SHA256SUMS_NAME = "SHA256SUMS"
PREDECESSOR_SITE_MANIFEST_NAME = "SITE_RELEASE_MANIFEST_PRE_FC35.json"
HISTORICAL_FORCE_MANIFEST_NAME = "FORCE_CURVE_BENCH_RELEASE_MANIFEST.json"
COMPONENT_MANIFEST_NAME = "FORCE_CURVE_BENCH_RELEASE_MANIFEST_fc-3.5.json"
PACKAGE_ID = "force-curve-bench-site-fc-3.5"
COMPONENT_PACKAGE_ID = "force-curve-bench-fc-3.5"
ARTIFACT_ROLE = "public_multi_tool_site_release"
FORCE_BUILD = "fc-3.5"
PARTS_BUILD = "lib-6.1"
CANONICAL_PUBLIC_URL = "https://buddyog.github.io/topre-force-curves/"
RELEASE_GIT_TAG = "fc-3.5"
OG_IMAGE_URL = (
    "https://buddyog.github.io/topre-force-curves/"
    "assets/force-curve-bench-fc-3.5-og.png"
)
OG_IMAGE_PATH = "assets/force-curve-bench-fc-3.5-og.png"
POLICY_PACKAGE_PATH = (
    "generator/domelab_pipeline/config/force_curve_release_overlay.json"
)
SUBJECTIVE_PILOT_ROOT = "documentation/subjective-pilot"
SUBJECTIVE_PILOT_SUMS_PATH = f"{SUBJECTIVE_PILOT_ROOT}/SHA256SUMS.json"
RESEARCH_PAPER_STATUS_PATH = "documentation/research-paper/README.md"
REQUIRED_OVERLAY_PATHS = frozenset(
    {
        POLICY_PACKAGE_PATH,
        OG_IMAGE_PATH,
        SUBJECTIVE_PILOT_SUMS_PATH,
        RESEARCH_PAPER_STATUS_PATH,
    }
)
# Pinned identities of the verified e9dde99 predecessor package.  These make
# the predecessor proof independent of values copied into the new manifest.
PREDECESSOR_SITE_MANIFEST_SHA256 = (
    "3f6ec42010a2f797ced8528dac687fb1a5ddd4017448784b8bf4efdfc74f47b2"
)
PREDECESSOR_SHA256SUMS_SHA256 = (
    "e37818817dc2c069497caf1de2b95d9b70435558f52473a2b5defaee1598da87"
)
MANIFEST_VERSION = 2
POLICY_VERSION = 1
TEMP_PREFIX = ".force-release-"

ROOT_VIEWER_PATH = "index.html"
ROOT_PARTS_PATH = "dome-lab-parts.html"
GENERATED_MANIFEST_PATH = "generated/generated_manifest.json"
GENERATED_VIEWER_PATH = "generated/packs/viewer.staged.html"
GENERATED_VTESTS_PATH = "generated/packs/viewer_vtests.json"
GENERATED_PICKER_PATH = "generated/packs/picker.staged.html"
GENERATED_SCHEMA_PATH = "generated/schema_meta.staged.json"
GENERATED_EXCLUSION_PATH = "generated/exclusion_manifest.json"
GENERATED_PARITY_PATH = "generated/parity_report.json"

GENERATED_MUTABLE = frozenset(
    {
        GENERATED_MANIFEST_PATH,
        GENERATED_VIEWER_PATH,
        GENERATED_VTESTS_PATH,
        GENERATED_SCHEMA_PATH,
        GENERATED_EXCLUSION_PATH,
    }
)
REQUIRED_STAGE_FILES = frozenset(
    {
        "bench_tests.staged.json",
        "curve_pack_provenance.json",
        "exclusion_manifest.json",
        "generated_manifest.json",
        "intake_retention_decisions.json",
        "packs/perception_scores.json",
        "packs/picker.staged.html",
        "packs/viewer_embedded.json",
        "packs/viewer.staged.html",
        "packs/viewer_vtests.json",
        "parity_report.json",
        "raw_path_manifest.json",
        "schema_meta.staged.json",
    }
)
PROTECTED_ROOT_FILES = frozenset(
    {
        ROOT_VIEWER_PATH,
        ROOT_PARTS_PATH,
        "dome-lab.html",
        "ec-switch-explorer.html",
        SITE_MANIFEST_NAME,
        SHA256SUMS_NAME,
        PREDECESSOR_SITE_MANIFEST_NAME,
        HISTORICAL_FORCE_MANIFEST_NAME,
        COMPONENT_MANIFEST_NAME,
    }
)
HEX64 = re.compile(r"[0-9a-f]{64}")
HEX40 = re.compile(r"[0-9a-f]{40}")


class ForceReleaseError(RuntimeError):
    """A deterministic fc-3.5 release contract was not satisfied."""


def _read_utf8_exact(path: Path, label: str) -> str:
    """Decode UTF-8 without universal-newline translation.

    Generated CSVs intentionally contain CRLF records.  ``Path.read_text``
    normalizes those bytes on Windows, which makes a reconstructed
    ``generated_manifest.json`` describe different payloads than the files
    that the generator actually wrote.  Release verification is byte based,
    so every artifact read that participates in a hash or equality check must
    preserve line endings exactly.
    """
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as error:
        raise ForceReleaseError(f"cannot read {label}: {path}: {error}") from error


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(
            _read_utf8_exact(path, label),
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON token {token}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ForceReleaseError(f"cannot read {label}: {path}: {error}") from error


def _normalize_relative(value: Any, label: str) -> str:
    try:
        return parts._normalize_relative(value, label)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error


def _resolve_directory(value: str | os.PathLike[str], label: str) -> Path:
    try:
        return parts._resolve_directory(value, label)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error


def _resolve_file(value: str | os.PathLike[str], label: str) -> Path:
    try:
        return parts._resolve_file(value, label)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error


def _scan_regular_files(root: Path) -> dict[str, Path]:
    try:
        return parts._scan_regular_files(root)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error


def _manifest_rows(manifest: Mapping[str, Any], label: str) -> dict[str, dict[str, Any]]:
    try:
        return parts._manifest_rows(manifest, label)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error


def _overlay_path_is_protected(relative: str) -> bool:
    return (
        relative in PROTECTED_ROOT_FILES
        or relative.startswith("canonical-evidence/")
        or relative.startswith("generated/")
        or relative.casefold().endswith(".csv")
    )


def _load_policy(path: Path) -> dict[str, Any]:
    policy = _read_json(path, "Force viewer overlay policy")
    if not isinstance(policy, dict) or set(policy) != {
        "policy_version",
        "name",
        "overlay_paths",
    }:
        raise ForceReleaseError("overlay policy has the wrong field set")
    if policy["policy_version"] != POLICY_VERSION:
        raise ForceReleaseError("unsupported Force viewer overlay-policy version")
    if not isinstance(policy["name"], str) or not policy["name"].strip():
        raise ForceReleaseError("overlay policy name must be non-empty")
    values = policy["overlay_paths"]
    if not isinstance(values, list) or not values:
        raise ForceReleaseError("overlay policy must declare at least one path")
    paths = [_normalize_relative(value, "overlay path") for value in values]
    if len(set(paths)) != len(paths):
        raise ForceReleaseError("overlay policy contains duplicate paths")
    if paths != sorted(paths, key=lambda value: value.encode("utf-8")):
        raise ForceReleaseError("overlay paths must be in canonical order")
    folded: dict[str, str] = {}
    for relative in paths:
        key = relative.casefold()
        if key in folded:
            raise ForceReleaseError(
                f"case-insensitive overlay collision: {folded[key]!r} and {relative!r}"
            )
        folded[key] = relative
        if _overlay_path_is_protected(relative):
            raise ForceReleaseError(
                f"overlay policy attempts to replace protected path: {relative}"
            )
    for relative in paths:
        components = PurePosixPath(relative).parts
        for index in range(1, len(components)):
            ancestor = "/".join(components[:index])
            if ancestor.casefold() in folded:
                raise ForceReleaseError(
                    f"overlay file/directory collision: {ancestor!r} and {relative!r}"
                )
    return {**policy, "overlay_paths": paths}


def _validate_subjective_pilot_inventory(root: Path) -> None:
    """Validate the pilot's own sealed inventory inside a source/package tree."""
    checksum_path = root / Path(*PurePosixPath(SUBJECTIVE_PILOT_SUMS_PATH).parts)
    payload = _read_json(checksum_path, "subjective-pilot SHA256SUMS.json")
    if (
        not isinstance(payload, dict)
        or set(payload) != {"files", "inventory_scope", "pilot_id"}
        or payload.get("inventory_scope")
        != "all regular files in this directory except SHA256SUMS.json"
        or payload.get("pilot_id") != "subjective-pilot-v1"
        or not isinstance(payload.get("files"), list)
    ):
        raise ForceReleaseError("subjective-pilot SHA256SUMS.json has the wrong contract")
    pilot_root = checksum_path.parent
    actual = {
        path.relative_to(pilot_root).as_posix(): path
        for path in pilot_root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    rows: dict[str, dict[str, Any]] = {}
    ordered_paths: list[str] = []
    for index, row in enumerate(payload["files"]):
        if not isinstance(row, dict) or set(row) != {"bytes", "path", "sha256"}:
            raise ForceReleaseError(
                f"subjective-pilot checksum row {index} has the wrong fields"
            )
        relative = _normalize_relative(row["path"], "subjective-pilot path")
        if "/" in relative or relative in rows:
            raise ForceReleaseError(
                f"subjective-pilot checksum row has an invalid path: {relative}"
            )
        if (
            type(row["bytes"]) is not int
            or row["bytes"] < 0
            or not isinstance(row["sha256"], str)
            or not HEX64.fullmatch(row["sha256"])
        ):
            raise ForceReleaseError(
                f"subjective-pilot checksum row has an invalid identity: {relative}"
            )
        rows[relative] = row
        ordered_paths.append(relative)
    canonical_order = sorted(ordered_paths, key=lambda value: value.encode("utf-8"))
    if ordered_paths != canonical_order or set(rows) != set(actual):
        raise ForceReleaseError(
            "subjective-pilot checksum inventory is incomplete or non-canonical"
        )
    for relative, path in actual.items():
        row = rows[relative]
        if row["bytes"] != path.stat().st_size or row["sha256"] != parts._sha256(path):
            raise ForceReleaseError(
                f"subjective-pilot checksum mismatch: {relative}"
            )


def _strict_json_bytes(path: Path, label: str) -> Any:
    return _read_json(path, label)


def _parse_viewer_build(path: Path) -> dict[str, Any]:
    try:
        source = _read_utf8_exact(path, "generated viewer")
    except (OSError, UnicodeError) as error:
        raise ForceReleaseError(f"cannot read generated viewer: {path}: {error}") from error
    _validate_viewer_publication(source)
    marker = re.search(r"\bconst\s+VIEWER_BUILD\s*=\s*", source)
    if marker is None:
        raise ForceReleaseError("generated viewer has no canonical VIEWER_BUILD blob")
    decoder = json.JSONDecoder(
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON token {token}")
        )
    )
    try:
        build, end = decoder.raw_decode(source, marker.end())
    except (json.JSONDecodeError, ValueError) as error:
        raise ForceReleaseError(f"generated viewer has invalid VIEWER_BUILD JSON: {error}") from error
    if not re.match(r"\s*;\s*/\*\s*generated\b", source[end:], re.IGNORECASE):
        raise ForceReleaseError("generated viewer VIEWER_BUILD lacks the generated marker")
    if not isinstance(build, dict):
        raise ForceReleaseError("generated viewer VIEWER_BUILD must be an object")
    expected = {
        "bench_build": FORCE_BUILD,
        "mode": "release",
        "presentation_role": "public_release",
        "release_eligible": True,
        "canonical_data_release_eligible": True,
    }
    for key, value in expected.items():
        if build.get(key) != value:
            raise ForceReleaseError(
                f"generated viewer has the wrong release identity: {key}={build.get(key)!r}"
            )
    if not isinstance(build.get("repo_commit"), str) or not HEX40.fullmatch(
        build["repo_commit"]
    ):
        raise ForceReleaseError("generated viewer has no valid data repo_commit")
    for key in ("canonical_evidence_identity", "data_identity"):
        if not isinstance(build.get(key), str) or not HEX64.fullmatch(build[key]):
            raise ForceReleaseError(f"generated viewer has no valid {key}")
    return build


def _validate_viewer_publication(source: str) -> None:
    required = {
        "canonical URL": f'<link rel="canonical" href="{CANONICAL_PUBLIC_URL}">',
        "Open Graph URL": f'<meta property="og:url" content="{CANONICAL_PUBLIC_URL}">',
        "Open Graph image": f'<meta property="og:image" content="{OG_IMAGE_URL}">',
    }
    for label, literal in required.items():
        if source.count(literal) != 1:
            raise ForceReleaseError(f"generated viewer lacks one exact {label}")
    for marker in ("placeholder", "example.com"):
        if marker in source[: source.find("</head>")].casefold():
            raise ForceReleaseError(f"generated viewer head contains forbidden {marker}")


def _validate_vtests(path: Path, viewer_build: Mapping[str, Any]) -> None:
    value = _strict_json_bytes(path, "viewer_vtests.json")
    if not isinstance(value, list) or not value:
        raise ForceReleaseError("viewer_vtests.json must be a non-empty array")
    expected_count = viewer_build.get("record_count")
    if type(expected_count) is not int or expected_count != len(value):
        raise ForceReleaseError(
            "viewer_vtests.json count does not match VIEWER_BUILD.record_count"
        )
    ids: set[str] = set()
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ForceReleaseError(f"viewer_vtests.json row {index} is not an object")
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ForceReleaseError(
                f"viewer_vtests.json row {index} has a missing or duplicate id"
            )
        ids.add(identifier)


def _extract_json_constant(source: str, name: str) -> Any:
    marker = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*", source)
    if marker is None:
        raise ForceReleaseError(f"generated viewer has no {name} blob")
    decoder = json.JSONDecoder(
        parse_constant=lambda token: (_ for _ in ()).throw(
            ValueError(f"non-finite JSON token {token}")
        )
    )
    try:
        value, _ = decoder.raw_decode(source, marker.end())
    except (json.JSONDecodeError, ValueError) as error:
        raise ForceReleaseError(f"generated viewer has invalid {name} JSON: {error}") from error
    return value


def _identity_hash(value: Any) -> str:
    return parts._sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _source_identities(source_root: Path) -> dict[str, str]:
    package_root = source_root / "generator" / "domelab_pipeline"
    release_reference = package_root / "release_reference"
    if not package_root.is_dir() or not release_reference.is_dir():
        raise ForceReleaseError("release source has no generator/domelab_pipeline tree")
    generator_sources = {
        path.name: parts._sha256(path)
        for path in sorted(package_root.iterdir(), key=lambda value: value.name)
        if path.is_file() and path.suffix == ".py"
    }
    reference_sources = {
        path.relative_to(release_reference).as_posix(): parts._sha256(path)
        for path in sorted(
            release_reference.rglob("*"),
            key=lambda value: value.relative_to(release_reference).as_posix(),
        )
        if path.is_file()
    }
    if not generator_sources or not reference_sources:
        raise ForceReleaseError("release source identity inputs are empty")
    return {
        "generator_source_hash": _identity_hash(generator_sources),
        "release_reference_hash": _identity_hash(reference_sources),
    }


def _object_differences(old: Any, new: Any, prefix: str = "") -> set[str]:
    if type(old) is not type(new):
        return {prefix or "/"}
    if isinstance(old, dict):
        differences: set[str] = set()
        for key in set(old) | set(new):
            path = f"{prefix}/{key}"
            if key not in old or key not in new:
                differences.add(path)
            else:
                differences.update(_object_differences(old[key], new[key], path))
        return differences
    if isinstance(old, list):
        return set() if old == new else {prefix or "/"}
    return set() if old == new else {prefix or "/"}


def _stage_attestation(
    payloads: Mapping[str, str], source_identities: Mapping[str, str]
) -> dict[str, Any]:
    entries = [
        {
            "path": relative,
            "bytes": len(payloads[relative].encode("utf-8")),
            "sha256": parts._sha256_bytes(payloads[relative].encode("utf-8")),
        }
        for relative in sorted(payloads, key=lambda value: value.encode("utf-8"))
    ]
    schema = json.loads(payloads["schema_meta.staged.json"])
    return {
        "validation": "byte_identical_full_regeneration_from_declared_source_and_cache",
        "artifact_count": len(entries),
        "bytes": sum(row["bytes"] for row in entries),
        "tree_sha256": parts._sha256_bytes(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "sealed_generated_manifest_sha256": parts._sha256_bytes(
            payloads["generated_manifest.json"].encode("utf-8")
        ),
        "schema_meta_sha256": parts._sha256_bytes(
            payloads["schema_meta.staged.json"].encode("utf-8")
        ),
        "exclusion_manifest_sha256": parts._sha256_bytes(
            payloads["exclusion_manifest.json"].encode("utf-8")
        ),
        "parity_report_sha256": parts._sha256_bytes(
            payloads["parity_report.json"].encode("utf-8")
        ),
        "viewer_sha256": parts._sha256_bytes(
            payloads["packs/viewer.staged.html"].encode("utf-8")
        ),
        "viewer_vtests_sha256": parts._sha256_bytes(
            payloads["packs/viewer_vtests.json"].encode("utf-8")
        ),
        "config_hash": schema["config_hash"],
        **source_identities,
        "published_generated_tree": "composed_hybrid",
        "published_from_stage": [
            "exclusion_manifest.json",
            "packs/viewer.staged.html",
            "packs/viewer_vtests.json",
            "schema_meta.staged.json",
        ],
        "preserved_from_lib61_base": ["packs/picker.staged.html"],
    }


def _regenerate_release_stage(
    source_root: Path, cache_root: Path, repo_commit: str, parity_payload: str
) -> dict[str, str]:
    """Regenerate through source and reattach the byte-preserved parity proof.

    Parity itself was already generated and sealed by the supplied full stage;
    it is unchanged from lib-6.1.  Running the scientific generator with
    ``--no-parity`` makes standalone verification independent of an installed
    Node/jsdom runtime.  The preserved parity payload is then reattached and
    the canonical full-stage manifest is reconstructed byte-for-byte.
    """
    generator_root = source_root / "generator"
    if not (generator_root / "domelab_pipeline" / "pipeline.py").is_file():
        raise ForceReleaseError("declared release source has no generator pipeline")
    with tempfile.TemporaryDirectory(prefix="fc35-regenerate-") as parent:
        output = Path(parent) / "stage"
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        prior_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = os.pathsep.join(
            [os.fspath(generator_root), prior_pythonpath]
            if prior_pythonpath
            else [os.fspath(generator_root)]
        )
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "domelab_pipeline.cli",
                "--cache",
                os.fspath(cache_root),
                "--commit",
                repo_commit,
                "--out",
                os.fspath(output),
                "--viewer-profile",
                "release",
                "--no-parity",
                "--write",
            ],
            cwd=source_root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise ForceReleaseError(
                "full source regeneration failed: "
                f"exit={result.returncode}; stdout={result.stdout[-1000:]!r}; "
                f"stderr={result.stderr[-2000:]!r}"
            )
        files = _scan_regular_files(output)
        payloads: dict[str, str] = {}
        for relative, path in files.items():
            try:
                payloads[relative] = _read_utf8_exact(
                    path, f"regenerated artifact {relative}"
                )
            except (OSError, UnicodeError) as error:
                raise ForceReleaseError(
                    f"regenerated artifact is not UTF-8 text: {relative}: {error}"
                ) from error
        payloads.pop("generated_manifest.json", None)
        payloads["parity_report.json"] = parity_payload
        manifest = {
            relative: parts._sha256_bytes(payload.encode("utf-8"))
            for relative, payload in payloads.items()
        }
        payloads["generated_manifest.json"] = (
            json.dumps(manifest, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
        )
        return payloads


def _validate_stage_metadata(
    payloads: Mapping[str, str],
    *,
    source_identities: Mapping[str, str],
    predecessor_files: Mapping[str, Path] | None,
    evidence_hash: str,
    repo_commit: str,
) -> None:
    missing = sorted(REQUIRED_STAGE_FILES - set(payloads))
    if missing:
        raise ForceReleaseError(f"fc-3.5 staging is missing required paths: {missing}")
    schema = json.loads(payloads["schema_meta.staged.json"])
    exclusion = json.loads(payloads["exclusion_manifest.json"])
    parity = json.loads(payloads["parity_report.json"])
    raw_manifest = json.loads(payloads["raw_path_manifest.json"])
    curve_provenance = json.loads(payloads["curve_pack_provenance.json"])
    bench_tests = json.loads(payloads["bench_tests.staged.json"])
    vtests = json.loads(payloads["packs/viewer_vtests.json"])
    if not isinstance(schema, dict) or not isinstance(schema.get("provenance_hashes"), dict):
        raise ForceReleaseError("schema_meta.staged.json has no provenance hashes")
    provenance = schema["provenance_hashes"]
    for key, expected in source_identities.items():
        if provenance.get(key) != expected:
            raise ForceReleaseError(f"staged schema is not bound to current {key}")
    if schema.get("config_hash") != provenance.get("bundle_hash"):
        raise ForceReleaseError("staged schema config_hash does not equal bundle_hash")
    if (
        provenance.get("evidence_epoch_hash") != evidence_hash
        or (schema.get("evidence_epoch") or {}).get("identity") != evidence_hash
        or schema.get("repo_commit") != repo_commit
    ):
        raise ForceReleaseError("staged schema targets a different evidence epoch")
    if (
        not isinstance(exclusion, dict)
        or exclusion.get("artifact_role") != "canonical_retention_authority"
        or exclusion.get("release_eligible") is not True
        or exclusion.get("repo_commit") != repo_commit
        or exclusion.get("config_hash") != schema.get("config_hash")
    ):
        raise ForceReleaseError("staged exclusion manifest has inconsistent authority")
    if predecessor_files is not None:
        old_exclusion = _read_json(
            predecessor_files[GENERATED_EXCLUSION_PATH], "base exclusion manifest"
        )
        if _object_differences(old_exclusion, exclusion) != {"/config_hash"}:
            raise ForceReleaseError(
                "staged exclusion manifest must preserve every field except config_hash"
            )
        old_schema = _read_json(
            predecessor_files[GENERATED_SCHEMA_PATH], "base schema metadata"
        )
        allowed_schema_changes = {
            "/config_hash",
            "/provenance_hashes/bundle_hash",
            "/provenance_hashes/generator_source_hash",
            "/provenance_hashes/release_reference_hash",
        }
        if _object_differences(old_schema, schema) != allowed_schema_changes:
            raise ForceReleaseError(
                "staged schema changed outside presentation/source identity fields"
            )
    if (
        not isinstance(parity, dict)
        or parity.get("artifact_role") != "canonical_retention_authority"
        or parity.get("release_eligible") is not True
        or parity.get("exact_null_flag_audit_match") is not True
        or not isinstance(parity.get("rows"), list)
        or not parity["rows"]
        or not isinstance(parity.get("max_abs_delta"), (int, float))
        or not isinstance(parity.get("max_audit_abs_delta"), (int, float))
        or parity["max_abs_delta"] > 1e-9
        or parity["max_audit_abs_delta"] > 1e-9
    ):
        raise ForceReleaseError("staged parity report does not pass release tolerances")
    if (
        not isinstance(raw_manifest, dict)
        or raw_manifest.get("repo_commit") != repo_commit
        or not isinstance(curve_provenance, dict)
        or curve_provenance.get("repo_commit") != repo_commit
        or curve_provenance.get("evidence_epoch_hash") != evidence_hash
    ):
        raise ForceReleaseError("staged data provenance does not match the frozen source")
    if not isinstance(bench_tests, list) or not isinstance(vtests, list) or len(bench_tests) != len(vtests):
        raise ForceReleaseError("staged bench records and viewer records have different counts")
    viewer = payloads["packs/viewer.staged.html"]
    if _extract_json_constant(viewer, "VTESTS") != vtests:
        raise ForceReleaseError("viewer VTESTS blob differs from viewer_vtests.json")
    if _extract_json_constant(viewer, "EMBEDDED") != json.loads(
        payloads["packs/viewer_embedded.json"]
    ):
        raise ForceReleaseError("viewer EMBEDDED blob differs from viewer_embedded.json")
    perception_pack = json.loads(payloads["packs/perception_scores.json"])
    if (
        not isinstance(perception_pack, dict)
        or _extract_json_constant(viewer, "PERCEPTION_MODEL")
        != perception_pack.get("model")
    ):
        raise ForceReleaseError("viewer perception model differs from perception_scores.json")


def _validate_full_stage(
    stage_files: Mapping[str, Path],
    *,
    source_root: Path,
    base_root: Path,
    predecessor_files: Mapping[str, Path],
    evidence_hash: str,
    repo_commit: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    try:
        parts._validate_generated_manifest(stage_files)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(f"staged generated manifest failed: {error}") from error
    source_identities = _source_identities(source_root)
    payloads: dict[str, str] = {}
    for relative, path in stage_files.items():
        try:
            payloads[relative] = _read_utf8_exact(
                path, f"staged artifact {relative}"
            )
        except (OSError, UnicodeError) as error:
            raise ForceReleaseError(f"staged artifact is not UTF-8 text: {relative}: {error}") from error
    _validate_stage_metadata(
        payloads,
        source_identities=source_identities,
        predecessor_files=predecessor_files,
        evidence_hash=evidence_hash,
        repo_commit=repo_commit,
    )
    cache_root = base_root / "canonical-evidence" / "raw_cache" / f"repo-{repo_commit}"
    if not cache_root.is_dir():
        raise ForceReleaseError(f"frozen regeneration cache is missing: {cache_root}")
    parity_path = predecessor_files.get(GENERATED_PARITY_PATH)
    if parity_path is None:
        raise ForceReleaseError("lib-6.1 base has no parity_report.json")
    if stage_files["parity_report.json"].read_bytes() != parity_path.read_bytes():
        raise ForceReleaseError("fc-3.5 parity report is not byte-identical to the verified base")
    expected = _regenerate_release_stage(
        source_root,
        cache_root,
        repo_commit,
        _read_utf8_exact(parity_path, "lib-6.1 parity report"),
    )
    if set(expected) != set(payloads):
        raise ForceReleaseError("staging inventory differs from a full source regeneration")
    for relative in sorted(expected):
        if expected[relative] != payloads[relative]:
            raise ForceReleaseError(
                f"staged artifact is not byte-identical to full regeneration: {relative}"
            )
    return expected, _stage_attestation(expected, source_identities)


def _base_contract(base_files: Mapping[str, Path]) -> dict[str, Any]:
    required = {
        SITE_MANIFEST_NAME,
        SHA256SUMS_NAME,
        HISTORICAL_FORCE_MANIFEST_NAME,
        ROOT_VIEWER_PATH,
        ROOT_PARTS_PATH,
        "dome-lab.html",
        "ec-switch-explorer.html",
        GENERATED_MANIFEST_PATH,
        GENERATED_VIEWER_PATH,
        GENERATED_VTESTS_PATH,
        GENERATED_PICKER_PATH,
        GENERATED_SCHEMA_PATH,
        GENERATED_EXCLUSION_PATH,
        GENERATED_PARITY_PATH,
        "canonical-evidence/EPOCH_MANIFEST.json",
    }
    missing = sorted(required - set(base_files))
    if missing:
        raise ForceReleaseError(f"base site release is missing required paths: {missing}")
    if PREDECESSOR_SITE_MANIFEST_NAME in base_files:
        raise ForceReleaseError(
            f"base site already contains reserved path: {PREDECESSOR_SITE_MANIFEST_NAME}"
        )
    if parts._sha256(base_files[SITE_MANIFEST_NAME]) != PREDECESSOR_SITE_MANIFEST_SHA256:
        raise ForceReleaseError("base site manifest does not match the pinned predecessor")
    if parts._sha256(base_files[SHA256SUMS_NAME]) != PREDECESSOR_SHA256SUMS_SHA256:
        raise ForceReleaseError("base SHA256SUMS does not match the pinned predecessor")
    manifest = _read_json(base_files[SITE_MANIFEST_NAME], "base site manifest")
    if not isinstance(manifest, dict) or manifest.get("package_id") != parts.PACKAGE_ID:
        raise ForceReleaseError("verified base has the wrong lib-6.1 site identity")
    rows = _manifest_rows(manifest, "base site manifest")
    payload = set(base_files) - {SITE_MANIFEST_NAME, SHA256SUMS_NAME}
    if set(rows) != payload:
        raise ForceReleaseError("base site manifest has missing or extra package paths")
    for relative, row in rows.items():
        path = base_files[relative]
        if path.stat().st_size != row["bytes"] or parts._sha256(path) != row["sha256"]:
            raise ForceReleaseError(f"base site payload mismatch: {relative}")
    tool_builds = manifest.get("tool_builds")
    if not isinstance(tool_builds, dict):
        raise ForceReleaseError("base site manifest has no tool-build identities")
    force = tool_builds.get("force_curve_bench")
    picker = tool_builds.get("ec_parts_library")
    explorer = tool_builds.get("ec_switch_explorer")
    if not isinstance(force, dict) or force.get("build") != parts.FORCE_BUILD:
        raise ForceReleaseError("verified base does not contain Force Curve Bench fc-3.4")
    if not isinstance(picker, dict) or picker.get("build") != PARTS_BUILD:
        raise ForceReleaseError("verified base does not contain EC Parts Library lib-6.1")
    if not isinstance(explorer, dict):
        raise ForceReleaseError("verified base has no EC Switch Explorer identity")
    if picker.get("sha256") != parts._sha256(base_files[ROOT_PARTS_PATH]):
        raise ForceReleaseError("base Parts Library identity does not match its entry point")
    if base_files[ROOT_PARTS_PATH].read_bytes() != base_files[GENERATED_PICKER_PATH].read_bytes():
        raise ForceReleaseError("base root Parts Library is not byte-identical to its picker")
    evidence = manifest.get("evidence_identity")
    if (
        not isinstance(evidence, dict)
        or not isinstance(evidence.get("evidence_epoch_hash"), str)
        or not HEX64.fullmatch(evidence["evidence_epoch_hash"])
    ):
        raise ForceReleaseError("base site manifest has no valid evidence identity")
    publication = manifest.get("publication")
    if not isinstance(publication, dict):
        raise ForceReleaseError("base site manifest has no publication identity")
    return {
        "manifest": manifest,
        "rows": rows,
        "evidence": evidence,
        "force": force,
        "picker": picker,
        "explorer": explorer,
        "publication": publication,
    }


def _historical_raw_paths(files: Mapping[str, Path]) -> set[str]:
    manifest = _read_json(
        files[HISTORICAL_FORCE_MANIFEST_NAME], "historical fc-3.4 manifest"
    )
    if not isinstance(manifest, dict) or manifest.get("bench_build") != parts.FORCE_BUILD:
        raise ForceReleaseError("historical Force Curve Bench manifest has the wrong identity")
    rows = _manifest_rows(manifest, "historical fc-3.4 manifest")
    raw = {
        relative
        for relative, row in rows.items()
        if relative.casefold().endswith(".csv")
        and row.get("component") == "frozen_repository"
    }
    if not raw:
        raise ForceReleaseError("historical Force Curve Bench manifest names no raw CSVs")
    for relative in raw:
        path = files.get(relative)
        row = rows[relative]
        if path is None or path.stat().st_size != row["bytes"] or parts._sha256(path) != row["sha256"]:
            raise ForceReleaseError(f"historical raw CSV identity mismatch: {relative}")
    return raw


def _write_generated_manifest(generated_root: Path) -> None:
    files = _scan_regular_files(generated_root)
    files.pop("generated_manifest.json", None)
    payload = {
        relative: parts._sha256(path)
        for relative, path in sorted(files.items(), key=lambda row: row[0].encode("utf-8"))
    }
    parts._write_exclusive(
        generated_root / "generated_manifest.json", parts._json_bytes(payload)
    )


def _tree_summary(files: Mapping[str, Path]) -> dict[str, Any]:
    return parts._tree_summary(files)


def _component_for(
    relative: str, overlay_paths: set[str], raw_paths: set[str]
) -> str:
    if relative == ROOT_VIEWER_PATH:
        return "force_curve_entrypoint"
    if relative in GENERATED_MUTABLE:
        return "force_curve_generated"
    if relative == PREDECESSOR_SITE_MANIFEST_NAME:
        return "predecessor_site_record"
    if relative == COMPONENT_MANIFEST_NAME:
        return "force_curve_component_manifest"
    if relative in overlay_paths:
        return "force_curve_overlay"
    if relative in {ROOT_PARTS_PATH, GENERATED_PICKER_PATH}:
        return "parts_library_preserved"
    if relative.startswith("canonical-evidence/"):
        return "canonical_evidence_preserved"
    if relative in raw_paths:
        return "raw_test_preserved"
    if relative == HISTORICAL_FORCE_MANIFEST_NAME:
        return "fc34_historical_record"
    return "base_site_preserved"


def _payload_rows(
    root: Path, overlay_paths: set[str], raw_paths: set[str]
) -> list[dict[str, Any]]:
    rows = []
    for relative, path in sorted(
        _scan_regular_files(root).items(), key=lambda row: row[0].encode("utf-8")
    ):
        if relative in {SITE_MANIFEST_NAME, SHA256SUMS_NAME}:
            continue
        rows.append(
            {
                "path": relative,
                "component": _component_for(relative, overlay_paths, raw_paths),
                "bytes": path.stat().st_size,
                "sha256": parts._sha256(path),
            }
        )
    return rows


def _overlay_rows(
    policy: Mapping[str, Any],
    source_files: Mapping[str, Path],
    predecessor_rows: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for relative in policy["overlay_paths"]:
        old = predecessor_rows.get(relative)
        rows.append(
            {
                "path": relative,
                "base_sha256": old["sha256"] if old is not None else None,
                "release_sha256": parts._sha256(source_files[relative]),
                "operation": "replace" if old is not None else "add",
            }
        )
    return rows


def _build_component_manifest(
    root: Path,
    *,
    predecessor: Mapping[str, Any],
    viewer_build: Mapping[str, Any],
    stage_attestation: Mapping[str, Any],
    canonical_url: str,
    git_tag: str,
) -> dict[str, Any]:
    files = _scan_regular_files(root)
    published_policy = _load_policy(files[POLICY_PACKAGE_PATH])
    component_paths = {
        *published_policy["overlay_paths"],
        ROOT_VIEWER_PATH,
        GENERATED_MANIFEST_PATH,
        GENERATED_VIEWER_PATH,
        GENERATED_VTESTS_PATH,
        GENERATED_SCHEMA_PATH,
        GENERATED_EXCLUSION_PATH,
    }
    missing = sorted(set(component_paths) - set(files))
    if missing:
        raise ForceReleaseError(f"cannot build fc-3.5 component manifest: {missing}")
    rows = [
        {
            "path": relative,
            "component": (
                "public_entrypoint"
                if relative == ROOT_VIEWER_PATH
                else "social_preview"
                if relative == OG_IMAGE_PATH
                else "release_policy"
                if relative == POLICY_PACKAGE_PATH
                else "generated_hybrid"
                if relative.startswith("generated/")
                else "viewer_overlay"
            ),
            "bytes": files[relative].stat().st_size,
            "sha256": parts._sha256(files[relative]),
        }
        for relative in sorted(component_paths, key=lambda value: value.encode("utf-8"))
    ]
    return {
        "manifest_version": 1,
        "package_id": COMPONENT_PACKAGE_ID,
        "artifact_role": "public_force_curve_bench_release",
        "release_eligible": True,
        "bench_build": viewer_build["bench_build"],
        "publication": {
            "canonical_public_url": canonical_url,
            "git_tag": git_tag,
        },
        "evidence_identity": {
            "evidence_epoch_hash": predecessor["evidence"]["evidence_epoch_hash"],
            "data_repo_commit": viewer_build["repo_commit"],
            "status": "preserved_byte_identical",
        },
        "predecessors": {
            "fc34_manifest_path": HISTORICAL_FORCE_MANIFEST_NAME,
            "fc34_manifest_sha256": parts._sha256(
                files[HISTORICAL_FORCE_MANIFEST_NAME]
            ),
            "site_manifest_path": PREDECESSOR_SITE_MANIFEST_NAME,
            "site_manifest_sha256": parts._sha256(
                files[PREDECESSOR_SITE_MANIFEST_NAME]
            ),
        },
        "parts_library_continuity": {
            "build": PARTS_BUILD,
            "root_path": ROOT_PARTS_PATH,
            "root_sha256": parts._sha256(files[ROOT_PARTS_PATH]),
            "generated_path": GENERATED_PICKER_PATH,
            "generated_sha256": parts._sha256(files[GENERATED_PICKER_PATH]),
            "status": "preserved_byte_identical",
        },
        "generation_attestation": dict(stage_attestation),
        "generated_tree": {
            "composition": "hybrid",
            "new_from_fc35_stage": [
                GENERATED_EXCLUSION_PATH,
                GENERATED_SCHEMA_PATH,
                GENERATED_VIEWER_PATH,
                GENERATED_VTESTS_PATH,
            ],
            "resealed": GENERATED_MANIFEST_PATH,
            "preserved_from_lib61_base": [GENERATED_PICKER_PATH],
        },
        "files": rows,
    }


def _generated_difference_rows(
    predecessor_rows: Mapping[str, Mapping[str, Any]], files: Mapping[str, Path]
) -> list[dict[str, Any]]:
    rows = []
    for relative in sorted(GENERATED_MUTABLE, key=lambda value: value.encode("utf-8")):
        old = predecessor_rows.get(relative)
        new = files.get(relative)
        if old is None or new is None:
            raise ForceReleaseError(f"generated transition path is missing: {relative}")
        digest = parts._sha256(new)
        if old["bytes"] == new.stat().st_size and old["sha256"] == digest:
            raise ForceReleaseError(f"fc-3.5 generated artifact did not change: {relative}")
        rows.append(
            {
                "path": relative,
                "base_sha256": old["sha256"],
                "release_sha256": digest,
                "operation": "replace",
            }
        )
    return rows


def _build_manifest(
    root: Path,
    *,
    base_files: Mapping[str, Path],
    predecessor: Mapping[str, Any],
    policy: Mapping[str, Any],
    policy_path: Path,
    source_files: Mapping[str, Path],
    viewer_build: Mapping[str, Any],
    stage_attestation: Mapping[str, Any],
    canonical_url: str,
    git_tag: str,
) -> dict[str, Any]:
    files = _scan_regular_files(root)
    raw_paths = _historical_raw_paths(files)
    overlay_paths = set(policy["overlay_paths"])
    canonical_files = {
        relative.removeprefix("canonical-evidence/"): path
        for relative, path in files.items()
        if relative.startswith("canonical-evidence/")
    }
    raw_files = {relative: files[relative] for relative in sorted(raw_paths)}
    parts_files = {
        ROOT_PARTS_PATH: files[ROOT_PARTS_PATH],
        GENERATED_PICKER_PATH: files[GENERATED_PICKER_PATH],
    }
    return {
        "manifest_version": MANIFEST_VERSION,
        "package_id": PACKAGE_ID,
        "artifact_role": ARTIFACT_ROLE,
        "release_eligible": True,
        "publication": {
            "canonical_public_url": canonical_url,
            "git_tag": git_tag,
        },
        "predecessor_site_release": {
            "package_id": predecessor["manifest"]["package_id"],
            "git_tag": predecessor["publication"].get("git_tag"),
            "manifest_path": PREDECESSOR_SITE_MANIFEST_NAME,
            "manifest_sha256": parts._sha256(base_files[SITE_MANIFEST_NAME]),
            "sha256sums_sha256": parts._sha256(base_files[SHA256SUMS_NAME]),
            "force_build": predecessor["force"]["build"],
            "parts_build": predecessor["picker"]["build"],
            "verification": "verified before overlay with the lib-6.1 site verifier",
        },
        "tool_builds": {
            "force_curve_bench": {
                "build": viewer_build["bench_build"],
                "path": ROOT_VIEWER_PATH,
                "sha256": parts._sha256(files[ROOT_VIEWER_PATH]),
                "presentation_role": viewer_build["presentation_role"],
                "release_eligible": viewer_build["release_eligible"],
                "data_repo_commit": viewer_build["repo_commit"],
                "data_identity": viewer_build["data_identity"],
            },
            "ec_parts_library": predecessor["picker"],
            "ec_switch_explorer": predecessor["explorer"],
        },
        "component_manifests": {
            "force_curve_bench": {
                "path": COMPONENT_MANIFEST_NAME,
                "package_id": COMPONENT_PACKAGE_ID,
                "bench_build": FORCE_BUILD,
                "sha256": parts._sha256(files[COMPONENT_MANIFEST_NAME]),
            },
            "historical_fc34": {
                "path": HISTORICAL_FORCE_MANIFEST_NAME,
                "sha256": parts._sha256(files[HISTORICAL_FORCE_MANIFEST_NAME]),
                "status": "preserved_byte_identical",
            },
        },
        "evidence_identity": {
            "path": "canonical-evidence",
            "evidence_epoch_hash": predecessor["evidence"]["evidence_epoch_hash"],
            "tree": _tree_summary(canonical_files),
            "status": "preserved_byte_identical",
        },
        "generation_attestation": dict(stage_attestation),
        "protection_contract": {
            "parts_library": _tree_summary(parts_files),
            "raw_csv_paths": _tree_summary(raw_files),
            "canonical_evidence": _tree_summary(canonical_files),
            "historical_force_manifest_sha256": parts._sha256(
                files[HISTORICAL_FORCE_MANIFEST_NAME]
            ),
            "dome_lab_legacy_sha256": parts._sha256(files["dome-lab.html"]),
            "ec_switch_explorer_sha256": parts._sha256(
                files["ec-switch-explorer.html"]
            ),
        },
        "overlay": {
            "policy_version": policy["policy_version"],
            "policy_name": policy["name"],
            "policy_sha256": parts._sha256(policy_path),
            "paths": _overlay_rows(policy, source_files, predecessor["rows"]),
            "generated_allowed_differences": _generated_difference_rows(
                predecessor["rows"], files
            ),
            "root_viewer_source": GENERATED_VIEWER_PATH,
            "predecessor_site_record": PREDECESSOR_SITE_MANIFEST_NAME,
        },
        "inventory": {
            "manifest_path": SITE_MANIFEST_NAME,
            "manifest_scope": (
                f"all regular files except {SITE_MANIFEST_NAME} and {SHA256SUMS_NAME}"
            ),
            "sha256sums_path": SHA256SUMS_NAME,
            "sha256sums_scope": f"all regular files except {SHA256SUMS_NAME}",
        },
        "files": _payload_rows(root, overlay_paths, raw_paths),
    }


def _validate_manifest_identity(manifest: Mapping[str, Any]) -> tuple[str, str]:
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ForceReleaseError("site manifest has the wrong version")
    if manifest.get("package_id") != PACKAGE_ID or manifest.get("artifact_role") != ARTIFACT_ROLE:
        raise ForceReleaseError("site manifest has the wrong package identity")
    if manifest.get("release_eligible") is not True:
        raise ForceReleaseError("site manifest is not release-eligible")
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or set(publication) != {
        "canonical_public_url",
        "git_tag",
    }:
        raise ForceReleaseError("site manifest has an invalid publication identity")
    try:
        canonical_url = parts._validate_url(publication["canonical_public_url"])
        git_tag = parts._validate_tag(
            publication["git_tag"]
        )
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error
    if canonical_url != CANONICAL_PUBLIC_URL or git_tag != RELEASE_GIT_TAG:
        raise ForceReleaseError("site manifest has the wrong fc-3.5 publication identity")
    return canonical_url, git_tag


def _expected_overlay(
    overlay: Any,
    predecessor_rows: Mapping[str, Mapping[str, Any]],
    files: Mapping[str, Path],
) -> set[str]:
    expected_fields = {
        "policy_version",
        "policy_name",
        "policy_sha256",
        "paths",
        "generated_allowed_differences",
        "root_viewer_source",
        "predecessor_site_record",
    }
    if not isinstance(overlay, dict) or set(overlay) != expected_fields:
        raise ForceReleaseError("site manifest has an invalid overlay contract")
    if overlay["policy_version"] != POLICY_VERSION:
        raise ForceReleaseError("site manifest has the wrong overlay-policy version")
    if not isinstance(overlay["policy_name"], str) or not overlay["policy_name"].strip():
        raise ForceReleaseError("site manifest has no overlay-policy name")
    if not isinstance(overlay["policy_sha256"], str) or not HEX64.fullmatch(
        overlay["policy_sha256"]
    ):
        raise ForceReleaseError("site manifest has an invalid overlay-policy hash")
    if overlay["root_viewer_source"] != GENERATED_VIEWER_PATH:
        raise ForceReleaseError("site manifest has the wrong root-viewer source")
    if overlay["predecessor_site_record"] != PREDECESSOR_SITE_MANIFEST_NAME:
        raise ForceReleaseError("site manifest has the wrong predecessor-site record")
    policy_file = files.get(POLICY_PACKAGE_PATH)
    if policy_file is None:
        raise ForceReleaseError("published Force viewer overlay policy is missing")
    policy = _load_policy(policy_file)
    if parts._sha256(policy_file) != overlay["policy_sha256"]:
        raise ForceReleaseError("published overlay policy hash does not match the manifest")
    rows = overlay["paths"]
    if not isinstance(rows, list) or not rows:
        raise ForceReleaseError("site manifest has no overlay paths")
    if rows != sorted(rows, key=lambda row: str(row.get("path", "")).encode("utf-8")):
        raise ForceReleaseError("site-manifest overlay paths are not in canonical order")
    paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "path",
            "base_sha256",
            "release_sha256",
            "operation",
        }:
            raise ForceReleaseError("site manifest contains an invalid overlay-path row")
        relative = _normalize_relative(row["path"], "site overlay path")
        if relative in paths or _overlay_path_is_protected(relative):
            raise ForceReleaseError(f"invalid site overlay path: {relative}")
        paths.add(relative)
        old = predecessor_rows.get(relative)
        current = files.get(relative)
        if current is None or row != {
            "path": relative,
            "base_sha256": old["sha256"] if old is not None else None,
            "release_sha256": parts._sha256(current),
            "operation": "replace" if old is not None else "add",
        }:
            raise ForceReleaseError(f"site overlay identity mismatch: {relative}")
    if paths != set(policy["overlay_paths"]):
        raise ForceReleaseError("site manifest overlay paths differ from the published policy")
    missing_required_overlay = sorted(REQUIRED_OVERLAY_PATHS - paths)
    if missing_required_overlay:
        raise ForceReleaseError(
            "overlay policy omits required fc-3.5 paths: "
            f"{missing_required_overlay}"
        )
    generated = overlay["generated_allowed_differences"]
    expected_generated = _generated_difference_rows(predecessor_rows, files)
    if generated != expected_generated:
        raise ForceReleaseError("site generated-difference contract is inconsistent")
    return paths


def verify_force_curve_release(package_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = _resolve_directory(package_root, "Force Curve Bench site release")
    files = _scan_regular_files(root)
    required = {
        SITE_MANIFEST_NAME,
        SHA256SUMS_NAME,
        PREDECESSOR_SITE_MANIFEST_NAME,
        HISTORICAL_FORCE_MANIFEST_NAME,
        COMPONENT_MANIFEST_NAME,
        ROOT_VIEWER_PATH,
        ROOT_PARTS_PATH,
        "dome-lab.html",
        "ec-switch-explorer.html",
        GENERATED_MANIFEST_PATH,
        GENERATED_VIEWER_PATH,
        GENERATED_VTESTS_PATH,
        GENERATED_PICKER_PATH,
        GENERATED_SCHEMA_PATH,
        GENERATED_EXCLUSION_PATH,
        GENERATED_PARITY_PATH,
        OG_IMAGE_PATH,
        POLICY_PACKAGE_PATH,
        "canonical-evidence/EPOCH_MANIFEST.json",
    }
    missing = sorted(required - set(files))
    if missing:
        raise ForceReleaseError(f"site release is missing required paths: {missing}")

    manifest = _read_json(files[SITE_MANIFEST_NAME], "site release manifest")
    if not isinstance(manifest, dict):
        raise ForceReleaseError("site release manifest must be an object")
    canonical_url, git_tag = _validate_manifest_identity(manifest)
    declared = _manifest_rows(manifest, "site release manifest")
    payload = set(files) - {SITE_MANIFEST_NAME, SHA256SUMS_NAME}
    if set(declared) != payload:
        raise ForceReleaseError("site manifest has missing or extra package paths")

    predecessor_manifest = _read_json(
        files[PREDECESSOR_SITE_MANIFEST_NAME], "predecessor site manifest"
    )
    if not isinstance(predecessor_manifest, dict):
        raise ForceReleaseError("predecessor site manifest must be an object")
    predecessor_rows = _manifest_rows(predecessor_manifest, "predecessor site manifest")
    predecessor_tools = predecessor_manifest.get("tool_builds")
    predecessor_publication = predecessor_manifest.get("publication")
    predecessor_evidence = predecessor_manifest.get("evidence_identity")
    if (
        predecessor_manifest.get("package_id") != parts.PACKAGE_ID
        or not isinstance(predecessor_tools, dict)
        or not isinstance(predecessor_publication, dict)
        or not isinstance(predecessor_evidence, dict)
    ):
        raise ForceReleaseError("predecessor site record has the wrong lib-6.1 identity")
    predecessor_force = predecessor_tools.get("force_curve_bench")
    predecessor_picker = predecessor_tools.get("ec_parts_library")
    predecessor_explorer = predecessor_tools.get("ec_switch_explorer")
    if (
        not isinstance(predecessor_force, dict)
        or predecessor_force.get("build") != parts.FORCE_BUILD
        or not isinstance(predecessor_picker, dict)
        or predecessor_picker.get("build") != PARTS_BUILD
        or not isinstance(predecessor_explorer, dict)
    ):
        raise ForceReleaseError("predecessor site record has inconsistent tool builds")

    predecessor_identity = manifest.get("predecessor_site_release")
    predecessor_record_sha = parts._sha256(files[PREDECESSOR_SITE_MANIFEST_NAME])
    if predecessor_record_sha != PREDECESSOR_SITE_MANIFEST_SHA256:
        raise ForceReleaseError("predecessor site record is not the pinned e9dde99 manifest")
    expected_predecessor = {
        "package_id": predecessor_manifest["package_id"],
        "git_tag": predecessor_publication.get("git_tag"),
        "manifest_path": PREDECESSOR_SITE_MANIFEST_NAME,
        "manifest_sha256": PREDECESSOR_SITE_MANIFEST_SHA256,
        "sha256sums_sha256": PREDECESSOR_SHA256SUMS_SHA256,
        "force_build": predecessor_force["build"],
        "parts_build": predecessor_picker["build"],
        "verification": "verified before overlay with the lib-6.1 site verifier",
    }
    if predecessor_identity != expected_predecessor:
        raise ForceReleaseError("site manifest predecessor identity is inconsistent")

    overlay_paths = _expected_overlay(manifest.get("overlay"), predecessor_rows, files)
    _validate_subjective_pilot_inventory(root)
    exempt = {
        ROOT_VIEWER_PATH,
        *GENERATED_MUTABLE,
        *overlay_paths,
    }
    for relative, old in predecessor_rows.items():
        if relative in exempt:
            continue
        current = files.get(relative)
        if current is None or current.stat().st_size != old["bytes"] or parts._sha256(current) != old["sha256"]:
            raise ForceReleaseError(f"preserved base-site path changed: {relative}")
    expected_added = {
        relative for relative in overlay_paths if relative not in predecessor_rows
    } | {PREDECESSOR_SITE_MANIFEST_NAME, COMPONENT_MANIFEST_NAME}
    actual_added = payload - set(predecessor_rows)
    if actual_added != expected_added:
        raise ForceReleaseError(
            f"release contains undeclared added paths: {sorted(actual_added - expected_added)}"
        )

    raw_paths = _historical_raw_paths(files)
    for relative in raw_paths:
        old = predecessor_rows.get(relative)
        current = files.get(relative)
        if old is None or current is None or old["sha256"] != parts._sha256(current):
            raise ForceReleaseError(f"raw CSV continuity failed: {relative}")
    canonical_paths = {
        relative for relative in predecessor_rows if relative.startswith("canonical-evidence/")
    }
    if not canonical_paths:
        raise ForceReleaseError("predecessor site record names no canonical evidence")
    for relative in canonical_paths:
        current = files.get(relative)
        if current is None or predecessor_rows[relative]["sha256"] != parts._sha256(current):
            raise ForceReleaseError(f"canonical evidence continuity failed: {relative}")

    for relative in payload:
        row = declared[relative]
        if set(row) != {"path", "component", "bytes", "sha256"}:
            raise ForceReleaseError(f"invalid site-manifest file row: {relative}")
        expected_component = _component_for(relative, overlay_paths, raw_paths)
        path = files[relative]
        if (
            row["component"] != expected_component
            or row["bytes"] != path.stat().st_size
            or row["sha256"] != parts._sha256(path)
        ):
            raise ForceReleaseError(f"site release payload mismatch: {relative}")

    try:
        sums = parts._parse_sha256sums(files[SHA256SUMS_NAME])
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error
    if set(sums) != set(files) - {SHA256SUMS_NAME}:
        raise ForceReleaseError("SHA256SUMS has missing or extra package paths")
    for relative, digest in sums.items():
        if digest != parts._sha256(files[relative]):
            raise ForceReleaseError(f"SHA256SUMS mismatch: {relative}")

    if files[ROOT_VIEWER_PATH].read_bytes() != files[GENERATED_VIEWER_PATH].read_bytes():
        raise ForceReleaseError("root Force viewer is not byte-identical to generated viewer")
    if files[ROOT_PARTS_PATH].read_bytes() != files[GENERATED_PICKER_PATH].read_bytes():
        raise ForceReleaseError("root Parts Library is not byte-identical to generated picker")
    for relative in (ROOT_PARTS_PATH, GENERATED_PICKER_PATH):
        old = predecessor_rows.get(relative)
        if old is None or old["sha256"] != parts._sha256(files[relative]):
            raise ForceReleaseError(f"lib-6.1 byte continuity failed: {relative}")
    old_historical = predecessor_rows.get(HISTORICAL_FORCE_MANIFEST_NAME)
    if old_historical is None or old_historical["sha256"] != parts._sha256(
        files[HISTORICAL_FORCE_MANIFEST_NAME]
    ):
        raise ForceReleaseError("historical fc-3.4 manifest changed")

    generated_files = {
        relative.removeprefix("generated/"): path
        for relative, path in files.items()
        if relative.startswith("generated/")
    }
    try:
        parts._validate_generated_manifest(generated_files)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error
    viewer_build = _parse_viewer_build(files[GENERATED_VIEWER_PATH])
    _validate_vtests(files[GENERATED_VTESTS_PATH], viewer_build)
    evidence_hash = predecessor_evidence.get("evidence_epoch_hash")
    if (
        viewer_build["canonical_evidence_identity"] != evidence_hash
        or viewer_build["data_identity"] != evidence_hash
        or viewer_build["repo_commit"] != predecessor_picker.get("data_repo_commit")
    ):
        raise ForceReleaseError("fc-3.5 viewer is not bound to the preserved evidence epoch")

    source_identities = _source_identities(root)
    before_regeneration = parts._entries(files)
    cache_root = (
        root
        / "canonical-evidence"
        / "raw_cache"
        / f"repo-{viewer_build['repo_commit']}"
    )
    if not cache_root.is_dir():
        raise ForceReleaseError(f"frozen regeneration cache is missing: {cache_root}")
    regenerated = _regenerate_release_stage(
        root,
        cache_root,
        viewer_build["repo_commit"],
        _read_utf8_exact(files[GENERATED_PARITY_PATH], "published parity report"),
    )
    _validate_stage_metadata(
        regenerated,
        source_identities=source_identities,
        predecessor_files=None,
        evidence_hash=evidence_hash,
        repo_commit=viewer_build["repo_commit"],
    )
    expected_attestation = _stage_attestation(regenerated, source_identities)
    if manifest.get("generation_attestation") != expected_attestation:
        raise ForceReleaseError("site manifest generation attestation is inconsistent")
    expected_component_manifest = _build_component_manifest(
        root,
        predecessor={"evidence": predecessor_evidence},
        viewer_build=viewer_build,
        stage_attestation=expected_attestation,
        canonical_url=canonical_url,
        git_tag=git_tag,
    )
    component_manifest = _read_json(
        files[COMPONENT_MANIFEST_NAME], "fc-3.5 component manifest"
    )
    if component_manifest != expected_component_manifest:
        raise ForceReleaseError("fc-3.5 component manifest is inconsistent")
    expected_component_bindings = {
        "force_curve_bench": {
            "path": COMPONENT_MANIFEST_NAME,
            "package_id": COMPONENT_PACKAGE_ID,
            "bench_build": FORCE_BUILD,
            "sha256": parts._sha256(files[COMPONENT_MANIFEST_NAME]),
        },
        "historical_fc34": {
            "path": HISTORICAL_FORCE_MANIFEST_NAME,
            "sha256": parts._sha256(files[HISTORICAL_FORCE_MANIFEST_NAME]),
            "status": "preserved_byte_identical",
        },
    }
    if manifest.get("component_manifests") != expected_component_bindings:
        raise ForceReleaseError("site manifest component-manifest bindings are inconsistent")
    published_stage_paths = {
        "exclusion_manifest.json": GENERATED_EXCLUSION_PATH,
        "packs/viewer.staged.html": GENERATED_VIEWER_PATH,
        "packs/viewer_vtests.json": GENERATED_VTESTS_PATH,
        "schema_meta.staged.json": GENERATED_SCHEMA_PATH,
    }
    for staged_relative, published_relative in published_stage_paths.items():
        if files[published_relative].read_bytes() != regenerated[staged_relative].encode("utf-8"):
            raise ForceReleaseError(
                f"published hybrid artifact differs from full regeneration: {published_relative}"
            )
    after_regeneration_files = _scan_regular_files(root)
    if parts._entries(after_regeneration_files) != before_regeneration:
        raise ForceReleaseError("release package changed during verification regeneration")

    expected_force = {
        "build": FORCE_BUILD,
        "path": ROOT_VIEWER_PATH,
        "sha256": parts._sha256(files[ROOT_VIEWER_PATH]),
        "presentation_role": "public_release",
        "release_eligible": True,
        "data_repo_commit": viewer_build["repo_commit"],
        "data_identity": viewer_build["data_identity"],
    }
    expected_tools = {
        "force_curve_bench": expected_force,
        "ec_parts_library": predecessor_picker,
        "ec_switch_explorer": predecessor_explorer,
    }
    if manifest.get("tool_builds") != expected_tools:
        raise ForceReleaseError("site manifest tool-build identities are inconsistent")

    canonical_files = {
        relative.removeprefix("canonical-evidence/"): files[relative]
        for relative in sorted(canonical_paths)
    }
    raw_files = {relative: files[relative] for relative in sorted(raw_paths)}
    parts_files = {
        ROOT_PARTS_PATH: files[ROOT_PARTS_PATH],
        GENERATED_PICKER_PATH: files[GENERATED_PICKER_PATH],
    }
    expected_evidence = {
        "path": "canonical-evidence",
        "evidence_epoch_hash": evidence_hash,
        "tree": _tree_summary(canonical_files),
        "status": "preserved_byte_identical",
    }
    if manifest.get("evidence_identity") != expected_evidence:
        raise ForceReleaseError("site manifest evidence identity is inconsistent")
    expected_protection = {
        "parts_library": _tree_summary(parts_files),
        "raw_csv_paths": _tree_summary(raw_files),
        "canonical_evidence": _tree_summary(canonical_files),
        "historical_force_manifest_sha256": parts._sha256(
            files[HISTORICAL_FORCE_MANIFEST_NAME]
        ),
        "dome_lab_legacy_sha256": parts._sha256(files["dome-lab.html"]),
        "ec_switch_explorer_sha256": parts._sha256(files["ec-switch-explorer.html"]),
    }
    if manifest.get("protection_contract") != expected_protection:
        raise ForceReleaseError("site manifest protection contract is inconsistent")
    expected_inventory = {
        "manifest_path": SITE_MANIFEST_NAME,
        "manifest_scope": f"all regular files except {SITE_MANIFEST_NAME} and {SHA256SUMS_NAME}",
        "sha256sums_path": SHA256SUMS_NAME,
        "sha256sums_scope": f"all regular files except {SHA256SUMS_NAME}",
    }
    if manifest.get("inventory") != expected_inventory:
        raise ForceReleaseError("site manifest inventory scope is inconsistent")

    try:
        parts._run_canonical_verifier(root / "canonical-evidence")
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error
    return {
        "status": "PASS",
        "package_id": PACKAGE_ID,
        "force_build": FORCE_BUILD,
        "parts_build": PARTS_BUILD,
        "canonical_public_url": canonical_url,
        "git_tag": git_tag,
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files.values()),
        "index_sha256": parts._sha256(files[ROOT_VIEWER_PATH]),
        "parts_sha256": parts._sha256(files[ROOT_PARTS_PATH]),
        "manifest_sha256": parts._sha256(files[SITE_MANIFEST_NAME]),
        "sha256sums_sha256": parts._sha256(files[SHA256SUMS_NAME]),
        "evidence_tree_sha256": _tree_summary(canonical_files)["sha256"],
    }


def _promote_atomic(staging: Path, output: Path) -> None:
    lock = output.with_name(f".{output.name}.force-release-lock")
    descriptor: int | None = None
    try:
        descriptor = os.open(os.fspath(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"Force Curve Bench fc-3.5 release promotion lock\n")
        os.close(descriptor)
        descriptor = None
        if os.path.lexists(os.fspath(output)):
            raise ForceReleaseError(f"refusing to replace existing output: {output}")
        os.rename(staging, output)
    except FileExistsError as error:
        raise ForceReleaseError(
            f"another release promotion is active or the output exists: {output}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def build_force_curve_release(
    *,
    base_release: str | os.PathLike[str],
    release_source: str | os.PathLike[str],
    staging: str | os.PathLike[str],
    policy: str | os.PathLike[str],
    output: str | os.PathLike[str],
    canonical_url: str,
    git_tag: str,
) -> dict[str, Any]:
    base_root = _resolve_directory(base_release, "verified fc-3.4 + lib-6.1 base")
    source_root = _resolve_directory(release_source, "release source")
    stage_root = _resolve_directory(staging, "fc-3.5 generated staging")
    policy_path = _resolve_file(policy, "Force viewer overlay policy")
    try:
        canonical_url = parts._validate_url(canonical_url)
        git_tag = parts._validate_tag(git_tag)
    except parts.PartsReleaseError as error:
        raise ForceReleaseError(str(error)) from error
    if canonical_url != CANONICAL_PUBLIC_URL or git_tag != RELEASE_GIT_TAG:
        raise ForceReleaseError("fc-3.5 must use its exact canonical URL and Git tag")
    output_path = Path(output).resolve(strict=False)
    if os.path.lexists(os.fspath(output_path)):
        raise ForceReleaseError(f"refusing to replace existing or unsafe output: {output_path}")
    for label, root in (
        ("base release", base_root),
        ("release source", source_root),
        ("generated staging", stage_root),
    ):
        if parts._path_within(output_path, root):
            raise ForceReleaseError(f"output must not be inside {label}")

    # Deliberately first: do not inspect overlay inputs or create output until
    # the currently published multi-tool site passes its unchanged verifier.
    try:
        base_report = parts.verify_parts_library_release(base_root)
    except Exception as error:
        raise ForceReleaseError(f"base site verification failed: {error}") from error
    if (
        not isinstance(base_report, dict)
        or base_report.get("status") != "PASS"
        or base_report.get("package_id") != parts.PACKAGE_ID
        or base_report.get("force_build") != parts.FORCE_BUILD
        or base_report.get("parts_build") != PARTS_BUILD
    ):
        raise ForceReleaseError("base site verifier returned the wrong identity")

    base_files = _scan_regular_files(base_root)
    predecessor = _base_contract(base_files)
    policy_object = _load_policy(policy_path)
    expected_policy_path = (
        source_root / Path(*PurePosixPath(POLICY_PACKAGE_PATH).parts)
    ).resolve(strict=True)
    if policy_path != expected_policy_path:
        raise ForceReleaseError(
            f"policy must be the published source file {POLICY_PACKAGE_PATH}"
        )
    missing_required_overlay = sorted(
        REQUIRED_OVERLAY_PATHS - set(policy_object["overlay_paths"])
    )
    if missing_required_overlay:
        raise ForceReleaseError(
            "overlay policy omits required fc-3.5 paths: "
            f"{missing_required_overlay}"
        )
    source_files: dict[str, Path] = {}
    for relative in policy_object["overlay_paths"]:
        path = source_root / Path(*PurePosixPath(relative).parts)
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise ForceReleaseError(f"overlay source path is missing: {relative}") from error
        if (
            not parts._path_within(resolved, source_root)
            or not resolved.is_file()
            or path.is_symlink()
        ):
            raise ForceReleaseError(f"unsafe overlay source path: {relative}")
        source_files[relative] = resolved
    _validate_subjective_pilot_inventory(source_root)

    stage_files = _scan_regular_files(stage_root)
    stage_missing = sorted(REQUIRED_STAGE_FILES - set(stage_files))
    if stage_missing:
        raise ForceReleaseError(
            f"fc-3.5 staging is missing required paths: {stage_missing}"
        )
    viewer_build = _parse_viewer_build(stage_files["packs/viewer.staged.html"])
    _validate_vtests(stage_files["packs/viewer_vtests.json"], viewer_build)
    if (
        viewer_build["canonical_evidence_identity"]
        != predecessor["evidence"]["evidence_epoch_hash"]
        or viewer_build["data_identity"]
        != predecessor["evidence"]["evidence_epoch_hash"]
        or viewer_build["repo_commit"] != predecessor["picker"].get("data_repo_commit")
    ):
        raise ForceReleaseError("staged fc-3.5 viewer targets a different evidence epoch")
    regenerated_stage, stage_attestation = _validate_full_stage(
        stage_files,
        source_root=source_root,
        base_root=base_root,
        predecessor_files=base_files,
        evidence_hash=predecessor["evidence"]["evidence_epoch_hash"],
        repo_commit=viewer_build["repo_commit"],
    )

    base_snapshot = parts._entries(base_files)
    source_snapshot = parts._entries(source_files)
    stage_snapshot = parts._entries(stage_files)
    policy_snapshot = (policy_path.stat().st_size, parts._sha256(policy_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX, dir=output_path.parent))
    promoted = False
    try:
        omitted = {
            SITE_MANIFEST_NAME,
            SHA256SUMS_NAME,
            ROOT_VIEWER_PATH,
            *GENERATED_MUTABLE,
            *policy_object["overlay_paths"],
        }
        parts._copy_files(
            {relative: path for relative, path in base_files.items() if relative not in omitted},
            temporary,
        )
        parts._copy_files(source_files, temporary)
        parts._copy_file(
            stage_files["packs/viewer.staged.html"], temporary / GENERATED_VIEWER_PATH
        )
        parts._copy_file(
            stage_files["packs/viewer_vtests.json"], temporary / GENERATED_VTESTS_PATH
        )
        parts._copy_file(
            stage_files["schema_meta.staged.json"], temporary / GENERATED_SCHEMA_PATH
        )
        parts._copy_file(
            stage_files["exclusion_manifest.json"], temporary / GENERATED_EXCLUSION_PATH
        )
        parts._copy_file(
            stage_files["packs/viewer.staged.html"], temporary / ROOT_VIEWER_PATH
        )
        parts._copy_file(
            base_files[SITE_MANIFEST_NAME], temporary / PREDECESSOR_SITE_MANIFEST_NAME
        )
        _write_generated_manifest(temporary / "generated")
        component_manifest = _build_component_manifest(
            temporary,
            predecessor=predecessor,
            viewer_build=viewer_build,
            stage_attestation=stage_attestation,
            canonical_url=canonical_url,
            git_tag=git_tag,
        )
        parts._write_exclusive(
            temporary / COMPONENT_MANIFEST_NAME,
            parts._json_bytes(component_manifest),
        )

        manifest = _build_manifest(
            temporary,
            base_files=base_files,
            predecessor=predecessor,
            policy=policy_object,
            policy_path=policy_path,
            source_files=source_files,
            viewer_build=viewer_build,
            stage_attestation=stage_attestation,
            canonical_url=canonical_url,
            git_tag=git_tag,
        )
        parts._write_exclusive(
            temporary / SITE_MANIFEST_NAME, parts._json_bytes(manifest)
        )
        parts._write_sha256sums(temporary)
        report = verify_force_curve_release(temporary)

        if parts._entries(base_files) != base_snapshot:
            raise ForceReleaseError("base site changed during the release build")
        if parts._entries(source_files) != source_snapshot:
            raise ForceReleaseError("release overlay source changed during the release build")
        if parts._entries(stage_files) != stage_snapshot:
            raise ForceReleaseError("fc-3.5 staging changed during the release build")
        if _stage_attestation(regenerated_stage, _source_identities(source_root)) != stage_attestation:
            raise ForceReleaseError("regenerated-stage attestation changed during the release build")
        if (policy_path.stat().st_size, parts._sha256(policy_path)) != policy_snapshot:
            raise ForceReleaseError("overlay policy changed during the release build")

        _promote_atomic(temporary, output_path)
        promoted = True
        try:
            final_report = verify_force_curve_release(output_path)
            if report != final_report:
                raise ForceReleaseError("verification report changed during atomic promotion")
        except Exception as verification_error:
            try:
                os.rename(output_path, temporary)
                promoted = False
            except OSError as rollback_error:
                raise ForceReleaseError(
                    "post-promotion verification failed and output rollback failed: "
                    f"{output_path}: {rollback_error}"
                ) from verification_error
            raise
        return final_report
    finally:
        if not promoted and temporary.exists():
            shutil.rmtree(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build and atomically promote fc-3.5")
    build.add_argument("--base-release", required=True, type=Path)
    build.add_argument("--release-source", required=True, type=Path)
    build.add_argument("--staging", required=True, type=Path)
    build.add_argument("--policy", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--canonical-url", required=True)
    build.add_argument("--git-tag", required=True)
    verify = subparsers.add_parser("verify", help="verify an fc-3.5 site release")
    verify.add_argument("package_root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build_force_curve_release(
                base_release=args.base_release,
                release_source=args.release_source,
                staging=args.staging,
                policy=args.policy,
                output=args.output,
                canonical_url=args.canonical_url,
                git_tag=args.git_tag,
            )
        else:
            report = verify_force_curve_release(args.package_root)
    except (ForceReleaseError, parts.PartsReleaseError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
