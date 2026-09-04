"""Boundary tests for the deterministic Force Curve Bench fc-3.5 overlay."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, os.fspath(TOOLS))
import build_force_curve_release as release  # noqa: E402


CANONICAL_URL = "https://buddyog.github.io/topre-force-curves/"
GIT_TAG = "fc-3.5"
DATA_COMMIT = "6e86ac1955a0c566c7aae521705e51371992ba8a"
EVIDENCE_HASH = "7aa8588b50856816b7fce90dd6e743c26c6f16926071123291cb054352b6cd4a"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(root: Path, relative: str, payload: str | bytes) -> Path:
    path = root / Path(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    path.write_bytes(payload)
    return path


def _json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _viewer(build: dict, title: str) -> str:
    return (
        "<!doctype html><head><title>"
        + title
        + "</title>"
        + f'<link rel="canonical" href="{CANONICAL_URL}">'
        + f'<meta property="og:url" content="{CANONICAL_URL}">'
        + f'<meta property="og:image" content="{release.OG_IMAGE_URL}">'
        + "</head><script>\nconst PERCEPTION_MODEL = {\"version\":\"test\"};\n"
        + "const EMBEDDED = {};\nconst VTESTS = [{\"id\":\"new-test\"}];\n"
        + "const VIEWER_BUILD = "
        + json.dumps(build, sort_keys=True, separators=(",", ":"))
        + "; /* generated build/method/data identities */\n</script>\n"
    )


def _viewer_build(version: str) -> dict:
    return {
        "bench_build": version,
        "canonical_data_release_eligible": True,
        "canonical_evidence_identity": EVIDENCE_HASH,
        "data_identity": EVIDENCE_HASH,
        "mode": "release",
        "presentation_role": "public_release",
        "record_count": 1,
        "release_eligible": True,
        "repo_commit": DATA_COMMIT,
    }


def _seal_generated(root: Path) -> None:
    target = root / "generated_manifest.json"
    if target.exists():
        target.unlink()
    rows = {
        path.relative_to(root).as_posix(): _sha(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    _json_write(target, rows)


def _seal_subjective_pilot(root: Path) -> None:
    checksum = root / "SHA256SUMS.json"
    rows = [
        {
            "bytes": path.stat().st_size,
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha(path),
        }
        for path in sorted(root.rglob("*"), key=lambda item: item.name.encode("utf-8"))
        if path.is_file() and path != checksum
    ]
    _json_write(
        checksum,
        {
            "files": rows,
            "inventory_scope": "all regular files in this directory except SHA256SUMS.json",
            "pilot_id": "subjective-pilot-v1",
        },
    )


def _inventory_rows(root: Path) -> list[dict]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "component": "synthetic_lib61_base",
            "bytes": path.stat().st_size,
            "sha256": _sha(path),
        }
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        if path.is_file()
        and path.name not in {release.SITE_MANIFEST_NAME, release.SHA256SUMS_NAME}
    ]


def _write_sha256sums(root: Path) -> None:
    rows = [
        f"{_sha(path)}  {path.relative_to(root).as_posix()}\n"
        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())
        if path.is_file() and path.name != release.SHA256SUMS_NAME
    ]
    (root / release.SHA256SUMS_NAME).write_text(
        "".join(rows), encoding="utf-8", newline="\n"
    )


def _file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _reseal_outer(root: Path) -> None:
    manifest_path = root / release.SITE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["files"]:
        path = root / Path(*row["path"].split("/"))
        row["bytes"] = path.stat().st_size
        row["sha256"] = _sha(path)
    _json_write(manifest_path, manifest)
    _write_sha256sums(root)


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    base = tmp_path / "lib61-base"
    source = tmp_path / "release-source"
    staging = tmp_path / "fc35-staging"
    base.mkdir()
    source.mkdir()
    staging.mkdir()

    old_viewer = _viewer(_viewer_build("fc-3.4"), "Force Curve Bench fc-3.4")
    _write(base, "index.html", old_viewer)
    _write(base, "dome-lab-parts.html", "<!doctype html>lib-6.1 picker\n")
    _write(base, "dome-lab.html", "legacy dome-lab entry point\n")
    _write(base, "ec-switch-explorer.html", "legacy explorer\n")
    _write(base, "README.md", "old public documentation\n")
    raw = _write(base, "Raw_Dome/DataLog_1.csv", "Travel (mm),Load (gf)\n0,0\n")
    _write(base, "generator/old-source.py", "OLD = True\n")
    _write(base, "generator/domelab_pipeline/a.py", "SOURCE = 'old'\n")
    _write(
        base,
        "generator/domelab_pipeline/release_reference/index.release.html",
        "old template\n",
    )
    _write(base, "canonical-evidence/EPOCH_MANIFEST.json", '{"epoch":"sealed"}\n')
    _write(
        base,
        "canonical-evidence/tools/verify_canonical_epoch.py",
        "import json\nprint(json.dumps({'status':'PASS'},sort_keys=True))\n",
    )
    _write(
        base,
        f"canonical-evidence/raw_cache/repo-{DATA_COMMIT}/Raw_Dome/DataLog_1.csv",
        "Travel (mm),Load (gf)\n0,0\n",
    )
    _write(base, "documentation/subjective-pilot/README.md", "sealed pilot\n")
    _write(base, "documentation/subjective-pilot/analysis.json", '{"n":25}\n')

    generated = base / "generated"
    _write(generated, "packs/viewer.staged.html", old_viewer)
    _json_write(generated / "packs/viewer_vtests.json", [{"id": "old-test"}])
    _write(generated, "packs/picker.staged.html", "<!doctype html>lib-6.1 picker\n")
    _write(generated, "science.json", '{"measurement":42}\n')
    old_schema = {
        "config_hash": "d" * 64,
        "evidence_epoch": {"identity": EVIDENCE_HASH},
        "provenance_hashes": {
            "bundle_hash": "d" * 64,
            "evidence_epoch_hash": EVIDENCE_HASH,
            "generator_source_hash": "a" * 64,
            "release_reference_hash": "c" * 64,
        },
        "repo_commit": DATA_COMMIT,
    }
    _json_write(generated / "schema_meta.staged.json", old_schema)
    old_exclusion = {
        "artifact_role": "canonical_retention_authority",
        "config_hash": "d" * 64,
        "entries": [],
        "registry_hash": "f" * 64,
        "release_eligible": True,
        "repo_commit": DATA_COMMIT,
    }
    _json_write(generated / "exclusion_manifest.json", old_exclusion)
    parity_report = {
        "artifact_role": "canonical_retention_authority",
        "exact_null_flag_audit_match": True,
        "max_abs_delta": 0.0,
        "max_audit_abs_delta": 0.0,
        "release_eligible": True,
        "rows": [{"run": "DataLog_1.csv"}],
    }
    _json_write(generated / "parity_report.json", parity_report)
    _seal_generated(generated)

    historical = {
        "manifest_version": 1,
        "package_id": release.parts.fc34.PACKAGE_ID,
        "artifact_role": "public_force_curve_bench_release",
        "release_eligible": True,
        "bench_build": "fc-3.4",
        "publication": {"canonical_public_url": CANONICAL_URL, "git_tag": "fc-3.4"},
        "evidence_identity": {"evidence_epoch_hash": EVIDENCE_HASH},
        "files": [
            {
                "path": "Raw_Dome/DataLog_1.csv",
                "component": "frozen_repository",
                "bytes": raw.stat().st_size,
                "sha256": _sha(raw),
            }
        ],
    }
    _json_write(base / release.HISTORICAL_FORCE_MANIFEST_NAME, historical)

    picker_identity = {
        "build": "lib-6.1",
        "path": "dome-lab-parts.html",
        "sha256": _sha(base / "dome-lab-parts.html"),
        "presentation_role": "public_release",
        "release_eligible": True,
        "parts_library_source_identity": "b" * 64,
        "data_repo_commit": DATA_COMMIT,
    }
    explorer_identity = {
        "path": "ec-switch-explorer.html",
        "sha256": _sha(base / "ec-switch-explorer.html"),
        "status": "preserved_byte_identical",
    }
    base_manifest = {
        "manifest_version": 1,
        "package_id": release.parts.PACKAGE_ID,
        "artifact_role": release.ARTIFACT_ROLE,
        "release_eligible": True,
        "publication": {
            "canonical_public_url": CANONICAL_URL,
            "git_tag": "beyond-snap-ratio-v2.1",
        },
        "tool_builds": {
            "force_curve_bench": {
                "build": "fc-3.4",
                "path": "index.html",
                "sha256": _sha(base / "index.html"),
                "status": "preserved_byte_identical",
            },
            "ec_parts_library": picker_identity,
            "ec_switch_explorer": explorer_identity,
        },
        "evidence_identity": {
            "path": "canonical-evidence",
            "evidence_epoch_hash": EVIDENCE_HASH,
            "tree": {},
            "status": "preserved_byte_identical",
        },
        "files": _inventory_rows(base),
    }
    _json_write(base / release.SITE_MANIFEST_NAME, base_manifest)
    _write_sha256sums(base)
    monkeypatch.setattr(
        release,
        "PREDECESSOR_SITE_MANIFEST_SHA256",
        _sha(base / release.SITE_MANIFEST_NAME),
    )
    monkeypatch.setattr(
        release,
        "PREDECESSOR_SHA256SUMS_SHA256",
        _sha(base / release.SHA256SUMS_NAME),
    )

    _write(source, "README.md", "fc-3.5 public documentation\n")
    _write(source, release.OG_IMAGE_PATH, b"synthetic png bytes")
    _write(source, "documentation/RELEASE_NOTES_fc-3.5.md", "fc-3.5 notes\n")
    _write(source, release.RESEARCH_PAPER_STATUS_PATH, "research status\n")
    _write(source, "documentation/subjective-pilot/README.md", "sealed pilot\n")
    _write(source, "documentation/subjective-pilot/analysis.json", '{"n":25}\n')
    _seal_subjective_pilot(source / release.SUBJECTIVE_PILOT_ROOT)
    _write(source, "generator/domelab_pipeline/a.py", "SOURCE = 'new'\n")
    _write(
        source,
        "generator/domelab_pipeline/release_reference/index.release.html",
        "new template\n",
    )
    policy = source / release.POLICY_PACKAGE_PATH
    _json_write(
        policy,
        {
            "policy_version": 1,
            "name": "test-force-fc-3.5-overlay",
            "overlay_paths": [
                "README.md",
                release.OG_IMAGE_PATH,
                "documentation/RELEASE_NOTES_fc-3.5.md",
                release.RESEARCH_PAPER_STATUS_PATH,
                release.SUBJECTIVE_PILOT_SUMS_PATH,
                "generator/domelab_pipeline/a.py",
                release.POLICY_PACKAGE_PATH,
                "generator/domelab_pipeline/release_reference/index.release.html",
            ],
        },
    )

    source_identities = release._source_identities(source)
    new_schema = json.loads(json.dumps(old_schema))
    new_schema["config_hash"] = "e" * 64
    new_schema["provenance_hashes"]["bundle_hash"] = "e" * 64
    new_schema["provenance_hashes"].update(source_identities)
    new_exclusion = {**old_exclusion, "config_hash": "e" * 64}
    new_viewer = _viewer(_viewer_build("fc-3.5"), "Force Curve Bench fc-3.5")
    _write(staging, "packs/viewer.staged.html", new_viewer)
    _json_write(staging / "packs/viewer_vtests.json", [{"id": "new-test"}])
    _json_write(staging / "packs/viewer_embedded.json", {})
    _json_write(
        staging / "packs/perception_scores.json",
        {"model": {"version": "test"}, "records": [], "reference": []},
    )
    _write(staging, "packs/picker.staged.html", "newly generated picker not published\n")
    _json_write(staging / "bench_tests.staged.json", [{"test_id": "new-test"}])
    _json_write(
        staging / "curve_pack_provenance.json",
        {"repo_commit": DATA_COMMIT, "evidence_epoch_hash": EVIDENCE_HASH},
    )
    _json_write(staging / "exclusion_manifest.json", new_exclusion)
    _json_write(staging / "intake_retention_decisions.json", {})
    _json_write(staging / "parity_report.json", parity_report)
    _json_write(
        staging / "raw_path_manifest.json",
        {"repo_commit": DATA_COMMIT, "rows": []},
    )
    _json_write(staging / "schema_meta.staged.json", new_schema)
    _write(staging, "acquisition_qc.csv", b"run,status\r\n1,PASS\r\n")
    _seal_generated(staging)
    expected_stage = {
        path.relative_to(staging).as_posix(): path.read_bytes().decode("utf-8")
        for path in staging.rglob("*")
        if path.is_file()
    }

    calls = []

    def verified_base(path):
        calls.append(Path(path))
        return {
            "status": "PASS",
            "package_id": release.parts.PACKAGE_ID,
            "force_build": "fc-3.4",
            "parts_build": "lib-6.1",
        }

    monkeypatch.setattr(release.parts, "verify_parts_library_release", verified_base)
    monkeypatch.setattr(
        release,
        "_regenerate_release_stage",
        lambda source_root, cache_root, repo_commit, parity_payload: dict(expected_stage),
    )

    def build(output: Path):
        return release.build_force_curve_release(
            base_release=base,
            release_source=source,
            staging=staging,
            policy=policy,
            output=output,
            canonical_url=CANONICAL_URL,
            git_tag=GIT_TAG,
        )

    return {
        "base": base,
        "source": source,
        "staging": staging,
        "policy": policy,
        "calls": calls,
        "build": build,
        "tmp": tmp_path,
    }


def test_build_is_deterministic_and_preserves_lib61_and_evidence(workspace):
    first = workspace["tmp"] / "release-one"
    second = workspace["tmp"] / "release-two"
    report_one = workspace["build"](first)
    report_two = workspace["build"](second)

    assert report_one == report_two
    assert report_one["status"] == "PASS"
    assert report_one["force_build"] == "fc-3.5"
    assert report_one["parts_build"] == "lib-6.1"
    assert _file_map(first) == _file_map(second)
    assert len(workspace["calls"]) == 2

    base = workspace["base"]
    for relative in (
        "dome-lab-parts.html",
        "generated/packs/picker.staged.html",
        "Raw_Dome/DataLog_1.csv",
        "canonical-evidence/EPOCH_MANIFEST.json",
        "canonical-evidence/tools/verify_canonical_epoch.py",
        "dome-lab.html",
        "ec-switch-explorer.html",
        release.HISTORICAL_FORCE_MANIFEST_NAME,
    ):
        assert (first / relative).read_bytes() == (base / relative).read_bytes()
    assert (first / "index.html").read_bytes() == (
        workspace["staging"] / "packs/viewer.staged.html"
    ).read_bytes()
    assert (first / "generated/packs/viewer_vtests.json").read_bytes() == (
        workspace["staging"] / "packs/viewer_vtests.json"
    ).read_bytes()
    assert (first / release.PREDECESSOR_SITE_MANIFEST_NAME).read_bytes() == (
        base / release.SITE_MANIFEST_NAME
    ).read_bytes()

    manifest = json.loads((first / release.SITE_MANIFEST_NAME).read_text())
    assert manifest["predecessor_site_release"]["parts_build"] == "lib-6.1"
    assert manifest["predecessor_site_release"]["force_build"] == "fc-3.4"
    assert manifest["tool_builds"]["force_curve_bench"]["build"] == "fc-3.5"
    assert manifest["tool_builds"]["ec_parts_library"] == json.loads(
        (base / release.SITE_MANIFEST_NAME).read_text()
    )["tool_builds"]["ec_parts_library"]
    component_path = first / release.COMPONENT_MANIFEST_NAME
    component = json.loads(component_path.read_text(encoding="utf-8"))
    assert component["package_id"] == release.COMPONENT_PACKAGE_ID
    assert component["bench_build"] == "fc-3.5"
    assert {
        row["path"] for row in component["files"]
    } >= set(json.loads(workspace["policy"].read_text())["overlay_paths"])
    assert manifest["component_manifests"]["force_curve_bench"]["sha256"] == _sha(
        component_path
    )


def test_crlf_generated_artifacts_retain_their_byte_hash(workspace):
    csv_path = workspace["staging"] / "acquisition_qc.csv"
    assert b"\r\n" in csv_path.read_bytes()
    sealed = json.loads(
        (workspace["staging"] / "generated_manifest.json").read_text(encoding="utf-8")
    )
    assert sealed["acquisition_qc.csv"] == _sha(csv_path)
    report = workspace["build"](workspace["tmp"] / "crlf-release")
    assert report["status"] == "PASS"


def test_base_is_verified_before_policy_or_output(workspace, monkeypatch):
    attempts = []

    def reject(path):
        attempts.append(Path(path))
        raise RuntimeError("base rejected")

    monkeypatch.setattr(release.parts, "verify_parts_library_release", reject)
    workspace["policy"].write_text("not json", encoding="utf-8")
    output = workspace["tmp"] / "must-not-exist"
    with pytest.raises(release.ForceReleaseError, match="base site verification failed"):
        workspace["build"](output)
    assert attempts == [workspace["base"]]
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("bench_build", "fc-3.5-review.1"),
        ("mode", "review"),
        ("presentation_role", "review_candidate"),
        ("release_eligible", False),
        ("canonical_data_release_eligible", False),
        ("repo_commit", "0" * 40),
        ("data_identity", "0" * 64),
    ],
)
def test_rejects_wrong_staged_viewer_identity(workspace, field, value):
    build = _viewer_build("fc-3.5")
    build[field] = value
    (workspace["staging"] / "packs/viewer.staged.html").write_text(
        _viewer(build, "bad viewer"), encoding="utf-8"
    )
    with pytest.raises(release.ForceReleaseError):
        workspace["build"](workspace["tmp"] / f"bad-{field}")


@pytest.mark.parametrize(
    "relative",
    [
        "index.html",
        "dome-lab-parts.html",
        "dome-lab.html",
        "ec-switch-explorer.html",
        "FORCE_CURVE_BENCH_RELEASE_MANIFEST.json",
        "SITE_RELEASE_MANIFEST.json",
        "SHA256SUMS",
        "generated/packs/picker.staged.html",
        "canonical-evidence/EPOCH_MANIFEST.json",
        "Raw_Dome/DataLog_1.csv",
    ],
)
def test_overlay_policy_rejects_protected_paths(workspace, relative):
    _json_write(
        workspace["policy"],
        {
            "policy_version": 1,
            "name": "bad-policy",
            "overlay_paths": [relative],
        },
    )
    _write(workspace["source"], relative, "tampered\n")
    with pytest.raises(release.ForceReleaseError, match="protected path"):
        workspace["build"](workspace["tmp"] / "bad-policy-output")


@pytest.mark.parametrize(
    "relative",
    [
        "dome-lab-parts.html",
        "generated/packs/picker.staged.html",
        "Raw_Dome/DataLog_1.csv",
        "canonical-evidence/EPOCH_MANIFEST.json",
        "FORCE_CURVE_BENCH_RELEASE_MANIFEST.json",
    ],
)
def test_preserved_tampering_is_rejected_after_outer_rehash(workspace, relative):
    output = workspace["tmp"] / ("tampered-" + relative.replace("/", "-"))
    workspace["build"](output)
    path = output / relative
    path.write_bytes(path.read_bytes() + b"tampered\n")
    if relative.startswith("generated/"):
        _seal_generated(output / "generated")
    _reseal_outer(output)
    with pytest.raises(release.ForceReleaseError):
        release.verify_force_curve_release(output)


def test_generated_extra_file_is_rejected_even_when_manifests_are_resealed(workspace):
    output = workspace["tmp"] / "generated-extra"
    workspace["build"](output)
    _write(output, "generated/packs/undeclared.json", "{}\n")
    _seal_generated(output / "generated")
    manifest = json.loads((output / release.SITE_MANIFEST_NAME).read_text())
    extra = output / "generated/packs/undeclared.json"
    manifest["files"].append(
        {
            "path": "generated/packs/undeclared.json",
            "component": "base_site_preserved",
            "bytes": extra.stat().st_size,
            "sha256": _sha(extra),
        }
    )
    manifest["files"].sort(key=lambda row: row["path"].encode("utf-8"))
    generated_manifest = output / release.GENERATED_MANIFEST_PATH
    for row in manifest["files"]:
        if row["path"] == release.GENERATED_MANIFEST_PATH:
            row["bytes"] = generated_manifest.stat().st_size
            row["sha256"] = _sha(generated_manifest)
    _json_write(output / release.SITE_MANIFEST_NAME, manifest)
    _write_sha256sums(output)
    with pytest.raises(release.ForceReleaseError):
        release.verify_force_curve_release(output)


def test_vtests_must_match_viewer_record_count(workspace):
    _json_write(
        workspace["staging"] / "packs/viewer_vtests.json",
        [{"id": "one"}, {"id": "two"}],
    )
    with pytest.raises(release.ForceReleaseError, match="record_count"):
        workspace["build"](workspace["tmp"] / "bad-count")


def test_plausible_hand_edited_viewer_fails_full_regeneration(workspace):
    viewer = workspace["staging"] / "packs/viewer.staged.html"
    viewer.write_text(
        viewer.read_text(encoding="utf-8").replace(
            "Force Curve Bench fc-3.5", "Force Curve Bench hand edit"
        ),
        encoding="utf-8",
    )
    _seal_generated(workspace["staging"])
    with pytest.raises(release.ForceReleaseError, match="full regeneration"):
        workspace["build"](workspace["tmp"] / "hand-edited-viewer")


def test_coordinated_vtests_hand_edit_fails_full_regeneration(workspace):
    viewer = workspace["staging"] / "packs/viewer.staged.html"
    viewer.write_text(
        viewer.read_text(encoding="utf-8").replace('"id":"new-test"', '"id":"plausible-edit"'),
        encoding="utf-8",
    )
    _json_write(
        workspace["staging"] / "packs/viewer_vtests.json",
        [{"id": "plausible-edit"}],
    )
    _json_write(
        workspace["staging"] / "bench_tests.staged.json",
        [{"test_id": "plausible-edit"}],
    )
    _seal_generated(workspace["staging"])
    with pytest.raises(release.ForceReleaseError, match="full regeneration"):
        workspace["build"](workspace["tmp"] / "coordinated-vtests-edit")


def test_hand_edited_schema_source_identity_fails_closed(workspace):
    schema_path = workspace["staging"] / "schema_meta.staged.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["provenance_hashes"]["generator_source_hash"] = "0" * 64
    _json_write(schema_path, schema)
    _seal_generated(workspace["staging"])
    with pytest.raises(release.ForceReleaseError, match="current generator_source_hash"):
        workspace["build"](workspace["tmp"] / "bad-source-binding")


def test_failed_parity_cannot_be_resealed_into_release(workspace):
    parity_path = workspace["staging"] / "parity_report.json"
    parity = json.loads(parity_path.read_text(encoding="utf-8"))
    parity["max_abs_delta"] = 0.01
    _json_write(parity_path, parity)
    _seal_generated(workspace["staging"])
    with pytest.raises(release.ForceReleaseError, match="parity report"):
        workspace["build"](workspace["tmp"] / "failed-parity")


def test_viewer_requires_exact_canonical_and_open_graph_urls(workspace):
    viewer = workspace["staging"] / "packs/viewer.staged.html"
    viewer.write_text(
        viewer.read_text(encoding="utf-8").replace(
            '<meta property="og:url" content="https://buddyog.github.io/topre-force-curves/">',
            '<meta property="og:url" content="https://example.invalid/">',
        ),
        encoding="utf-8",
    )
    _seal_generated(workspace["staging"])
    with pytest.raises(release.ForceReleaseError, match="Open Graph URL"):
        workspace["build"](workspace["tmp"] / "bad-og-url")


def test_build_requires_exact_release_tag(workspace):
    with pytest.raises(release.ForceReleaseError, match="exact canonical URL and Git tag"):
        release.build_force_curve_release(
            base_release=workspace["base"],
            release_source=workspace["source"],
            staging=workspace["staging"],
            policy=workspace["policy"],
            output=workspace["tmp"] / "wrong-tag",
            canonical_url=CANONICAL_URL,
            git_tag="fc-3.5-approximate",
        )


def test_published_policy_tampering_is_rejected_after_outer_rehash(workspace):
    output = workspace["tmp"] / "policy-tamper"
    workspace["build"](output)
    policy_path = output / release.POLICY_PACKAGE_PATH
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["name"] = "tampered-policy"
    _json_write(policy_path, policy)
    _reseal_outer(output)
    with pytest.raises(release.ForceReleaseError, match="policy hash"):
        release.verify_force_curve_release(output)


def test_source_subjective_pilot_checksum_fails_closed(workspace):
    pilot_data = workspace["source"] / "documentation/subjective-pilot/analysis.json"
    pilot_data.write_bytes(pilot_data.read_bytes() + b"tampered\n")
    with pytest.raises(release.ForceReleaseError, match="subjective-pilot checksum mismatch"):
        workspace["build"](workspace["tmp"] / "bad-pilot-checksum")


def test_component_manifest_tampering_is_rejected_after_outer_rehash(workspace):
    output = workspace["tmp"] / "component-tamper"
    workspace["build"](output)
    component_path = output / release.COMPONENT_MANIFEST_NAME
    component = json.loads(component_path.read_text(encoding="utf-8"))
    component["artifact_role"] = "plausible_but_false_role"
    _json_write(component_path, component)
    manifest_path = output / release.SITE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["component_manifests"]["force_curve_bench"]["sha256"] = _sha(
        component_path
    )
    for row in manifest["files"]:
        if row["path"] == release.COMPONENT_MANIFEST_NAME:
            row["bytes"] = component_path.stat().st_size
            row["sha256"] = _sha(component_path)
    _json_write(manifest_path, manifest)
    _write_sha256sums(output)
    with pytest.raises(release.ForceReleaseError, match="component manifest is inconsistent"):
        release.verify_force_curve_release(output)


def test_pinned_predecessor_sha256sums_is_required(workspace, monkeypatch):
    monkeypatch.setattr(release, "PREDECESSOR_SHA256SUMS_SHA256", "0" * 64)
    with pytest.raises(release.ForceReleaseError, match="pinned predecessor"):
        workspace["build"](workspace["tmp"] / "wrong-predecessor")


def test_existing_output_is_never_replaced(workspace):
    output = workspace["tmp"] / "existing"
    output.mkdir()
    sentinel = _write(output, "sentinel.txt", "keep\n")
    with pytest.raises(release.ForceReleaseError, match="refusing to replace"):
        workspace["build"](output)
    assert sentinel.read_text() == "keep\n"


def test_sha256_inventory_tampering_is_rejected(workspace):
    output = workspace["tmp"] / "bad-sums"
    workspace["build"](output)
    sums = output / release.SHA256SUMS_NAME
    sums.write_text(sums.read_text().replace("a", "b", 1), encoding="utf-8")
    with pytest.raises(release.ForceReleaseError):
        release.verify_force_curve_release(output)
