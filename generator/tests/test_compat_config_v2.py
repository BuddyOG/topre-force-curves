import copy
import hashlib
import importlib.util
import json
import os

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CFG = os.path.join(ROOT, "generator", "domelab_pipeline", "config")
TOOL = os.path.join(ROOT, "tools", "generate_catalog_config.py")


def _tool():
    spec = importlib.util.spec_from_file_location("compat_config_v2", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(name):
    with open(os.path.join(CFG, name), encoding="utf-8") as fh:
        return json.load(fh)


def test_strict_json_loader_rejects_duplicate_keys_at_any_depth(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"outer":{"status":"a","status":"b"}}',
                    encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON object key: 'status'"):
        _tool()._strict_json_load(str(path))


def test_semantic_pair_validation_rejects_reversed_duplicates():
    tool = _tool()
    parts = _load("r8/parts.json")
    overlay = _load("catalog_overlay.json")
    compat = _load("compat_overlay.json")
    duplicate = copy.deepcopy(compat)
    edge = copy.deepcopy(duplicate["pairs"][0])
    edge["a"], edge["b"] = edge["b"], edge["a"]
    duplicate["pairs"].append(edge)
    with pytest.raises(ValueError, match="duplicate semantic pair"):
        tool.build_evidence(parts, _load("r8/compatibility.json"),
                            duplicate, overlay)


def test_pair_ids_are_endpoint_derived_and_order_independent():
    tool = _tool()
    expected = tool.compatibility_id("housing::topre", "slider::topre")
    assert expected == tool.compatibility_id("slider::topre",
                                             "housing::topre")
    assert expected != tool.compatibility_id("housing::topre",
                                             "slider::deskeys")


def test_committed_v2_evidence_has_verifiable_sources_and_stable_ids():
    tool = _tool()
    evidence = _load("compat_evidence.json")
    assert evidence["schema"] == "compat-evidence-v2"
    sources = evidence["source_artifacts"]
    assert set(sources) == {
        "generator", "r8_parts", "r8_compatibility", "r8_compat_rules",
        "compat_overlay", "catalog_overlay",
    }
    for record in sources.values():
        path = os.path.join(ROOT, *record["path"].split("/"))
        with open(path, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == record["sha256"]
    for edge in evidence["pairs"]:
        assert edge["id"] == tool.compatibility_id(edge["a"], edge["b"])
        assert isinstance(edge["source_refs"], list)
        assert edge["source_refs"]
        assert set(edge["source_refs"]) <= set(sources)


def test_ui_selectable_coverage_is_derived_and_matches_current_catalog():
    tool = _tool()
    parts = _load("r8/parts.json")
    overlay = _load("catalog_overlay.json")
    items = tool.build_items(parts, overlay)
    selectable = {key for key, item in items.items()
                  if item["ui_selectable"]}
    evidence = _load("compat_evidence.json")
    pairs = [edge for edge in evidence["pairs"]
             if edge["a"] in selectable and edge["b"] in selectable]
    applicable = [edge for edge in pairs
                  if edge["state"] != "not_applicable"]
    unresolved = [edge for edge in applicable
                  if edge["state"] in ("unknown", "pending")
                  or edge["adjudication"] in ("owner_pending",
                                               "unadjudicated")]
    coverage = evidence["coverage"]["ui_selectable"]
    assert coverage == {
        "items": 66,
        "pairs": 2145,
        "applicable_pairs": 1746,
        "resolved_pairs": 264,
        "unresolved_pairs": 1482,
        "states": {
            "compatible": 101,
            "conditional": 38,
            "incompatible": 156,
            "not_applicable": 399,
            "pending": 43,
            "unknown": 1408,
        },
    }
    assert len(selectable) == coverage["items"]
    assert len(pairs) == coverage["pairs"]
    assert len(applicable) == coverage["applicable_pairs"]
    assert len(unresolved) == coverage["unresolved_pairs"]
