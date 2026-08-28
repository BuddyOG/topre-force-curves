"""Focused fail-closed tests for the public Force Curve Bench packager."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import struct
import zlib

import pytest

from tools import build_public_release as release


URL = "https://unrealkeyboards.com/force-curve-bench/"
TAG = "fc-3.4"
OG_URL = URL + release.EXPECTED_OG_ASSET_PATH
OG_WIDTH = 2
OG_HEIGHT = 3


def _write(path: Path, payload: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_text(payload, encoding="utf-8", newline="\n")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob(path: Path) -> str:
    payload = path.read_bytes()
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def _png(width: int = OG_WIDTH, height: int = OG_HEIGHT) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes([10, 20, 30]) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _viewer(*, mode: str = "release", canonical_url: str = URL) -> str:
    build = {
        "mode": mode,
        "bench_build": "fc-3.4",
        "presentation_role": "public_release",
        "release_eligible": True,
        "data_artifact_role": "canonical_retention_authority",
        "canonical_data_release_eligible": True,
        "repo_commit": release.EXPECTED_REPO_COMMIT,
        "data_identity": release.EXPECTED_EVIDENCE_IDENTITY,
        "canonical_evidence_identity": release.EXPECTED_EVIDENCE_IDENTITY,
        "record_count": 2,
        "set_count": 2,
        "retained_run_count": 4,
        "semantic_run_binding_count": 4,
        "unique_acquisition_count": 4,
        "independent_measurement_cohort_count": 2,
    }
    return f"""<!doctype html>
<html><head>
<link rel="canonical" href="{canonical_url}">
<meta property="og:url" content="{canonical_url}">
<meta property="og:image" content="{OG_URL}">
<meta property="og:image:width" content="{OG_WIDTH}">
<meta property="og:image:height" content="{OG_HEIGHT}">
<style>
@font-face{{font-family:Inter;src:url(data:font/woff2;base64,QQ==)}}
@font-face{{font-family:Plex;src:url(data:font/woff2;base64,Qg==)}}
@font-face{{font-family:Plex;src:url(data:font/woff2;base64,Qw==)}}
</style></head><body>
<footer>{release.PROJECT_RIGHTS_NOTICE}</footer>
<script>const VIEWER_BUILD = {json.dumps(build, sort_keys=True)};</script>
</body></html>
"""


def _generator(root: Path) -> Path:
    _write(root / "pyproject.toml", "[project]\nname='fixture'\n")
    _write(root / "requirements-lock.txt", "pytest==9.1.1\n")
    _write(root / "js/package.json", "{}\n")
    _write(root / "js/package-lock.json", "{}\n")
    _write(root / "domelab_pipeline/pipeline.py", "# fixture pipeline\n")
    reference = root / "domelab_pipeline/release_reference"
    _write(reference / "index.release.html", "<!doctype html><title>template</title>\n")
    fonts = reference / "third_party/fonts"
    _write(fonts / "README.md", "# Font sources\nSIL Open Font License 1.1\n")
    _write(fonts / "INTER-LICENSE.txt", "SIL OPEN FONT LICENSE Version 1.1\nInter\n")
    _write(fonts / "IBM-PLEX-LICENSE.txt", "SIL OPEN FONT LICENSE Version 1.1\nIBM Plex\n")
    _write(fonts / "Inter-latin.woff2", b"inter font")
    _write(fonts / "IBMPlexMono-500-latin.woff2", b"plex 500")
    _write(fonts / "IBMPlexMono-600-latin.woff2", b"plex 600")
    _write(root / "tools/build_public_release.py", "# packaged release builder\n")
    _write(root / "tests/test_fixture.py", "def test_fixture(): pass\n")
    _write(root / "node_modules/ignored.js", "ignored\n")
    _write(root / "build/ignored.bin", b"ignored")
    _write(root / "domelab_pipeline/__pycache__/ignored.pyc", b"ignored")
    _write(root / "domelab_pipeline.egg-info/PKG-INFO", "ignored\n")
    return root


def _docs(root: Path, generator: Path) -> Path:
    text = f"""# Force Curve Bench

Public viewer: {URL}

Frozen Git tag: `{TAG}`

{release.PROJECT_RIGHTS_NOTICE}

The owner permits sharing unmodified charts exported by Force Curve Bench and
unmodified data files published with the repository when attribution is
included. This is not an open license.

Embedded fonts use the SIL Open Font License 1.1.
"""
    _write(root / "README.md", text)
    _write(
        root / "documentation/index.html",
        f"<!doctype html><h1>Docs</h1><p>{text}</p><h2 id='rights-and-reuse'>Terms</h2>",
    )
    _write(
        root / "documentation/THIRD_PARTY_NOTICES.md",
        "# Third-party notices\nInter and IBM Plex Mono — SIL Open Font License 1.1.\n",
    )
    font_root = generator / "domelab_pipeline/release_reference/third_party/fonts"
    for name in ("INTER-LICENSE.txt", "IBM-PLEX-LICENSE.txt"):
        _write(root / "documentation/licenses" / name, (font_root / name).read_bytes())
    _write(root / release.EXPECTED_OG_ASSET_PATH, _png())
    _write(root / "DRAFT_CHECKLIST.md", "must not ship\n")
    _write(root / ".pytest_cache/ignored", "must not ship\n")
    return root


def _seal_stage(root: Path) -> None:
    manifest = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != "generated_manifest.json":
            manifest[path.relative_to(root).as_posix()] = _sha(path)
    _write(
        root / "generated_manifest.json",
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
    )


def _stage(root: Path, generator: Path) -> Path:
    _write(root / "packs/viewer.staged.html", _viewer())
    provenance = release._generator_provenance(generator)
    schema = {
        "repo_commit": release.EXPECTED_REPO_COMMIT,
        "provenance_hashes": {
            **provenance,
            "evidence_epoch_hash": release.EXPECTED_EVIDENCE_IDENTITY,
            "bundle_hash": "a" * 64,
        },
    }
    _write(root / "schema_meta.staged.json", json.dumps(schema))
    parity = {
        "artifact_role": "canonical_retention_authority",
        "release_eligible": True,
        "exact_null_flag_audit_match": True,
        "metrics_per_run": 14,
        "audit_fields_per_run": 13,
        "runs": 4,
        "max_abs_delta": 1e-13,
        "max_audit_abs_delta": 1e-14,
    }
    _write(root / "parity_report.json", json.dumps(parity))
    _write(root / "bench_tests.staged.json", "[]\n")
    _write(root / "intake_retention_decisions.json", "{}\n")
    _write(root / "packs/curves/fixture.staged.json", "{}\n")
    _seal_stage(root)
    return root


def _canonical(root: Path) -> Path:
    verifier = """#!/usr/bin/env python3
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
passed = not (root / "INVALID").exists()
print(json.dumps({"status": "PASS" if passed else "FAIL"}))
raise SystemExit(0 if passed else 1)
"""
    _write(root / release.CANONICAL_VERIFIER, verifier)
    cache_relative = f"raw_cache/repo-{release.EXPECTED_REPO_COMMIT}"
    cache = root / cache_relative
    frozen_payloads = {
        "README.md": b"# Frozen legacy repository\n",
        "Raw_Dome/DataLog_1.csv": b"Distance,Force\n0,0\n1,10\n",
        "dome-lab-parts.html": b"<!doctype html><title>Legacy Parts</title>\n",
        "dome-lab.html": b"<!doctype html><title>Legacy Dome Lab</title>\n",
        "ec-switch-explorer.html": b"<!doctype html><title>Legacy EC Explorer</title>\n",
        "index.html": b"<!doctype html><title>Legacy Force Curves</title>\n",
    }
    for relative, payload in frozen_payloads.items():
        _write(cache / relative, payload)
    inventory_rows = []
    for relative in sorted(frozen_payloads, key=lambda value: value.encode("utf-8")):
        path = cache / relative
        inventory_rows.append(
            {
                "path": relative,
                "bytes": str(path.stat().st_size),
                "sha256": _sha(path),
                "category": "raw_csv" if relative.endswith(".csv") else "legacy_tool",
                "git_blob_oid": _git_blob(path),
                "git_object_format": "sha1",
                "mode": "100644",
                "git_object_type": "blob",
                "is_raw_csv": "True" if relative.endswith(".csv") else "False",
                "set": "Raw_Dome" if relative.endswith(".csv") else "",
                "acquisition_id": "acq_fixture" if relative.endswith(".csv") else "",
                "evidence_group_id": "egrp_fixture" if relative.endswith(".csv") else "",
            }
        )
    inventory_relative = "epoch_inputs/manifest/repository_file_inventory.csv"
    header = ",".join(release.REPOSITORY_INVENTORY_FIELDS) + "\n"
    lines = [header]
    for row in inventory_rows:
        lines.append(
            ",".join(row[field] for field in release.REPOSITORY_INVENTORY_FIELDS) + "\n"
        )
    _write(root / inventory_relative, "".join(lines))
    tree_oid = release._git_tree_oid(inventory_rows)
    manifest = {
        "manifest_version": 1,
        "package_id": release.EXPECTED_CANONICAL_PACKAGE_ID,
        "epoch_id": "canonical-evidence-2026-08-15-6e86ac19",
        "frozen_repository": {
            "commit_oid": release.EXPECTED_REPO_COMMIT,
            "tree_oid": tree_oid,
            "git_object_format": "sha1",
            "cache_root": cache_relative,
            "inventory_path": inventory_relative,
        },
        "identity": {"evidence_epoch_hash": release.EXPECTED_EVIDENCE_IDENTITY},
        "expected_counts": {
            "raw_paths": 4,
            "repository_paths": len(inventory_rows),
            "curve_packs": 2,
            "semantic_records": 2,
            "unique_acquisitions": 4,
        },
    }
    _write(root / "EPOCH_MANIFEST.json", json.dumps(manifest))
    _write(root / "README.md", "# Sealed canonical evidence\n")
    _write(root / "SHA256SUMS.csv", "fixture inventory\n")
    return root


def _rebuild_frozen_inventory(canonical: Path) -> str:
    manifest_path = canonical / "EPOCH_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    frozen = manifest["frozen_repository"]
    cache = canonical / frozen["cache_root"]
    rows = []
    for path in sorted(
        (candidate for candidate in cache.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(cache).as_posix().encode("utf-8"),
    ):
        relative = path.relative_to(cache).as_posix()
        rows.append(
            {
                "path": relative,
                "bytes": str(path.stat().st_size),
                "sha256": _sha(path),
                "category": "raw_csv" if relative.endswith(".csv") else "legacy_tool",
                "git_blob_oid": _git_blob(path),
                "git_object_format": "sha1",
                "mode": "100644",
                "git_object_type": "blob",
                "is_raw_csv": "True" if relative.endswith(".csv") else "False",
                "set": "Raw_Dome" if relative.endswith(".csv") else "",
                "acquisition_id": "acq_fixture" if relative.endswith(".csv") else "",
                "evidence_group_id": "egrp_fixture" if relative.endswith(".csv") else "",
            }
        )
    inventory = canonical / frozen["inventory_path"]
    lines = [",".join(release.REPOSITORY_INVENTORY_FIELDS) + "\n"]
    lines.extend(
        ",".join(row[field] for field in release.REPOSITORY_INVENTORY_FIELDS) + "\n"
        for row in rows
    )
    _write(inventory, "".join(lines))
    tree_oid = release._git_tree_oid(rows)
    frozen["tree_oid"] = tree_oid
    manifest["expected_counts"]["repository_paths"] = len(rows)
    _write(manifest_path, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return tree_oid


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    generator = _generator(tmp_path / "generator")
    docs = _docs(tmp_path / "public-docs", generator)
    staging = _stage(tmp_path / "staging", generator)
    canonical = _canonical(tmp_path / "canonical")
    monkeypatch.setattr(
        release,
        "EXPECTED_CANONICAL_VERIFIER_SHA256",
        _sha(canonical / release.CANONICAL_VERIFIER),
    )
    monkeypatch.setattr(
        release,
        "EXPECTED_OG_IMAGE_SHA256",
        _sha(docs / release.EXPECTED_OG_ASSET_PATH),
    )
    canonical_manifest = json.loads(
        (canonical / "EPOCH_MANIFEST.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(
        release,
        "EXPECTED_REPO_TREE",
        canonical_manifest["frozen_repository"]["tree_oid"],
    )
    return {
        "generator": generator,
        "docs": docs,
        "staging": staging,
        "viewer": staging / "packs/viewer.staged.html",
        "canonical": canonical,
        "output": tmp_path / "release",
    }


def _build(workspace, **overrides):
    arguments = {
        "viewer": workspace["viewer"],
        "staging": workspace["staging"],
        "public_docs": workspace["docs"],
        "generator": workspace["generator"],
        "canonical_evidence": workspace["canonical"],
        "output": workspace["output"],
        "canonical_url": URL,
        "git_tag": TAG,
    }
    arguments.update(overrides)
    return release.build_public_release(**arguments)


def test_builds_deterministic_distinct_public_authority(workspace, tmp_path):
    first = _build(workspace)
    root = workspace["output"]
    assert first["status"] == "PASS"
    assert first["bench_build"] == "fc-3.4"
    assert first["canonical_public_url"] == URL
    assert first["git_tag"] == TAG
    assert (root / release.MANIFEST_NAME).is_file()
    assert (root / release.SHA256SUMS_NAME).is_file()
    assert (root / release.GITATTRIBUTES_NAME).read_bytes() == release.GITATTRIBUTES_BYTES
    assert (root / release.NOJEKYLL_NAME).read_bytes() == b""
    assert not (root / "STEP3_REVIEW_MANIFEST.json").exists()
    assert not (root / "EPOCH_MANIFEST.json").exists()
    assert (root / "canonical-evidence/EPOCH_MANIFEST.json").is_file()
    assert (root / "index.html").read_bytes() == workspace["viewer"].read_bytes()
    frozen_cache = (
        workspace["canonical"]
        / f"raw_cache/repo-{release.EXPECTED_REPO_COMMIT}"
    )
    assert (root / "Raw_Dome/DataLog_1.csv").read_bytes() == (
        frozen_cache / "Raw_Dome/DataLog_1.csv"
    ).read_bytes()
    for legacy in ("dome-lab.html", "dome-lab-parts.html", "ec-switch-explorer.html"):
        assert (root / legacy).read_bytes() == (frozen_cache / legacy).read_bytes()
    assert (root / "index.html").read_bytes() != (frozen_cache / "index.html").read_bytes()
    assert (root / "README.md").read_bytes() != (frozen_cache / "README.md").read_bytes()
    assert not (root / "documentation/DRAFT_CHECKLIST.md").exists()
    assert not (root / "generator/node_modules").exists()
    assert not (root / "generator/build").exists()
    assert not (root / "generator/domelab_pipeline.egg-info").exists()
    assert len(list((root / "generator/domelab_pipeline/release_reference/third_party/fonts").glob("*.woff2"))) == 3
    assert (root / release.EXPECTED_OG_ASSET_PATH).read_bytes() == _png()
    manifest = json.loads((root / release.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["publication"]["og_image"] == {
        "url": OG_URL,
        "path": release.EXPECTED_OG_ASSET_PATH,
        "bytes": len(_png()),
        "sha256": _sha(root / release.EXPECTED_OG_ASSET_PATH),
        "width": OG_WIDTH,
        "height": OG_HEIGHT,
    }
    asset_row = next(
        row for row in manifest["files"] if row["path"] == release.EXPECTED_OG_ASSET_PATH
    )
    assert asset_row["component"] == "assets"
    frozen_row = next(
        row for row in manifest["files"] if row["path"] == "dome-lab.html"
    )
    assert frozen_row["component"] == "frozen_repository"
    frozen_identity = manifest["source_identity"]["frozen_repository"]
    assert frozen_identity["tree_oid"] == release.EXPECTED_REPO_TREE
    assert frozen_identity["frozen_file_count"] == 6
    assert frozen_identity["preserved_file_count"] == 4
    assert set(frozen_identity["release_authority_replacements"]) == {
        "README.md",
        "index.html",
    }
    attributes_row = next(
        row for row in manifest["files"] if row["path"] == release.GITATTRIBUTES_NAME
    )
    assert attributes_row["component"] == "release_configuration"
    assert release.verify_public_release(root)["status"] == "PASS"

    second_root = tmp_path / "release-again"
    second = _build(workspace, output=second_root)
    assert second["manifest_sha256"] == first["manifest_sha256"]
    assert second["sha256sums_sha256"] == first["sha256sums_sha256"]
    assert (second_root / release.MANIFEST_NAME).read_bytes() == (
        root / release.MANIFEST_NAME
    ).read_bytes()
    assert (second_root / release.SHA256SUMS_NAME).read_bytes() == (
        root / release.SHA256SUMS_NAME
    ).read_bytes()


def test_short_atomic_sibling_handles_deep_evidence_path_at_windows_budget(
    workspace, tmp_path, monkeypatch
):
    output = tmp_path / "force-curve-bench-fc-3.4-public"
    set_directory = "Topre_Slider_Black_Silenced_0.3mm_Poron"
    filename = "DataLog_1.csv"
    base_relative = Path(set_directory) / filename
    base_final = output / "canonical-evidence" / base_relative
    # Put the promoted file near, but safely below, classic Windows MAX_PATH.
    # The retired output-name-derived temporary prefix crosses that boundary;
    # the short sibling stays materially below it.
    filler_length = 245 - len(str(base_final)) - 1
    assert filler_length >= 8
    filler = "deep-" + "x" * (filler_length - len("deep-"))
    deep_relative = Path(set_directory) / filler / filename
    final_target = output / "canonical-evidence" / deep_relative
    legacy_name = f".{output.name}.staging-" + "x" * 8
    legacy_target = output.parent / legacy_name / "canonical-evidence" / deep_relative
    short_name = release.TEMP_STAGING_PREFIX + "x" * 8
    short_target = output.parent / short_name / "canonical-evidence" / deep_relative
    assert len(str(final_target)) == 245
    assert len(str(legacy_target)) >= 260
    assert len(str(short_target)) < len(str(final_target)) < 260

    payload = b"realistic deep retained-run payload\n"
    _write(workspace["canonical"] / deep_relative, payload)
    created: list[Path] = []
    real_mkdtemp = release.tempfile.mkdtemp

    def tracked_mkdtemp(*args, **kwargs):
        assert kwargs["prefix"] == release.TEMP_STAGING_PREFIX
        result = real_mkdtemp(*args, **kwargs)
        created.append(Path(result))
        return result

    monkeypatch.setattr(release.tempfile, "mkdtemp", tracked_mkdtemp)
    report = _build(workspace, output=output)
    assert report["status"] == "PASS"
    assert (output / "canonical-evidence" / deep_relative).read_bytes() == payload
    assert len(created) == 1
    assert created[0].name.startswith(release.TEMP_STAGING_PREFIX)
    assert not created[0].exists()


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("canonical_url", "https://example.com/TBD", "placeholder"),
        ("canonical_url", "http://unrealkeyboards.com/viewer", "public HTTPS"),
        ("git_tag", "PENDING", "placeholder"),
        ("git_tag", "latest", "placeholder"),
    ],
)
def test_refuses_placeholder_or_nonpublic_release_identifiers(
    workspace, field, value, match
):
    with pytest.raises(release.PublicReleaseError, match=match):
        _build(workspace, **{field: value})
    assert not workspace["output"].exists()


def test_refuses_unresolved_placeholder_in_public_material(workspace):
    _write(
        workspace["docs"] / "README.md",
        (workspace["docs"] / "README.md").read_text(encoding="utf-8")
        + "\nPUBLIC_VIEWER_URL_PENDING\n",
    )
    with pytest.raises(release.PublicReleaseError, match="unresolved release placeholders"):
        _build(workspace)
    assert not workspace["output"].exists()


def test_refuses_review_profile_even_if_stage_is_resealed(workspace):
    _write(workspace["viewer"], _viewer(mode="review"))
    _seal_stage(workspace["staging"])
    with pytest.raises(release.PublicReleaseError, match="public release profile"):
        _build(workspace)


def test_refuses_viewer_that_is_not_the_staged_generated_viewer(workspace, tmp_path):
    other = tmp_path / "other.html"
    _write(other, workspace["viewer"].read_text(encoding="utf-8") + "\n")
    with pytest.raises(release.PublicReleaseError, match="not byte-identical"):
        _build(workspace, viewer=other)


def test_refuses_existing_output_without_touching_it(workspace):
    workspace["output"].mkdir()
    marker = workspace["output"] / "keep.txt"
    _write(marker, "keep\n")
    with pytest.raises(release.PublicReleaseError, match="refusing to replace"):
        _build(workspace)
    assert marker.read_text(encoding="utf-8") == "keep\n"


def test_refuses_modified_font_license(workspace):
    _write(
        workspace["docs"] / "documentation/licenses/INTER-LICENSE.txt",
        "different license bytes\n",
    )
    with pytest.raises(release.PublicReleaseError, match="not byte-identical"):
        _build(workspace)


def test_refuses_missing_og_asset(workspace):
    (workspace["docs"] / release.EXPECTED_OG_ASSET_PATH).unlink()
    with pytest.raises(release.PublicReleaseError, match="exactly the referenced release OG image"):
        _build(workspace)


def test_refuses_unreferenced_public_asset(workspace):
    _write(workspace["docs"] / "assets/not-referenced.png", _png())
    with pytest.raises(release.PublicReleaseError, match="unreferenced"):
        _build(workspace)


def test_refuses_hash_pinned_og_asset_change(workspace):
    image = workspace["docs"] / release.EXPECTED_OG_ASSET_PATH
    _write(image, image.read_bytes() + b"changed")
    with pytest.raises(release.PublicReleaseError, match="hash-pinned"):
        _build(workspace)


def test_refuses_invalid_png_even_if_test_hash_pin_is_updated(workspace, monkeypatch):
    image = workspace["docs"] / release.EXPECTED_OG_ASSET_PATH
    _write(image, b"not a PNG")
    monkeypatch.setattr(release, "EXPECTED_OG_IMAGE_SHA256", _sha(image))
    with pytest.raises(release.PublicReleaseError, match="PNG signature"):
        _build(workspace)


def test_refuses_og_metadata_dimensions_that_differ_from_png(workspace):
    source = workspace["viewer"].read_text(encoding="utf-8")
    _write(workspace["viewer"], source.replace('content="2">', 'content="9">', 1))
    _seal_stage(workspace["staging"])
    with pytest.raises(release.PublicReleaseError, match="width/height metadata"):
        _build(workspace)


def test_canonical_verifier_failure_prevents_any_output(workspace):
    _write(workspace["canonical"] / "INVALID", "fail\n")
    with pytest.raises(release.PublicReleaseError, match="canonical verifier failed"):
        _build(workspace)
    assert not workspace["output"].exists()


def test_failed_temporary_build_is_cleaned_without_partial_output(
    workspace, monkeypatch
):
    def fail_write(_root):
        raise release.PublicReleaseError("simulated finalization failure")

    monkeypatch.setattr(release, "_write_sha256sums", fail_write)
    with pytest.raises(release.PublicReleaseError, match="simulated finalization failure"):
        _build(workspace)
    assert not workspace["output"].exists()
    assert not list(
        workspace["output"].parent.glob(f"{release.TEMP_STAGING_PREFIX}*")
    )


def test_verifier_rejects_tampering_and_extra_files(workspace):
    _build(workspace)
    root = workspace["output"]
    _write(root / "README.md", "tampered\n")
    with pytest.raises(release.PublicReleaseError, match="hash/size mismatch"):
        release.verify_public_release(root)


def test_verifier_rejects_extra_file_even_with_valid_payload_unchanged(workspace):
    _build(workspace)
    root = workspace["output"]
    _write(root / "extra.txt", "undeclared\n")
    with pytest.raises(release.PublicReleaseError, match="missing or extra"):
        release.verify_public_release(root)


@pytest.mark.parametrize(
    ("field_path", "replacement", "match"),
    [
        (
            ("rights", "project_license"),
            "MIT",
            "project-rights wording",
        ),
        (
            ("rights", "terms_path"),
            "documentation/index.html#different-terms",
            "project-rights wording",
        ),
        (
            ("inventory", "manifest_scope"),
            "selected files only",
            "inventory scope",
        ),
        (
            ("copy_policy", "frozen_repository_policy"),
            "legacy paths may be omitted",
            "copy policy",
        ),
        (
            ("copy_policy", "excluded_directory_names"),
            [],
            "copy policy",
        ),
        (
            ("build_identity", "pipeline_bundle_hash"),
            "b" * 64,
            "build identity",
        ),
        (
            ("build_identity", "parity", "runs"),
            999,
            "build identity",
        ),
        (
            ("evidence_identity", "authority_note"),
            "The public manifest supersedes the evidence authority.",
            "evidence identity",
        ),
        (
            ("evidence_identity", "verifier_path"),
            "canonical-evidence/tools/different_verifier.py",
            "evidence identity",
        ),
    ],
)
def test_verifier_rejects_rehashed_manifest_claim_tampering(
    workspace, field_path, replacement, match
):
    _build(workspace)
    root = workspace["output"]
    manifest_path = root / release.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = manifest
    for field in field_path[:-1]:
        target = target[field]
    target[field_path[-1]] = replacement
    _write(manifest_path, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (root / release.SHA256SUMS_NAME).unlink()
    release._write_sha256sums(root)

    with pytest.raises(release.PublicReleaseError, match=match):
        release.verify_public_release(root)


def test_verifier_rejects_missing_og_asset(workspace):
    _build(workspace)
    root = workspace["output"]
    (root / release.EXPECTED_OG_ASSET_PATH).unlink()
    with pytest.raises(release.PublicReleaseError, match="incomplete"):
        release.verify_public_release(root)


def test_verifier_rejects_tampered_og_asset(workspace):
    _build(workspace)
    root = workspace["output"]
    _write(root / release.EXPECTED_OG_ASSET_PATH, _png(3, 3))
    with pytest.raises(release.PublicReleaseError, match="hash/size mismatch"):
        release.verify_public_release(root)


def test_refuses_tampered_frozen_cache_even_when_sealed_verifier_fixture_passes(
    workspace,
):
    cache = (
        workspace["canonical"]
        / f"raw_cache/repo-{release.EXPECTED_REPO_COMMIT}"
    )
    _write(cache / "dome-lab.html", "changed legacy page\n")
    with pytest.raises(release.PublicReleaseError, match="SHA256/size mismatch"):
        _build(workspace)
    assert not workspace["output"].exists()


def test_refuses_unapproved_frozen_release_path_collision(
    workspace, monkeypatch
):
    cache = (
        workspace["canonical"]
        / f"raw_cache/repo-{release.EXPECTED_REPO_COMMIT}"
    )
    _write(cache / "documentation/index.html", "frozen collision\n")
    tree_oid = _rebuild_frozen_inventory(workspace["canonical"])
    monkeypatch.setattr(release, "EXPECTED_REPO_TREE", tree_oid)
    with pytest.raises(release.PublicReleaseError, match="collisions must be exactly"):
        _build(workspace)
    assert not workspace["output"].exists()


def test_explicit_frozen_source_is_validated_and_untracked_files_are_not_copied(
    workspace, tmp_path
):
    canonical_cache = (
        workspace["canonical"]
        / f"raw_cache/repo-{release.EXPECTED_REPO_COMMIT}"
    )
    explicit = tmp_path / "explicit-checkout"
    shutil.copytree(canonical_cache, explicit)
    _write(explicit / "untracked.txt", "not in frozen Git tree\n")
    report = _build(workspace, frozen_repository=explicit)
    assert report["status"] == "PASS"
    assert not (workspace["output"] / "untracked.txt").exists()
    assert (workspace["output"] / "dome-lab.html").read_bytes() == (
        explicit / "dome-lab.html"
    ).read_bytes()


def test_refuses_explicit_frozen_source_that_differs_from_sealed_cache(
    workspace, tmp_path
):
    canonical_cache = (
        workspace["canonical"]
        / f"raw_cache/repo-{release.EXPECTED_REPO_COMMIT}"
    )
    explicit = tmp_path / "explicit-checkout"
    shutil.copytree(canonical_cache, explicit)
    _write(explicit / "dome-lab.html", "wrong checkout bytes\n")
    with pytest.raises(release.PublicReleaseError, match="SHA256/size mismatch"):
        _build(workspace, frozen_repository=explicit)


def test_verifier_rejects_frozen_path_tampering_even_if_inventories_are_rehashed(
    workspace,
):
    _build(workspace)
    root = workspace["output"]
    legacy = root / "dome-lab.html"
    _write(legacy, "tampered legacy page\n")

    manifest_path = root / release.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(item for item in manifest["files"] if item["path"] == "dome-lab.html")
    row["bytes"] = legacy.stat().st_size
    row["sha256"] = _sha(legacy)
    manifest["byte_totals"]["payload_bytes"] = sum(
        item["bytes"] for item in manifest["files"]
    )
    manifest["byte_totals"]["by_component"] = release._component_totals(
        manifest["files"]
    )
    _write(manifest_path, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (root / release.SHA256SUMS_NAME).unlink()
    release._write_sha256sums(root)

    with pytest.raises(release.PublicReleaseError, match="not preserved byte-identically"):
        release.verify_public_release(root)


def test_verifier_requires_exact_gitattributes(workspace):
    _build(workspace)
    root = workspace["output"]
    attributes = root / release.GITATTRIBUTES_NAME
    assert attributes.read_bytes() == b"* -text\n"
    attributes.unlink()
    with pytest.raises(release.PublicReleaseError, match="incomplete"):
        release.verify_public_release(root)


def test_verifier_rejects_tampered_gitattributes_even_if_inventory_is_rehashed(
    workspace,
):
    _build(workspace)
    root = workspace["output"]
    attributes = root / release.GITATTRIBUTES_NAME
    _write(attributes, "* text=auto\n")

    manifest_path = root / release.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(
        item
        for item in manifest["files"]
        if item["path"] == release.GITATTRIBUTES_NAME
    )
    row["bytes"] = attributes.stat().st_size
    row["sha256"] = _sha(attributes)
    manifest["byte_totals"]["payload_bytes"] = sum(
        item["bytes"] for item in manifest["files"]
    )
    manifest["byte_totals"]["by_component"] = release._component_totals(
        manifest["files"]
    )
    _write(manifest_path, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (root / release.SHA256SUMS_NAME).unlink()
    release._write_sha256sums(root)

    with pytest.raises(release.PublicReleaseError, match="must contain exactly"):
        release.verify_public_release(root)


def test_verifier_requires_nojekyll(workspace):
    _build(workspace)
    root = workspace["output"]
    marker = root / release.NOJEKYLL_NAME
    assert marker.read_bytes() == b""
    marker.unlink()
    with pytest.raises(release.PublicReleaseError, match="incomplete"):
        release.verify_public_release(root)


def test_verifier_rejects_nonempty_nojekyll_even_if_inventory_is_rehashed(
    workspace,
):
    _build(workspace)
    root = workspace["output"]
    marker = root / release.NOJEKYLL_NAME
    _write(marker, "must stay empty\n")

    manifest_path = root / release.MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(
        item for item in manifest["files"] if item["path"] == release.NOJEKYLL_NAME
    )
    row["bytes"] = marker.stat().st_size
    row["sha256"] = _sha(marker)
    manifest["byte_totals"]["payload_bytes"] = sum(
        item["bytes"] for item in manifest["files"]
    )
    manifest["byte_totals"]["by_component"] = release._component_totals(
        manifest["files"]
    )
    _write(manifest_path, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (root / release.SHA256SUMS_NAME).unlink()
    release._write_sha256sums(root)

    with pytest.raises(release.PublicReleaseError, match="must be an empty file"):
        release.verify_public_release(root)


def test_post_promotion_verification_failure_rolls_back_new_output(
    workspace, monkeypatch
):
    real_verify = release.verify_public_release
    calls = 0

    def fail_after_promotion(root):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise release.PublicReleaseError("simulated post-promotion failure")
        return real_verify(root)

    monkeypatch.setattr(release, "verify_public_release", fail_after_promotion)
    with pytest.raises(release.PublicReleaseError, match="post-promotion failure"):
        _build(workspace)
    assert calls == 2
    assert not workspace["output"].exists()
    assert not list(
        workspace["output"].parent.glob(f"{release.TEMP_STAGING_PREFIX}*")
    )
