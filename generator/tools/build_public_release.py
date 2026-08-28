#!/usr/bin/env python3
"""Build or verify the deterministic Force Curve Bench public release package.

The builder is deliberately fail-closed.  It accepts an already generated
release staging tree and copies that tree, the exact public documentation,
current generator source, and the independently sealed canonical-evidence
package into a new immutable directory.  Inputs are validated before copying,
again after copying, and once more through the completed package manifest.

No historical Step-2 or Step-3 manifest is promoted to the root.  The public
release has its own authority, ``FORCE_CURVE_BENCH_RELEASE_MANIFEST.json``;
the sealed ``EPOCH_MANIFEST.json`` remains nested under
``canonical-evidence/`` and retains its original meaning.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit
import zlib


MANIFEST_NAME = "FORCE_CURVE_BENCH_RELEASE_MANIFEST.json"
SHA256SUMS_NAME = "SHA256SUMS"
GITATTRIBUTES_NAME = ".gitattributes"
GITATTRIBUTES_BYTES = b"* -text\n"
NOJEKYLL_NAME = ".nojekyll"
NOJEKYLL_BYTES = b""
TEMP_STAGING_PREFIX = ".fc34-"
MANIFEST_VERSION = 1
PACKAGE_ID = "force-curve-bench-fc-3.4-public"
ARTIFACT_ROLE = "public_force_curve_bench_release"
BENCH_BUILD = "fc-3.4"
PRESENTATION_ROLE = "public_release"
DATA_ARTIFACT_ROLE = "canonical_retention_authority"
FROZEN_RELEASE_REPLACEMENTS = ("README.md", "index.html")
REPOSITORY_INVENTORY_FIELDS = (
    "path",
    "bytes",
    "sha256",
    "category",
    "git_blob_oid",
    "git_object_format",
    "mode",
    "git_object_type",
    "is_raw_csv",
    "set",
    "acquisition_id",
    "evidence_group_id",
)

EXPECTED_REPO_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
EXPECTED_REPO_TREE = "e43d25a3fed8c5177467bba96a5abbdd5a3442b0"
EXPECTED_EVIDENCE_IDENTITY = (
    "7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a"
)
EXPECTED_CANONICAL_PACKAGE_ID = "canonical-evidence-epoch-6e86ac19-step2"
EXPECTED_CANONICAL_VERIFIER_SHA256 = (
    "36faf29111351a66e71b9d0f1a61c1d14cad4603181806c45f538e52fbad017e"
)
CANONICAL_VERIFIER = "tools/verify_canonical_epoch.py"
EXPECTED_OG_ASSET_PATH = "assets/force-curve-bench-fc-3.4-og.png"
EXPECTED_OG_IMAGE_SHA256 = (
    "e4ce9f3df6a1a166c0683d50bb854843719ddd3d435487c12ef1c03961fbbba0"
)

PROJECT_RIGHTS_NOTICE = (
    "© 2026 Brian “BuddyOG” Gebo — Unreal Keyboards. All rights reserved."
)
PROJECT_LICENSE = "All rights reserved; no open-source license is granted."
TERMS_PATH = "documentation/index.html#rights-and-reuse"
SHARING_PERMISSION = (
    "The owner permits sharing unmodified charts exported by Force Curve Bench "
    "and unmodified data files published with the repository when the share "
    "includes attribution to BuddyOG / Unreal Keyboards and a link to the "
    "repository or canonical live viewer. This limited permission is not an "
    "open license or a broader grant for the software, documentation, or data."
)
FONT_RIGHTS_NOTE = (
    "Inter and IBM Plex Mono are redistributed separately under the SIL Open "
    "Font License 1.1; those font licenses do not change the project rights."
)
CANONICAL_EVIDENCE_EXCEPTION = (
    "No exclusion policy is applied inside canonical-evidence; every sealed "
    "byte is copied and reverified."
)
FROZEN_REPOSITORY_POLICY = (
    "Every path from the frozen Git tree is copied byte-identically to the "
    "package root except index.html and README.md, which are intentionally "
    "replaced by the fc-3.4 viewer and public README."
)
CHECKOUT_BYTE_PRESERVATION_PURPOSE = (
    "disable Git text/EOL conversion for every release path"
)
STATIC_HOSTING_BYPASS_PURPOSE = (
    "publish the package as exact static files without Jekyll processing"
)
EVIDENCE_AUTHORITY_NOTE = (
    "The nested EPOCH_MANIFEST.json remains the sealed evidence authority; "
    "it is not the public-release manifest."
)

REQUIRED_GENERATOR_FILES = (
    "pyproject.toml",
    "requirements-lock.txt",
    "js/package.json",
    "js/package-lock.json",
    "domelab_pipeline/pipeline.py",
    "domelab_pipeline/release_reference/index.release.html",
    "domelab_pipeline/release_reference/third_party/fonts/README.md",
    "domelab_pipeline/release_reference/third_party/fonts/INTER-LICENSE.txt",
    "domelab_pipeline/release_reference/third_party/fonts/IBM-PLEX-LICENSE.txt",
    "tools/build_public_release.py",
)
REQUIRED_DOC_FILES = (
    "README.md",
    "documentation/index.html",
    "documentation/THIRD_PARTY_NOTICES.md",
    "documentation/licenses/INTER-LICENSE.txt",
    "documentation/licenses/IBM-PLEX-LICENSE.txt",
)
REQUIRED_GENERATED_FILES = (
    "generated_manifest.json",
    "schema_meta.staged.json",
    "parity_report.json",
    "bench_tests.staged.json",
    "intake_retention_decisions.json",
    "packs/viewer.staged.html",
)

EXCLUDED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "venv",
    }
)
EXCLUDED_FILE_NAMES = frozenset(
    {
        ".coverage",
        ".DS_Store",
        "DRAFT_CHECKLIST.md",
        "Thumbs.db",
    }
)
EXCLUDED_FILE_SUFFIXES = frozenset({".pyc", ".pyo"})

PLACEHOLDER_PATTERNS = {
    "pending public URL token": re.compile(r"PUBLIC_VIEWER_URL_PENDING", re.I),
    "promotion-time placeholder": re.compile(r"promotion[- ]time placeholder", re.I),
    "pending owner choice": re.compile(r"pending (?:the )?owner(?:'s)? choice", re.I),
    "unfinished release statement": re.compile(
        r"(?:remain|remains|is|are) pending(?:[.;]| owner| final| browser| promotion)",
        re.I,
    ),
    "owner-selects URL comment": re.compile(
        r"owner (?:selects|chooses).{0,40}canonical.{0,20}url", re.I
    ),
    "template host": re.compile(
        r"(?:https?://)?(?:www\.)?(?:example\.(?:com|org|net)|localhost)(?:[:/]|\b)",
        re.I,
    ),
    "template token": re.compile(
        r"\b(?:TBD|TKTK|REPLACE[_ -]?ME|CHANGE[_ -]?ME|YOUR[_ -]?(?:URL|HASH|TAG))\b",
        re.I,
    ),
    "angle-bracket release token": re.compile(
        r"<(?:published-canonical-evidence-root|released-(?:index\.html|manifest\.json)|"
        r"promotion-time[^>]*|epoch-workspace)>",
        re.I,
    ),
    "mustache token": re.compile(r"\{\{[^{}]+\}\}"),
}

FONT_ASSET_PATTERN = re.compile(r"\.woff2$", re.I)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
TAG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MANIFEST_FIELDS = {
    "manifest_version",
    "package_id",
    "artifact_role",
    "release_eligible",
    "bench_build",
    "release_profile",
    "publication",
    "rights",
    "source_identity",
    "build_identity",
    "evidence_identity",
    "counts",
    "third_party_fonts",
    "copy_policy",
    "inventory",
    "byte_totals",
    "files",
}


class PublicReleaseError(RuntimeError):
    """An input or package violates the public-release contract."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PublicReleaseError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _read_json(path: Path) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, PublicReleaseError) as error:
        raise PublicReleaseError(f"cannot read strict UTF-8 JSON {path}: {error}") from error


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _canonical_json_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _resolve_directory(path: str | os.PathLike[str], label: str) -> Path:
    candidate = Path(path)
    if candidate.is_symlink() or _is_reparse_point(candidate) or not candidate.is_dir():
        raise PublicReleaseError(
            f"{label} must be an existing non-link directory: {candidate}"
        )
    try:
        return candidate.resolve(strict=True)
    except OSError as error:
        raise PublicReleaseError(f"cannot resolve {label} {candidate}: {error}") from error


def _resolve_file(path: str | os.PathLike[str], label: str) -> Path:
    candidate = Path(path)
    if candidate.is_symlink() or _is_reparse_point(candidate) or not candidate.is_file():
        raise PublicReleaseError(
            f"{label} must be an existing regular non-link file: {candidate}"
        )
    try:
        return candidate.resolve(strict=True)
    except OSError as error:
        raise PublicReleaseError(f"cannot resolve {label} {candidate}: {error}") from error


def _normalize_relative(raw: str, label: str = "path") -> str:
    if not isinstance(raw, str) or not raw:
        raise PublicReleaseError(f"{label} must be a nonempty string")
    if "\\" in raw or ":" in raw or "\x00" in raw or raw.startswith("/"):
        raise PublicReleaseError(f"unsafe {label}: {raw!r}")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or pure.as_posix() != raw:
        raise PublicReleaseError(f"non-canonical {label}: {raw!r}")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise PublicReleaseError(f"unsafe {label}: {raw!r}")
    return raw


def _path_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath(
            [os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(root))]
        ) == os.path.normcase(os.path.abspath(root))
    except ValueError:
        return False


def _scan_regular_files(root: Path) -> dict[str, Path]:
    """Inventory every file and reject links, special entries, and case collisions."""
    root = _resolve_directory(root, "input tree")
    files: dict[str, Path] = {}
    folded: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        kept: list[str] = []
        for name in sorted(dirnames):
            child = directory_path / name
            relative = _normalize_relative(child.relative_to(root).as_posix())
            if child.is_symlink() or _is_reparse_point(child) or not child.is_dir():
                raise PublicReleaseError(
                    f"linked or non-directory entry is forbidden: {relative}"
                )
            kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            child = directory_path / name
            relative = _normalize_relative(child.relative_to(root).as_posix())
            if child.is_symlink() or _is_reparse_point(child) or not child.is_file():
                raise PublicReleaseError(
                    f"linked or non-regular file is forbidden: {relative}"
                )
            key = relative.casefold()
            if key in folded:
                raise PublicReleaseError(
                    f"case-insensitive path collision: {folded[key]!r} and {relative!r}"
                )
            folded[key] = relative
            files[relative] = child
    return files


def _exclude_directory(name: str) -> bool:
    lowered = name.casefold()
    return lowered in {item.casefold() for item in EXCLUDED_DIRECTORY_NAMES} or lowered.endswith(
        ".egg-info"
    )


def _selected_files(root: Path) -> tuple[dict[str, Path], list[str]]:
    """Inventory a source/docs tree while recording deterministic exclusions."""
    root = _resolve_directory(root, "selective input tree")
    files: dict[str, Path] = {}
    excluded: list[str] = []
    folded: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        kept: list[str] = []
        for name in sorted(dirnames):
            child = directory_path / name
            relative = _normalize_relative(child.relative_to(root).as_posix())
            if child.is_symlink() or _is_reparse_point(child) or not child.is_dir():
                raise PublicReleaseError(
                    f"linked or non-directory entry is forbidden: {relative}"
                )
            if _exclude_directory(name):
                excluded.append(relative + "/")
            else:
                kept.append(name)
        dirnames[:] = kept
        for name in sorted(filenames):
            child = directory_path / name
            relative = _normalize_relative(child.relative_to(root).as_posix())
            if child.is_symlink() or _is_reparse_point(child) or not child.is_file():
                raise PublicReleaseError(
                    f"linked or non-regular file is forbidden: {relative}"
                )
            if (
                name in EXCLUDED_FILE_NAMES
                or child.suffix.casefold() in EXCLUDED_FILE_SUFFIXES
            ):
                excluded.append(relative)
                continue
            key = relative.casefold()
            if key in folded:
                raise PublicReleaseError(
                    f"case-insensitive path collision: {folded[key]!r} and {relative!r}"
                )
            folded[key] = relative
            files[relative] = child
    return files, sorted(excluded, key=lambda value: value.encode("utf-8"))


def _entries(files: Mapping[str, Path]) -> list[dict[str, Any]]:
    return [
        {"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)}
        for relative, path in sorted(files.items(), key=lambda row: row[0].encode("utf-8"))
    ]


def _tree_summary(files: Mapping[str, Path]) -> dict[str, Any]:
    rows = _entries(files)
    return {
        "file_count": len(rows),
        "bytes": sum(row["bytes"] for row in rows),
        "tree_sha256": _canonical_json_hash(rows),
    }


def _git_object_oid(kind: str, payload: bytes) -> str:
    header = f"{kind} {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def _git_tree_oid(rows: Iterable[Mapping[str, str]]) -> str:
    """Reconstruct a SHA-1 Git tree from a validated flat blob inventory."""
    root: dict[str, Any] = {}
    for row in rows:
        parts = PurePosixPath(row["path"]).parts
        node = root
        for part in parts[:-1]:
            existing = node.get(part)
            if existing is None:
                existing = {}
                node[part] = existing
            if not isinstance(existing, dict):
                raise PublicReleaseError(
                    f"frozen repository has a file/directory prefix collision: {row['path']}"
                )
            node = existing
        name = parts[-1]
        if name in node:
            raise PublicReleaseError(f"duplicate frozen repository path: {row['path']}")
        node[name] = (row["mode"], row["git_blob_oid"])

    def digest(node: Mapping[str, Any]) -> str:
        entries: list[tuple[bytes, bytes]] = []
        for name, value in node.items():
            encoded_name = name.encode("utf-8")
            if isinstance(value, dict):
                mode = b"40000"
                oid = digest(value)
                sort_key = encoded_name + b"/"
            else:
                mode = value[0].encode("ascii")
                oid = value[1]
                sort_key = encoded_name
            entry = mode + b" " + encoded_name + b"\0" + bytes.fromhex(oid)
            entries.append((sort_key, entry))
        payload = b"".join(entry for _, entry in sorted(entries, key=lambda item: item[0]))
        return _git_object_oid("tree", payload)

    return digest(root)


def _read_repository_inventory(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != REPOSITORY_INVENTORY_FIELDS:
                raise PublicReleaseError(
                    "frozen repository inventory has unexpected or reordered columns"
                )
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        raise PublicReleaseError(
            f"cannot read frozen repository inventory {path}: {error}"
        ) from error
    if not rows:
        raise PublicReleaseError("frozen repository inventory is empty")

    seen: set[str] = set()
    folded: dict[str, str] = {}
    for number, row in enumerate(rows, start=2):
        if (
            None in row
            or set(row) != set(REPOSITORY_INVENTORY_FIELDS)
            or any(not isinstance(row.get(field), str) for field in REPOSITORY_INVENTORY_FIELDS)
        ):
            raise PublicReleaseError(f"invalid frozen repository inventory row {number}")
        relative = _normalize_relative(row["path"], "frozen repository path")
        if any(ord(character) < 32 for character in relative):
            raise PublicReleaseError(f"control character in frozen repository path: {relative!r}")
        if relative in seen:
            raise PublicReleaseError(f"duplicate frozen repository path: {relative}")
        key = relative.casefold()
        if key in folded:
            raise PublicReleaseError(
                f"case-insensitive frozen path collision: {folded[key]!r} and {relative!r}"
            )
        seen.add(relative)
        folded[key] = relative
        raw_bytes = row["bytes"]
        try:
            byte_count = int(raw_bytes)
        except ValueError as error:
            raise PublicReleaseError(
                f"invalid frozen repository byte count at row {number}"
            ) from error
        if byte_count < 0 or str(byte_count) != raw_bytes:
            raise PublicReleaseError(
                f"non-canonical frozen repository byte count at row {number}"
            )
        if not HEX64.fullmatch(row["sha256"]):
            raise PublicReleaseError(f"invalid frozen repository SHA256 at row {number}")
        if not HEX40.fullmatch(row["git_blob_oid"]):
            raise PublicReleaseError(f"invalid frozen repository blob OID at row {number}")
        if row["git_object_format"] != "sha1" or row["git_object_type"] != "blob":
            raise PublicReleaseError(
                f"unsupported frozen repository Git object identity at row {number}"
            )
        if row["mode"] not in {"100644", "100755"}:
            raise PublicReleaseError(
                f"unsupported frozen repository file mode at row {number}: {row['mode']!r}"
            )
    canonical_order = sorted(rows, key=lambda row: row["path"].encode("utf-8"))
    if rows != canonical_order:
        raise PublicReleaseError("frozen repository inventory is not in canonical path order")
    return rows


def _files_at_inventory_paths(root: Path, rows: Iterable[Mapping[str, str]]) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for row in rows:
        relative = row["path"]
        path = root / Path(*PurePosixPath(relative).parts)
        if path.is_symlink() or _is_reparse_point(path) or not path.is_file():
            raise PublicReleaseError(
                f"frozen repository source lacks a regular non-link file: {relative}"
            )
        files[relative] = path
    return files


def _validate_frozen_file_identities(
    files: Mapping[str, Path], rows: Iterable[Mapping[str, str]], label: str
) -> None:
    for row in rows:
        relative = row["path"]
        path = files[relative]
        payload = path.read_bytes()
        if len(payload) != int(row["bytes"]) or _sha256_bytes(payload) != row["sha256"]:
            raise PublicReleaseError(f"{label} SHA256/size mismatch: {relative}")
        if _git_object_oid("blob", payload) != row["git_blob_oid"]:
            raise PublicReleaseError(f"{label} Git blob mismatch: {relative}")


def _frozen_repository_contract(
    canonical_root: Path,
    canonical_manifest: Mapping[str, Any],
    source_root: Path | None = None,
) -> dict[str, Any]:
    frozen = canonical_manifest.get("frozen_repository")
    if not isinstance(frozen, dict):
        raise PublicReleaseError("canonical evidence has no frozen_repository object")
    cache_relative = _normalize_relative(
        frozen.get("cache_root"), "frozen repository cache path"
    )
    inventory_relative = _normalize_relative(
        frozen.get("inventory_path"), "frozen repository inventory path"
    )
    inventory_path = canonical_root / Path(*PurePosixPath(inventory_relative).parts)
    if inventory_path.is_symlink() or _is_reparse_point(inventory_path) or not inventory_path.is_file():
        raise PublicReleaseError("canonical evidence lacks the frozen repository inventory")
    rows = _read_repository_inventory(inventory_path)
    expected_count = canonical_manifest.get("expected_counts", {}).get("repository_paths")
    if type(expected_count) is not int or expected_count != len(rows):
        raise PublicReleaseError("frozen repository inventory count is inconsistent")
    tree_oid = _git_tree_oid(rows)
    if tree_oid != frozen.get("tree_oid") or tree_oid != EXPECTED_REPO_TREE:
        raise PublicReleaseError(
            f"frozen repository Git tree mismatch: reconstructed={tree_oid!r}"
        )

    cache_root = _resolve_directory(
        canonical_root / Path(*PurePosixPath(cache_relative).parts),
        "sealed frozen repository cache",
    )
    cache_files = _scan_regular_files(cache_root)
    expected_paths = {row["path"] for row in rows}
    if set(cache_files) != expected_paths:
        missing = sorted(expected_paths - set(cache_files))
        extra = sorted(set(cache_files) - expected_paths)
        raise PublicReleaseError(
            "sealed frozen repository cache has missing or extra paths; "
            f"missing={missing}, extra={extra}"
        )
    _validate_frozen_file_identities(cache_files, rows, "sealed frozen repository cache")

    files = cache_files
    source = "canonical_evidence_raw_cache"
    if source_root is not None:
        files = _files_at_inventory_paths(source_root, rows)
        _validate_frozen_file_identities(files, rows, "explicit frozen repository source")
        if _entries(files) != _entries(cache_files):
            raise PublicReleaseError(
                "explicit frozen repository source is not byte-identical to the sealed cache"
            )
        source = "explicit_source_validated_against_canonical_evidence"
    return {
        "files": files,
        "rows": rows,
        "cache_relative": cache_relative,
        "inventory_relative": inventory_relative,
        "commit_oid": frozen["commit_oid"],
        "tree_oid": tree_oid,
        "git_object_format": "sha1",
        "materialization_source": source,
        "summary": _tree_summary(files),
    }


def _require_paths(files: Mapping[str, Path], required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(files), key=lambda value: value.encode("utf-8"))
    if missing:
        raise PublicReleaseError(f"{label} is incomplete; missing: {missing}")


def _extract_json_const(source: str, name: str) -> Any:
    match = re.search(rf"\bconst\s+{re.escape(name)}\s*=", source)
    if not match:
        raise PublicReleaseError(f"viewer has no generated {name} constant")
    start = match.end()
    while start < len(source) and source[start].isspace():
        start += 1
    try:
        value, end = json.JSONDecoder(
            object_pairs_hook=_reject_duplicate_keys
        ).raw_decode(source, start)
    except (json.JSONDecodeError, PublicReleaseError) as error:
        raise PublicReleaseError(f"viewer {name} is not strict JSON: {error}") from error
    if source[end:].lstrip()[:1] != ";":
        raise PublicReleaseError(f"viewer {name} JSON is not terminated by a semicolon")
    return value


def _validate_url(raw: str) -> str:
    if not isinstance(raw, str) or raw != raw.strip() or len(raw) > 2048:
        raise PublicReleaseError("canonical URL must be a trimmed nonempty string")
    lowered = raw.casefold()
    if any(
        token in lowered
        for token in ("pending", "placeholder", "replace", "example.", "localhost", "tbd")
    ):
        raise PublicReleaseError("canonical URL contains an obvious placeholder")
    parsed = urlsplit(raw)
    try:
        port = parsed.port
    except ValueError as error:
        raise PublicReleaseError("canonical URL contains an invalid port") from error
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise PublicReleaseError(
            "canonical URL must be a clean public HTTPS URL without credentials, port, query, or fragment"
        )
    if parsed.hostname.casefold().endswith((".invalid", ".test", ".example")):
        raise PublicReleaseError("canonical URL uses a non-public placeholder host")
    return raw


def _validate_git_tag(raw: str) -> str:
    if not isinstance(raw, str) or raw != raw.strip() or not TAG_PATTERN.fullmatch(raw):
        raise PublicReleaseError(
            "Git tag must contain only letters, digits, period, underscore, and hyphen"
        )
    lowered = raw.casefold()
    if not any(character.isdigit() for character in raw) or any(
        token in lowered
        for token in ("pending", "placeholder", "replace", "draft", "latest", "tbd", "todo")
    ):
        raise PublicReleaseError("Git tag is an obvious placeholder rather than a frozen tag")
    return raw


def _read_utf8(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PublicReleaseError(f"cannot read {label} as UTF-8: {path}: {error}") from error


def _scan_placeholders(files: Mapping[str, Path], label: str) -> None:
    findings: list[str] = []
    text_suffixes = {".css", ".html", ".js", ".json", ".md", ".txt"}
    for relative, path in sorted(files.items()):
        if path.suffix.casefold() not in text_suffixes:
            continue
        source = _read_utf8(path, f"{label} file")
        for name, pattern in PLACEHOLDER_PATTERNS.items():
            if pattern.search(source):
                findings.append(f"{relative}: {name}")
    if findings:
        raise PublicReleaseError(f"{label} contains unresolved release placeholders: {findings}")


def _html_tag_with_attributes(source: str, tag: str, attributes: Mapping[str, str]) -> bool:
    for match in re.finditer(rf"<{re.escape(tag)}\b[^>]*>", source, re.I):
        candidate = match.group(0)
        if all(
            re.search(
                rf"\b{re.escape(name)}\s*=\s*([\"']){re.escape(value)}\1",
                candidate,
                re.I,
            )
            for name, value in attributes.items()
        ):
            return True
    return False


def _validate_viewer(viewer: Path, canonical_url: str) -> dict[str, Any]:
    source = _read_utf8(viewer, "release viewer")
    _scan_placeholders({"index.html": viewer}, "release viewer")
    build = _extract_json_const(source, "VIEWER_BUILD")
    if not isinstance(build, dict):
        raise PublicReleaseError("VIEWER_BUILD must be an object")
    expected = {
        "mode": "release",
        "bench_build": BENCH_BUILD,
        "presentation_role": PRESENTATION_ROLE,
        "release_eligible": True,
        "data_artifact_role": DATA_ARTIFACT_ROLE,
        "canonical_data_release_eligible": True,
        "repo_commit": EXPECTED_REPO_COMMIT,
        "data_identity": EXPECTED_EVIDENCE_IDENTITY,
        "canonical_evidence_identity": EXPECTED_EVIDENCE_IDENTITY,
    }
    wrong = {key: (build.get(key), value) for key, value in expected.items() if build.get(key) != value}
    if wrong:
        raise PublicReleaseError(f"viewer is not the exact public release profile: {wrong}")
    for field in (
        "record_count",
        "set_count",
        "retained_run_count",
        "semantic_run_binding_count",
        "unique_acquisition_count",
        "independent_measurement_cohort_count",
    ):
        if type(build.get(field)) is not int or build[field] <= 0:
            raise PublicReleaseError(f"VIEWER_BUILD.{field} must be a positive integer")
    if not _html_tag_with_attributes(
        source, "link", {"rel": "canonical", "href": canonical_url}
    ):
        raise PublicReleaseError("viewer does not contain the exact canonical URL link tag")
    if not _html_tag_with_attributes(
        source, "meta", {"property": "og:url", "content": canonical_url}
    ):
        raise PublicReleaseError("viewer does not contain the exact og:url metadata")
    image_matches = re.findall(
        r"<meta\b(?=[^>]*\bproperty\s*=\s*([\"'])og:image\1)[^>]*\bcontent\s*=\s*([\"'])(.*?)\2[^>]*>",
        source,
        re.I,
    )
    image_urls = [match[2] for match in image_matches]
    if len(image_urls) != 1 or not image_urls[0].startswith("https://"):
        raise PublicReleaseError("viewer must contain exactly one public HTTPS og:image")
    dimension_values: dict[str, int] = {}
    for dimension in ("width", "height"):
        matches = re.findall(
            rf"<meta\b(?=[^>]*\bproperty\s*=\s*([\"'])og:image:{dimension}\1)"
            rf"[^>]*\bcontent\s*=\s*([\"'])(\d+)\2[^>]*>",
            source,
            re.I,
        )
        if len(matches) != 1:
            raise PublicReleaseError(
                f"viewer must contain exactly one numeric og:image:{dimension}"
            )
        value = int(matches[0][2])
        if value <= 0:
            raise PublicReleaseError(f"viewer og:image:{dimension} must be positive")
        dimension_values[dimension] = value
    if canonical_url not in source:
        raise PublicReleaseError("canonical URL is absent from the viewer")
    if PROJECT_RIGHTS_NOTICE not in source:
        raise PublicReleaseError("viewer footer does not contain the settled project rights notice")
    if re.search(r"https?://fonts\.(?:googleapis|gstatic)\.com", source, re.I):
        raise PublicReleaseError("viewer still depends on a remote font service")
    if source.count("data:font/woff2;base64,") < 3 or source.count("@font-face") < 3:
        raise PublicReleaseError("viewer does not contain all three self-hosted WOFF2 font faces")
    return {
        "build": build,
        "og_image": {
            "url": image_urls[0],
            "width": dimension_values["width"],
            "height": dimension_values["height"],
        },
    }


def _png_dimensions(path: Path) -> tuple[int, int]:
    """Validate a PNG chunk stream and return its positive IHDR dimensions."""
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise PublicReleaseError(f"cannot read OG image {path}: {error}") from error
    if len(payload) < 45 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise PublicReleaseError("OG image has an invalid PNG signature")
    offset = 8
    chunks: list[tuple[bytes, bytes]] = []
    while offset < len(payload):
        if offset + 12 > len(payload):
            raise PublicReleaseError("OG image has a truncated PNG chunk")
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(payload):
            raise PublicReleaseError("OG image has an out-of-range PNG chunk")
        data = payload[offset + 8 : offset + 8 + length]
        stored_crc = struct.unpack(">I", payload[offset + 8 + length : end])[0]
        calculated_crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        if stored_crc != calculated_crc:
            raise PublicReleaseError("OG image has a PNG CRC mismatch")
        chunks.append((chunk_type, data))
        offset = end
        if chunk_type == b"IEND":
            break
    if offset != len(payload):
        raise PublicReleaseError("OG image has trailing bytes after IEND")
    if not chunks or chunks[0][0] != b"IHDR" or len(chunks[0][1]) != 13:
        raise PublicReleaseError("OG image lacks a canonical 13-byte IHDR")
    if chunks[-1] != (b"IEND", b"") or not any(kind == b"IDAT" for kind, _ in chunks):
        raise PublicReleaseError("OG image lacks IDAT or terminal IEND")
    width, height = struct.unpack(">II", chunks[0][1][:8])
    if width <= 0 or height <= 0:
        raise PublicReleaseError("OG image dimensions must both be nonzero")
    return width, height


def _validate_assets(
    files: Mapping[str, Path], canonical_url: str, og_image: Mapping[str, Any]
) -> dict[str, Any]:
    asset_paths = sorted(
        relative for relative in files if relative.startswith("assets/")
    )
    if asset_paths != [EXPECTED_OG_ASSET_PATH]:
        missing = EXPECTED_OG_ASSET_PATH not in asset_paths
        unreferenced = [path for path in asset_paths if path != EXPECTED_OG_ASSET_PATH]
        raise PublicReleaseError(
            "public assets must contain exactly the referenced release OG image; "
            f"missing={missing}, unreferenced={unreferenced}"
        )
    image_url = og_image.get("url")
    if not isinstance(image_url, str):
        raise PublicReleaseError("viewer og:image URL is missing")
    canonical_parts = urlsplit(canonical_url)
    image_parts = urlsplit(image_url)
    base_path = canonical_parts.path
    if not base_path.endswith("/"):
        base_path = base_path.rsplit("/", 1)[0] + "/"
    expected_image_path = base_path + EXPECTED_OG_ASSET_PATH
    if (
        image_parts.scheme != "https"
        or image_parts.netloc.casefold() != canonical_parts.netloc.casefold()
        or image_parts.path != expected_image_path
        or image_parts.query
        or image_parts.fragment
    ):
        raise PublicReleaseError(
            "viewer og:image must be the exact packaged asset below the canonical public URL"
        )
    image_path = files[EXPECTED_OG_ASSET_PATH]
    digest = _sha256(image_path)
    if digest != EXPECTED_OG_IMAGE_SHA256:
        raise PublicReleaseError(
            "OG image does not match the hash-pinned fc-3.4 release asset"
        )
    width, height = _png_dimensions(image_path)
    if og_image.get("width") != width or og_image.get("height") != height:
        raise PublicReleaseError(
            "viewer og:image width/height metadata differs from the packaged PNG"
        )
    return {
        "url": image_url,
        "path": EXPECTED_OG_ASSET_PATH,
        "bytes": image_path.stat().st_size,
        "sha256": digest,
        "width": width,
        "height": height,
    }


def _validate_public_layout(files: Mapping[str, Path]) -> None:
    unexpected = sorted(
        relative
        for relative in files
        if relative != "README.md"
        and not relative.startswith("documentation/")
        and not relative.startswith("assets/")
    )
    if unexpected:
        raise PublicReleaseError(
            f"public documentation has unsupported top-level release paths: {unexpected}"
        )


def _validate_docs(
    docs_root: Path,
    files: Mapping[str, Path],
    canonical_url: str,
    git_tag: str,
    generator_root: Path,
) -> None:
    _require_paths(files, REQUIRED_DOC_FILES, "public documentation")
    _scan_placeholders(files, "public documentation")
    combined = "\n".join(
        _read_utf8(path, "public documentation")
        for relative, path in sorted(files.items())
        if path.suffix.casefold() in {".html", ".md", ".txt"}
    )
    if canonical_url not in combined:
        raise PublicReleaseError("canonical URL is absent from the public documentation")
    if git_tag not in combined:
        raise PublicReleaseError("frozen Git tag is absent from the public documentation")
    compact = re.sub(r"[*_`]", "", combined)
    for required in (PROJECT_RIGHTS_NOTICE, "SIL Open Font License 1.1"):
        if required not in compact:
            raise PublicReleaseError(f"public documentation lacks required wording: {required!r}")
    if not all(
        phrase in compact
        for phrase in (
            "permits sharing unmodified charts",
            "unmodified data files",
            "not an open license",
        )
    ):
        raise PublicReleaseError("public documentation lacks the settled limited-sharing terms")
    font_root = generator_root / "domelab_pipeline/release_reference/third_party/fonts"
    for name in ("INTER-LICENSE.txt", "IBM-PLEX-LICENSE.txt"):
        source = font_root / name
        public = docs_root / "documentation/licenses" / name
        if _sha256(source) != _sha256(public):
            raise PublicReleaseError(f"public font license is not byte-identical to source: {name}")


def _generator_provenance(generator_root: Path) -> dict[str, str]:
    package = generator_root / "domelab_pipeline"
    release = package / "release_reference"
    if not package.is_dir() or not release.is_dir():
        raise PublicReleaseError("generator lacks domelab_pipeline/release_reference")
    python_hashes = {
        path.name: _sha256(path)
        for path in sorted(package.iterdir(), key=lambda item: item.name)
        if path.is_file() and not path.is_symlink() and path.suffix == ".py"
    }
    release_hashes: dict[str, str] = {}
    for directory, dirnames, filenames in os.walk(release, followlinks=False):
        dirnames.sort()
        directory_path = Path(directory)
        for name in sorted(filenames):
            path = directory_path / name
            if path.is_symlink() or _is_reparse_point(path) or not path.is_file():
                raise PublicReleaseError(f"unsafe release-reference entry: {path}")
            relative = path.relative_to(release).as_posix()
            release_hashes[relative] = _sha256(path)
    if not python_hashes or "index.release.html" not in release_hashes:
        raise PublicReleaseError("generator source snapshot is incomplete")
    return {
        "generator_source_hash": _canonical_json_hash(python_hashes),
        "release_reference_hash": _canonical_json_hash(release_hashes),
    }


def _validate_generator(
    generator_root: Path, files: Mapping[str, Path], schema: Mapping[str, Any]
) -> dict[str, Any]:
    _require_paths(files, REQUIRED_GENERATOR_FILES, "generator source")
    provenance = _generator_provenance(generator_root)
    declared = schema.get("provenance_hashes")
    if not isinstance(declared, dict):
        raise PublicReleaseError("schema_meta has no provenance_hashes object")
    wrong = {
        key: (provenance[key], declared.get(key))
        for key in provenance
        if provenance[key] != declared.get(key)
    }
    if wrong:
        raise PublicReleaseError(
            f"release staging was not generated from the supplied generator source: {wrong}"
        )
    font_prefix = "domelab_pipeline/release_reference/third_party/fonts/"
    font_paths = sorted(path for path in files if path.startswith(font_prefix))
    assets = [path for path in font_paths if FONT_ASSET_PATTERN.search(path)]
    licenses = [path for path in font_paths if path.endswith("-LICENSE.txt")]
    if len(assets) < 3 or len(licenses) < 2:
        raise PublicReleaseError("generator does not include all font assets and licenses")
    return {**provenance, "font_paths": font_paths}


def _validate_generated(staging: Path, files: Mapping[str, Path]) -> dict[str, Any]:
    _require_paths(files, REQUIRED_GENERATED_FILES, "release staging")
    generated_manifest = _read_json(files["generated_manifest.json"])
    if not isinstance(generated_manifest, dict) or not all(
        isinstance(path, str) and isinstance(digest, str)
        for path, digest in generated_manifest.items()
    ):
        raise PublicReleaseError("generated_manifest.json must be a path-to-SHA256 object")
    expected_paths = set(files) - {"generated_manifest.json"}
    if set(generated_manifest) != expected_paths:
        missing = sorted(expected_paths - set(generated_manifest))
        extra = sorted(set(generated_manifest) - expected_paths)
        raise PublicReleaseError(
            f"generated manifest has missing or extra paths; missing={missing}, extra={extra}"
        )
    for relative in sorted(expected_paths):
        digest = generated_manifest[relative]
        if not HEX64.fullmatch(digest) or _sha256(files[relative]) != digest:
            raise PublicReleaseError(f"generated staging hash mismatch: {relative}")
    schema = _read_json(files["schema_meta.staged.json"])
    if not isinstance(schema, dict):
        raise PublicReleaseError("schema_meta.staged.json must be an object")
    if schema.get("repo_commit") != EXPECTED_REPO_COMMIT:
        raise PublicReleaseError("generated schema has the wrong repository commit")
    provenance = schema.get("provenance_hashes")
    if not isinstance(provenance, dict) or provenance.get(
        "evidence_epoch_hash"
    ) != EXPECTED_EVIDENCE_IDENTITY:
        raise PublicReleaseError("generated schema has the wrong evidence identity")
    parity = _read_json(files["parity_report.json"])
    if not isinstance(parity, dict):
        raise PublicReleaseError("parity_report.json must be an object")
    parity_expected = {
        "artifact_role": DATA_ARTIFACT_ROLE,
        "release_eligible": True,
        "exact_null_flag_audit_match": True,
        "metrics_per_run": 14,
        "audit_fields_per_run": 13,
    }
    wrong = {
        key: (parity.get(key), value)
        for key, value in parity_expected.items()
        if parity.get(key) != value
    }
    if wrong or type(parity.get("runs")) is not int or parity["runs"] <= 0:
        raise PublicReleaseError(f"full release parity proof is incomplete: {wrong}")
    return {"schema": schema, "parity": parity}


def _canonical_contract(
    root: Path, frozen_repository_root: Path | None = None
) -> dict[str, Any]:
    files = _scan_regular_files(root)
    _require_paths(
        files,
        ("EPOCH_MANIFEST.json", "README.md", "SHA256SUMS.csv", CANONICAL_VERIFIER),
        "canonical-evidence package",
    )
    if _sha256(files[CANONICAL_VERIFIER]) != EXPECTED_CANONICAL_VERIFIER_SHA256:
        raise PublicReleaseError("canonical verifier does not match the pinned trust root")
    manifest = _read_json(files["EPOCH_MANIFEST.json"])
    if not isinstance(manifest, dict):
        raise PublicReleaseError("canonical EPOCH_MANIFEST.json must be an object")
    frozen = manifest.get("frozen_repository")
    identity = manifest.get("identity")
    counts = manifest.get("expected_counts")
    if manifest.get("package_id") != EXPECTED_CANONICAL_PACKAGE_ID:
        raise PublicReleaseError("canonical evidence has the wrong package_id")
    if not isinstance(frozen, dict) or (
        frozen.get("commit_oid") != EXPECTED_REPO_COMMIT
        or frozen.get("tree_oid") != EXPECTED_REPO_TREE
    ):
        raise PublicReleaseError("canonical evidence has the wrong frozen repository")
    if not isinstance(identity, dict) or identity.get(
        "evidence_epoch_hash"
    ) != EXPECTED_EVIDENCE_IDENTITY:
        raise PublicReleaseError("canonical evidence has the wrong epoch identity")
    if not isinstance(counts, dict):
        raise PublicReleaseError("canonical evidence has no expected_counts object")
    frozen_repository = _frozen_repository_contract(
        root, manifest, frozen_repository_root
    )
    return {
        "files": files,
        "manifest": manifest,
        "counts": counts,
        "frozen_repository": frozen_repository,
    }


def _run_canonical_verifier(root: Path) -> None:
    verifier = root / Path(*PurePosixPath(CANONICAL_VERIFIER).parts)
    if _sha256(verifier) != EXPECTED_CANONICAL_VERIFIER_SHA256:
        raise PublicReleaseError("canonical verifier trust-root hash mismatch")
    result = subprocess.run(
        [sys.executable, os.fspath(verifier), os.fspath(root), "--compact"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        report = json.loads(result.stdout, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, PublicReleaseError) as error:
        raise PublicReleaseError(
            f"canonical verifier did not emit strict JSON: {error}; stderr={result.stderr[-1000:]!r}"
        ) from error
    if result.returncode != 0 or not isinstance(report, dict) or report.get("status") != "PASS":
        raise PublicReleaseError(
            f"canonical verifier failed with exit {result.returncode}: {report!r}"
        )


def _copy_files(files: Mapping[str, Path], destination: Path) -> None:
    for relative, source in sorted(files.items(), key=lambda row: row[0].encode("utf-8")):
        target = destination / Path(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if _lexists(target):
            raise PublicReleaseError(f"copy-plan collision at {target}")
        with source.open("rb") as input_stream, target.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)


def _prefix_files(files: Mapping[str, Path], prefix: str) -> dict[str, Path]:
    return {f"{prefix}/{relative}": path for relative, path in files.items()}


def _validate_release_copy_plan(
    frozen_paths: Iterable[str], release_owned_paths: Iterable[str]
) -> None:
    frozen = set(frozen_paths)
    release_owned = set(release_owned_paths)
    collisions = frozen & release_owned
    allowed = set(FROZEN_RELEASE_REPLACEMENTS)
    if collisions != allowed:
        raise PublicReleaseError(
            "frozen/release copy-plan collisions must be exactly index.html and README.md; "
            f"actual={sorted(collisions)}, expected={sorted(allowed)}"
        )

    planned = (frozen - allowed) | release_owned
    folded: dict[str, str] = {}
    for relative in sorted(planned, key=lambda value: value.encode("utf-8")):
        key = relative.casefold()
        if key in folded:
            raise PublicReleaseError(
                f"case-insensitive release copy-plan collision: {folded[key]!r} and {relative!r}"
            )
        folded[key] = relative
    planned_folded = set(folded)
    for relative in planned:
        parts = PurePosixPath(relative).parts
        for index in range(1, len(parts)):
            ancestor = "/".join(parts[:index])
            if ancestor.casefold() in planned_folded:
                raise PublicReleaseError(
                    f"release copy-plan file/directory collision: {ancestor!r} and {relative!r}"
                )


def _payload_inventory(
    root: Path, frozen_repository_paths: Iterable[str]
) -> list[dict[str, Any]]:
    files = _scan_regular_files(root)
    forbidden = {MANIFEST_NAME, SHA256SUMS_NAME}
    frozen_paths = set(frozen_repository_paths)
    replacements = set(FROZEN_RELEASE_REPLACEMENTS)
    rows: list[dict[str, Any]] = []
    for relative, path in sorted(files.items(), key=lambda row: row[0].encode("utf-8")):
        if relative in forbidden:
            continue
        if relative in frozen_paths and relative not in replacements:
            component = "frozen_repository"
        else:
            top = relative.split("/", 1)[0]
            component = {
                ".gitattributes": "release_configuration",
                ".nojekyll": "release_configuration",
                "README.md": "documentation",
                "documentation": "documentation",
                "assets": "assets",
                "index.html": "viewer",
                "generator": "generator",
                "generated": "generated",
                "canonical-evidence": "canonical_evidence",
            }.get(top)
        if component is None:
            raise PublicReleaseError(f"unexpected top-level release payload: {relative}")
        rows.append(
            {
                "path": relative,
                "component": component,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    return rows


def _component_totals(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = totals.setdefault(row["component"], {"file_count": 0, "bytes": 0})
        bucket["file_count"] += 1
        bucket["bytes"] += row["bytes"]
    return dict(sorted(totals.items()))


def _parity_manifest_identity(parity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "runs": parity["runs"],
        "metrics_per_run": parity["metrics_per_run"],
        "audit_fields_per_run": parity["audit_fields_per_run"],
        "exact_null_flag_audit_match": parity["exact_null_flag_audit_match"],
        "max_abs_delta": parity.get("max_abs_delta"),
        "max_audit_abs_delta": parity.get("max_audit_abs_delta"),
    }


def _rights_manifest_identity() -> dict[str, str]:
    return {
        "project_notice": PROJECT_RIGHTS_NOTICE,
        "project_license": PROJECT_LICENSE,
        "limited_sharing_permission": SHARING_PERMISSION,
        "third_party_fonts": FONT_RIGHTS_NOTE,
        "terms_path": TERMS_PATH,
    }


def _inventory_manifest_identity() -> dict[str, str]:
    return {
        "manifest_path": MANIFEST_NAME,
        "manifest_scope": (
            f"all regular package files except {MANIFEST_NAME} and {SHA256SUMS_NAME}"
        ),
        "sha256sums_path": SHA256SUMS_NAME,
        "sha256sums_scope": f"all regular package files except {SHA256SUMS_NAME}",
        "path_order": "ascending UTF-8 byte order",
    }


def _validate_excluded_input_paths(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict) or set(value) != {"documentation", "generator"}:
        raise PublicReleaseError(
            "manifest excluded-input paths must contain exactly documentation and generator"
        )
    validated: dict[str, list[str]] = {}
    for component in ("documentation", "generator"):
        rows = value[component]
        if not isinstance(rows, list) or any(not isinstance(row, str) for row in rows):
            raise PublicReleaseError(
                f"manifest excluded-input paths for {component} must be an array of strings"
            )
        if rows != sorted(rows, key=lambda row: row.encode("utf-8")) or len(rows) != len(
            set(rows)
        ):
            raise PublicReleaseError(
                f"manifest excluded-input paths for {component} are not unique canonical order"
            )
        folded: dict[str, str] = {}
        excluded_directories: list[str] = []
        for raw in rows:
            is_directory = raw.endswith("/")
            candidate = raw[:-1] if is_directory else raw
            relative = _normalize_relative(candidate, "excluded input path")
            key = relative.casefold()
            if key in folded:
                raise PublicReleaseError(
                    "case-insensitive excluded-input collision: "
                    f"{folded[key]!r} and {raw!r}"
                )
            folded[key] = raw
            name = PurePosixPath(relative).name
            if is_directory:
                if not _exclude_directory(name):
                    raise PublicReleaseError(
                        f"excluded input directory is outside the declared policy: {raw}"
                    )
                excluded_directories.append(relative + "/")
            elif (
                name not in EXCLUDED_FILE_NAMES
                and PurePosixPath(relative).suffix.casefold()
                not in EXCLUDED_FILE_SUFFIXES
            ):
                raise PublicReleaseError(
                    f"excluded input file is outside the declared policy: {raw}"
                )
        for raw in rows:
            candidate = raw[:-1] if raw.endswith("/") else raw
            if any(
                candidate.startswith(directory)
                for directory in excluded_directories
                if candidate + "/" != directory
            ):
                raise PublicReleaseError(
                    f"redundant excluded input below an excluded directory: {raw}"
                )
        validated[component] = list(rows)
    return validated


def _copy_policy_manifest_identity(
    root: Path, excluded_input_paths: Mapping[str, list[str]]
) -> dict[str, Any]:
    return {
        "excluded_directory_names": sorted(EXCLUDED_DIRECTORY_NAMES),
        "excluded_file_names": sorted(EXCLUDED_FILE_NAMES),
        "excluded_file_suffixes": sorted(EXCLUDED_FILE_SUFFIXES),
        "excluded_input_paths": {
            key: value for key, value in sorted(excluded_input_paths.items())
        },
        "canonical_evidence_exception": CANONICAL_EVIDENCE_EXCEPTION,
        "frozen_repository_policy": FROZEN_REPOSITORY_POLICY,
        "checkout_byte_preservation": {
            "path": GITATTRIBUTES_NAME,
            "sha256": _sha256(root / GITATTRIBUTES_NAME),
            "rule": "* -text",
            "purpose": CHECKOUT_BYTE_PRESERVATION_PURPOSE,
        },
        "static_hosting_bypass": {
            "path": NOJEKYLL_NAME,
            "sha256": _sha256(root / NOJEKYLL_NAME),
            "bytes": (root / NOJEKYLL_NAME).stat().st_size,
            "purpose": STATIC_HOSTING_BYPASS_PURPOSE,
        },
    }


def _frozen_repository_manifest_identity(
    root: Path, frozen_repository: Mapping[str, Any]
) -> dict[str, Any]:
    files = frozen_repository["files"]
    replacements: dict[str, dict[str, Any]] = {}
    for relative in FROZEN_RELEASE_REPLACEMENTS:
        release_path = root / relative
        replacements[relative] = {
            "frozen_bytes": files[relative].stat().st_size,
            "frozen_sha256": _sha256(files[relative]),
            "release_bytes": release_path.stat().st_size,
            "release_sha256": _sha256(release_path),
        }
    return {
        "commit_oid": frozen_repository["commit_oid"],
        "tree_oid": frozen_repository["tree_oid"],
        "git_object_format": frozen_repository["git_object_format"],
        "source_cache_path": (
            "canonical-evidence/" + frozen_repository["cache_relative"]
        ),
        "source_inventory_path": (
            "canonical-evidence/" + frozen_repository["inventory_relative"]
        ),
        "source_tree": frozen_repository["summary"],
        "frozen_file_count": len(files),
        "preserved_file_count": len(files) - len(FROZEN_RELEASE_REPLACEMENTS),
        "release_authority_replacements": replacements,
    }


def _manifest(
    root: Path,
    rows: list[dict[str, Any]],
    canonical_url: str,
    git_tag: str,
    viewer_build: Mapping[str, Any],
    og_asset: Mapping[str, Any],
    generated: Mapping[str, Any],
    generator_provenance: Mapping[str, Any],
    canonical: Mapping[str, Any],
    input_summaries: Mapping[str, Any],
    excluded: Mapping[str, list[str]],
) -> dict[str, Any]:
    viewer_path = root / "index.html"
    schema = generated["schema"]
    parity = generated["parity"]
    canonical_manifest = canonical["manifest"]
    canonical_counts = canonical["counts"]
    frozen_repository = canonical["frozen_repository"]
    font_rows = [
        row
        for row in rows
        if row["path"].startswith(
            "generator/domelab_pipeline/release_reference/third_party/fonts/"
        )
    ]
    return {
        "manifest_version": MANIFEST_VERSION,
        "package_id": PACKAGE_ID,
        "artifact_role": ARTIFACT_ROLE,
        "release_eligible": True,
        "bench_build": BENCH_BUILD,
        "release_profile": {
            "mode": viewer_build["mode"],
            "presentation_role": viewer_build["presentation_role"],
            "data_artifact_role": viewer_build["data_artifact_role"],
            "canonical_data_release_eligible": viewer_build[
                "canonical_data_release_eligible"
            ],
        },
        "publication": {
            "canonical_public_url": canonical_url,
            "git_tag": git_tag,
            "og_image": dict(og_asset),
        },
        "rights": _rights_manifest_identity(),
        "source_identity": {
            "generator_tree": input_summaries["generator"],
            "generator_source_hash": generator_provenance["generator_source_hash"],
            "release_reference_hash": generator_provenance["release_reference_hash"],
            "frozen_repository": _frozen_repository_manifest_identity(
                root, frozen_repository
            ),
        },
        "build_identity": {
            "viewer": {
                "path": "index.html",
                "bytes": viewer_path.stat().st_size,
                "sha256": _sha256(viewer_path),
                "viewer_build_sha256": _canonical_json_hash(viewer_build),
            },
            "generated_tree": input_summaries["generated"],
            "generated_manifest_sha256": _sha256(
                root / "generated/generated_manifest.json"
            ),
            "schema_meta_sha256": _sha256(root / "generated/schema_meta.staged.json"),
            "parity_report_sha256": _sha256(root / "generated/parity_report.json"),
            "pipeline_bundle_hash": schema["provenance_hashes"].get("bundle_hash"),
            "parity": _parity_manifest_identity(parity),
        },
        "evidence_identity": {
            "nested_path": "canonical-evidence",
            "nested_manifest": "canonical-evidence/EPOCH_MANIFEST.json",
            "package_id": canonical_manifest["package_id"],
            "epoch_id": canonical_manifest.get("epoch_id"),
            "evidence_epoch_hash": canonical_manifest["identity"][
                "evidence_epoch_hash"
            ],
            "repository_commit": canonical_manifest["frozen_repository"]["commit_oid"],
            "repository_tree": canonical_manifest["frozen_repository"]["tree_oid"],
            "tree": input_summaries["canonical_evidence"],
            "verifier_path": f"canonical-evidence/{CANONICAL_VERIFIER}",
            "verifier_sha256": EXPECTED_CANONICAL_VERIFIER_SHA256,
            "authority_note": EVIDENCE_AUTHORITY_NOTE,
        },
        "counts": {
            "viewer_records": viewer_build["record_count"],
            "viewer_sets": viewer_build["set_count"],
            "retained_run_bindings": viewer_build["retained_run_count"],
            "unique_acquisitions": viewer_build["unique_acquisition_count"],
            "independent_measurement_cohorts": viewer_build[
                "independent_measurement_cohort_count"
            ],
            "canonical_raw_paths": canonical_counts.get("raw_paths"),
            "canonical_curve_packs": canonical_counts.get("curve_packs"),
            "frozen_repository_paths": len(frozen_repository["files"]),
            "frozen_repository_preserved_paths": (
                len(frozen_repository["files"]) - len(FROZEN_RELEASE_REPLACEMENTS)
            ),
            "release_authority_replacements": len(FROZEN_RELEASE_REPLACEMENTS),
        },
        "third_party_fonts": font_rows,
        "copy_policy": _copy_policy_manifest_identity(root, excluded),
        "inventory": _inventory_manifest_identity(),
        "byte_totals": {
            "payload_file_count": len(rows),
            "payload_bytes": sum(row["bytes"] for row in rows),
            "by_component": _component_totals(rows),
        },
        "files": rows,
    }


def _write_exclusive(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(payload)


def _write_sha256sums(root: Path) -> None:
    actual = _scan_regular_files(root)
    rows = []
    for relative, path in sorted(actual.items(), key=lambda row: row[0].encode("utf-8")):
        if relative == SHA256SUMS_NAME:
            continue
        rows.append(f"{_sha256(path)}  {relative}\n")
    _write_exclusive(root / SHA256SUMS_NAME, "".join(rows).encode("utf-8"))


def _parse_sha256sums(path: Path) -> list[tuple[str, str]]:
    source = _read_utf8(path, SHA256SUMS_NAME)
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for number, line in enumerate(source.splitlines(), start=1):
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            raise PublicReleaseError(f"invalid {SHA256SUMS_NAME} line {number}")
        digest, relative = match.groups()
        relative = _normalize_relative(relative, "SHA256SUMS path")
        if relative in seen:
            raise PublicReleaseError(f"duplicate SHA256SUMS path: {relative}")
        seen.add(relative)
        rows.append((relative, digest))
    expected_order = sorted(rows, key=lambda row: row[0].encode("utf-8"))
    if rows != expected_order:
        raise PublicReleaseError("SHA256SUMS is not in canonical path order")
    return rows


def _validate_manifest_identity(manifest: Mapping[str, Any]) -> None:
    if set(manifest) != MANIFEST_FIELDS:
        missing = sorted(MANIFEST_FIELDS - set(manifest))
        extra = sorted(set(manifest) - MANIFEST_FIELDS)
        raise PublicReleaseError(
            f"release manifest has missing or extra top-level fields; missing={missing}, extra={extra}"
        )
    expected = {
        "manifest_version": MANIFEST_VERSION,
        "package_id": PACKAGE_ID,
        "artifact_role": ARTIFACT_ROLE,
        "release_eligible": True,
        "bench_build": BENCH_BUILD,
    }
    wrong = {
        key: (manifest.get(key), value)
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    if wrong:
        raise PublicReleaseError(f"release manifest identity mismatch: {wrong}")
    profile = manifest.get("release_profile")
    if not isinstance(profile, dict) or profile != {
        "mode": "release",
        "presentation_role": PRESENTATION_ROLE,
        "data_artifact_role": DATA_ARTIFACT_ROLE,
        "canonical_data_release_eligible": True,
    }:
        raise PublicReleaseError("release manifest has the wrong release profile")


def verify_public_release(package_root: str | os.PathLike[str]) -> dict[str, Any]:
    root = _resolve_directory(package_root, "public release package")
    actual = _scan_regular_files(root)
    required = {
        MANIFEST_NAME,
        SHA256SUMS_NAME,
        GITATTRIBUTES_NAME,
        NOJEKYLL_NAME,
        "index.html",
        "README.md",
        EXPECTED_OG_ASSET_PATH,
        "documentation/index.html",
        "generator/pyproject.toml",
        "generated/generated_manifest.json",
        "canonical-evidence/EPOCH_MANIFEST.json",
    }
    _require_paths(actual, required, "public release package")
    if actual[GITATTRIBUTES_NAME].read_bytes() != GITATTRIBUTES_BYTES:
        raise PublicReleaseError(
            f"{GITATTRIBUTES_NAME} must contain exactly '* -text\\n'"
        )
    if actual[NOJEKYLL_NAME].read_bytes() != NOJEKYLL_BYTES:
        raise PublicReleaseError(f"{NOJEKYLL_NAME} must be an empty file")
    if "STEP3_REVIEW_MANIFEST.json" in actual or "EPOCH_MANIFEST.json" in actual:
        raise PublicReleaseError("historical evidence/review manifest is forbidden at release root")

    manifest = _read_json(actual[MANIFEST_NAME])
    if not isinstance(manifest, dict):
        raise PublicReleaseError("public release manifest must be an object")
    _validate_manifest_identity(manifest)
    publication = manifest.get("publication")
    if not isinstance(publication, dict):
        raise PublicReleaseError("release manifest has no publication object")
    canonical_url = _validate_url(publication.get("canonical_public_url"))
    git_tag = _validate_git_tag(publication.get("git_tag"))
    if manifest.get("inventory") != _inventory_manifest_identity():
        raise PublicReleaseError("release manifest inventory scope is inconsistent")

    declared_rows = manifest.get("files")
    if not isinstance(declared_rows, list):
        raise PublicReleaseError("release manifest files must be an array")
    declared: dict[str, dict[str, Any]] = {}
    for row in declared_rows:
        if not isinstance(row, dict) or set(row) != {"path", "component", "bytes", "sha256"}:
            raise PublicReleaseError("invalid release-manifest file row")
        relative = _normalize_relative(row.get("path"), "release-manifest path")
        if relative in declared:
            raise PublicReleaseError(f"duplicate release-manifest path: {relative}")
        if type(row.get("bytes")) is not int or row["bytes"] < 0:
            raise PublicReleaseError(f"invalid byte count for {relative}")
        if not isinstance(row.get("sha256"), str) or not HEX64.fullmatch(row["sha256"]):
            raise PublicReleaseError(f"invalid SHA256 for {relative}")
        declared[relative] = row
    if declared_rows != sorted(
        declared_rows, key=lambda row: row["path"].encode("utf-8")
    ):
        raise PublicReleaseError("release manifest file inventory is not in canonical order")
    actual_payload = set(actual) - {MANIFEST_NAME, SHA256SUMS_NAME}
    if set(declared) != actual_payload:
        raise PublicReleaseError("release manifest has missing or extra package paths")
    for relative in sorted(actual_payload):
        path = actual[relative]
        row = declared[relative]
        if path.stat().st_size != row["bytes"] or _sha256(path) != row["sha256"]:
            raise PublicReleaseError(f"release payload hash/size mismatch: {relative}")

    sums = _parse_sha256sums(actual[SHA256SUMS_NAME])
    expected_sum_paths = set(actual) - {SHA256SUMS_NAME}
    if {relative for relative, _ in sums} != expected_sum_paths:
        raise PublicReleaseError("SHA256SUMS has missing or extra package paths")
    for relative, digest in sums:
        if _sha256(actual[relative]) != digest:
            raise PublicReleaseError(f"SHA256SUMS mismatch: {relative}")

    if actual["index.html"].read_bytes() != actual[
        "generated/packs/viewer.staged.html"
    ].read_bytes():
        raise PublicReleaseError("root index.html is not byte-identical to generated viewer")
    viewer_contract = _validate_viewer(actual["index.html"], canonical_url)
    viewer_build = viewer_contract["build"]

    generated_files = {
        relative.removeprefix("generated/"): path
        for relative, path in actual.items()
        if relative.startswith("generated/")
    }
    generated = _validate_generated(root / "generated", generated_files)
    if viewer_build["retained_run_count"] != generated["parity"]["runs"]:
        raise PublicReleaseError("viewer retained-run count differs from parity proof")

    generator_files = {
        relative.removeprefix("generator/"): path
        for relative, path in actual.items()
        if relative.startswith("generator/")
    }
    generator_provenance = _validate_generator(
        root / "generator", generator_files, generated["schema"]
    )
    public_files = {
        relative: path
        for relative, path in actual.items()
        if relative == "README.md"
        or relative.startswith("documentation/")
        or relative.startswith("assets/")
    }
    _validate_public_layout(public_files)
    og_asset = _validate_assets(public_files, canonical_url, viewer_contract["og_image"])
    docs_files = {
        relative: path
        for relative, path in public_files.items()
        if relative == "README.md" or relative.startswith("documentation/")
    }
    _validate_docs(root, docs_files, canonical_url, git_tag, root / "generator")
    if publication != {
        "canonical_public_url": canonical_url,
        "git_tag": git_tag,
        "og_image": og_asset,
    }:
        raise PublicReleaseError("release manifest publication identity is inconsistent")

    canonical_root = root / "canonical-evidence"
    canonical = _canonical_contract(canonical_root)
    _run_canonical_verifier(canonical_root)
    frozen_repository = canonical["frozen_repository"]
    frozen_files = frozen_repository["files"]
    release_owned_paths = {
        MANIFEST_NAME,
        SHA256SUMS_NAME,
        GITATTRIBUTES_NAME,
        NOJEKYLL_NAME,
        "index.html",
        "README.md",
        *(
            relative
            for relative in actual
            if relative.startswith("documentation/")
            or relative.startswith("assets/")
            or relative.startswith("generator/")
            or relative.startswith("generated/")
            or relative.startswith("canonical-evidence/")
        ),
    }
    _validate_release_copy_plan(frozen_files, release_owned_paths)
    for relative, frozen_path in frozen_files.items():
        if relative in FROZEN_RELEASE_REPLACEMENTS:
            continue
        packaged = actual.get(relative)
        if packaged is None or packaged.read_bytes() != frozen_path.read_bytes():
            raise PublicReleaseError(
                f"frozen repository path was not preserved byte-identically: {relative}"
            )
    expected_rows = _payload_inventory(root, frozen_files)
    if declared_rows != expected_rows:
        raise PublicReleaseError(
            "release manifest payload inventory/components are inconsistent"
        )
    if viewer_build["repo_commit"] != canonical["manifest"]["frozen_repository"][
        "commit_oid"
    ]:
        raise PublicReleaseError("viewer and canonical evidence repository identities differ")
    if viewer_build["data_identity"] != canonical["manifest"]["identity"][
        "evidence_epoch_hash"
    ]:
        raise PublicReleaseError("viewer and canonical evidence epoch identities differ")

    expected_component_totals = _component_totals(declared_rows)
    totals = manifest.get("byte_totals")
    if not isinstance(totals, dict) or totals != {
        "payload_file_count": len(declared_rows),
        "payload_bytes": sum(row["bytes"] for row in declared_rows),
        "by_component": expected_component_totals,
    }:
        raise PublicReleaseError("release manifest byte totals are inconsistent")

    source_identity = manifest.get("source_identity")
    evidence_identity = manifest.get("evidence_identity")
    build_identity = manifest.get("build_identity")
    expected_source_identity = {
        "generator_tree": _tree_summary(generator_files),
        "generator_source_hash": generator_provenance["generator_source_hash"],
        "release_reference_hash": generator_provenance["release_reference_hash"],
        "frozen_repository": _frozen_repository_manifest_identity(
            root, frozen_repository
        ),
    }
    if source_identity != expected_source_identity:
        raise PublicReleaseError("manifest source identity is inconsistent")
    copy_policy = manifest.get("copy_policy")
    if not isinstance(copy_policy, dict):
        raise PublicReleaseError("manifest copy policy must be an object")
    excluded_input_paths = _validate_excluded_input_paths(
        copy_policy.get("excluded_input_paths")
    )
    if copy_policy != _copy_policy_manifest_identity(root, excluded_input_paths):
        raise PublicReleaseError("manifest copy policy is inconsistent")

    canonical_manifest = canonical["manifest"]
    expected_evidence_identity = {
        "nested_path": "canonical-evidence",
        "nested_manifest": "canonical-evidence/EPOCH_MANIFEST.json",
        "package_id": canonical_manifest["package_id"],
        "epoch_id": canonical_manifest.get("epoch_id"),
        "evidence_epoch_hash": canonical_manifest["identity"][
            "evidence_epoch_hash"
        ],
        "repository_commit": canonical_manifest["frozen_repository"]["commit_oid"],
        "repository_tree": canonical_manifest["frozen_repository"]["tree_oid"],
        "tree": _tree_summary(canonical["files"]),
        "verifier_path": f"canonical-evidence/{CANONICAL_VERIFIER}",
        "verifier_sha256": EXPECTED_CANONICAL_VERIFIER_SHA256,
        "authority_note": EVIDENCE_AUTHORITY_NOTE,
    }
    if evidence_identity != expected_evidence_identity:
        raise PublicReleaseError("manifest evidence identity is inconsistent")

    expected_build_identity = {
        "viewer": {
            "path": "index.html",
            "bytes": actual["index.html"].stat().st_size,
            "sha256": _sha256(actual["index.html"]),
            "viewer_build_sha256": _canonical_json_hash(viewer_build),
        },
        "generated_tree": _tree_summary(generated_files),
        "generated_manifest_sha256": _sha256(
            actual["generated/generated_manifest.json"]
        ),
        "schema_meta_sha256": _sha256(actual["generated/schema_meta.staged.json"]),
        "parity_report_sha256": _sha256(actual["generated/parity_report.json"]),
        "pipeline_bundle_hash": generated["schema"]["provenance_hashes"].get(
            "bundle_hash"
        ),
        "parity": _parity_manifest_identity(generated["parity"]),
    }
    if build_identity != expected_build_identity:
        raise PublicReleaseError("manifest build identity is inconsistent")
    rights = manifest.get("rights")
    if rights != _rights_manifest_identity():
        raise PublicReleaseError("manifest project-rights wording is inconsistent")
    expected_font_rows = [
        row
        for row in declared_rows
        if row["path"].startswith(
            "generator/domelab_pipeline/release_reference/third_party/fonts/"
        )
    ]
    if manifest.get("third_party_fonts") != expected_font_rows:
        raise PublicReleaseError("manifest third-party font inventory is inconsistent")

    counts = manifest.get("counts")
    expected_counts = {
        "viewer_records": viewer_build["record_count"],
        "viewer_sets": viewer_build["set_count"],
        "retained_run_bindings": viewer_build["retained_run_count"],
        "unique_acquisitions": viewer_build["unique_acquisition_count"],
        "independent_measurement_cohorts": viewer_build[
            "independent_measurement_cohort_count"
        ],
        "canonical_raw_paths": canonical["counts"].get("raw_paths"),
        "canonical_curve_packs": canonical["counts"].get("curve_packs"),
        "frozen_repository_paths": len(frozen_files),
        "frozen_repository_preserved_paths": (
            len(frozen_files) - len(FROZEN_RELEASE_REPLACEMENTS)
        ),
        "release_authority_replacements": len(FROZEN_RELEASE_REPLACEMENTS),
    }
    if counts != expected_counts:
        raise PublicReleaseError("manifest record/run counts are inconsistent")

    return {
        "status": "PASS",
        "package_id": PACKAGE_ID,
        "bench_build": BENCH_BUILD,
        "canonical_public_url": canonical_url,
        "git_tag": git_tag,
        "repo_commit": EXPECTED_REPO_COMMIT,
        "evidence_identity": EXPECTED_EVIDENCE_IDENTITY,
        "frozen_repository_paths": len(frozen_files),
        "frozen_repository_preserved_paths": (
            len(frozen_files) - len(FROZEN_RELEASE_REPLACEMENTS)
        ),
        "viewer_sha256": _sha256(actual["index.html"]),
        "manifest_sha256": _sha256(actual[MANIFEST_NAME]),
        "sha256sums_sha256": _sha256(actual[SHA256SUMS_NAME]),
        "file_count": len(actual),
        "bytes": sum(path.stat().st_size for path in actual.values()),
    }


def _snapshot_matches(files: Mapping[str, Path], expected: list[dict[str, Any]], label: str) -> None:
    if _entries(files) != expected:
        raise PublicReleaseError(f"{label} changed while the release package was being built")


def _promote_atomic(staging: Path, output: Path) -> None:
    lock = output.with_name(f".{output.name}.release-lock")
    descriptor: int | None = None
    try:
        descriptor = os.open(os.fspath(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, b"Force Curve Bench release promotion lock\n")
        os.close(descriptor)
        descriptor = None
        if _lexists(output):
            raise PublicReleaseError(f"refusing to replace existing output: {output}")
        os.rename(staging, output)
    except FileExistsError as error:
        raise PublicReleaseError(
            f"another release promotion is active or the output exists: {output}"
        ) from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def build_public_release(
    *,
    viewer: str | os.PathLike[str],
    staging: str | os.PathLike[str],
    public_docs: str | os.PathLike[str],
    generator: str | os.PathLike[str],
    canonical_evidence: str | os.PathLike[str],
    frozen_repository: str | os.PathLike[str] | None = None,
    output: str | os.PathLike[str],
    canonical_url: str,
    git_tag: str,
) -> dict[str, Any]:
    canonical_url = _validate_url(canonical_url)
    git_tag = _validate_git_tag(git_tag)
    viewer_path = _resolve_file(viewer, "final release viewer")
    staging_root = _resolve_directory(staging, "release staging")
    docs_root = _resolve_directory(public_docs, "public documentation")
    generator_root = _resolve_directory(generator, "generator source")
    canonical_root = _resolve_directory(canonical_evidence, "canonical evidence")
    frozen_repository_root = (
        _resolve_directory(frozen_repository, "explicit frozen repository source")
        if frozen_repository is not None
        else None
    )

    output_path = Path(output).absolute()
    parent = _resolve_directory(output_path.parent, "output parent")
    output_path = parent / output_path.name
    if output_path.name in ("", ".", "..") or _lexists(output_path):
        raise PublicReleaseError(f"refusing to replace existing or unsafe output: {output_path}")
    for label, root in (
        ("release staging", staging_root),
        ("public documentation", docs_root),
        ("generator source", generator_root),
        ("canonical evidence", canonical_root),
        *((
            ("explicit frozen repository source", frozen_repository_root),
        ) if frozen_repository_root is not None else ()),
    ):
        if _path_within(output_path, root):
            raise PublicReleaseError(f"output must not be inside {label}")

    staging_files = _scan_regular_files(staging_root)
    public_files, docs_excluded = _selected_files(docs_root)
    _validate_public_layout(public_files)
    generator_files, generator_excluded = _selected_files(generator_root)
    canonical = _canonical_contract(canonical_root, frozen_repository_root)
    generated = _validate_generated(staging_root, staging_files)
    _require_paths(generator_files, REQUIRED_GENERATOR_FILES, "generator source")
    if viewer_path.read_bytes() != staging_files["packs/viewer.staged.html"].read_bytes():
        raise PublicReleaseError(
            "final release viewer is not byte-identical to staging/packs/viewer.staged.html"
        )
    viewer_contract = _validate_viewer(viewer_path, canonical_url)
    viewer_build = viewer_contract["build"]
    og_asset = _validate_assets(
        public_files, canonical_url, viewer_contract["og_image"]
    )
    generator_provenance = _validate_generator(
        generator_root, generator_files, generated["schema"]
    )
    docs_files = {
        relative: path
        for relative, path in public_files.items()
        if relative == "README.md" or relative.startswith("documentation/")
    }
    _validate_docs(docs_root, docs_files, canonical_url, git_tag, generator_root)
    if viewer_build["retained_run_count"] != generated["parity"]["runs"]:
        raise PublicReleaseError("viewer retained-run count differs from parity proof")
    _run_canonical_verifier(canonical_root)

    release_owned_paths = {
        "index.html",
        "README.md",
        MANIFEST_NAME,
        SHA256SUMS_NAME,
        GITATTRIBUTES_NAME,
        NOJEKYLL_NAME,
        *(
            relative
            for relative in public_files
            if relative.startswith("documentation/") or relative.startswith("assets/")
        ),
        *(_prefix_files(generator_files, "generator")),
        *(_prefix_files(staging_files, "generated")),
        *(_prefix_files(canonical["files"], "canonical-evidence")),
    }
    frozen_files = canonical["frozen_repository"]["files"]
    _validate_release_copy_plan(frozen_files, release_owned_paths)

    snapshots = {
        "staging": _entries(staging_files),
        "documentation": _entries(public_files),
        "generator": _entries(generator_files),
        "canonical_evidence": _entries(canonical["files"]),
        "frozen_repository": _entries(frozen_files),
    }
    input_summaries = {
        "generated": _tree_summary(staging_files),
        "documentation": _tree_summary(public_files),
        "generator": _tree_summary(generator_files),
        "canonical_evidence": _tree_summary(canonical["files"]),
        "frozen_repository": _tree_summary(frozen_files),
    }
    temporary = Path(
        tempfile.mkdtemp(prefix=TEMP_STAGING_PREFIX, dir=parent)
    )
    promoted = False
    try:
        _copy_files(
            {
                relative: path
                for relative, path in frozen_files.items()
                if relative not in FROZEN_RELEASE_REPLACEMENTS
            },
            temporary,
        )
        _write_exclusive(temporary / GITATTRIBUTES_NAME, GITATTRIBUTES_BYTES)
        _write_exclusive(temporary / NOJEKYLL_NAME, NOJEKYLL_BYTES)
        _write_exclusive(temporary / "index.html", viewer_path.read_bytes())
        _copy_files(
            {relative.removeprefix("documentation/"): path for relative, path in docs_files.items() if relative.startswith("documentation/")},
            temporary / "documentation",
        )
        _write_exclusive(temporary / "README.md", docs_files["README.md"].read_bytes())
        _copy_files(
            {
                relative.removeprefix("assets/"): path
                for relative, path in public_files.items()
                if relative.startswith("assets/")
            },
            temporary / "assets",
        )
        _copy_files(generator_files, temporary / "generator")
        _copy_files(staging_files, temporary / "generated")
        _copy_files(canonical["files"], temporary / "canonical-evidence")

        copied_canonical = _canonical_contract(temporary / "canonical-evidence")
        if _entries(copied_canonical["files"]) != snapshots["canonical_evidence"]:
            raise PublicReleaseError("canonical evidence changed while being copied")
        _run_canonical_verifier(temporary / "canonical-evidence")

        rows = _payload_inventory(temporary, frozen_files)
        manifest = _manifest(
            temporary,
            rows,
            canonical_url,
            git_tag,
            viewer_build,
            og_asset,
            generated,
            generator_provenance,
            canonical,
            input_summaries,
            {"documentation": docs_excluded, "generator": generator_excluded},
        )
        _write_exclusive(temporary / MANIFEST_NAME, _json_bytes(manifest))
        _write_sha256sums(temporary)
        report = verify_public_release(temporary)

        _snapshot_matches(staging_files, snapshots["staging"], "release staging")
        _snapshot_matches(
            public_files, snapshots["documentation"], "public documentation"
        )
        _snapshot_matches(generator_files, snapshots["generator"], "generator source")
        _snapshot_matches(
            canonical["files"], snapshots["canonical_evidence"], "canonical evidence"
        )
        _snapshot_matches(
            frozen_files, snapshots["frozen_repository"], "frozen repository"
        )
        if _sha256(viewer_path) != _sha256(staging_files["packs/viewer.staged.html"]):
            raise PublicReleaseError("final viewer changed while the package was being built")

        _promote_atomic(temporary, output_path)
        promoted = True
        try:
            final_report = verify_public_release(output_path)
            if report != final_report:
                # The path is intentionally absent from the report, so verification
                # must be byte-for-byte stable before and after atomic promotion.
                raise PublicReleaseError(
                    "verification report changed during atomic promotion"
                )
        except Exception as verification_error:
            try:
                os.rename(output_path, temporary)
                promoted = False
            except OSError as rollback_error:
                raise PublicReleaseError(
                    "post-promotion verification failed and the newly created output "
                    f"could not be rolled back: {output_path}: {rollback_error}"
                ) from verification_error
            raise
        return final_report
    finally:
        if not promoted and temporary.exists():
            shutil.rmtree(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build and atomically promote a release")
    build.add_argument("--viewer", required=True, type=Path)
    build.add_argument("--staging", required=True, type=Path)
    build.add_argument("--public-docs", required=True, type=Path)
    build.add_argument("--generator", required=True, type=Path)
    build.add_argument("--canonical-evidence", required=True, type=Path)
    build.add_argument(
        "--frozen-repository",
        type=Path,
        help=(
            "optional source checkout/materialization for the frozen repository; "
            "every inventoried file is checked against the sealed canonical raw cache"
        ),
    )
    build.add_argument("--output", required=True, type=Path)
    build.add_argument("--canonical-url", required=True)
    build.add_argument("--git-tag", required=True)
    verify = subparsers.add_parser("verify", help="verify an existing release package")
    verify.add_argument("package_root", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            report = build_public_release(
                viewer=args.viewer,
                staging=args.staging,
                public_docs=args.public_docs,
                generator=args.generator,
                canonical_evidence=args.canonical_evidence,
                frozen_repository=args.frozen_repository,
                output=args.output,
                canonical_url=args.canonical_url,
                git_tag=args.git_tag,
            )
        else:
            report = verify_public_release(args.package_root)
    except PublicReleaseError as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
