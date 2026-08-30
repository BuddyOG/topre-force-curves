# -*- coding: utf-8 -*-
"""Round 2 gates: branch-versus-f8203d4 measurement parity, complete r8
accounting, cache-identity coverage, and case-insensitive retired wording."""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "domelab_pipeline")
CFG = os.path.join(PKG, "config")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_measurement_artifacts_match_the_pristine_f8203d4_generation(review_staging):
    """The parity gate: every measurement-bearing artifact and all 76 curve
    packs generated on this branch hash identically to a pristine f8203d4
    generation (pinned in config/f8203d4_measurement_baseline.json). The
    epoch is never resealed for presentation work."""
    base = _load(os.path.join(CFG, "f8203d4_measurement_baseline.json"))
    assert base["source_commit"] == "f8203d4d74d49b79a26ffc89985d906f2161d276"
    files = base["files"]
    curves = [k for k in files if k.startswith("packs/curves/")]
    assert len(curves) == 76
    for core in ("bench_tests.staged.json", "per_run_full_precision.json",
                 "intake_retention_decisions.json", "eligibility_decisions.json",
                 "evidence_history.staged.json", "acquisition_qc.csv",
                 "median_comparison.json"):
        assert core in files, core
    mism = []
    for rel, want in sorted(files.items()):
        got = _sha(os.path.join(review_staging, rel))
        if got != want:
            mism.append(rel)
    assert not mism, mism


def test_r8_source_accounting_remains_complete_without_shipping_the_source(
        review_staging):
    xw = _load(os.path.join(CFG, "r8_crosswalk.json"))["records"]
    parts = [e for e in xw.values()
             if e.get("r8_id") and not e["r8_id"].startswith("kbd::")]
    kbds = [e for e in xw.values()
            if e.get("r8_id") and e["r8_id"].startswith("kbd::")]
    assert len(parts) == 152
    assert len(kbds) == 21
    r8_parts = _load(os.path.join(CFG, "r8", "parts.json"))
    r8_kbd = _load(os.path.join(CFG, "r8", "keyboards.json"))
    assert {e["r8_id"] for e in parts} == set(r8_parts)
    assert {e["r8_id"] for e in kbds} == set(r8_kbd)
    # lib-6 keeps the complete source and disposition accounting generator-side.
    # The consumer tool receives only purpose-built projections; it must not
    # embed the former verbatim source payload merely to prove accountability.
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        t = f.read()
    for anchor in ("const DOME_MEASUREMENTS = ", "const MODPARTS = ",
                   "const KEYBOARDS = "):
        assert anchor in t, anchor
    for token in ("const R8_SRC", '"source_record"',
                  '"provenance_payload"', '"r8_crosswalk"'):
        assert token not in t, token
    ledger = os.path.join(HERE, "..", "..", "documentation",
                          "R8_DISPOSITION_LEDGER.md")
    with open(ledger, encoding="utf-8") as f:
        led = f.read()
    assert "152" in led and "21" in led
    for e in list(xw.values())[::7]:            # spot coverage across the ledger
        assert (e["r8_id"] or e["catalog_id"]) in led


def test_review_staging_cache_identity_covers_presentation_inputs(review_staging):
    """Every generator input affects the cache identity: the marker equals
    the combined scientific + parts-library identity, so template or config
    edits regenerate the cached tree."""
    from domelab_pipeline.pipeline import (generator_source_identity,
                                           parts_library_source_identity, _h)
    marker = os.path.join(review_staging, ".source_identity")
    if not os.path.isfile(marker):          # externally supplied staging
        import pytest
        pytest.skip("staging supplied via DOMELAB_REVIEW_STAGING")
    with open(marker, encoding="utf-8") as f:
        recorded = f.read().strip()
    expect = _h({"scientific": generator_source_identity(),
                 "library": parts_library_source_identity()})
    assert recorded == expect


def test_parts_library_identity_lists_every_presentation_input():
    from domelab_pipeline.pipeline import parts_library_source_identity
    ident = parts_library_source_identity()
    keys = set(ident)
    assert "release_reference/dome-lab-parts.release.html" in keys
    for rel in ("config/parts_record_map.json", "config/compat_evidence.json",
                "config/presets.json", "config/r8_crosswalk.json",
                "config/r8/parts.json", "config/r8/keyboards.json",
                "config/r8/compatibility.json",
                "config/f8203d4_measurement_baseline.json"):
        assert rel in keys, rel
    for h in ident.values():
        assert re.fullmatch(r"[0-9a-f]{64}", h)


def test_retired_public_wording_is_gone_case_insensitively(review_staging):
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        page = f.read()
    for pattern in (r"full[-\s]?stroke", r"pending\s+release",
                    r"waiting\s+for\s+a\s+slider", r"total\s+energy",
                    r"norm\.?\s*drop\b",
                    r"every\s+part\s+and\s+dome\s+ever\s+made",
                    r"one\s+confirmed\s+dataset",
                    r"without\s+open\s+questions",
                    r"wildly\s+differently"):
        assert not re.search(pattern, page, re.I), pattern
    # Shopify owns site-level navigation.  The embedded artifact is one
    # builder and one contextual chooser, with none of the retired microsite
    # or research-viewer chrome.
    for token in ("<nav", 'id="view-home"', 'id="view-library"',
                  'id="view-workshop"', "themeToggle", "showView(",
                  "Force Curve Bench", "EC Switch Explorer", "Parts Library",
                  "exactMatchedRecords", "renderBuildSum", "prevCurveSVG",
                  "benchValsHTML", "Detected force-wall onset"):
        assert token not in page, token
    for required in ('id="builderApp"', 'id="buildView"',
                     'id="chooseView"', 'id="platformCard"'):
        assert required in page, required
    assert 'id="startKeyboard"' not in page
