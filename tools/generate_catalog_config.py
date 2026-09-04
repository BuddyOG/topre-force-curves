#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic generator for the parts-library config triple.

Regenerates, byte-stably, from the vendored r8 source plus explicit authored
and owner-confirmed overlays:

    config/compat_evidence.json   six-state stable-ID pair closure
    config/presets.json           registry + brand-kit presets
    config/r8_crosswalk.json      complete r8 disposition crosswalk
    documentation/R8_DISPOSITION_LEDGER.md

Authority vocabulary (no statement is ever upgraded past its source):
    source_imported   imported r8 / lib-5.0 assertions
    owner_pending     the 31 reverted DynaCaps promotions; the 4 brand kits
    owner_confirmed   selections returned in the owner defaults workbook
    unadjudicated     absent-but-applicable pairs (explicit unknowns)
    model_derived     slot-model not_applicable rulings
Compatibility last_reviewed remains null until a compatibility review records
a date. Preset selections record their separate owner-review provenance.

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


def build_presets(r8_parts, r8_kbd, overlay, stabilizer_assemblies,
                  owner_defaults):
    KSLOT = {"slider": "slider", "stabilizer_slider": "sl2", "dome": "dome",
             "housing": "h1", "conical_spring": "spring",
             "silencing_ring": "ring", "stabilizer_housing": "h2",
             "spacebar_stabilizer": "sb",
             "stabilizer_assembly": "stab2uAssembly"}
    EMPTY_UNIVERSE = list(KSLOT.values()) + ["ring2u", "keycap"]
    ring_none = overlay["ring_none"]["id"]
    assembly_ids = {row["id"] for row in stabilizer_assemblies["assemblies"]}
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
            if cat == "stabilizer_assembly":
                if pid not in assembly_ids:
                    raise SystemExit(
                        f"keyboard {kid} references unknown 2u assembly {pid}")
                tid = pid
            elif cat == "dome":
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
                        "notes": "Manufacturer-parts shortcut: loads only "
                                 "parts this brand sells; it is not a verified "
                                 "working configuration, and unlisted slots "
                                 "are chosen separately.",
                        "slots": {k: {"part": v,
                                      "source": "authored_brand_kit"}
                                  for k, v in slots.items()},
                        "empty": empty})

    no_dome = "No dome loaded by default \u2014 choose the dome you are using"
    kit("kit::deskeys", "Deskeys",
        {"slider": "slider::deskeys", "h1": "housings::deskeys",
         "h2": "stabilizer_housing_2u::deskeys",
         "sl2": "stabilizer_slider_2u::deskeys",
         "sb": "spacebar_stabilizer::deskeys",
         "spring": "conical_springs::deskeys_conical"},
        {"dome": no_dome,
         "ring": "Deskeys sells 0.2\u20131.0 mm rings \u2014 pick one"})
    kit("kit::dynacaps", "DynaCaps",
        {"slider": "slider::dynacaps", "h1": "housings::dynacaps",
         "h2": "stabilizer_housing_2u::dynacaps",
         "sl2": "stabilizer_slider_2u::dynacaps",
         "sb": "spacebar_stabilizer::dynacaps",
         "spring": "conical_springs::dynacaps"},
        {"dome": no_dome,
         "ring": "DynaCaps sells 0.3/0.5 mm Poron and Silicone rings \u2014 "
                 "pick one"})
    kit("kit::klc", "KLC",
        {"slider": "slider::klc_playground", "h1": "housings::klc_playground",
         "h2": "stabilizer_housing_2u::klc_playground",
         "sl2": "stabilizer_slider_2u::klc_playground",
         "sb": "spacebar_stabilizer::klc_playground",
         "spring": "conical_springs::klc_playground"},
        {"dome": no_dome,
         "ring": "KLC sells 0.3 mm Poron and Silicone rings (both in the "
                 "catalog) \u2014 pick one"})
    kit("kit::metakeebs", "MetaKeebs",
        {"slider": "slider::metapulse", "h1": "housings::metapulse",
         "h2": "stabilizer_housing_2u::metapulse",
         "sl2": "stabilizer_slider_2u::metapulse",
         "sb": "spacebar_stabilizer::metapulse",
         "spring": "conical_springs::metapulse"},
        {"dome": no_dome,
         "ring": "MetaPulse sells a 0.5 mm Poron ring \u2014 optional, pick "
                 "it explicitly"})
    # The vendored r8 registry remains untouched. Apply the returned workbook
    # as a separately reviewable authority layer after source import and
    # authored-kit construction.
    if owner_defaults.get("schema") != "owner-starting-point-defaults-v1":
        raise SystemExit("unsupported owner_starting_point_defaults.json schema")
    review = owner_defaults.get("review")
    if not isinstance(review, dict):
        raise SystemExit("owner defaults must contain review provenance")
    required_review = {"id", "adjudication", "date", "source_file", "sha256"}
    if set(review) != required_review:
        raise SystemExit("owner defaults review provenance has unexpected fields")
    if review.get("adjudication") != "owner_confirmed":
        raise SystemExit("owner defaults review must be owner_confirmed")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(review.get("date"))):
        raise SystemExit("owner defaults review date must use YYYY-MM-DD")
    if not re.fullmatch(r"[0-9a-f]{64}", str(review.get("sha256"))):
        raise SystemExit("owner defaults workbook SHA256 is invalid")
    amendments = owner_defaults.get("amendments", [])
    if not isinstance(amendments, list):
        raise SystemExit("owner defaults amendments must be a list")
    for amendment in amendments:
        required_amendment = {
            "id", "date", "adjudication", "source", "supporting_url", "changes"
        }
        if not isinstance(amendment, dict) or set(amendment) != required_amendment:
            raise SystemExit("owner defaults amendment has unexpected fields")
        if amendment["adjudication"] != "owner_confirmed":
            raise SystemExit("owner defaults amendment must be owner_confirmed")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(amendment["date"])):
            raise SystemExit("owner defaults amendment date must use YYYY-MM-DD")
        if not amendment["source"] or not amendment["supporting_url"]:
            raise SystemExit("owner defaults amendment lacks provenance")
        if not isinstance(amendment["changes"], list) or not amendment["changes"]:
            raise SystemExit("owner defaults amendment must record changes")

    explicit_none = owner_defaults.get("explicit_none_parts")
    if not isinstance(explicit_none, dict) or not explicit_none:
        raise SystemExit("owner defaults must declare explicit-none identities")
    for none_id, row in explicit_none.items():
        if not none_id.startswith("none::") or not isinstance(row, dict):
            raise SystemExit(f"invalid explicit-none identity {none_id!r}")
        if row.get("slot") not in set(EMPTY_UNIVERSE):
            raise SystemExit(f"explicit-none identity {none_id} has unknown slot")
        if not row.get("name") or not row.get("meaning"):
            raise SystemExit(f"explicit-none identity {none_id} lacks copy")

    assembly_by_id = {row["id"]: row
                      for row in stabilizer_assemblies["assemblies"]}
    part_slots = {ring_none: "ring"}
    for rid, part in r8_parts.items():
        cat = part["category"]
        if cat == "dome":
            part_slots[dome_db_id(overlay, rid)] = "dome"
        elif cat in KSLOT:
            part_slots[tpl_id_for(rid)] = KSLOT[cat]
        elif cat == "keycap":
            part_slots[tpl_id_for(rid)] = "keycap"
    for shell_id in overlay["shells"]:
        part_slots[shell_id] = "shell"
    for assembly_id in assembly_by_id:
        part_slots[assembly_id] = "stab2uAssembly"
    for none_id, row in explicit_none.items():
        if none_id in part_slots:
            raise SystemExit(f"explicit-none identity collides with part {none_id}")
        part_slots[none_id] = row["slot"]

    override_rows = owner_defaults.get("presets")
    if not isinstance(override_rows, dict) or not override_rows:
        raise SystemExit("owner defaults must contain preset overrides")
    expected_reviewed = (set(overlay.get("public_keyboard_ids", []))
                         | set(overlay.get("public_brand_kit_ids", [])))
    actual_reviewed = set(override_rows)
    if actual_reviewed != expected_reviewed:
        missing = sorted(expected_reviewed - actual_reviewed)
        extra = sorted(actual_reviewed - expected_reviewed)
        raise SystemExit("owner defaults must cover the exact public starter "
                         f"set; missing={missing}, extra={extra}")
    preset_by_id = {row["id"]: row for row in presets}
    owner_source = "owner_starting_point_defaults"
    for preset_id, override in sorted(override_rows.items()):
        if preset_id not in preset_by_id:
            raise SystemExit(f"owner defaults name unknown preset {preset_id}")
        if (not isinstance(override, dict)
                or not set(override) <= {"slots", "notes"}):
            raise SystemExit(f"owner defaults {preset_id} has unexpected fields")
        selections = override.get("slots")
        if not isinstance(selections, dict) or not selections:
            raise SystemExit(f"owner defaults {preset_id} has no selections")
        if ("stab2uAssembly" in selections
                and set(selections) & {"h2", "sl2", "ring2u"}):
            raise SystemExit(f"owner defaults {preset_id} redundantly selects "
                             "2u assembly child parts")
        preset = preset_by_id[preset_id]
        for slot, part_id in sorted(selections.items()):
            expected_slot = part_slots.get(part_id)
            if expected_slot is None:
                raise SystemExit(f"owner defaults {preset_id} references "
                                 f"unknown part {part_id}")
            if expected_slot != slot:
                raise SystemExit(f"owner defaults {preset_id} puts {part_id} "
                                 f"in {slot}, expected {expected_slot}")
            preset["slots"][slot] = {
                "part": part_id,
                "source": owner_source,
                "adjudication": "owner_confirmed",
                "review": review["id"],
                "selection_state": ("explicit_none"
                                    if part_id in explicit_none else "selected"),
            }
            preset["empty"].pop(slot, None)
        if "notes" in override:
            if not isinstance(override["notes"], str):
                raise SystemExit(f"owner defaults {preset_id} notes must be text")
            preset["notes"] = override["notes"]
        preset["adjudication"] = "owner_confirmed"
        preset["owner_review"] = {"id": review["id"],
                                  "date": review["date"]}

    # A selected 2u assembly is the sole parent selection. Its h2/sl2/ring2u
    # children stay independently editable at runtime, but are not redundantly
    # encoded in the preset itself.
    for preset in presets:
        assembly_selection = preset["slots"].get("stab2uAssembly")
        if not assembly_selection:
            continue
        assembly_id = assembly_selection["part"]
        if assembly_id not in assembly_by_id:
            raise SystemExit(f"preset {preset['id']} references unknown 2u "
                             f"assembly {assembly_id}")
        preset["assembly_owned"] = {}
        for child_slot in ("h2", "sl2", "ring2u"):
            preset["slots"].pop(child_slot, None)
            preset["empty"][child_slot] = (
                "represented by the selected 2u stabilizer assembly; the "
                "child remains independently editable after loading")
            preset["assembly_owned"][child_slot] = {
                "assembly": assembly_id,
                "source": assembly_selection["source"],
                "adjudication": assembly_selection.get(
                    "adjudication", preset["adjudication"]),
            }

    presets.sort(key=lambda p: p["id"])
    return {"schema": "presets-v1",
            "purpose": "Registry-generated presets. Stable part IDs only; a "
                       "preset never invents a component \u2014 empty slots "
                       "carry the reason. Owner-confirmed workbook choices "
                       "are applied without changing the vendored r8 source.",
            "generator": "tools/generate_catalog_config.py",
            "owner_review": review,
            "owner_amendments": amendments,
            "explicit_none_parts": explicit_none,
            "source_artifacts": {
                "owner_starting_point_defaults": _artifact(
                    "owner_starting_point_defaults.json"),
                "stabilizer_assemblies": _artifact(
                    "stabilizer_assemblies.json"),
            },
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

    # Current consumer-facing core universe (plate, PCB, and mod-tier parts
    # excluded). Compute this from the catalog so a documented OEM addition
    # cannot leave a stale hard-coded census behind.
    consumer_core = sorted(i for i, v in items.items()
                           if v["cls"] in ("core", "shell")
                           and v["slot"] not in ("plate", "pcb"))
    total_core = len(consumer_core) * (len(consumer_core) - 1) // 2

    same_slot = collections.Counter()
    shell_model = collections.Counter()
    for i, a in enumerate(consumer_core):
        for b in consumer_core[i + 1:]:
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
    applicable_core = total_core - n_same - n_shell
    observed_core_applicable = sum(
        1 for e in pairs
        if e["a"] in consumer_core and e["b"] in consumer_core
        and e["state"] != "not_applicable")
    assert applicable_core == observed_core_applicable
    assert c["pairs"] - c["not_applicable"] == sum(
        1 for e in pairs if e["state"] != "not_applicable")

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
    issue_rids = {rid for rid, part in r8_parts.items()
                  if part.get("part_issue")}
    ui_ids = {rid for rid, item in items.items() if item["ui_selectable"]}
    browser_source_edges = [
        e for e in pairs
        if e["state"] not in ("unknown", "not_applicable")
        and e["a"] in ui_ids and e["b"] in ui_ids
    ]
    suppressed_issue_edges = [
        e for e in browser_source_edges
        if e["a"] in issue_rids or e["b"] in issue_rids
    ]
    browser_pair_edges = len(browser_source_edges) - len(suppressed_issue_edges)
    suppressed_by_part = collections.Counter(
        e["a"] if e["a"] in issue_rids else e["b"]
        for e in suppressed_issue_edges
    )

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
- Items: {c['items']} co-selectable non-dome catalog identities across the
  complete vendored catalog and authored shell abstractions.
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

## Current consumer-core reconciliation
The consumer core is derived from the present catalog rather than frozen to
the earlier 43-vertex review snapshot.
- Core vertices: {len(consumer_core)}; unordered pairs: {total_core}.
- Same-slot exclusions: {n_same} ({same_bits}).
- Shell-model exclusions: {n_shell} \u2014 {shell_bits}.
- Applicable pairs over the current core: {applicable_core}. Every
  explicit `unknown` entry naming its evidence gap. Across the full evidence
  universe the applicable count is {c['pairs'] - c['not_applicable']}.

## lib-6.1 consumer projection

The complete closure and counts above remain the audit authority. The
`lib-6.1` browser payload is a smaller consumer projection containing
**{browser_pair_edges} decision-changing pair edges**. It suppresses
{len(suppressed_issue_edges)} source-imported or pending edges whose repeated
pair form is subsumed by a part-scoped conical-spring finding:
{', '.join(f'{rid} {count}' for rid, count in sorted(suppressed_by_part.items()))}.

This suppression changes presentation, not provenance. Deskeys and KLC are
shown once as part-scoped **Does not work** findings; MetaPulse is shown once
as a part-scoped **Not verified** finding. Only the culprit spring row is
flagged, the whole-build result inherits that issue, and unrelated component
rows are not blamed. Any genuine pair-specific finding that is not subsumed by
a part-scoped issue remains in the consumer projection and is evaluated
normally.

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


def build_ledger(xwalk, part_count, keyboard_count):
    counts = collections.Counter(v["disposition"] for v in xwalk.values())
    L = ["# r8 catalog crosswalk and disposition ledger\n",
         "Every record in the vendored r8 source (config/r8/) accounted for. "
         "Stable IDs on both sides; no record is silently out of scope. "
         "Regenerated deterministically by tools/generate_catalog_config.py.\n",
         f"- r8 part records: {part_count}; keyboard records: {keyboard_count}.",
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
    stabilizer_assemblies = _load("stabilizer_assemblies.json")
    owner_defaults = _load("owner_starting_point_defaults.json")
    if stabilizer_assemblies.get("schema") != "stabilizer-assemblies-v1":
        raise SystemExit("unsupported stabilizer_assemblies.json schema")
    assembly_rows = stabilizer_assemblies.get("assemblies")
    if not isinstance(assembly_rows, list) or not assembly_rows:
        raise SystemExit("stabilizer_assemblies.json must contain assemblies")
    assembly_ids = [row.get("id") for row in assembly_rows]
    if any(not isinstance(value, str) or not value for value in assembly_ids):
        raise SystemExit("every 2u stabilizer assembly needs a stable id")
    if len(assembly_ids) != len(set(assembly_ids)):
        raise SystemExit("duplicate 2u stabilizer assembly id")
    assembly_slot_categories = {
        "h2": "stabilizer_housing",
        "sl2": "stabilizer_slider",
        "ring2u": "silencing_ring",
    }
    for assembly in assembly_rows:
        slots = assembly.get("slots")
        if not isinstance(slots, dict) or set(slots) != set(assembly_slot_categories):
            raise SystemExit(f"2u assembly {assembly['id']} must define "
                             "h2/sl2/ring2u")
        if assembly.get("housingMode") not in {"shell", "loose"}:
            raise SystemExit(f"2u assembly {assembly['id']} has invalid "
                             "housingMode")
        if (assembly["housingMode"] == "shell") != (slots["h2"] is None):
            raise SystemExit(f"2u assembly {assembly['id']} housingMode and "
                             "h2 selection disagree")
        for slot, expected_category in assembly_slot_categories.items():
            part_id = slots[slot]
            if part_id is None:
                if slot != "h2":
                    raise SystemExit(f"2u assembly {assembly['id']} has null "
                                     f"{slot}")
                continue
            if slot == "ring2u" and part_id == catalog_overlay["ring_none"]["id"]:
                continue
            part = r8_parts.get(part_id)
            if not part or part.get("category") != expected_category:
                raise SystemExit(f"2u assembly {assembly['id']} references "
                                 f"invalid {slot} part {part_id}")
    source_artifacts = {
        "generator": _artifact("@generator"),
        "r8_parts": _artifact("r8/parts.json"),
        "r8_keyboards": _artifact("r8/keyboards.json"),
        "r8_compatibility": _artifact("r8/compatibility.json"),
        "r8_compat_rules": _artifact("r8/compat_rules.json"),
        "compat_overlay": _artifact("compat_overlay.json"),
        "catalog_overlay": _artifact("catalog_overlay.json"),
        "stabilizer_assemblies": _artifact("stabilizer_assemblies.json"),
    }

    xwalk = build_crosswalk(r8_parts, r8_kbd, catalog_overlay)
    outputs = {
        os.path.join(CFG, "r8_crosswalk.json"): _dump(
            {"schema": "r8-crosswalk-v1",
             "generator": "tools/generate_catalog_config.py",
             "source": {"reference": "03_product_data_r8_reference",
                        "vendored": "config/r8/",
                        "records": {"parts": len(r8_parts),
                                    "keyboards": len(r8_kbd)}},
             "records": xwalk}),
        os.path.join(CFG, "compat_evidence.json"): _dump(
            build_evidence(r8_parts, r8_comp, compat_overlay,
                           catalog_overlay, compat_rules, source_artifacts)),
        os.path.join(CFG, "presets.json"): _dump(
            build_presets(r8_parts, r8_kbd, catalog_overlay,
                          stabilizer_assemblies, owner_defaults)),
        os.path.join(DOC, "R8_DISPOSITION_LEDGER.md"): build_ledger(
            xwalk, len(r8_parts), len(r8_kbd)),
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
