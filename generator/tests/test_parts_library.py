# -*- coding: utf-8 -*-
"""Parts-library invariants: template hygiene, explicit mapping integrity,
six-state compatibility evidence, and generated identity, checked
generator-side against the committed config sources."""
import json
import sys
import subprocess
import os
import re

import pytest

from domelab_pipeline.packs import _inline_json

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(HERE, "..", "domelab_pipeline")
TPL = os.path.join(PKG, "release_reference", "dome-lab-parts.release.html")
MAP = os.path.join(PKG, "config", "parts_record_map.json")
EVID = os.path.join(PKG, "config", "compat_evidence.json")
R8C = os.path.join(PKG, "config", "r8", "compatibility.json")
PRESET_CFG = os.path.join(PKG, "config", "presets.json")
R8_PARTS = os.path.join(PKG, "config", "r8", "parts.json")
R8_KEYBOARDS = os.path.join(PKG, "config", "r8", "keyboards.json")

VALID_STATES = {"compatible", "incompatible", "conditional", "pending",
                "unknown", "not_applicable"}

PUBLIC_KEYBOARD_STARTERS = {
    "kbd::hhkb_30th",
    "kbd::hhkb_bt",
    "kbd::hhkb_classic",
    "kbd::hhkb_classic_type_s",
    "kbd::hhkb_hybrid",
    "kbd::hhkb_hybrid_jp",
    "kbd::hhkb_hybrid_type_s",
    "kbd::hhkb_pro_1",
    "kbd::hhkb_pro_2",
    "kbd::hhkb_pro_2_jp",
    "kbd::hhkb_pro_2_jp_type_s",
    "kbd::hhkb_pro_2_type_s",
    "kbd::realforce_rc1",
}


def _template():
    with open(TPL, encoding="utf-8", newline="") as f:
        return f.read()


def _blob(text, pattern):
    m = re.search(pattern, text, re.S)
    assert m, pattern
    return json.loads(m.group(1))


def _evidence():
    with open(EVID, encoding="utf-8") as f:
        return json.load(f)


def test_template_is_one_consumer_builder_with_narrow_generation_anchors():
    t = _template()
    # Shopify owns the Dome Lab home and global tool navigation.  This file is
    # one component builder with a contextual chooser, not a nested microsite.
    for token in ("ec-parts-dataset", "BENCH_MAP", "matchDome", "CURVE_ALIAS",
                  "SNAPSHOT_TESTS", "TOTAL ENERGY", "Norm. drop",
                  "function analyze", "function parseCSV", "function averageStrokes",
                  '"COMPAT":', "PRESETS_OEM", "PRESETS_AM", "FACTORY_RING",
                  "findDomeW", "const byName", "function matchedTests",
                  "function domeSetSelected", "fonts.googleapis.com",
                  "<nav", 'id="view-home"', 'id="view-library"',
                  'id="view-workshop"', "themeToggle", "showView(",
                  "Force Curve Bench", "EC Switch Explorer", "Parts Library",
                  "exactMatchedRecords", "renderBuildSum", "prevCurveSVG",
                  "benchValsHTML", "Detected force-wall onset", "COMPAT_RULES"):
        assert token not in t, token
    for phrase in (r"full[-\s]?stroke", r"pending\s+release",
                   r"waiting\s+for\s+a\s+slider", r"every\s+part\s+and\s+dome\s+ever\s+made",
                   r"one\s+confirmed\s+dataset", r"without\s+open\s+questions"):
        assert not re.search(phrase, t, re.I), phrase
    for anchor in ("const DOME_MEASUREMENTS = []",
                   "const PICKER_BUILD = {}",
                   "const COMPAT_EVIDENCE = {}", "const PRESETS = []",
                   "const MODPARTS = []", "const KEYBOARDS = []"):
        assert t.count(anchor) == 1, anchor
    for required in ('id="builderApp"', 'id="buildView"', 'id="chooseView"',
                     "const SLOT_DEFS=", "function qualifiedKeyboardPresets(",
                     "function assessCandidate(", "function assessBuild("):
        assert required in t, required


def test_record_map_matches_canonical_fleet(review_staging):
    with open(MAP, encoding="utf-8") as f:
        cfg = json.load(f)
    assert cfg["schema"] == "parts-record-map-v1"
    rm = cfg["records"]
    with open(os.path.join(review_staging, "bench_tests.staged.json"),
              encoding="utf-8") as f:
        records = json.load(f)
    by_id = {r["test_id"]: r for r in records}
    assert set(rm) == set(by_id)
    for tid, entry in rm.items():
        rec = by_id[tid]
        assert entry["kind"] == rec["kind"], tid
        assert entry["set"] == rec["set"], tid
        target = entry["target"]
        assert target.startswith(("dome_db:", "part:")), (tid, target)
        if rec["kind"] == "dome_baseline":
            assert target.startswith("dome_db:"), tid
        else:
            assert target.startswith("part:"), tid


def test_record_map_targets_exist_and_kinds_separate():
    t = _template()
    dome_ids = {d["id"] for d in _blob(
        t, r"const DOME_DB=(\[.*?\]);\r?\nconst RINGPARTS="
    )}
    ec = _blob(t, r"const EC=(\{.*?\});\r?\nconst DOME_DB=")
    ring_ids = {r["id"] for r in _blob(
        t, r"const RINGPARTS=(\[[^\r\n]*\]);"
    )}
    part_ids = ({p["id"] for p in ec["PARTS"]} | {s["id"] for s in ec["SHELLS"]}
                | ring_ids)
    with open(MAP, encoding="utf-8") as f:
        rm = json.load(f)["records"]
    for tid, entry in rm.items():
        target = entry["target"]
        if target.startswith("dome_db:"):
            assert target[8:] in dome_ids, (tid, target)
            assert target[8:] not in part_ids, (tid, target)
        else:
            assert target[5:] in part_ids, (tid, target)
            assert target[5:] not in dome_ids, (tid, target)


def _catalog_rids():
    """Co-selectable vertex universe from the config source of truth (the
    vendored r8 non-dome parts plus the overlay shells), with the template's
    EC blob for note resolution."""
    t = _template()
    ec = _blob(t, r"const EC=(\{.*?\});\r?\nconst DOME_DB=")
    with open(os.path.join(PKG, "config", "r8", "parts.json"),
              encoding="utf-8") as f:
        r8 = json.load(f)
    with open(os.path.join(PKG, "config", "catalog_overlay.json"),
              encoding="utf-8") as f:
        ov = json.load(f)
    rids = {rid for rid, p in r8.items() if p["category"] != "dome"}
    rids |= set(ov["shells"])
    return rids, ec


def test_evidence_source_is_well_formed_and_closed():
    ev = _evidence()
    pairs = ev["pairs"]
    ids = set()
    vertices = set()
    for e in pairs:
        assert e["state"] in VALID_STATES, e["id"]
        assert (e["a"], e["b"]) == tuple(sorted([e["a"], e["b"]])), e["id"]
        assert e["a"] != e["b"], e["id"]
        assert e["id"] not in ids
        ids.add(e["id"])
        vertices.update((e["a"], e["b"]))
        # qualifier normalized out of the note id
        assert not (e["note_id"] and "(" in e["note_id"]), e["id"]
        if e["state"] == "conditional":
            assert e["note_id"], e["id"]           # conditional carries its note
        if e["state"] in ("unknown", "not_applicable"):
            assert e["reason"], e["id"]            # applicability is explicit data
        assert e["adjudication"] in ("source_imported", "owner_pending",
                                     "unadjudicated", "model_derived"), e["id"]
        assert e["last_reviewed"] is None, e["id"]   # no invented review dates
    n = len(vertices)
    assert len(pairs) == n * (n - 1) // 2, (len(pairs), n)   # full closure
    assert ev["counts"]["pairs"] == len(pairs)
    # every co-selectable catalog item participates in the closed universe
    rids, _ = _catalog_rids()
    assert rids == vertices, sorted(rids ^ vertices)[:6]


def test_evidence_census_matches_the_committed_closure():
    ev = _evidence()
    from collections import Counter
    census = Counter(e["state"] for e in ev["pairs"])
    assert dict(census) == {"compatible": 101, "incompatible": 156,
                            "conditional": 38, "pending": 43,
                            "unknown": 2666, "not_applicable": 399}
    assert len(ev["pairs"]) == 3403


def test_r8_exception_promotions_are_reverted_until_owner_approval():
    ev = _evidence()
    with open(R8C, encoding="utf-8") as f:
        r8 = json.load(f)
    by_pair = {(e["a"], e["b"]): e for e in ev["pairs"]}
    reverted = 0
    for edge in r8:
        if "keyboard" in edge or edge.get("status") != "exceptions":
            continue
        e = by_pair[tuple(sorted([edge["a"], edge["b"]]))]
        assert e["state"] in ("conditional", "pending"), e["id"]
        if e["adjudication"] == "owner_pending":
            reverted += 1
            assert e["note_id"] == "note_dynacaps_conical_universal", e["id"]
    assert reverted == 31
    assert ev["counts"]["r8_exception_promotions_reverted"] == 31


def test_scratch_qualifier_restored_for_both_silent_variants():
    ev = _evidence()
    hits = [e for e in ev["pairs"]
            if e["a"] == "housing::dynacaps"
            and e["b"] in ("slider::hhkb_type_s", "slider::topre_silenced_purple")]
    assert len(hits) == 2
    for e in hits:
        assert e["state"] == "conditional"
        assert e["note_id"] == "note_dynacaps_housing"
        assert e["qualifier"] == "scratchy"
    # and the note text itself resolves in the template
    _, ec = _catalog_rids()
    assert "note_dynacaps_housing" in ec["NOTES"]
    assert "note_dynacaps_conical_universal" in ec["NOTES"]


def test_note_ids_resolve_and_opening_vs_barrel_rule_is_preserved():
    ev = _evidence()
    _, ec = _catalog_rids()
    for e in ev["pairs"]:
        if e["note_id"]:
            assert e["note_id"] in ec["NOTES"], (e["id"], e["note_id"])
    rule = ev["rules"]["opening_vs_barrel"]
    assert rule["status"] == "not_evaluable"
    assert "dimensions" in rule["reason"]


def test_generated_picker_identity_and_dome_measurement_projection(review_staging):
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        p = f.read()
    assert "ec-parts-dataset" not in p
    build = _blob(p, r"const PICKER_BUILD = (\{.*?\}); /\* GENERATED")
    assert build["library_build"] == "lib-6.0-review.1"
    assert build["release_eligible"] is False
    assert set(build) == {
        "library_build", "mode", "presentation_role",
        "release_eligible", "repo_commit", "parts_library_source_identity",
    }
    assert re.fullmatch(r"[0-9a-f]{64}", build["parts_library_source_identity"])

    # The public tool receives one exact row per measured dome specimen, not
    # the full 76-record scientific pack and not a family average.
    measured = _blob(
        p, r"const DOME_MEASUREMENTS = (\[.*?\]); /\* GENERATED"
    )
    with open(MAP, encoding="utf-8") as f:
        record_map = json.load(f)["records"]
    with open(os.path.join(review_staging, "bench_tests.staged.json"),
              encoding="utf-8") as f:
        records = json.load(f)
    from domelab_pipeline.perception import build_perception_pack
    scores = {
        row["test_id"]: row
        for row in build_perception_pack(records)["records"]
    }
    by_id = {row["test_id"]: row for row in records}
    expected = []
    for test_id, mapping in sorted(record_map.items()):
        if not mapping["target"].startswith("dome_db:"):
            continue
        rec = by_id[test_id]
        score = scores[test_id]
        expected.append({
            "catalog_id": mapping["target"][8:],
            "specimen_id": rec["tested_part"],
            "label": rec.get("name") or rec["set"],
            "collapse_force_gf": rec["collapse_force_gf"],
            "weight_index": score["weight_index"],
            "tactility_index": score["tactility_index"],
        })
    assert measured == expected
    assert len(measured) == 68
    assert len({row["specimen_id"] for row in measured}) == len(measured)
    assert all(set(row) == {
        "catalog_id", "specimen_id", "label", "collapse_force_gf",
        "weight_index", "tactility_index",
    } for row in measured)
    assert all(isinstance(row["collapse_force_gf"], (int, float))
               and 0 <= row["weight_index"] <= 100
               and 0 <= row["tactility_index"] <= 100
               for row in measured)
    assert "function metricRange(" in p


def test_generated_picker_omits_full_scientific_and_provenance_payloads(
        review_staging):
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        page = f.read()
    for token in ("const TESTS", "MINI_CURVES", "const R8_SRC",
                  "const RECORD_MAP", "CANONICAL_RUNS",
                  "GENERATED_EXCLUSIONS", '"raw_paths"', '"raw_sha256"',
                  '"raw_git_blob_oids"', '"acquisition_ids"',
                  '"membership_authority"', '"config_hash"'):
        assert token not in page, token


def test_inline_json_cannot_terminate_the_script_element():
    payload = {"label": "</script><img src=x onerror=alert(1)>", "amp": "a&b"}
    encoded = _inline_json(payload)
    assert "</script" not in encoded.lower()
    assert "<img" not in encoded.lower()
    assert "\\u003c/script>" in encoded
    assert json.loads(encoded) == payload


def test_identity_and_presets_equal_across_viewer_profiles(tmp_path_factory,
                                                           cache, commit,
                                                           review_staging):
    """The parts library is profile-independent: same records, same counts,
    same presentation-input identity whether generated for review or
    release. Only the profile-derived naming may differ."""
    from domelab_pipeline.pipeline import generate
    out = tmp_path_factory.mktemp("release_profile")
    generate(cache, commit, str(out), write=True, run_parity=False,
             viewer_profile="release")
    def build_of(root):
        with open(os.path.join(root, "packs", "picker.staged.html"),
                  encoding="utf-8", newline="") as f:
            page = f.read()
        b = _blob(page, r"const PICKER_BUILD = (\{.*?\}); /\* GENERATED")
        pr = _blob(page, r"const PRESETS = (\[.*?\]); /\* GENERATED")
        return b, pr
    rb, rp = build_of(str(out))
    vb, vp = build_of(review_staging)
    for key in ("parts_library_source_identity", "repo_commit"):
        assert rb[key] == vb[key], key
    assert rp == vp
    assert vb["library_build"] == "lib-6.0-review.1"
    assert vb["release_eligible"] is False
    assert rb["library_build"] == "lib-6.0"
    assert rb["release_eligible"] is True


def test_browser_catalog_is_a_narrow_projection_of_the_vendored_source(
        review_staging):
    """The complete 152-part/21-keyboard source remains in config, while the
    browser receives only the two usable keycap rows and 13 exact keyboard
    starters.  This preserves source accountability without turning internal
    records into unfinished consumer choices or shipping verbatim R8_SRC."""
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        page = f.read()
    with open(R8_PARTS, encoding="utf-8") as f:
        parts = json.load(f)
    with open(R8_KEYBOARDS, encoding="utf-8") as f:
        kbds = json.load(f)
    assert len(parts) == 152 and len(kbds) == 21
    assert "const R8_SRC" not in page
    mods = _blob(page, r"const MODPARTS = (\[.*?\]); /\* GENERATED")
    assert {m["rid"] for m in mods} == {"keycap::mx", "keycap::topre"}
    assert all(m["cat"] == "Keycaps" for m in mods)
    for m in mods:
        rec = parts[m["rid"]]
        assert m["name"] == rec["part_name"], m["rid"]
        assert m["u"] == (rec.get("source_url") or ""), m["rid"]
        assert m["notes"] == list(rec.get("notes") or []), m["rid"]
        assert set(m) == {"id", "rid", "name", "cat", "brand", "stem", "notes", "u"}
    kb = _blob(page, r"const KEYBOARDS = (\[.*?\]); /\* GENERATED")
    assert {k["rid"] for k in kb} == PUBLIC_KEYBOARD_STARTERS
    for k in kb:
        rec = kbds[k["rid"]]
        assert k["name"] == rec["display_name"] and k["u"] == (rec.get("url") or "")
        assert set(k) == {"id", "rid", "name", "brand", "kind", "notes", "u"}
        assert "note_" not in k["notes"]
    public_ec = _blob(page, r"const EC=(\{.*?\});\r?\nconst DOME_DB=")
    assert set(public_ec) == {"PARTS", "SHELLS", "NOTES"}
    assert all("avail" not in row and "vendor" not in row
               for row in public_ec["PARTS"] + public_ec["SHELLS"])
    assert all(not re.search(r"r8 source|owner adjudication|Omitted from product page|\* \| \*",
                             note["text"], re.I)
               for note in public_ec["NOTES"].values())
    public_domes = _blob(
        page, r"const DOME_DB=(\[.*?\]);\r?\nconst RINGPARTS="
    )
    assert all("avail" not in row and "prov" not in row and "img" not in row
               for row in public_domes)
    assert "function renderR8Source" not in page


def _tool_module():
    import importlib.util
    path = os.path.join(HERE, "..", "..", "tools", "generate_catalog_config.py")
    spec = importlib.util.spec_from_file_location("gen_catalog_config", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_public_slot_model_excludes_catalog_only_categories():
    t = _template()
    slot_block = re.search(r"const SLOT_DEFS=\[(.*?)\];", t, re.S)
    assert slot_block
    slot_lists = set(re.findall(
        r'\{key:"[^"]+",label:"[^"]+",list:"([^"]+)"',
        slot_block.group(1),
    ))
    assert slot_lists == {
        "domes", "sliders", "housings1u", "springs", "rings", "keycaps",
        "housings2u", "sliders2u", "spacebars",
    }
    assert "function initMods(" not in t
    assert 'if(raw.cat!=="Keycaps")continue;' in t
    for list_name in ("keycap_orings", "landing_pads", "pcbs", "plates",
                      "plate_gaskets", "slider_gaskets", "spacebar_springs",
                      "travel_spacers"):
        assert f"CATALOG.{list_name}" not in t, list_name


def test_exact_public_keyboard_starter_set(review_staging):
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        page = f.read()
    presets = _blob(page, r"const PRESETS = (\[.*?\]); /\* GENERATED")
    eligible = {
        preset["id"] for preset in presets
        if preset["id"].startswith("kbd::")
        and preset["id"] not in {"kbd::hhkb", "kbd::hhkb_type_s"}
        and preset.get("slots")
    }
    assert eligible == PUBLIC_KEYBOARD_STARTERS
    assert len(eligible) == 13
    assert not any(preset["id"].startswith("kit::") for preset in presets
                   if preset["id"] in eligible)
    assert all(set(preset) <= {"id", "label", "slots", "notice"}
               and {"id", "label", "slots"} <= set(preset)
               for preset in presets)
    assert all(set(selection) == {"part"}
               for preset in presets for selection in preset["slots"].values())
    # RC1 has a recorded 30g/45g choice, so the consumer initializer must not
    # silently select the 30g alternative.
    rc1 = next(preset for preset in presets
               if preset["id"] == "kbd::realforce_rc1")
    assert "dome" not in rc1["slots"]
    assert "30 g and 45 g variants" in rc1["notice"]
    with open(os.path.join(PKG, "config", "presets.json"), encoding="utf-8") as f:
        source_presets = json.load(f)["presets"]
    source_rc1 = next(preset for preset in source_presets
                      if preset["id"] == "kbd::realforce_rc1")
    assert "30g and 45g variants" in source_rc1["empty"]["dome"]


def test_presets_reference_only_resolvable_ids():
    """Every preset slot id resolves in the generated catalog universe:
    template ids for core parts, r8 ids for mods/keycaps, DOME_DB ids,
    overlay shells, and the explicit ring::none. Every preset explains its
    keycap slot instead of leaving it derivable."""
    tool = _tool_module()
    with open(os.path.join(PKG, "config", "r8", "parts.json"),
              encoding="utf-8") as f:
        r8 = json.load(f)
    with open(os.path.join(PKG, "config", "catalog_overlay.json"),
              encoding="utf-8") as f:
        ov = json.load(f)
    with open(os.path.join(PKG, "config", "presets.json"),
              encoding="utf-8") as f:
        presets = json.load(f)["presets"]
    ids = set(ov["shells"]) | {ov["ring_none"]["id"]}
    ids |= set(ov["dome_catalog_ids"].values())
    for rid, p in r8.items():
        if p["category"] == "dome":
            continue
        ids.add(rid)                       # r8 id (mods, keycaps, rings)
        ids.add(tool.tpl_id_for(rid))      # template id (core parts)
    assert len(presets) == 25
    for pr in presets:
        for slot, spec in pr["slots"].items():
            assert spec["part"] in ids, (pr["id"], slot, spec["part"])
        assert ("keycap" in pr["slots"]) or ("keycap" in pr["empty"]), pr["id"]
        assert pr["adjudication"] in ("source_imported", "owner_pending")
    shelled = [p["id"] for p in presets if "shell" in p["slots"]]
    assert len(shelled) == 15 and all(i.startswith("kbd::") for i in shelled)


def test_config_generator_is_deterministic():
    """tools/generate_catalog_config.py --check: the committed evidence,
    presets, crosswalk, and ledger regenerate byte-identically."""
    tool = os.path.join(HERE, "..", "..", "tools", "generate_catalog_config.py")
    out = subprocess.run([sys.executable, tool, "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_compat_rules_remain_generator_side(review_staging):
    t = _template()
    assert "COMPAT_RULES" not in t
    with open(os.path.join(review_staging, "packs", "picker.staged.html"),
              encoding="utf-8", newline="") as f:
        page = f.read()
    assert "COMPAT_RULES" not in page
    rules = _evidence()["rules"]
    assert "opening_vs_barrel" in rules
    assert rules["opening_vs_barrel"]["status"] == "not_evaluable"
