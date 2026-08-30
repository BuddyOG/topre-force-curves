#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic generator for the parts-library config triple.

Regenerates, byte-stably, from the vendored r8 source plus the two explicit
authored overlays:

    config/compat_evidence.json   six-state stable-ID pair closure
    config/presets.json           registry + brand-kit presets
    config/r8_crosswalk.json      complete r8 disposition crosswalk
    documentation/R8_DISPOSITION_LEDGER.md

Authority vocabulary (no statement is ever upgraded past its source):
    source_imported   imported r8 / lib-5.0 assertions
    owner_pending     the 31 reverted DynaCaps promotions; the 4 brand kits
    unadjudicated     absent-but-applicable pairs (explicit unknowns)
    model_derived     slot-model not_applicable rulings
last_reviewed is null everywhere until a real owner review records a date.

Usage: python tools/generate_catalog_config.py [--check]
--check regenerates into memory and exits nonzero on any byte difference
from the committed files (the determinism gate the test suite runs).
"""
import argparse
import collections
import hashlib
import io
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
CFG = os.path.join(ROOT, "generator", "domelab_pipeline", "config")
DOC = os.path.join(ROOT, "documentation")


def _reject_duplicate_keys(pairs):
    """JSON object hook that refuses silent last-key-wins corruption."""
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        obj[key] = value
    return obj


def _strict_json_load(path):
    try:
        with io.open(path, encoding="utf-8") as fh:
            return json.load(fh, object_pairs_hook=_reject_duplicate_keys)
    except ValueError as exc:
        raise ValueError(f"{os.path.relpath(path, ROOT)}: {exc}") from exc


def _load(name):
    return _strict_json_load(os.path.join(CFG, name))


def _artifact(name):
    """Repository-relative path and byte hash for a generator input."""
    path = os.path.join(CFG, name) if name != "@generator" else __file__
    with io.open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    return {"path": os.path.relpath(path, ROOT).replace(os.sep, "/"),
            "sha256": digest}


def _dump(obj):
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


PREFIX = {"housing::": "housings::", "conical_spring::": "conical_springs::",
          "stabilizer_slider::": "stabilizer_slider_2u::",
          "stabilizer_housing::": "stabilizer_housing_2u::"}
SPECIAL = {"conical_spring::deskeys": "conical_springs::deskeys_conical"}
NEWER = ("dm-niz-purple-60g", "dm-topre-gx1-45g", "dm-topre-hhkb-pro2-45g",
         "dm-topre-r1-30g", "dm-topre-r1-45g", "dm-topre-r1-55g",
         "dm-topre-r2-30g", "dm-topre-r2-45g", "dm-topre-r2-55g",
         "dm-topre-rgb-45g")


def dome_db_id(overlay, rid):
    """Explicit r8-dome -> DOME_DB id from the overlay; ids predate r8
    naming, so derivation by slug would invent identities."""
    try:
        return overlay["dome_catalog_ids"][rid]
    except KeyError:
        raise SystemExit(f"no DOME_DB id mapped for r8 dome {rid}; add it to "
                         "config/catalog_overlay.json dome_catalog_ids")


def tpl_id_for(rid):
    if rid in SPECIAL:
        return SPECIAL[rid]
    for a, b in PREFIX.items():
        if rid.startswith(a):
            return b + rid[len(a):]
    return rid


def build_crosswalk(r8_parts, r8_kbd, overlay):
    xwalk = {}
    mod_or_generic = {k for k, p in r8_parts.items()
                      if p.get("tier") == "mod"
                      or k in ("keycap::mx", "keycap::topre",
                               "plate::topre", "pcb::generic")}
    for rid, p in sorted(r8_parts.items()):
        entry = {"r8_id": rid, "part_name": p["part_name"],
                 "category": p["category"], "tier": p.get("tier"),
                 "brand": p.get("brand")}
        if p["category"] == "dome":
            entry.update(disposition="integrated_dome_catalog",
                         catalog_id=dome_db_id(overlay, rid))
        elif rid in mod_or_generic:
            entry.update(disposition="integrated_round2", catalog_id=rid,
                         note="added to the catalog in Round 2; "
                              "previously omitted")
        else:
            entry.update(disposition="integrated_builder_catalog",
                         catalog_id=tpl_id_for(rid))
        xwalk[rid] = entry
    for kid, k in sorted(r8_kbd.items()):
        xwalk[kid] = {"r8_id": kid, "part_name": k["display_name"],
                      "category": "keyboard", "tier": None,
                      "brand": k.get("brand"),
                      "disposition": "integrated_round2_keyboard_registry",
                      "catalog_id": kid}
    for did in NEWER:
        xwalk["newer::" + did] = {
            "r8_id": None, "part_name": did, "category": "dome", "tier": None,
            "brand": None, "disposition": "newer_measured_identity_unverified",
            "catalog_id": did,
            "note": "measured under fc-3.4; external catalog provenance "
                    "not yet established"}
    for sid, sh in sorted(overlay["shells"].items()):
        xwalk[sid] = {"r8_id": None, "part_name": sh["name"],
                      "category": "shell", "tier": None, "brand": None,
                      "disposition": "template_shell_abstraction",
                      "catalog_id": sid,
                      "note": "represents the r8 keyboard-scoped MetaPulse "
                              "edges as shell pair edges; the shell is a "
                              "Topre-molded housing array"}
    return xwalk


def build_items(r8_parts, overlay):
    """Full non-dome evidence universe plus the runtime-selectable subset.

    Full closure intentionally retains library-only records.  The
    ``ui_selectable`` flag is derived from catalog_overlay.buildable_lists so
    coverage reporting cannot confuse that full evidence universe with the
    parts the current builder can actually co-select.
    """
    items = {}

    buildable = set(overlay["buildable_lists"])

    def add(sid, name, slot, cls, list_key):
        if sid in items:
            raise ValueError(f"duplicate compatibility item id: {sid}")
        items[sid] = {"name": name, "slot": slot, "cls": cls,
                      "list_key": list_key,
                      "ui_selectable": list_key in buildable}

    SLOT = {"slider": "slider", "stabilizer_slider": "stab_slider",
            "stabilizer_housing": "stab_housing", "housing": "housing",
            "spacebar_stabilizer": "spacebar", "conical_spring": "spring",
            "keycap": "keycap", "plate": "plate", "pcb": "pcb"}
    LIST = {"slider": "sliders", "stabilizer_slider": "sliders2u",
            "stabilizer_housing": "housings2u", "housing": "housings1u",
            "spacebar_stabilizer": "spacebars",
            "conical_spring": "springs", "keycap": "keycaps",
            "plate": "plates", "pcb": "pcbs",
            "silencing_ring": "rings", "plate_gasket": "plate_gaskets",
            "slider_gasket": "slider_gaskets",
            "travel_spacer": "travel_spacers",
            "landing_pad": "landing_pads",
            "spacebar_spring": "spacebar_springs",
            "keycap_oring": "keycap_orings"}
    for rid, p in sorted(r8_parts.items()):
        cat = p["category"]
        if cat == "dome":
            continue
        if p.get("tier") == "mod":
            add(rid, p["part_name"], "mod:" + cat, "mod", LIST[cat])
        elif cat == "silencing_ring":
            add(rid, p["part_name"], "ring", "ring", LIST[cat])
        elif cat in SLOT:
            add(rid, p["part_name"], SLOT[cat], "core", LIST[cat])
    for sid, sh in sorted(overlay["shells"].items()):
        add(sid, sh["name"], "shell", "shell", "shells")
    return items


def _edge_index(edges, label, items, statuses, keyboard_scoped=False):
    """Validate and index a pair source without silently overwriting pairs."""
    out = {}
    scoped = set()
    for pos, edge in enumerate(edges):
        if keyboard_scoped and "keyboard" in edge:
            if "b" not in edge:
                raise ValueError(f"{label}[{pos}] keyboard edge lacks b")
            if edge["b"] not in items:
                raise ValueError(f"{label}[{pos}] unknown endpoint {edge['b']}")
            if edge.get("status") not in statuses:
                raise ValueError(f"{label}[{pos}] invalid status "
                                 f"{edge.get('status')!r}")
            scoped_key = (edge["keyboard"], edge["b"])
            if scoped_key in scoped:
                raise ValueError(f"{label} duplicate keyboard-scoped pair: "
                                 f"{scoped_key[0]} <-> {scoped_key[1]}")
            scoped.add(scoped_key)
            continue
        if "a" not in edge or "b" not in edge:
            raise ValueError(f"{label}[{pos}] must contain a and b")
        a, b = edge["a"], edge["b"]
        if a == b:
            raise ValueError(f"{label}[{pos}] self-pair {a}")
        unknown = [x for x in (a, b) if x not in items]
        if unknown:
            raise ValueError(f"{label}[{pos}] unknown endpoint(s): "
                             + ", ".join(unknown))
        status = edge.get("status") if label == "r8/compatibility.json" \
            else edge.get("lib50_status")
        if status not in statuses:
            raise ValueError(f"{label}[{pos}] invalid status {status!r}")
        key = tuple(sorted((a, b)))
        if key in out:
            raise ValueError(f"{label} duplicate semantic pair: "
                             f"{key[0]} <-> {key[1]}")
        out[key] = edge
    return out


def compatibility_id(a, b):
    """Stable ID derived solely from the canonical ordered endpoint pair."""
    a, b = sorted((a, b))
    payload = (a + "\0" + b).encode("utf-8")
    return "ce2_" + hashlib.sha256(payload).hexdigest()


def applicability_for(items):
    def applicability(a, b):
        A, Bi = items[a], items[b]
        if A["slot"] == Bi["slot"] and not A["slot"].startswith("mod:"):
            return False, f"mutually exclusive: one {A['slot']} per build"
        pair = {A["slot"], Bi["slot"]}
        if "shell" in pair:
            other = Bi if A["slot"] == "shell" else A
            shell = a if A["slot"] == "shell" else b
            if other["slot"] in ("housing", "stab_housing"):
                return False, "mutually exclusive: the shell is the housing array"
            if other["slot"] == "spacebar" and shell == "shell::rc1":
                return False, ("not co-selected: RC1 shell integrates the "
                               "spacebar stabilizer")
        return True, None
    return applicability


def build_evidence(r8_parts, r8_comp, compat_overlay, overlay,
                   compat_rules=None, source_artifacts=None):
    items = build_items(r8_parts, overlay)
    applicability = applicability_for(items)

    def norm_note(raw):
        if not raw:
            return None, None
        m = re.match(r"^([A-Za-z0-9_]+)(?:\s*\((.*)\))?$", raw.strip())
        return (m.group(1), m.group(2)) if m else (raw, None)

    r8_edge = _edge_index(
        r8_comp, "r8/compatibility.json", items,
        {"compatible", "incompatible", "exceptions"},
        keyboard_scoped=True)
    lib_edge = _edge_index(
        compat_overlay["pairs"], "compat_overlay.json", items,
        {"compatible", "incompatible", "compatible_note", "pending"})

    pairs = []
    ids = sorted(items)
    reverted = 0
    for i, j in itertools.combinations(range(len(ids)), 2):
        key = (ids[i], ids[j])
        ok, why = applicability(*key)
        r8e = r8_edge.get(key)
        libe = lib_edge.get(key)
        entry = {"a": key[0], "b": key[1]}
        if not ok:
            entry.update(state="not_applicable", source="slot_model",
                         source_refs=["generator", "catalog_overlay"],
                         note_id=None, qualifier=None, reason=why,
                         last_reviewed=None, adjudication="model_derived")
        elif r8e or libe:
            nid, qual = norm_note((r8e or {}).get("note")
                                  or (libe or {}).get("note_id"))
            if libe and libe.get("note_id"):
                nid, qual = libe["note_id"], libe.get("qualifier")
            lib_s = (libe or {}).get("lib50_status")
            r8_s = (r8e or {}).get("status")
            if r8_s == "exceptions":
                if lib_s == "compatible":
                    state, adj = "conditional", "owner_pending"
                    reverted += 1
                elif lib_s == "compatible_note":
                    state, adj = "conditional", "source_imported"
                elif lib_s == "pending":
                    state, adj = "pending", "source_imported"
                else:
                    state, adj = "conditional", "unadjudicated"
                src = "r8+lib50" if libe else "r8"
            elif r8_s in ("compatible", "incompatible"):
                state, adj, src = r8_s, "source_imported", "r8"
                if lib_s == "compatible_note":
                    state, src = "conditional", "r8+lib50"
            else:
                state = {"compatible": "compatible",
                         "incompatible": "incompatible",
                         "compatible_note": "conditional",
                         "pending": "pending"}[lib_s]
                adj, src = "source_imported", "lib50"
            refs = []
            if r8e:
                refs.append("r8_compatibility")
            if libe:
                refs.append("compat_overlay")
            entry.update(state=state, source=src, source_refs=refs,
                         note_id=nid, qualifier=qual,
                         reason=None, last_reviewed=None, adjudication=adj)
        else:
            entry.update(state="unknown", source="none", note_id=None,
                         source_refs=["r8_compatibility", "compat_overlay"],
                         qualifier=None,
                         reason="no compatibility evidence recorded",
                         last_reviewed=None, adjudication="unadjudicated")
        pairs.append(entry)

    pair_ids = set()
    for e in pairs:
        e["id"] = compatibility_id(e["a"], e["b"])
        if e["id"] in pair_ids:
            raise ValueError(f"compatibility id collision: {e['id']}")
        pair_ids.add(e["id"])
    by_state = collections.Counter(e["state"] for e in pairs)
    core = [i for i in ids if items[i]["cls"] in ("core", "shell")]
    core_pairs = [e for e in pairs
                  if items[e["a"]]["cls"] in ("core", "shell")
                  and items[e["b"]]["cls"] in ("core", "shell")]
    core_applicable = sum(1 for e in core_pairs
                          if e["state"] != "not_applicable")
    ui_ids = {i for i in ids if items[i]["ui_selectable"]}
    ui_pairs = [e for e in pairs if e["a"] in ui_ids and e["b"] in ui_ids]
    ui_by_state = collections.Counter(e["state"] for e in ui_pairs)
    ui_applicable = [e for e in ui_pairs
                     if e["state"] != "not_applicable"]
    ui_unresolved = [e for e in ui_applicable
                     if e["state"] in ("unknown", "pending")
                     or e["adjudication"] in ("owner_pending",
                                               "unadjudicated")]
    rules = compat_rules or {"rules": []}
    rule_records = {}
    for rule in rules.get("rules", []):
        rid = rule["rule_id"]
        rule_records[rid] = {
            "applies": rule["applies"], "check": rule["check"],
            "status": "not_evaluable",
            "reason": "no part in the vendored r8 source carries dimensions; "
                      "the rule is preserved, injected, and reported "
                      "Not evaluable at runtime until dimensions exist",
            "source": "r8 compat_rules.json",
            "source_refs": ["r8_compat_rules"]}
    evidence = {
        "schema": "compat-evidence-v2",
        "states": ["compatible", "incompatible", "conditional", "pending",
                   "unknown", "not_applicable"],
        "adjudications": ["source_imported", "owner_pending", "unadjudicated",
                          "model_derived"],
        "purpose": "Stable-ID six-state compatibility evidence with full pair "
                   "closure. An absent lookup is a data error; the runtime "
                   "synthesizes unknown and surfaces it, never silence. "
                   "Imported statements are source_imported, never "
                   "owner-confirmed; last_reviewed stays null until a real "
                   "owner review records a date.",
        "generator": "tools/generate_catalog_config.py (deterministic; inputs: "
                     "config/r8/ + config/compat_overlay.json + "
                     "config/catalog_overlay.json)",
        "source_artifacts": source_artifacts or {},
        "applicability_model": "Full catalog evidence closure plus a "
            "ui_selectable subset derived from catalog_overlay.json "
            "buildable_lists. One item per co-selection slot (slider, "
            "stabilizer slider, stabilizer housing, housing, spacebar "
            "stabilizer, spring, keycap, plate, pcb, shell, ring). Same-slot "
            "pairs and shell-vs-housing pairs are not_applicable with the "
            "reason recorded. Library-only records remain in full closure "
            "but are excluded from UI coverage. Applicability is data, not "
            "inference.",
        "rules": rule_records,
        "counts": {"items": len(ids), "pairs": len(pairs), **dict(by_state),
                   "core_vertices": len(core),
                   "core_applicable_pairs": core_applicable,
                   "r8_exception_promotions_reverted": reverted},
        "coverage": {"ui_selectable": {
            "items": len(ui_ids), "pairs": len(ui_pairs),
            "applicable_pairs": len(ui_applicable),
            "resolved_pairs": len(ui_applicable) - len(ui_unresolved),
            "unresolved_pairs": len(ui_unresolved),
            "states": dict(sorted(ui_by_state.items()))}},
        "pairs": sorted(pairs, key=lambda e: (e["a"], e["b"])),
    }
    return evidence


def build_presets(r8_parts, r8_kbd, overlay):
    KSLOT = {"slider": "slider", "stabilizer_slider": "sl2", "dome": "dome",
             "housing": "h1", "conical_spring": "spring",
             "silencing_ring": "ring", "stabilizer_housing": "h2",
             "spacebar_stabilizer": "sb"}
    EMPTY_UNIVERSE = list(KSLOT.values()) + ["keycap"]
    ring_none = overlay["ring_none"]["id"]
    presets = []
    for kid, k in sorted(r8_kbd.items()):
        slots, empty = {}, {}
        for cat, pid in (k.get("default_parts") or {}).items():
            key = KSLOT[cat]
            if cat == "silencing_ring" and pid == "silencing_ring::none":
                slots[key] = {"part": ring_none,
                              "source": "r8_keyboard_registry (none mapped to "
                                        "the explicit No-ring choice)"}
                continue
            if cat == "dome":
                tid = dome_db_id(overlay, pid) if pid in r8_parts else pid
            else:
                tid = tpl_id_for(pid)
            slots[key] = {"part": tid, "source": "r8_keyboard_registry"}
        # A registry can identify multiple factory variants without telling
        # us which variant is physically installed. The overlay records those
        # cases explicitly so the builder asks the user instead of inventing
        # a default selection (currently Realforce RC1 30g/45g domes).
        for key, reason in (overlay.get("preset_slot_omissions", {})
                            .get(kid, {})).items():
            if key not in EMPTY_UNIVERSE:
                raise SystemExit(
                    f"preset_slot_omissions names unknown slot {key} for {kid}")
            slots.pop(key, None)
            empty[key] = reason
        shell = overlay["kbd_shell"].get(kid)
        if shell:
            slots["shell"] = {"part": shell,
                              "source": "template_shell_crosswalk"}
            for represented in ("h1", "h2"):
                if represented in slots:
                    del slots[represented]
                empty[represented] = (
                    "represented by the selected molded shell; no loose "
                    "housing identity is overlaid")
            if overlay["shells"].get(shell, {}).get("adds_spacebar_stab"):
                slots.pop("sb", None)
                empty["sb"] = (
                    "represented by the selected shell's integrated "
                    "spacebar stabilizer")
        for key in EMPTY_UNIVERSE:
            if key in slots or key in empty:
                continue
            if key == "keycap":
                empty[key] = ("not specified by the source \u2014 choose MX "
                              "or Topre keycaps")
            else:
                empty[key] = ("not specified by the r8 keyboard registry "
                              "\u2014 sourced or chosen separately")
        presets.append({"id": kid, "label": k["display_name"],
                        "group": k["kind"], "brand": k.get("brand"),
                        "source": "r8_keyboard_registry",
                        "adjudication": "source_imported",
                        "notes": k.get("notes") or "",
                        "slots": slots, "empty": empty})

    def kit(kid, label, slots, empty):
        empty = dict(empty)
        empty["keycap"] = ("not specified by the source \u2014 choose MX or "
                           "Topre keycaps")
        for key in EMPTY_UNIVERSE:
            if key not in slots and key not in empty:
                empty[key] = "not specified by this brand kit"
        presets.append({"id": kid, "label": label, "group": "brand_kit",
                        "brand": label, "source": "authored_brand_kit",
                        "adjudication": "owner_pending",
                        "notes": "brand kit: only parts this brand actually "
                                 "sells; unlisted slots are chosen separately",
                        "slots": {k: {"part": v,
                                      "source": "authored_brand_kit"}
                                  for k, v in slots.items()},
                        "empty": empty})

    kit("kit::deskeys", "Deskeys",
        {"slider": "slider::deskeys", "h1": "housings::deskeys",
         "h2": "stabilizer_housing_2u::deskeys",
         "sl2": "stabilizer_slider_2u::deskeys",
         "sb": "spacebar_stabilizer::deskeys",
         "spring": "conical_springs::deskeys_conical"},
        {"dome": "Deskeys sells V1/V2/V3/T1/CARROTS at many weights \u2014 "
                 "pick one",
         "ring": "Deskeys sells 0.2\u20131.0 mm rings \u2014 pick one"})
    kit("kit::dynacaps", "DynaCaps",
        {"slider": "slider::dynacaps", "h1": "housings::dynacaps",
         "h2": "stabilizer_housing_2u::dynacaps",
         "sl2": "stabilizer_slider_2u::dynacaps",
         "sb": "spacebar_stabilizer::dynacaps",
         "spring": "conical_springs::dynacaps"},
        {"dome": "DynaCaps sells Light/Medium/Heavy and more \u2014 pick a "
                 "weight",
         "ring": "DynaCaps sells 0.3/0.5 mm Poron and Silicone rings \u2014 "
                 "pick one"})
    kit("kit::klc", "KLC",
        {"slider": "slider::klc_playground", "h1": "housings::klc_playground",
         "h2": "stabilizer_housing_2u::klc_playground",
         "sl2": "stabilizer_slider_2u::klc_playground",
         "sb": "spacebar_stabilizer::klc_playground",
         "spring": "conical_springs::klc_playground"},
        {"dome": "KLC sells 35/45/55 g domes \u2014 pick a weight",
         "ring": "KLC sells 0.3 mm Poron and Silicone rings (both in the "
                 "catalog) \u2014 pick one"})
    kit("kit::metapulse", "MetaPulse",
        {"slider": "slider::metapulse", "h1": "housings::metapulse",
         "h2": "stabilizer_housing_2u::metapulse",
         "sl2": "stabilizer_slider_2u::metapulse",
         "sb": "spacebar_stabilizer::metapulse",
         "spring": "conical_springs::metapulse"},
        {"dome": "MetaPulse sells BS/RS domes at many weights \u2014 pick one",
         "ring": "MetaPulse sells a 0.5 mm Poron ring \u2014 optional, pick "
                 "it explicitly"})
    presets.sort(key=lambda p: p["id"])
    return {"schema": "presets-v1",
            "purpose": "Registry-generated presets. Stable part IDs only; a "
                       "preset never invents a component \u2014 empty slots "
                       "carry the reason. Imported registry statements are "
                       "source_imported; the authored brand kits are "
                       "owner_pending.",
            "generator": "tools/generate_catalog_config.py",
            "presets": presets}


def build_audit(evidence, r8_parts, r8_comp, overlay):
    """Deterministic compatibility audit over the committed evidence.
    Every number is computed here and asserted internally; the doc cannot
    drift from the data."""
    items = build_items(r8_parts, overlay)
    pairs = evidence["pairs"]
    by_id = {(e["a"], e["b"]): e for e in pairs}
    c = evidence["counts"]
    ui = evidence["coverage"]["ui_selectable"]

    # -- the reviewer's 43-vertex universe (39 core parts, 2 shells,
    #    2 keycaps; plate and PCB excluded) --
    core43 = sorted(i for i, v in items.items()
                    if v["cls"] in ("core", "shell")
                    and v["slot"] not in ("plate", "pcb"))
    assert len(core43) == 43, len(core43)
    total43 = len(core43) * 42 // 2
    assert total43 == 903

    same_slot = collections.Counter()
    shell_model = collections.Counter()
    for i, a in enumerate(core43):
        for b in core43[i + 1:]:
            e = by_id[(a, b)] if (a, b) in by_id else by_id[(b, a)]
            if e["state"] != "not_applicable":
                continue
            slots = {items[a]["slot"], items[b]["slot"]}
            if "shell" in slots:
                if slots == {"shell"}:
                    shell_model["shell x shell"] += 1
                elif "housing" in slots:
                    shell_model["shell x housing"] += 1
                elif "stab_housing" in slots:
                    shell_model["shell x stabilizer housing"] += 1
                elif "spacebar" in slots:
                    shell_model["RC1 shell x spacebar stabilizer"] += 1
                else:
                    raise AssertionError((a, b, slots))
            else:
                same_slot[items[a]["slot"]] += 1
    n_same = sum(same_slot.values())
    n_shell = sum(shell_model.values())
    # The Round 2 audit misclassified the shell x shell pair as same-slot
    # (117/29). Correct classification: 116 same-slot + 30 shell-model.
    assert n_same == 116, dict(same_slot)
    assert n_shell == 30, dict(shell_model)
    assert shell_model == collections.Counter(
        {"shell x housing": 10, "shell x stabilizer housing": 14,
         "shell x shell": 1, "RC1 shell x spacebar stabilizer": 5})
    applicable43 = total43 - n_same - n_shell
    assert applicable43 == 757
    assert c["pairs"] - c["not_applicable"] == 3004

    r8_edges = [e for e in r8_comp if "keyboard" not in e]
    assert len(r8_edges) == 335, len(r8_edges)

    reverted = [e for e in pairs if e["adjudication"] == "owner_pending"]
    assert len(reverted) == c["r8_exception_promotions_reverted"] == 31
    quald = [e for e in pairs if e.get("qualifier")]
    src_counts = collections.Counter(
        e["source"] for e in pairs if e["source"] in ("r8", "lib50", "r8+lib50"))
    shell_refine = [e for e in pairs
                    if e["source"] == "lib50" and e["a"].startswith("shell::")
                    and e["state"] != "not_applicable"]

    def li(entries):
        return "\n".join(f"  - `{e['id']}` {e['a']} \u2194 {e['b']}"
                          for e in sorted(entries,
                                          key=lambda x: (x["a"], x["b"])))

    same_bits = ", ".join(f"{k.replace('_', ' ')}s {v}"
                          for k, v in sorted(same_slot.items()))
    shell_bits = "; ".join(f"{k} ({v})"
                           for k, v in sorted(shell_model.items()))
    return f"""# Compatibility audit \u2014 six-state evidence source

Truth source: `config/compat_evidence.json` (schema compat-evidence-v2),
regenerated deterministically by `tools/generate_catalog_config.py` from the
vendored r8 source plus the two committed authored overlays. The template
carries no authored compatibility graph; the generator injects this file and
the runtime synthesizes an explicit, surfaced *unknown* for any absent
lookup. Nothing absent ever renders as compatible. This audit is the same
tool's fifth output: every number below is computed from the evidence and
asserted at generation time.

## Universe and closure
- Items: {c['items']} co-selectable non-dome catalog identities (39 core
  builder parts, 2 shells, 2 keycap records, plate, PCB, 23 silencing rings,
  15 mod-tier products).
- Pairs: {c['pairs']} = C({c['items']},2); full closure, every pair carries
  an explicit state.
- States: compatible {c['compatible']}, incompatible {c['incompatible']},
  conditional {c['conditional']}, pending {c['pending']}, unknown
  {c['unknown']}, not_applicable {c['not_applicable']}.

## Runtime-selectable coverage
The builder subset is derived from `catalog_overlay.json` `buildable_lists`,
not from a second hard-coded census. Library-only plate, PCB, and mod-tier
records remain in the full evidence closure but do not inflate these figures.
- Identities selectable by the current UI: {ui['items']}.
- Pair closure over that subset: {ui['pairs']}.
- Applicable pairs: {ui['applicable_pairs']}.
- Resolved source-imported pairs: {ui['resolved_pairs']}.
- Unresolved pairs (unknown, pending, owner_pending, or unadjudicated):
  {ui['unresolved_pairs']}.
- State census: {', '.join(f'{k} {v}' for k, v in sorted(ui['states'].items()))}.

## Reconciliation with the review's 787-pair count
The reviewer counted 787 potentially co-selected pairs over the pre-Round-2
universe of 43 vertices (39 parts, 2 shells, 2 keycaps): C(43,2) = 903 minus
116 same-slot pairs = 787, with 337 explicit edges and 450 absent.
- Same-slot exclusions among the 43: {n_same} ({same_bits}).
- Shell-model exclusions among the 43: {n_shell} \u2014 {shell_bits}. The
  Round 2 audit bucketed the shell\u00d7shell pair into same-slot (117/29);
  it belongs here \u2014 its recorded reason is the shell slot model.
- Applicable pairs over the 43 under this model: {applicable43}
  (= 903 \u2212 116 \u2212 30). Every absent-but-applicable pair is an
  explicit `unknown` entry naming its evidence gap. Over the full Round 2
  universe the applicable count is {c['pairs'] - c['not_applicable']}.

## r8 agreement and the {len(reverted)} reverted promotions
- r8 part-scoped edges: {len(r8_edges)}; every `compatible` and
  `incompatible` r8 status is preserved verbatim (**source_imported** \u2014
  imported statements are never recorded as owner-confirmed, and
  `last_reviewed` stays null until a real owner review).
- All r8 `exceptions` edges are conditional or pending; the {len(reverted)}
  edges that lib-5.0 had silently promoted to plain compatible are reverted
  to **conditional / owner_pending** carrying
  `note_dynacaps_conical_universal`, and the runtime renders \u201cOwner
  adjudication pending \u2014 treat as unconfirmed.\u201d
{li(reverted)}

## Restored qualifiers
{li(quald)}
  \u2014 note `note_dynacaps_housing` + qualifier `(scratchy)`, rendered for
  both Topre Silent variants; the lib-5.0 inline-key convention that dropped
  the note at runtime is retired.

## Preserved rule
- `opening_vs_barrel` (r8 compat_rules.json): status **not_evaluable**
  \u2014 no part in the vendored r8 source carries dimensions; the rule is
  preserved, injected (`COMPAT_RULES`), and reported Not evaluable at
  runtime until dimensions exist.

## Sources
- Explicit evidence by source: {', '.join(f'{k} {v}' for k, v in sorted(src_counts.items()))}.
- Every pair carries `source_refs`; every referenced source artifact has a
  repository-relative path and SHA-256 in the top-level `source_artifacts`
  registry. Pair IDs are SHA-256-derived from their ordered endpoint IDs and
  therefore do not renumber when unrelated catalog items are added.
- The r8 keyboard-scoped MetaPulse statements are carried at the shell
  level as authored lib-5.0 refinements ({len(shell_refine)} edges: the two
  stabilizer-slider pairs and the HHKB-shell \u00d7 spacebar-stabilizer
  pair, all attributed to `note_metapulse_stab_incompat`); the RC1 spacebar
  side is not_applicable because the RC1 shell integrates its spacebar
  stabilizer.
- Regenerated by `tools/generate_catalog_config.py`; `--check` is the
  determinism gate.
"""


def build_ledger(xwalk):
    counts = collections.Counter(v["disposition"] for v in xwalk.values())
    L = ["# r8 catalog crosswalk and disposition ledger\n",
         "Every record in the vendored r8 source (config/r8/) accounted for. "
         "Stable IDs on both sides; no record is silently out of scope. "
         "Regenerated deterministically by tools/generate_catalog_config.py.\n",
         "- r8 part records: 152; keyboard records: 21.",
         "- Dispositions: " + ", ".join(f"{k}: {v}"
                                        for k, v in sorted(counts.items()))
         + "\n"]
    for disp in sorted(counts):
        L.append(f"## {disp}\n")
        for rid, e in sorted(xwalk.items()):
            if e["disposition"] != disp:
                continue
            L.append(f"- `{rid}` \u2192 `{e['catalog_id']}` \u2014 "
                     f"{e['part_name']}"
                     + (f" ({e['note']})" if e.get("note") else ""))
        L.append("")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify committed outputs match regeneration")
    args = ap.parse_args()

    r8_parts = _load("r8/parts.json")
    r8_kbd = _load("r8/keyboards.json")
    r8_comp = _load("r8/compatibility.json")
    compat_rules = _load("r8/compat_rules.json")
    compat_overlay = _load("compat_overlay.json")
    catalog_overlay = _load("catalog_overlay.json")
    source_artifacts = {
        "generator": _artifact("@generator"),
        "r8_parts": _artifact("r8/parts.json"),
        "r8_compatibility": _artifact("r8/compatibility.json"),
        "r8_compat_rules": _artifact("r8/compat_rules.json"),
        "compat_overlay": _artifact("compat_overlay.json"),
        "catalog_overlay": _artifact("catalog_overlay.json"),
    }

    xwalk = build_crosswalk(r8_parts, r8_kbd, catalog_overlay)
    outputs = {
        os.path.join(CFG, "r8_crosswalk.json"): _dump(
            {"schema": "r8-crosswalk-v1",
             "generator": "tools/generate_catalog_config.py",
             "source": {"reference": "03_product_data_r8_reference",
                        "vendored": "config/r8/",
                        "records": {"parts": 152, "keyboards": 21}},
             "records": xwalk}),
        os.path.join(CFG, "compat_evidence.json"): _dump(
            build_evidence(r8_parts, r8_comp, compat_overlay,
                           catalog_overlay, compat_rules, source_artifacts)),
        os.path.join(CFG, "presets.json"): _dump(
            build_presets(r8_parts, r8_kbd, catalog_overlay)),
        os.path.join(DOC, "R8_DISPOSITION_LEDGER.md"): build_ledger(xwalk),
    }
    outputs[os.path.join(DOC, "COMPAT_AUDIT_r8.md")] = build_audit(
        json.loads(outputs[os.path.join(CFG, "compat_evidence.json")]),
        r8_parts, r8_comp, catalog_overlay)
    bad = []
    for path, text in outputs.items():
        if args.check:
            with io.open(path, encoding="utf-8", newline="") as fh:
                if fh.read() != text:
                    bad.append(os.path.relpath(path, ROOT))
        else:
            io.open(path, "w", encoding="utf-8", newline="\n").write(text)
            print("wrote", os.path.relpath(path, ROOT))
    if args.check:
        if bad:
            print("STALE (regenerate with tools/generate_catalog_config.py):")
            for p in bad:
                print("  ", p)
            return 1
        print("all generated configs match the committed files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
