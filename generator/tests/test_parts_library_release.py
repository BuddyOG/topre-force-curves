"""Focused boundary tests for the deterministic Parts Library site overlay."""

from __future__ import annotations

import hashlib
import base64
import json
import os
from pathlib import Path
import re
import sys

import pytest


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, os.fspath(TOOLS))
import build_parts_library_release as release  # noqa: E402


CANONICAL_URL = "https://buddyog.github.io/topre-force-curves/"
GIT_TAG = "ec-parts-lib-6.1"


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


def _picker(build: dict) -> str:
    return (
        "<!doctype html><script>\n"
        "const EMBED_ORIGINS=new Set(['https://unrealkeyboards.com']);\n"
        "let embedOrigin=null;\n"
        "function validViewportNumber(value,min,max){return typeof value==='number'&&Number.isFinite(value)&&value>=min&&value<=max;}\n"
        "try{const ref=new URL(document.referrer);if(EMBED_ORIGINS.has(ref.origin))embedOrigin=ref.origin;}catch(_error){}\n"
        "function sendHeight(){if(!embedOrigin)return;const raw=500;const height=Math.max(400,Math.min(20000,raw));parent.postMessage({type:'ukdl-height',h:height},embedOrigin);}\n"
        "window.addEventListener('message',function(event){if(event.source!==parent||!EMBED_ORIGINS.has(event.origin))return;if(embedOrigin&&event.origin!==embedOrigin)return;const data=event.data;if(!data||data.type!=='ukdl-viewport')return;if(!validViewportNumber(data.viewH,100,5000)||!validViewportNumber(data.visibleTop,0,10000000))return;if(!embedOrigin)embedOrigin=event.origin;sendHeight();});\n"
        "const PICKER_BUILD = "
        + json.dumps(build, sort_keys=True, separators=(",", ":"))
        + "; /* GENERATED identity */\n</script>\n"
    )


def _review_build() -> dict:
    return {
        "library_build": "lib-6.1-review.1",
        "mode": "review",
        "presentation_role": "review_candidate",
        "release_eligible": False,
        "parts_library_source_identity": "a" * 64,
        "repo_commit": "6e86ac1955a0c566c7aae521705e51371992ba8a",
    }


def _release_build() -> dict:
    return {
        "library_build": "lib-6.1",
        "mode": "release",
        "presentation_role": "public_release",
        "release_eligible": True,
        "parts_library_source_identity": "b" * 64,
        "repo_commit": "6e86ac1955a0c566c7aae521705e51371992ba8a",
    }


def _exclusion_manifest(config_hash: str, **updates) -> dict:
    value = {
        "artifact_role": "canonical_retention_authority",
        "config_hash": config_hash,
        "entries": [],
        "registry_hash": "f" * 64,
        "release_eligible": True,
        "repo_commit": "6e86ac1955a0c566c7aae521705e51371992ba8a",
    }
    value.update(updates)
    return value


def _seal_generated(root: Path) -> None:
    target = root / "generated_manifest.json"
    if target.exists():
        target.unlink()
    rows = {}
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if path.is_file():
            rows[path.relative_to(root).as_posix()] = _sha(path)
    _json_write(target, rows)


def _payload_rows(root: Path) -> list[dict]:
    excluded = {
        release.PREDECESSOR_MANIFEST_NAME,
        release.SHA256SUMS_NAME,
    }
    rows = []
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        rows.append(
            {
                "path": relative,
                "component": (
                    "frozen_repository"
                    if relative == "Raw_Dome/DataLog_1.csv"
                    else "synthetic_fc34_fixture"
                ),
                "bytes": path.stat().st_size,
                "sha256": _sha(path),
            }
        )
    return rows


def _file_map(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _write_active_sha256sums(root: Path) -> None:
    rows = []
    for path in sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix()):
        if not path.is_file() or path.name == release.SHA256SUMS_NAME:
            continue
        rows.append(f"{_sha(path)}  {path.relative_to(root).as_posix()}\n")
    (root / release.SHA256SUMS_NAME).write_text(
        "".join(rows), encoding="utf-8", newline="\n"
    )


def _reseal_outer_inventory(root: Path) -> None:
    manifest_path = root / release.SITE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["files"]:
        path = root / Path(*row["path"].split("/"))
        row["bytes"] = path.stat().st_size
        row["sha256"] = _sha(path)
    _json_write(manifest_path, manifest)
    _write_active_sha256sums(root)


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    base = tmp_path / "fc34-base"
    source = tmp_path / "release-source"
    staging = tmp_path / "release-staging"
    base.mkdir()
    source.mkdir()
    staging.mkdir()

    force_html = "<!doctype html><title>Force Curve Bench fc-3.4</title>\n"
    _write(base, "index.html", force_html)
    _write(base, "dome-lab-parts.html", "legacy parts page\n")
    _write(base, "dome-lab.html", "legacy dome lab\n")
    _write(base, "ec-switch-explorer.html", "preserved explorer\n")
    _write(base, "README.md", "fc-3.4 base\n")
    _write(base, "Raw_Dome/DataLog_1.csv", "Travel (mm),Load (gf)\n0,0\n")
    _write(base, "generator/old-source.txt", "old generator\n")
    _write(base, ".gitattributes", "* -text\n")
    _write(base, ".nojekyll", b"")
    _write(base, "canonical-evidence/EPOCH_MANIFEST.json", '{"epoch":"sealed"}\n')
    _write(
        base,
        "canonical-evidence/tools/verify_canonical_epoch.py",
        "import json\nprint(json.dumps({'status':'PASS'},sort_keys=True))\n",
    )

    base_generated = base / "generated"
    _write(base_generated, "packs/viewer.staged.html", force_html)
    _write(base_generated, "packs/picker.staged.html", _picker(_review_build()))
    _write(base_generated, "packs/picker_tests.json", '{"old":true}\n')
    _write(base_generated, "packs/picker_mini_curves.json", '{"old":true}\n')
    _write(base_generated, "packs/prose_scan_report.json", '{"old":true}\n')
    _write(base_generated, "schema_meta.staged.json", '{"old":true}\n')
    _write(base_generated, "science.json", '{"measurement":42}\n')
    _json_write(
        base_generated / "exclusion_manifest.json",
        _exclusion_manifest("d" * 64),
    )
    _seal_generated(base_generated)

    predecessor_manifest = {
        "manifest_version": 1,
        "package_id": release.fc34.PACKAGE_ID,
        "artifact_role": "public_force_curve_bench_release",
        "release_eligible": True,
        "bench_build": "fc-3.4",
        "publication": {
            "canonical_public_url": CANONICAL_URL,
            "git_tag": "fc-3.4",
        },
        "evidence_identity": {
            "evidence_epoch_hash": "c" * 64,
        },
        "files": _payload_rows(base),
    }
    _json_write(base / release.PREDECESSOR_MANIFEST_NAME, predecessor_manifest)
    _write(base, release.SHA256SUMS_NAME, "synthetic predecessor inventory\n")

    _write(source, "generator/new-source.txt", "new parts generator\n")
    policy = tmp_path / "overlay-policy.json"
    _json_write(
        policy,
        {
            "policy_version": 1,
            "name": "test-parts-overlay",
            "overlay_paths": ["generator/new-source.txt"],
        },
    )

    _write(staging, "packs/viewer.staged.html", force_html)
    _write(staging, "packs/picker.staged.html", _picker(_release_build()))
    _write(staging, "packs/picker_tests.json", '{"new":true}\n')
    _write(staging, "packs/picker_mini_curves.json", '{"new":true}\n')
    _write(staging, "packs/prose_scan_report.json", '{"new":true}\n')
    _write(staging, "schema_meta.staged.json", '{"new":true}\n')
    _write(staging, "science.json", '{"measurement":42}\n')
    _json_write(
        staging / "exclusion_manifest.json",
        _exclusion_manifest("e" * 64),
    )
    _seal_generated(staging)

    calls = []

    def verified_base(path):
        calls.append(Path(path))
        return {
            "status": "PASS",
            "package_id": release.fc34.PACKAGE_ID,
            "bench_build": "fc-3.4",
        }

    monkeypatch.setattr(release.fc34, "verify_public_release", verified_base)

    def build(output: Path):
        return release.build_parts_library_release(
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


def test_build_is_deterministic_and_preserves_fc34(workspace):
    first = workspace["tmp"] / "release-one"
    second = workspace["tmp"] / "release-two"
    report_one = workspace["build"](first)
    report_two = workspace["build"](second)

    assert report_one["status"] == report_two["status"] == "PASS"
    assert report_one["manifest_sha256"] == report_two["manifest_sha256"]
    assert report_one["sha256sums_sha256"] == report_two["sha256sums_sha256"]
    assert _file_map(first) == _file_map(second)
    assert len(workspace["calls"]) == 2

    base = workspace["base"]
    for relative in (
        "index.html",
        "Raw_Dome/DataLog_1.csv",
        "canonical-evidence/EPOCH_MANIFEST.json",
        "canonical-evidence/tools/verify_canonical_epoch.py",
        "dome-lab.html",
        "ec-switch-explorer.html",
        release.PREDECESSOR_MANIFEST_NAME,
    ):
        assert (first / relative).read_bytes() == (base / relative).read_bytes()
    assert (first / release.ROOT_PARTS_PATH).read_bytes() == (
        workspace["staging"] / "packs/picker.staged.html"
    ).read_bytes()
    assert (first / "generator/new-source.txt").read_text() == "new parts generator\n"

    manifest = json.loads((first / release.SITE_MANIFEST_NAME).read_text())
    assert manifest["predecessor_release"]["package_id"] == release.fc34.PACKAGE_ID
    assert manifest["predecessor_release"]["git_tag"] == "fc-3.4"
    assert manifest["tool_builds"]["force_curve_bench"]["build"] == "fc-3.4"
    assert manifest["tool_builds"]["ec_parts_library"]["build"] == "lib-6.1"
    assert manifest["overlay"]["root_picker_source"] == (
        "generated/packs/picker.staged.html"
    )
    exclusion_row = next(
        row
        for row in manifest["overlay"]["generated_allowed_differences"]
        if row["path"] == "generated/exclusion_manifest.json"
    )
    assert exclusion_row["transition"] == "config_hash_only"
    predecessor_payload = base64.b64decode(
        exclusion_row["predecessor_payload_base64"], validate=True
    )
    assert hashlib.sha256(predecessor_payload).hexdigest() == exclusion_row[
        "base_sha256"
    ]


def test_base_is_verified_before_overlay_or_output(workspace, monkeypatch):
    output = workspace["tmp"] / "must-not-exist"

    def reject(_path):
        raise release.fc34.PublicReleaseError("bad predecessor")

    monkeypatch.setattr(release.fc34, "verify_public_release", reject)
    with pytest.raises(release.PartsReleaseError, match="base verification failed"):
        workspace["build"](output)
    assert not output.exists()
    assert not list(workspace["tmp"].glob(release.TEMP_PREFIX + "*"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("library_build", "lib-6.1-review.1"),
        ("mode", "review"),
        ("presentation_role", "review_candidate"),
        ("release_eligible", False),
    ],
)
def test_requires_release_picker_identity(workspace, field, value):
    build = _release_build()
    build[field] = value
    _write(workspace["staging"], "packs/picker.staged.html", _picker(build))
    _seal_generated(workspace["staging"])
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="wrong release identity"):
        workspace["build"](output)
    assert not output.exists()


@pytest.mark.parametrize(
    "old,new,reason",
    [
        (
            "typeof value==='number'",
            "typeof value==='string'",
            "numeric-only viewport validation",
        ),
        (
            "Math.max(400,Math.min(20000,raw))",
            "Math.max(400,Math.min(50000,raw))",
            "400-20000 height clamp",
        ),
        (
            "if(embedOrigin&&event.origin!==embedOrigin)return;",
            "",
            "persistent first-origin lock",
        ),
        (
            "if(!embedOrigin)embedOrigin=event.origin;",
            "embedOrigin=event.origin;",
            "first-valid-message fallback lock",
        ),
    ],
)
def test_picker_embed_contract_rejects_weakened_bridge(tmp_path, old, new, reason):
    payload = _picker(_release_build())
    assert old in payload
    path = _write(tmp_path, "picker.html", payload.replace(old, new, 1))
    with pytest.raises(release.PartsReleaseError, match=reason):
        release._parse_picker_build(path)


@pytest.mark.parametrize(
    "injected,reason",
    [
        ("parent.postMessage({type:'x'}, '*');", "wildcard postMessage target"),
        ("history.pushState({}, '', '#chooser');", "history.pushState"),
        ("history.replaceState({}, '', '#details');", "history.replaceState"),
        ("location.hash='#parts';", "location-hash mutation"),
        ("const ukdlPlaceModal=function(){};", "legacy modal placement message"),
    ],
)
def test_picker_embed_contract_rejects_navigation_or_modal_pollution(
    tmp_path, injected, reason
):
    payload = _picker(_release_build()).replace("</script>", injected + "</script>")
    path = _write(tmp_path, "picker.html", payload)
    with pytest.raises(release.PartsReleaseError, match=re.escape(reason)):
        release._parse_picker_build(path)


def test_requires_staged_viewer_to_equal_base_index(workspace):
    _write(workspace["staging"], "packs/viewer.staged.html", "one byte different\n")
    _seal_generated(workspace["staging"])
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="not byte-identical"):
        workspace["build"](output)
    assert not output.exists()


def test_rejects_non_parts_generated_change(workspace):
    _write(workspace["staging"], "science.json", '{"measurement":43}\n')
    _seal_generated(workspace["staging"])
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="non-Parts generated artifact"):
        workspace["build"](output)
    assert not output.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("artifact_role", "review_candidate"),
        ("entries", [{"set": "invented"}]),
        ("registry_hash", "1" * 64),
        ("release_eligible", False),
        ("repo_commit", "1" * 40),
    ],
)
def test_exclusion_manifest_rejects_every_semantic_change(workspace, field, value):
    path = workspace["staging"] / "exclusion_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload[field] = value
    _json_write(path, payload)
    _seal_generated(workspace["staging"])
    output = workspace["tmp"] / "rejected"
    with pytest.raises(
        release.PartsReleaseError,
        match="exclusion_manifest.json transition must change config_hash only",
    ):
        workspace["build"](output)
    assert not output.exists()


def test_exclusion_manifest_rejects_added_or_missing_fields(workspace):
    path = workspace["staging"] / "exclusion_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["new_semantic_field"] = "not permitted"
    _json_write(path, payload)
    _seal_generated(workspace["staging"])
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="wrong semantic field set"):
        workspace["build"](output)
    assert not output.exists()


def test_exclusion_manifest_requires_valid_new_config_hash(workspace):
    path = workspace["staging"] / "exclusion_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["config_hash"] = "not-a-hash"
    _json_write(path, payload)
    _seal_generated(workspace["staging"])
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="invalid config_hash"):
        workspace["build"](output)
    assert not output.exists()


@pytest.mark.parametrize(
    "relative",
    [
        "index.html",
        "dome-lab-parts.html",
        "dome-lab.html",
        "ec-switch-explorer.html",
        "canonical-evidence/EPOCH_MANIFEST.json",
        "Raw_Dome/DataLog_1.csv",
        "generated/packs/picker.staged.html",
    ],
)
def test_overlay_policy_cannot_name_protected_paths(workspace, relative):
    _json_write(
        workspace["policy"],
        {
            "policy_version": 1,
            "name": "unsafe",
            "overlay_paths": [relative],
        },
    )
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="protected path"):
        workspace["build"](output)
    assert not output.exists()


@pytest.mark.parametrize(
    "relative",
    [
        "index.html",
        "Raw_Dome/DataLog_1.csv",
        "canonical-evidence/EPOCH_MANIFEST.json",
        "dome-lab.html",
        "ec-switch-explorer.html",
    ],
)
def test_protected_tampering_is_rejected_after_outer_rehash(workspace, relative):
    output = workspace["tmp"] / "release"
    workspace["build"](output)
    path = output / Path(*relative.split("/"))
    path.write_bytes(path.read_bytes() + b"tampered\n")
    _reseal_outer_inventory(output)
    with pytest.raises(release.PartsReleaseError, match="protected fc-3.4 path changed"):
        release.verify_parts_library_release(output)


def test_root_picker_tampering_is_rejected_after_outer_rehash(workspace):
    output = workspace["tmp"] / "release"
    workspace["build"](output)
    path = output / release.ROOT_PARTS_PATH
    path.write_bytes(path.read_bytes() + b"tampered\n")
    _reseal_outer_inventory(output)
    with pytest.raises(release.PartsReleaseError, match="not byte-identical to generated picker"):
        release.verify_parts_library_release(output)


def test_exclusion_semantic_tampering_is_rejected_after_full_rehash(workspace):
    output = workspace["tmp"] / "release"
    workspace["build"](output)
    path = output / "generated/exclusion_manifest.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["entries"] = [{"set": "invented"}]
    _json_write(path, payload)
    _seal_generated(output / "generated")
    _reseal_outer_inventory(output)
    with pytest.raises(
        release.PartsReleaseError,
        match="exclusion_manifest.json transition must change config_hash only",
    ):
        release.verify_parts_library_release(output)


def test_exclusion_predecessor_payload_is_bound_to_fc34_inventory(workspace):
    output = workspace["tmp"] / "release"
    workspace["build"](output)
    manifest_path = output / release.SITE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    row = next(
        item
        for item in manifest["overlay"]["generated_allowed_differences"]
        if item["path"] == "generated/exclusion_manifest.json"
    )
    predecessor = base64.b64decode(row["predecessor_payload_base64"], validate=True)
    row["predecessor_payload_base64"] = base64.b64encode(
        predecessor + b" \n"
    ).decode("ascii")
    _json_write(manifest_path, manifest)
    _write_active_sha256sums(output)
    with pytest.raises(
        release.PartsReleaseError,
        match="does not match fc-3.4 inventory",
    ):
        release.verify_parts_library_release(output)


def test_generated_manifest_must_seal_every_staged_file(workspace):
    _write(workspace["staging"], "unexpected.json", "{}\n")
    output = workspace["tmp"] / "rejected"
    with pytest.raises(release.PartsReleaseError, match="missing or extra staging paths"):
        workspace["build"](output)
    assert not output.exists()


def test_existing_output_is_never_replaced(workspace):
    output = workspace["tmp"] / "existing"
    output.mkdir()
    sentinel = _write(output, "sentinel.txt", "keep me\n")
    with pytest.raises(release.PartsReleaseError, match="refusing to replace"):
        workspace["build"](output)
    assert sentinel.read_text() == "keep me\n"
