#!/usr/bin/env python3
"""Build and verify a deterministic EC Parts Library site overlay.

The input ``base-release`` must first pass the unchanged fc-3.4 public-release
verifier.  The builder then copies that package byte-for-byte except for:

* exact source/documentation paths named by an overlay policy;
* the generated tree, whose non-Parts artifacts must remain byte-identical;
* ``dome-lab-parts.html``, copied from the generated release picker;
* the active site manifest and SHA-256 inventory.

The predecessor Force Curve Bench manifest remains in the package as immutable
history.  ``SITE_RELEASE_MANIFEST.json`` is the authority for the resulting
multi-tool site tree.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

import build_public_release as fc34


SITE_MANIFEST_NAME = "SITE_RELEASE_MANIFEST.json"
SHA256SUMS_NAME = "SHA256SUMS"
PREDECESSOR_MANIFEST_NAME = "FORCE_CURVE_BENCH_RELEASE_MANIFEST.json"
PACKAGE_ID = "ec-parts-library-site-lib-6.1"
ARTIFACT_ROLE = "public_multi_tool_site_release"
PARTS_BUILD = "lib-6.1"
FORCE_BUILD = "fc-3.4"
MANIFEST_VERSION = 1
POLICY_VERSION = 1
TEMP_PREFIX = ".parts-release-"

REQUIRED_STAGE_FILES = frozenset(
    {
        "generated_manifest.json",
        "packs/picker.staged.html",
        "packs/viewer.staged.html",
    }
)

# These are the only generated artifacts permitted to differ from the
# verified fc-3.4 predecessor. Everything scientific remains byte-identical.
PARTS_GENERATED_MUTABLE = frozenset(
    {
        "generated_manifest.json",
        "schema_meta.staged.json",
        "packs/picker.staged.html",
        "packs/picker_tests.json",
        "packs/picker_mini_curves.json",
        "packs/prose_scan_report.json",
    }
)
CONFIG_HASH_ONLY_GENERATED = "exclusion_manifest.json"
EXCLUSION_MANIFEST_FIELDS = frozenset(
    {
        "artifact_role",
        "config_hash",
        "entries",
        "registry_hash",
        "release_eligible",
        "repo_commit",
    }
)

ROOT_PARTS_PATH = "dome-lab-parts.html"
PROTECTED_ROOT_FILES = frozenset(
    {
        ".gitattributes",
        ".nojekyll",
        "index.html",
        "dome-lab.html",
        "ec-switch-explorer.html",
        PREDECESSOR_MANIFEST_NAME,
    }
)
HEX64 = re.compile(r"[0-9a-f]{64}")
SAFE_TAG = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,127}")
EMBED_HEIGHT_MIN = 400
EMBED_HEIGHT_MAX = 20_000


class PartsReleaseError(RuntimeError):
    """A deterministic release contract was not satisfied."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PartsReleaseError(f"cannot read {label}: {path}: {error}") from error


def _normalize_relative(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise PartsReleaseError(f"{label} must be a non-empty string")
    if "\\" in value or "\x00" in value:
        raise PartsReleaseError(f"unsafe {label}: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise PartsReleaseError(f"unsafe {label}: {value!r}")
    normalized = pure.as_posix()
    if normalized != value:
        raise PartsReleaseError(f"non-canonical {label}: {value!r}")
    return normalized


def _resolve_directory(value: str | os.PathLike[str], label: str) -> Path:
    path = Path(value).resolve(strict=True)
    if not path.is_dir():
        raise PartsReleaseError(f"{label} is not a directory: {path}")
    return path


def _resolve_file(value: str | os.PathLike[str], label: str) -> Path:
    path = Path(value).resolve(strict=True)
    if not path.is_file():
        raise PartsReleaseError(f"{label} is not a regular file: {path}")
    return path


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _scan_regular_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    folded: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in list(dirnames):
            candidate = current / name
            if candidate.is_symlink():
                raise PartsReleaseError(f"symbolic-link directory is forbidden: {candidate}")
        for name in filenames:
            path = current / name
            try:
                mode = path.lstat().st_mode
            except OSError as error:
                raise PartsReleaseError(f"cannot inspect release input: {path}: {error}") from error
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                raise PartsReleaseError(f"non-regular release input is forbidden: {path}")
            relative = path.relative_to(root).as_posix()
            relative = _normalize_relative(relative, "release path")
            key = relative.casefold()
            if key in folded:
                raise PartsReleaseError(
                    f"case-insensitive path collision: {folded[key]!r} and {relative!r}"
                )
            folded[key] = relative
            files[relative] = path
    return files


def _entries(files: Mapping[str, Path]) -> list[dict[str, Any]]:
    return [
        {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for relative, path in sorted(files.items(), key=lambda row: row[0].encode("utf-8"))
    ]


def _tree_summary(files: Mapping[str, Path]) -> dict[str, Any]:
    entries = _entries(files)
    return {
        "file_count": len(entries),
        "bytes": sum(row["bytes"] for row in entries),
        "sha256": _sha256_bytes(
            json.dumps(entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ),
    }


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if _lexists(target):
        raise PartsReleaseError(f"copy-plan collision at {target}")
    with source.open("rb") as input_stream, target.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def _copy_files(files: Mapping[str, Path], destination: Path) -> None:
    for relative, source in sorted(files.items(), key=lambda row: row[0].encode("utf-8")):
        _copy_file(source, destination / Path(*PurePosixPath(relative).parts))


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(payload)
    except FileExistsError as error:
        raise PartsReleaseError(f"refusing to overwrite release path: {path}") from error


def _validate_url(value: Any) -> str:
    if not isinstance(value, str):
        raise PartsReleaseError("canonical URL must be a string")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.query
        or parsed.fragment
        or "<" in value
        or ">" in value
        or "placeholder" in value.casefold()
    ):
        raise PartsReleaseError(f"invalid canonical URL: {value!r}")
    return value


def _validate_tag(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not SAFE_TAG.fullmatch(value)
        or value.endswith("/")
        or "//" in value
        or ".." in value
        or "placeholder" in value.casefold()
    ):
        raise PartsReleaseError(f"invalid Git tag: {value!r}")
    return value


def _load_policy(path: Path) -> dict[str, Any]:
    policy = _read_json(path, "overlay policy")
    if not isinstance(policy, dict) or set(policy) != {
        "policy_version",
        "name",
        "overlay_paths",
    }:
        raise PartsReleaseError("overlay policy has the wrong field set")
    if policy["policy_version"] != POLICY_VERSION:
        raise PartsReleaseError("unsupported overlay policy version")
    if not isinstance(policy["name"], str) or not policy["name"].strip():
        raise PartsReleaseError("overlay policy name must be non-empty")
    values = policy["overlay_paths"]
    if not isinstance(values, list) or not values:
        raise PartsReleaseError("overlay policy must declare at least one path")
    paths = [_normalize_relative(value, "overlay path") for value in values]
    if len(set(paths)) != len(paths):
        raise PartsReleaseError("overlay policy contains duplicate paths")
    if paths != sorted(paths, key=lambda value: value.encode("utf-8")):
        raise PartsReleaseError("overlay paths must be in canonical order")
    folded: dict[str, str] = {}
    for relative in paths:
        key = relative.casefold()
        if key in folded:
            raise PartsReleaseError(
                f"case-insensitive overlay collision: {folded[key]!r} and {relative!r}"
            )
        folded[key] = relative
        if _overlay_path_is_protected(relative):
            raise PartsReleaseError(f"overlay policy attempts to replace protected path: {relative}")
    for relative in paths:
        parts = PurePosixPath(relative).parts
        for index in range(1, len(parts)):
            ancestor = "/".join(parts[:index])
            if ancestor.casefold() in folded:
                raise PartsReleaseError(
                    f"overlay file/directory collision: {ancestor!r} and {relative!r}"
                )
    return {**policy, "overlay_paths": paths}


def _overlay_path_is_protected(relative: str) -> bool:
    return (
        relative in PROTECTED_ROOT_FILES
        or relative in {ROOT_PARTS_PATH, SITE_MANIFEST_NAME, SHA256SUMS_NAME}
        or relative.startswith("canonical-evidence/")
        or relative.startswith("generated/")
        or relative.casefold().endswith(".csv")
    )


def _manifest_rows(manifest: Mapping[str, Any], label: str) -> dict[str, dict[str, Any]]:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise PartsReleaseError(f"{label} has no file inventory")
    if rows != sorted(rows, key=lambda row: str(row.get("path", "")).encode("utf-8")):
        raise PartsReleaseError(f"{label} file inventory is not in canonical order")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise PartsReleaseError(f"{label} contains a non-object file row")
        relative = _normalize_relative(row.get("path"), f"{label} inventory path")
        digest = row.get("sha256")
        size = row.get("bytes")
        if relative in result:
            raise PartsReleaseError(f"{label} contains duplicate path: {relative}")
        if type(size) is not int or size < 0 or not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise PartsReleaseError(f"{label} contains invalid identity for {relative}")
        result[relative] = row
    return result


def _predecessor_contract(base_files: Mapping[str, Path]) -> dict[str, Any]:
    required = {
        PREDECESSOR_MANIFEST_NAME,
        SHA256SUMS_NAME,
        "index.html",
        ROOT_PARTS_PATH,
        "dome-lab.html",
        "ec-switch-explorer.html",
        "generated/packs/viewer.staged.html",
        "canonical-evidence/EPOCH_MANIFEST.json",
    }
    missing = sorted(required - set(base_files))
    if missing:
        raise PartsReleaseError(f"fc-3.4 base is missing required paths: {missing}")
    manifest = _read_json(base_files[PREDECESSOR_MANIFEST_NAME], "fc-3.4 manifest")
    if not isinstance(manifest, dict):
        raise PartsReleaseError("fc-3.4 manifest must be an object")
    if manifest.get("package_id") != fc34.PACKAGE_ID or manifest.get("bench_build") != FORCE_BUILD:
        raise PartsReleaseError("verified predecessor has the wrong fc-3.4 identity")
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or publication.get("git_tag") != "fc-3.4":
        raise PartsReleaseError("verified predecessor is not the fc-3.4 tag package")
    rows = _manifest_rows(manifest, "fc-3.4 manifest")
    for relative in required - {PREDECESSOR_MANIFEST_NAME, SHA256SUMS_NAME}:
        row = rows.get(relative)
        path = base_files[relative]
        if row is None or row["bytes"] != path.stat().st_size or row["sha256"] != _sha256(path):
            raise PartsReleaseError(f"fc-3.4 predecessor inventory mismatch: {relative}")
    evidence = manifest.get("evidence_identity")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("evidence_epoch_hash"), str):
        raise PartsReleaseError("fc-3.4 predecessor has no evidence identity")
    return {"manifest": manifest, "rows": rows, "evidence": evidence}


def _raw_predecessor_paths(rows: Mapping[str, Mapping[str, Any]]) -> set[str]:
    """Return the published repository's raw test CSVs, not report CSVs."""
    return {
        relative
        for relative, row in rows.items()
        if relative.casefold().endswith(".csv")
        and row.get("component") == "frozen_repository"
    }


def _protected_predecessor_paths(rows: Mapping[str, Mapping[str, Any]]) -> set[str]:
    protected = {
        "index.html",
        "dome-lab.html",
        "ec-switch-explorer.html",
        *(relative for relative in rows if relative.startswith("canonical-evidence/")),
        *_raw_predecessor_paths(rows),
    }
    return protected


def _validate_embed_contract(source: str) -> None:
    """Reject a generated picker that weakens the Shopify iframe boundary.

    The bridge is intentionally small.  An allowlisted ``document.referrer``
    may establish the parent origin before the first message; otherwise the
    first fully validated viewport message establishes it.  Once established,
    no later origin may replace it.  Viewport fields are numbers, not values
    coerced into numbers, and the child reports only a bounded document height.
    """

    required = {
        "an exact parent-origin allowlist": r"\bconst\s+EMBED_ORIGINS\s*=\s*new\s+Set\s*\(",
        "a nullable origin lock": r"\blet\s+embedOrigin\s*=\s*null\s*;",
        "an allowlisted referrer pre-lock": (
            r"new\s+URL\s*\(\s*document\.referrer\s*\).*?"
            r"EMBED_ORIGINS\.has\s*\(\s*ref\.origin\s*\).*?"
            r"embedOrigin\s*=\s*ref\.origin"
        ),
        "a parent-window source check": r"event\.source\s*!==\s*parent",
        "an allowlisted message-origin check": r"!\s*EMBED_ORIGINS\.has\s*\(\s*event\.origin\s*\)",
        "a persistent first-origin lock": (
            r"if\s*\(\s*embedOrigin\s*&&\s*event\.origin\s*!==\s*embedOrigin\s*\)\s*return"
        ),
        "numeric-only viewport validation": r"typeof\s+value\s*===\s*[\"']number[\"']",
        "finite viewport validation": r"Number\.isFinite\s*\(\s*value\s*\)",
        "a validated viewport-height field": r"validViewportNumber\s*\(\s*data\.viewH\s*,",
        "a validated viewport-offset field": r"validViewportNumber\s*\(\s*data\.visibleTop\s*,",
        "a first-valid-message fallback lock": r"if\s*\(\s*!embedOrigin\s*\)\s*embedOrigin\s*=\s*event\.origin",
        "a locked-origin send guard": r"if\s*\(\s*!embedOrigin\s*\)\s*return",
        "an exact-origin height message": (
            r"postMessage\s*\(\s*\{\s*type\s*:\s*[\"']ukdl-height[\"']\s*,"
            r"\s*h\s*:\s*height\s*\}\s*,\s*embedOrigin\s*\)"
        ),
        "the 400-20000 height clamp": (
            rf"Math\.max\s*\(\s*{EMBED_HEIGHT_MIN}\s*,\s*Math\.min\s*\(\s*"
            rf"{EMBED_HEIGHT_MAX}\s*,\s*raw\s*\)\s*\)"
        ),
    }
    matches: dict[str, re.Match[str]] = {}
    for label, pattern in required.items():
        match = re.search(pattern, source, re.DOTALL)
        if match is None:
            raise PartsReleaseError(f"generated picker embed bridge lacks {label}")
        matches[label] = match

    # The origin may be assigned from a validated referrer, or only after the
    # message type and both numeric fields have passed validation.
    message_fallback = matches["a first-valid-message fallback lock"].start()
    for label in (
        "a persistent first-origin lock",
        "a validated viewport-height field",
        "a validated viewport-offset field",
    ):
        if matches[label].start() >= message_fallback:
            raise PartsReleaseError(
                "generated picker embed bridge locks the message origin before validation"
            )

    forbidden = {
        "wildcard postMessage target": r"postMessage\s*\([^;]*,\s*[\"']\*[\"']\s*\)",
        "legacy modal placement message": r"ukdl-place-modal|ukdlPlaceModal",
        "history.pushState": r"\bhistory\.pushState\s*\(",
        "history.replaceState": r"\bhistory\.replaceState\s*\(",
        "location-hash mutation": r"\b(?:window\.)?location\.hash\s*=",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, source, re.DOTALL):
            raise PartsReleaseError(
                f"generated picker embed bridge contains forbidden {label}"
            )


def _parse_picker_build(path: Path) -> dict[str, Any]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PartsReleaseError(f"cannot read generated picker: {path}: {error}") from error
    _validate_embed_contract(source)
    match = re.search(
        r"\bconst\s+PICKER_BUILD\s*=\s*(\{.*?\})\s*;\s*/\*\s*GENERATED",
        source,
        re.DOTALL,
    )
    if match is None:
        raise PartsReleaseError("generated picker has no canonical PICKER_BUILD blob")
    try:
        build = json.loads(match.group(1))
    except json.JSONDecodeError as error:
        raise PartsReleaseError(f"generated picker has invalid PICKER_BUILD JSON: {error}") from error
    expected = {
        "library_build": PARTS_BUILD,
        "mode": "release",
        "presentation_role": "public_release",
        "release_eligible": True,
    }
    for key, value in expected.items():
        if build.get(key) != value:
            raise PartsReleaseError(
                f"generated picker has the wrong release identity: {key}={build.get(key)!r}"
            )
    if not isinstance(build.get("parts_library_source_identity"), str) or not HEX64.fullmatch(
        build["parts_library_source_identity"]
    ):
        raise PartsReleaseError("generated picker has no valid parts_library_source_identity")
    if not isinstance(build.get("repo_commit"), str) or not re.fullmatch(
        r"[0-9a-f]{40}", build["repo_commit"]
    ):
        raise PartsReleaseError("generated picker has no valid repo_commit")
    return build


def _validate_generated_manifest(files: Mapping[str, Path]) -> None:
    required = REQUIRED_STAGE_FILES - set(files)
    if required:
        raise PartsReleaseError(f"release staging is missing required files: {sorted(required)}")
    manifest = _read_json(files["generated_manifest.json"], "generated manifest")
    if not isinstance(manifest, dict):
        raise PartsReleaseError("generated manifest must be an object")
    expected_paths = set(files) - {"generated_manifest.json"}
    if set(manifest) != expected_paths:
        raise PartsReleaseError("generated manifest has missing or extra staging paths")
    if list(manifest) != sorted(manifest, key=lambda value: value.encode("utf-8")):
        raise PartsReleaseError("generated manifest paths are not in canonical order")
    for relative in sorted(expected_paths):
        digest = manifest[relative]
        if not isinstance(digest, str) or not HEX64.fullmatch(digest):
            raise PartsReleaseError(f"generated manifest has invalid digest: {relative}")
        if digest != _sha256(files[relative]):
            raise PartsReleaseError(f"generated manifest mismatch: {relative}")


def _exclusion_manifest_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise PartsReleaseError(f"{label} is not valid UTF-8 JSON: {error}") from error
    if not isinstance(value, dict) or set(value) != EXCLUSION_MANIFEST_FIELDS:
        raise PartsReleaseError(f"{label} has the wrong semantic field set")
    if not isinstance(value["artifact_role"], str) or not value["artifact_role"]:
        raise PartsReleaseError(f"{label} has an invalid artifact_role")
    if not isinstance(value["entries"], list):
        raise PartsReleaseError(f"{label} has invalid entries")
    if not isinstance(value["registry_hash"], str) or not HEX64.fullmatch(
        value["registry_hash"]
    ):
        raise PartsReleaseError(f"{label} has an invalid registry_hash")
    if type(value["release_eligible"]) is not bool:
        raise PartsReleaseError(f"{label} has an invalid release_eligible value")
    if not isinstance(value["repo_commit"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", value["repo_commit"]
    ):
        raise PartsReleaseError(f"{label} has an invalid repo_commit")
    if not isinstance(value["config_hash"], str) or not HEX64.fullmatch(
        value["config_hash"]
    ):
        raise PartsReleaseError(f"{label} has an invalid config_hash")
    return value


def _exclusion_transition_guard(
    predecessor_payload: bytes, release_payload: bytes
) -> dict[str, str]:
    predecessor = _exclusion_manifest_object(
        predecessor_payload, "fc-3.4 exclusion_manifest.json"
    )
    current = _exclusion_manifest_object(
        release_payload, "release exclusion_manifest.json"
    )
    changed_fields = sorted(
        key for key in EXCLUSION_MANIFEST_FIELDS if predecessor[key] != current[key]
    )
    if changed_fields != ["config_hash"]:
        raise PartsReleaseError(
            "exclusion_manifest.json transition must change config_hash only; "
            f"changed_fields={changed_fields}"
        )
    return {
        "transition": "config_hash_only",
        "predecessor_payload_base64": base64.b64encode(predecessor_payload).decode(
            "ascii"
        ),
    }


def _generated_difference_rows(
    base_files: Mapping[str, Path], stage_files: Mapping[str, Path]
) -> list[dict[str, Any]]:
    base_generated = {
        relative.removeprefix("generated/"): path
        for relative, path in base_files.items()
        if relative.startswith("generated/")
    }
    differences: list[dict[str, Any]] = []
    for relative in sorted(set(base_generated) | set(stage_files), key=lambda value: value.encode("utf-8")):
        old = base_generated.get(relative)
        new = stage_files.get(relative)
        same = old is not None and new is not None and old.read_bytes() == new.read_bytes()
        if same:
            continue
        guard: dict[str, str] = {}
        if relative == CONFIG_HASH_ONLY_GENERATED:
            if old is None or new is None:
                raise PartsReleaseError(
                    "exclusion_manifest.json must exist in both fc-3.4 and release staging"
                )
            guard = _exclusion_transition_guard(old.read_bytes(), new.read_bytes())
        elif relative not in PARTS_GENERATED_MUTABLE:
            raise PartsReleaseError(
                f"non-Parts generated artifact differs from fc-3.4: generated/{relative}"
            )
        differences.append({
            "path": f"generated/{relative}",
            "base_sha256": _sha256(old) if old is not None else None,
            "release_sha256": _sha256(new) if new is not None else None,
            **guard,
        })
    return differences


def _generated_difference_rows_from_inventory(
    predecessor_rows: Mapping[str, Mapping[str, Any]],
    output_files: Mapping[str, Path],
    declared_differences: Any,
) -> list[dict[str, Any]]:
    if not isinstance(declared_differences, list):
        raise PartsReleaseError("site manifest has no generated-difference rows")
    declared_by_path: dict[str, dict[str, Any]] = {}
    for row in declared_differences:
        if not isinstance(row, dict):
            raise PartsReleaseError("site manifest has an invalid generated-difference row")
        relative = _normalize_relative(
            row.get("path"), "generated-difference path"
        )
        if relative in declared_by_path:
            raise PartsReleaseError(
                f"duplicate generated-difference path: {relative}"
            )
        declared_by_path[relative] = row
    base_generated = {
        relative.removeprefix("generated/"): row
        for relative, row in predecessor_rows.items()
        if relative.startswith("generated/")
    }
    current_generated = {
        relative.removeprefix("generated/"): path
        for relative, path in output_files.items()
        if relative.startswith("generated/")
    }
    differences: list[dict[str, Any]] = []
    for relative in sorted(
        set(base_generated) | set(current_generated), key=lambda value: value.encode("utf-8")
    ):
        old = base_generated.get(relative)
        new = current_generated.get(relative)
        same = (
            old is not None
            and new is not None
            and old["bytes"] == new.stat().st_size
            and old["sha256"] == _sha256(new)
        )
        if same:
            continue
        guard: dict[str, str] = {}
        if relative == CONFIG_HASH_ONLY_GENERATED:
            if old is None or new is None:
                raise PartsReleaseError(
                    "exclusion_manifest.json must exist in both predecessor and release"
                )
            declared = declared_by_path.get(f"generated/{relative}")
            if not isinstance(declared, dict) or set(declared) != {
                "path",
                "base_sha256",
                "release_sha256",
                "transition",
                "predecessor_payload_base64",
            }:
                raise PartsReleaseError(
                    "site manifest lacks the exclusion_manifest.json semantic guard"
                )
            encoded = declared["predecessor_payload_base64"]
            if not isinstance(encoded, str):
                raise PartsReleaseError(
                    "exclusion_manifest.json predecessor payload is not base64 text"
                )
            try:
                predecessor_payload = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as error:
                raise PartsReleaseError(
                    "exclusion_manifest.json predecessor payload is invalid base64"
                ) from error
            if (
                len(predecessor_payload) != old["bytes"]
                or _sha256_bytes(predecessor_payload) != old["sha256"]
            ):
                raise PartsReleaseError(
                    "embedded exclusion_manifest.json does not match fc-3.4 inventory"
                )
            guard = _exclusion_transition_guard(
                predecessor_payload, new.read_bytes()
            )
        elif relative not in PARTS_GENERATED_MUTABLE:
            raise PartsReleaseError(
                f"non-Parts generated artifact differs from fc-3.4: generated/{relative}"
            )
        differences.append({
            "path": f"generated/{relative}",
            "base_sha256": old["sha256"] if old is not None else None,
            "release_sha256": _sha256(new) if new is not None else None,
            **guard,
        })
    return differences


def _validate_overlay_manifest(
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
        "root_picker_source",
    }
    if not isinstance(overlay, dict) or set(overlay) != expected_fields:
        raise PartsReleaseError("site manifest has an invalid overlay contract")
    if overlay["policy_version"] != POLICY_VERSION:
        raise PartsReleaseError("site manifest has the wrong overlay-policy version")
    if not isinstance(overlay["policy_name"], str) or not overlay["policy_name"].strip():
        raise PartsReleaseError("site manifest has no overlay-policy name")
    if not isinstance(overlay["policy_sha256"], str) or not HEX64.fullmatch(
        overlay["policy_sha256"]
    ):
        raise PartsReleaseError("site manifest has an invalid overlay-policy hash")
    if overlay["root_picker_source"] != "generated/packs/picker.staged.html":
        raise PartsReleaseError("site manifest has the wrong root-picker source")
    rows = overlay["paths"]
    if not isinstance(rows, list) or not rows:
        raise PartsReleaseError("site manifest has no overlay paths")
    if rows != sorted(rows, key=lambda row: str(row.get("path", "")).encode("utf-8")):
        raise PartsReleaseError("site-manifest overlay paths are not in canonical order")
    paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "path",
            "base_sha256",
            "release_sha256",
            "operation",
        }:
            raise PartsReleaseError("site manifest contains an invalid overlay-path row")
        relative = _normalize_relative(row["path"], "site overlay path")
        if relative in paths:
            raise PartsReleaseError(f"duplicate site overlay path: {relative}")
        if _overlay_path_is_protected(relative):
            raise PartsReleaseError(f"site manifest overlays protected path: {relative}")
        paths.add(relative)
        old = predecessor_rows.get(relative)
        current = files.get(relative)
        expected_operation = "replace" if old is not None else "add"
        expected_old_hash = old["sha256"] if old is not None else None
        if current is None:
            raise PartsReleaseError(f"site overlay path is absent: {relative}")
        if (
            row["operation"] != expected_operation
            or row["base_sha256"] != expected_old_hash
            or row["release_sha256"] != _sha256(current)
        ):
            raise PartsReleaseError(f"site overlay identity mismatch: {relative}")
    expected_generated = _generated_difference_rows_from_inventory(
        predecessor_rows, files, overlay["generated_allowed_differences"]
    )
    if overlay["generated_allowed_differences"] != expected_generated:
        raise PartsReleaseError("site manifest generated-difference contract is inconsistent")
    return paths


def _run_canonical_verifier(root: Path) -> None:
    verifier = root / "tools" / "verify_canonical_epoch.py"
    if not verifier.is_file():
        raise PartsReleaseError("canonical evidence verifier is missing")
    result = subprocess.run(
        [sys.executable, os.fspath(verifier), os.fspath(root)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise PartsReleaseError(
            f"canonical verifier did not emit strict JSON: {error}; stderr={result.stderr[-1000:]!r}"
        ) from error
    if result.returncode != 0 or not isinstance(report, dict) or report.get("status") != "PASS":
        raise PartsReleaseError(
            f"canonical evidence verifier failed with exit {result.returncode}: {report!r}"
        )


def _component_for(
    relative: str, overlay_paths: set[str], protected_paths: set[str]
) -> str:
    if relative == ROOT_PARTS_PATH:
        return "parts_library_entrypoint"
    if relative.startswith("generated/"):
        return "generated_release"
    if relative in overlay_paths:
        return "parts_library_overlay"
    if relative in protected_paths:
        return "fc34_protected"
    if relative == PREDECESSOR_MANIFEST_NAME:
        return "fc34_predecessor_record"
    return "fc34_base_preserved"


def _payload_rows(
    root: Path, overlay_paths: set[str], protected_paths: set[str]
) -> list[dict[str, Any]]:
    files = _scan_regular_files(root)
    rows: list[dict[str, Any]] = []
    for relative, path in sorted(files.items(), key=lambda row: row[0].encode("utf-8")):
        if relative in {SITE_MANIFEST_NAME, SHA256SUMS_NAME}:
            continue
        rows.append(
            {
                "path": relative,
                "component": _component_for(relative, overlay_paths, protected_paths),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return rows


def _write_sha256sums(root: Path) -> None:
    files = _scan_regular_files(root)
    rows = []
    for relative, path in sorted(files.items(), key=lambda row: row[0].encode("utf-8")):
        if relative == SHA256SUMS_NAME:
            continue
        rows.append(f"{_sha256(path)}  {relative}\n")
    _write_exclusive(root / SHA256SUMS_NAME, "".join(rows).encode("utf-8"))


def _parse_sha256sums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise PartsReleaseError(f"cannot read SHA256SUMS: {error}") from error
    rows: dict[str, str] = {}
    ordered: list[str] = []
    for number, line in enumerate(lines, 1):
        if len(line) < 67 or line[64:66] != "  ":
            raise PartsReleaseError(f"invalid SHA256SUMS line {number}")
        digest, relative = line[:64], line[66:]
        relative = _normalize_relative(relative, "SHA256SUMS path")
        if not HEX64.fullmatch(digest) or relative in rows:
            raise PartsReleaseError(f"invalid SHA256SUMS line {number}")
        rows[relative] = digest
        ordered.append(relative)
    if ordered != sorted(ordered, key=lambda value: value.encode("utf-8")):
        raise PartsReleaseError("SHA256SUMS is not in canonical path order")
    return rows


def _overlay_rows(
    policy: Mapping[str, Any], source_files: Mapping[str, Path], base_files: Mapping[str, Path]
) -> list[dict[str, Any]]:
    rows = []
    for relative in policy["overlay_paths"]:
        source = source_files[relative]
        old = base_files.get(relative)
        rows.append(
            {
                "path": relative,
                "base_sha256": _sha256(old) if old is not None else None,
                "release_sha256": _sha256(source),
                "operation": "replace" if old is not None else "add",
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
    stage_files: Mapping[str, Path],
    generated_differences: list[dict[str, Any]],
    picker_build: Mapping[str, Any],
    canonical_url: str,
    git_tag: str,
) -> dict[str, Any]:
    protected_paths = _protected_predecessor_paths(predecessor["rows"])
    overlay_paths = set(policy["overlay_paths"])
    output_files = _scan_regular_files(root)
    canonical_files = {
        relative.removeprefix("canonical-evidence/"): path
        for relative, path in output_files.items()
        if relative.startswith("canonical-evidence/")
    }
    raw_files = {
        relative: output_files[relative]
        for relative in sorted(_raw_predecessor_paths(predecessor["rows"]))
    }
    protected_files = {relative: output_files[relative] for relative in sorted(protected_paths)}
    return {
        "manifest_version": MANIFEST_VERSION,
        "package_id": PACKAGE_ID,
        "artifact_role": ARTIFACT_ROLE,
        "release_eligible": True,
        "publication": {
            "canonical_public_url": canonical_url,
            "git_tag": git_tag,
        },
        "predecessor_release": {
            "package_id": predecessor["manifest"]["package_id"],
            "bench_build": predecessor["manifest"]["bench_build"],
            "git_tag": predecessor["manifest"]["publication"]["git_tag"],
            "manifest_path": PREDECESSOR_MANIFEST_NAME,
            "manifest_sha256": _sha256(base_files[PREDECESSOR_MANIFEST_NAME]),
            "sha256sums_sha256": _sha256(base_files[SHA256SUMS_NAME]),
            "verification": "verified before overlay with the unchanged fc-3.4 verifier",
        },
        "tool_builds": {
            "force_curve_bench": {
                "build": FORCE_BUILD,
                "path": "index.html",
                "sha256": _sha256(output_files["index.html"]),
                "status": "preserved_byte_identical",
            },
            "ec_parts_library": {
                "build": picker_build["library_build"],
                "path": ROOT_PARTS_PATH,
                "sha256": _sha256(output_files[ROOT_PARTS_PATH]),
                "presentation_role": picker_build["presentation_role"],
                "release_eligible": picker_build["release_eligible"],
                "parts_library_source_identity": picker_build[
                    "parts_library_source_identity"
                ],
                "data_repo_commit": picker_build["repo_commit"],
            },
            "ec_switch_explorer": {
                "path": "ec-switch-explorer.html",
                "sha256": _sha256(output_files["ec-switch-explorer.html"]),
                "status": "preserved_byte_identical",
            },
        },
        "evidence_identity": {
            "path": "canonical-evidence",
            "evidence_epoch_hash": predecessor["evidence"]["evidence_epoch_hash"],
            "tree": _tree_summary(canonical_files),
            "status": "preserved_byte_identical",
        },
        "protection_contract": {
            "protected_paths": _tree_summary(protected_files),
            "raw_csv_paths": _tree_summary(raw_files),
            "force_viewer_sha256": _sha256(output_files["index.html"]),
            "dome_lab_legacy_sha256": _sha256(output_files["dome-lab.html"]),
            "ec_switch_explorer_sha256": _sha256(output_files["ec-switch-explorer.html"]),
        },
        "overlay": {
            "policy_version": policy["policy_version"],
            "policy_name": policy["name"],
            "policy_sha256": _sha256(policy_path),
            "paths": _overlay_rows(policy, source_files, base_files),
            "generated_allowed_differences": generated_differences,
            "root_picker_source": "generated/packs/picker.staged.html",
        },
        "inventory": {
            "manifest_path": SITE_MANIFEST_NAME,
            "manifest_scope": (
                f"all regular files except {SITE_MANIFEST_NAME} and {SHA256SUMS_NAME}"
            ),
            "sha256sums_path": SHA256SUMS_NAME,
            "sha256sums_scope": f"all regular files except {SHA256SUMS_NAME}",
        },
        "files": _payload_rows(root, overlay_paths, protected_paths),
    }


def _validate_site_manifest_identity(manifest: Mapping[str, Any]) -> tuple[str, str]:
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise PartsReleaseError("site manifest has the wrong version")
    if manifest.get("package_id") != PACKAGE_ID or manifest.get("artifact_role") != ARTIFACT_ROLE:
        raise PartsReleaseError("site manifest has the wrong package identity")
    if manifest.get("release_eligible") is not True:
        raise PartsReleaseError("site manifest is not release-eligible")
    publication = manifest.get("publication")
    if not isinstance(publication, dict) or set(publication) != {
        "canonical_public_url",
        "git_tag",
    }:
        raise PartsReleaseError("site manifest has an invalid publication identity")
    return _validate_url(publication["canonical_public_url"]), _validate_tag(
        publication["git_tag"]
    )


def verify_parts_library_release(package_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = _resolve_directory(package_root, "Parts Library site release")
    files = _scan_regular_files(root)
    required = {
        SITE_MANIFEST_NAME,
        SHA256SUMS_NAME,
        PREDECESSOR_MANIFEST_NAME,
        "index.html",
        ROOT_PARTS_PATH,
        "dome-lab.html",
        "ec-switch-explorer.html",
        "generated/generated_manifest.json",
        "generated/packs/picker.staged.html",
        "generated/packs/viewer.staged.html",
        "canonical-evidence/EPOCH_MANIFEST.json",
    }
    missing = sorted(required - set(files))
    if missing:
        raise PartsReleaseError(f"site release is missing required paths: {missing}")

    manifest = _read_json(files[SITE_MANIFEST_NAME], "site release manifest")
    if not isinstance(manifest, dict):
        raise PartsReleaseError("site release manifest must be an object")
    canonical_url, git_tag = _validate_site_manifest_identity(manifest)

    declared = _manifest_rows(manifest, "site release manifest")
    payload = set(files) - {SITE_MANIFEST_NAME, SHA256SUMS_NAME}
    if set(declared) != payload:
        raise PartsReleaseError("site manifest has missing or extra package paths")
    predecessor_manifest = _read_json(
        files[PREDECESSOR_MANIFEST_NAME], "fc-3.4 predecessor manifest"
    )
    predecessor = {
        "manifest": predecessor_manifest,
        "rows": _manifest_rows(predecessor_manifest, "fc-3.4 predecessor manifest"),
        "evidence": predecessor_manifest.get("evidence_identity"),
    }
    if predecessor_manifest.get("package_id") != fc34.PACKAGE_ID:
        raise PartsReleaseError("site package has the wrong predecessor manifest")
    if not isinstance(predecessor["evidence"], dict):
        raise PartsReleaseError("predecessor manifest has no evidence identity")
    predecessor_identity = manifest.get("predecessor_release")
    expected_predecessor_identity = {
        "package_id": predecessor_manifest.get("package_id"),
        "bench_build": predecessor_manifest.get("bench_build"),
        "git_tag": (predecessor_manifest.get("publication") or {}).get("git_tag"),
        "manifest_path": PREDECESSOR_MANIFEST_NAME,
        "manifest_sha256": _sha256(files[PREDECESSOR_MANIFEST_NAME]),
        "sha256sums_sha256": predecessor_identity.get("sha256sums_sha256")
        if isinstance(predecessor_identity, dict)
        else None,
        "verification": "verified before overlay with the unchanged fc-3.4 verifier",
    }
    if predecessor_identity != expected_predecessor_identity:
        raise PartsReleaseError("site manifest predecessor identity is inconsistent")
    if not isinstance(predecessor_identity.get("sha256sums_sha256"), str) or not HEX64.fullmatch(
        predecessor_identity["sha256sums_sha256"]
    ):
        raise PartsReleaseError("site manifest has an invalid predecessor SHA256SUMS identity")

    overlay_paths = _validate_overlay_manifest(
        manifest.get("overlay"), predecessor["rows"], files
    )

    protected_paths = _protected_predecessor_paths(predecessor["rows"])
    for relative in sorted(protected_paths):
        old = predecessor["rows"].get(relative)
        current = files.get(relative)
        if current is None or old is None:
            raise PartsReleaseError(f"protected predecessor path is missing: {relative}")
        if current.stat().st_size != old["bytes"] or _sha256(current) != old["sha256"]:
            raise PartsReleaseError(f"protected fc-3.4 path changed: {relative}")

    for relative in sorted(payload):
        row = declared[relative]
        expected_component = _component_for(relative, overlay_paths, protected_paths)
        if set(row) != {"path", "component", "bytes", "sha256"}:
            raise PartsReleaseError(f"invalid site-manifest file row: {relative}")
        if row["component"] != expected_component:
            raise PartsReleaseError(f"site-manifest component mismatch: {relative}")
        path = files[relative]
        if path.stat().st_size != row["bytes"] or _sha256(path) != row["sha256"]:
            raise PartsReleaseError(f"site release payload mismatch: {relative}")

    sums = _parse_sha256sums(files[SHA256SUMS_NAME])
    expected_sum_paths = set(files) - {SHA256SUMS_NAME}
    if set(sums) != expected_sum_paths:
        raise PartsReleaseError("SHA256SUMS has missing or extra package paths")
    for relative, digest in sums.items():
        if _sha256(files[relative]) != digest:
            raise PartsReleaseError(f"SHA256SUMS mismatch: {relative}")

    if files[ROOT_PARTS_PATH].read_bytes() != files[
        "generated/packs/picker.staged.html"
    ].read_bytes():
        raise PartsReleaseError("root Parts Library is not byte-identical to generated picker")
    if files["index.html"].read_bytes() != files[
        "generated/packs/viewer.staged.html"
    ].read_bytes():
        raise PartsReleaseError("root Force viewer is not byte-identical to generated viewer")

    generated_files = {
        relative.removeprefix("generated/"): path
        for relative, path in files.items()
        if relative.startswith("generated/")
    }
    _validate_generated_manifest(generated_files)
    picker_build = _parse_picker_build(files[ROOT_PARTS_PATH])

    tool_builds = manifest.get("tool_builds")
    if not isinstance(tool_builds, dict):
        raise PartsReleaseError("site manifest has no tool-build identities")
    expected_force = {
        "build": FORCE_BUILD,
        "path": "index.html",
        "sha256": _sha256(files["index.html"]),
        "status": "preserved_byte_identical",
    }
    expected_parts = {
        "build": picker_build["library_build"],
        "path": ROOT_PARTS_PATH,
        "sha256": _sha256(files[ROOT_PARTS_PATH]),
        "presentation_role": picker_build["presentation_role"],
        "release_eligible": picker_build["release_eligible"],
        "parts_library_source_identity": picker_build[
            "parts_library_source_identity"
        ],
        "data_repo_commit": picker_build["repo_commit"],
    }
    expected_explorer = {
        "path": "ec-switch-explorer.html",
        "sha256": _sha256(files["ec-switch-explorer.html"]),
        "status": "preserved_byte_identical",
    }
    if tool_builds != {
        "force_curve_bench": expected_force,
        "ec_parts_library": expected_parts,
        "ec_switch_explorer": expected_explorer,
    }:
        raise PartsReleaseError("site manifest tool-build identities are inconsistent")

    canonical_files = {
        relative.removeprefix("canonical-evidence/"): path
        for relative, path in files.items()
        if relative.startswith("canonical-evidence/")
    }
    evidence_identity = manifest.get("evidence_identity")
    if evidence_identity != {
        "path": "canonical-evidence",
        "evidence_epoch_hash": predecessor["evidence"].get("evidence_epoch_hash"),
        "tree": _tree_summary(canonical_files),
        "status": "preserved_byte_identical",
    }:
        raise PartsReleaseError("site manifest evidence identity is inconsistent")

    protected_files = {relative: files[relative] for relative in sorted(protected_paths)}
    raw_files = {
        relative: files[relative]
        for relative in sorted(_raw_predecessor_paths(predecessor["rows"]))
    }
    if manifest.get("protection_contract") != {
        "protected_paths": _tree_summary(protected_files),
        "raw_csv_paths": _tree_summary(raw_files),
        "force_viewer_sha256": _sha256(files["index.html"]),
        "dome_lab_legacy_sha256": _sha256(files["dome-lab.html"]),
        "ec_switch_explorer_sha256": _sha256(files["ec-switch-explorer.html"]),
    }:
        raise PartsReleaseError("site manifest protection contract is inconsistent")

    inventory = manifest.get("inventory")
    if inventory != {
        "manifest_path": SITE_MANIFEST_NAME,
        "manifest_scope": f"all regular files except {SITE_MANIFEST_NAME} and {SHA256SUMS_NAME}",
        "sha256sums_path": SHA256SUMS_NAME,
        "sha256sums_scope": f"all regular files except {SHA256SUMS_NAME}",
    }:
        raise PartsReleaseError("site manifest inventory scope is inconsistent")

    _run_canonical_verifier(root / "canonical-evidence")
    return {
        "status": "PASS",
        "package_id": PACKAGE_ID,
        "parts_build": PARTS_BUILD,
        "force_build": FORCE_BUILD,
        "canonical_public_url": canonical_url,
        "git_tag": git_tag,
        "file_count": len(files),
        "bytes": sum(path.stat().st_size for path in files.values()),
        "index_sha256": _sha256(files["index.html"]),
        "parts_sha256": _sha256(files[ROOT_PARTS_PATH]),
        "manifest_sha256": _sha256(files[SITE_MANIFEST_NAME]),
        "sha256sums_sha256": _sha256(files[SHA256SUMS_NAME]),
        "evidence_tree_sha256": _tree_summary(canonical_files)["sha256"],
    }


def _promote_atomic(staging: Path, output: Path) -> None:
    lock = output.with_name(f".{output.name}.parts-release-lock")
    descriptor: int | None = None
    try:
        descriptor = os.open(os.fspath(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"EC Parts Library release promotion lock\n")
        os.close(descriptor)
        descriptor = None
        if _lexists(output):
            raise PartsReleaseError(f"refusing to replace existing output: {output}")
        os.rename(staging, output)
    except FileExistsError as error:
        raise PartsReleaseError(
            f"another release promotion is active or the output exists: {output}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def build_parts_library_release(
    *,
    base_release: str | os.PathLike[str],
    release_source: str | os.PathLike[str],
    staging: str | os.PathLike[str],
    policy: str | os.PathLike[str],
    output: str | os.PathLike[str],
    canonical_url: str,
    git_tag: str,
) -> dict[str, Any]:
    base_root = _resolve_directory(base_release, "verified fc-3.4 base")
    source_root = _resolve_directory(release_source, "release source")
    stage_root = _resolve_directory(staging, "release staging")
    policy_path = _resolve_file(policy, "overlay policy")
    canonical_url = _validate_url(canonical_url)
    git_tag = _validate_tag(git_tag)
    output_path = Path(output).resolve(strict=False)
    if _lexists(output_path):
        raise PartsReleaseError(f"refusing to replace existing or unsafe output: {output_path}")
    for label, root in (
        ("fc-3.4 base", base_root),
        ("release source", source_root),
        ("release staging", stage_root),
    ):
        if _path_within(output_path, root):
            raise PartsReleaseError(f"output must not be inside {label}")

    # This call is deliberately first: no overlay is read or output created
    # until the unchanged predecessor verifier accepts the base package.
    try:
        base_report = fc34.verify_public_release(base_root)
    except Exception as error:
        raise PartsReleaseError(f"fc-3.4 base verification failed: {error}") from error
    if (
        not isinstance(base_report, dict)
        or base_report.get("status") != "PASS"
        or base_report.get("package_id") != fc34.PACKAGE_ID
        or base_report.get("bench_build") != FORCE_BUILD
    ):
        raise PartsReleaseError("fc-3.4 base verifier returned the wrong identity")

    base_files = _scan_regular_files(base_root)
    predecessor = _predecessor_contract(base_files)
    policy_object = _load_policy(policy_path)
    source_files: dict[str, Path] = {}
    for relative in policy_object["overlay_paths"]:
        path = source_root / Path(*PurePosixPath(relative).parts)
        try:
            resolved = path.resolve(strict=True)
        except OSError as error:
            raise PartsReleaseError(f"overlay source path is missing: {relative}") from error
        if (
            not _path_within(resolved, source_root)
            or not resolved.is_file()
            or path.is_symlink()
        ):
            raise PartsReleaseError(f"unsafe overlay source path: {relative}")
        source_files[relative] = resolved

    stage_files = _scan_regular_files(stage_root)
    _validate_generated_manifest(stage_files)
    picker_build = _parse_picker_build(stage_files["packs/picker.staged.html"])
    if stage_files["packs/viewer.staged.html"].read_bytes() != base_files[
        "index.html"
    ].read_bytes():
        raise PartsReleaseError(
            "release-staging Force viewer is not byte-identical to fc-3.4 index.html"
        )
    generated_differences = _generated_difference_rows(base_files, stage_files)

    base_snapshot = _entries(base_files)
    source_snapshot = _entries(source_files)
    stage_snapshot = _entries(stage_files)
    policy_snapshot = (policy_path.stat().st_size, _sha256(policy_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX, dir=output_path.parent))
    promoted = False
    try:
        omitted = {
            SHA256SUMS_NAME,
            SITE_MANIFEST_NAME,
            ROOT_PARTS_PATH,
            *policy_object["overlay_paths"],
            *(relative for relative in base_files if relative.startswith("generated/")),
        }
        _copy_files(
            {relative: path for relative, path in base_files.items() if relative not in omitted},
            temporary,
        )
        _copy_files(source_files, temporary)
        _copy_files(stage_files, temporary / "generated")
        _copy_file(
            stage_files["packs/picker.staged.html"], temporary / ROOT_PARTS_PATH
        )

        manifest = _build_manifest(
            temporary,
            base_files=base_files,
            predecessor=predecessor,
            policy=policy_object,
            policy_path=policy_path,
            source_files=source_files,
            stage_files=stage_files,
            generated_differences=generated_differences,
            picker_build=picker_build,
            canonical_url=canonical_url,
            git_tag=git_tag,
        )
        _write_exclusive(temporary / SITE_MANIFEST_NAME, _json_bytes(manifest))
        _write_sha256sums(temporary)
        report = verify_parts_library_release(temporary)

        if _entries(base_files) != base_snapshot:
            raise PartsReleaseError("fc-3.4 base changed during the release build")
        if _entries(source_files) != source_snapshot:
            raise PartsReleaseError("release overlay source changed during the release build")
        if _entries(stage_files) != stage_snapshot:
            raise PartsReleaseError("release staging changed during the release build")
        if (policy_path.stat().st_size, _sha256(policy_path)) != policy_snapshot:
            raise PartsReleaseError("overlay policy changed during the release build")

        _promote_atomic(temporary, output_path)
        promoted = True
        try:
            final_report = verify_parts_library_release(output_path)
            if report != final_report:
                raise PartsReleaseError("verification report changed during atomic promotion")
        except Exception as verification_error:
            try:
                os.rename(output_path, temporary)
                promoted = False
            except OSError as rollback_error:
                raise PartsReleaseError(
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
    build = subparsers.add_parser("build", help="build and atomically promote a site release")
    build.add_argument("--base-release", required=True, type=Path)
    build.add_argument("--release-source", required=True, type=Path)
    build.add_argument("--staging", required=True, type=Path)
    build.add_argument("--policy", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--canonical-url", required=True)
    build.add_argument("--git-tag", required=True)
    verify = subparsers.add_parser("verify", help="verify an existing Parts Library site release")
    verify.add_argument("package_root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build_parts_library_release(
                base_release=args.base_release,
                release_source=args.release_source,
                staging=args.staging,
                policy=args.policy,
                output=args.output,
                canonical_url=args.canonical_url,
                git_tag=args.git_tag,
            )
        else:
            report = verify_parts_library_release(args.package_root)
    except PartsReleaseError as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
