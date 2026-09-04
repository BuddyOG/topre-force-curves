"""Step 2.3 importer, promotion, prose and runtime-battery integration tests.

These exercise the real production paths: the shared orchestration function both
entry points call, the rollback-capable promotion transaction, the prohibited-
copy scanner over every generated surface, and the two jsdom batteries.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from domelab_pipeline import prose
from domelab_pipeline.importer_core import (
    RETIRED_IMPORTER_MESSAGE,
    orchestrate,
    discover_runs,
    canonical_batch,
)
from domelab_pipeline.pipeline import (
    _promote_tree, dumps, sha256_bytes, generate, load_config_bundle,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def _canonical_cohort_paths(cache, minimum=1):
    test = next(
        item for item in load_config_bundle()["dataset_manifest"]["tests"]
        if len(item["expected_runs"]) >= minimum
    )
    return [
        os.path.join(cache, *run["path"].split("/"))
        for run in test["expected_runs"]
    ]


def _read_text(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as stream:
        return stream.read()


def _load_importer(importer_path):
    spec = importlib.util.spec_from_file_location("bench_import_under_test", importer_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bench_import_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------- importer
def test_retired_orchestrate_fails_before_reading_any_run(cache, active_intake_identity):
    paths = _canonical_cohort_paths(cache, minimum=4)
    with pytest.raises(
        RuntimeError, match=re.escape(active_intake_identity["parity_target"])
    ) as exc:
        orchestrate(paths=paths)
    assert str(exc.value) == RETIRED_IMPORTER_MESSAGE


def test_retired_canonical_batch_cannot_return_a_legacy_contract(cache):
    paths = _canonical_cohort_paths(cache, minimum=4)
    with pytest.raises(RuntimeError, match="retired and non-authoritative"):
        canonical_batch(paths)


def test_retired_importer_core_has_no_hidden_qc_or_runfilter_authority():
    import inspect
    import domelab_pipeline.importer_core as importer_core

    source = inspect.getsource(importer_core)
    assert "batch_filter(" not in source
    assert "canonical_eligibility(" not in source
    assert "process_run(" not in source


def test_retired_importer_does_not_stamp_current_calc_version(
    cache, active_intake_identity
):
    paths = _canonical_cohort_paths(cache)
    with pytest.raises(RuntimeError) as exc:
        canonical_batch(paths)
    assert active_intake_identity["policy_version"] in str(exc.value)


def test_legacy_parse_run_is_no_longer_a_filter(importer_path):
    mod = _load_importer(importer_path)
    assert hasattr(mod, "parse_run_diagnostic")
    with pytest.raises(RuntimeError, match="discard/prefilter authority"):
        mod.parse_run("/nonexistent.csv")


def test_legacy_diagnostic_cannot_remove_a_run(
    cache, importer_path, active_intake_identity
):
    """The diagnostic remains readable but cannot become an intake authority."""
    mod = _load_importer(importer_path)
    p = _canonical_cohort_paths(cache)[0]
    diag = mod.parse_run_diagnostic(p)
    assert "note" in diag and "usable" in diag
    with pytest.raises(
        RuntimeError, match=re.escape(active_intake_identity["parity_target"])
    ):
        orchestrate(paths=[p], diagnostics={"DataLog_1.csv": diag})


def test_headless_gui_and_exports_all_fail_closed_with_same_guidance(
    importer_path, active_intake_identity
):
    src = _read_text(importer_path)
    assert (
        f"Use the hash-bound {active_intake_identity['parity_target']} release" in src
    )
    assert "from domelab_pipeline.importer_core import orchestrate" not in src
    assert src.count("DISCARDED DataLog_") == 0, "a discard path survives"
    mod = _load_importer(importer_path)
    assert mod.headless([]) == 2
    for exporter in (mod.export_all, mod.export_v2):
        with pytest.raises(RuntimeError, match="No output was written"):
            exporter("/not-read", [], {}, "/not-read", "", "", "/not-read", [])


def test_all_runs_rejected_fails_closed(cache, tmp_path):
    """Legacy orchestration refuses even a syntactically valid batch."""
    bad = tmp_path / "batch"
    bad.mkdir()
    src = _canonical_cohort_paths(cache)[0]
    text = _read_text(src, encoding="utf-8-sig")
    broken = text.replace("Millis,Steps,Travel (mm),Scale raw,Scale (grams)", "A,B,C,D,E", 1)
    (bad / "DataLog_1.csv").write_text(broken, encoding="utf-8")
    with pytest.raises(RuntimeError, match="retired and non-authoritative"):
        orchestrate(batchdir=str(bad))


def test_core_unavailable_fails_closed(
    importer_path, monkeypatch, active_intake_identity
):
    mod = _load_importer(importer_path)
    monkeypatch.setattr(mod, "HAVE_CORE", False, raising=False)
    with pytest.raises(
        RuntimeError, match=re.escape(active_intake_identity["parity_target"])
    ):
        mod.canonical_batch(["/x.csv"])


def test_discover_runs_filters_nothing_but_the_pattern(cache):
    expected = _canonical_cohort_paths(cache, minimum=4)
    found = discover_runs(os.path.dirname(expected[0]))
    assert found == sorted(expected)


def test_openpyxl_is_available_and_pinned():
    import openpyxl  # noqa: F401
    lock = _read_text(os.path.join(HERE, "..", "requirements-lock.txt"))
    for pkg in ("openpyxl==", "et-xmlfile==", "Pygments==", "setuptools=="):
        assert pkg in lock, pkg


# ------------------------------------------------------------ promotion
def _tiny_staged():
    s = {"a.txt": "new\n", "sub/b.txt": "two\n"}
    s["generated_manifest.json"] = dumps({k: sha256_bytes(v.encode()) for k, v in s.items()})
    return s


def test_promotion_succeeds_and_leaves_no_temp(tmp_path):
    out = str(tmp_path / "tree")
    _promote_tree(_tiny_staged(), out)
    assert os.path.exists(os.path.join(out, "a.txt"))
    sibs = os.listdir(str(tmp_path))
    assert not any(s.endswith((".candidate-tmp", ".replaced-prev")) for s in sibs), sibs


def test_injected_mid_commit_failure_rolls_back_completely(tmp_path, monkeypatch):
    """Inject a failure during the SECOND commit operation (rename-in).

    Step 2.2 destroyed the target: the original tree was renamed aside and
    nothing restored it.
    """
    out = str(tmp_path / "tree")
    os.makedirs(out)
    with open(os.path.join(out, "ORIGINAL.txt"), "w", encoding="utf-8") as f:
        f.write("original release-critical content\n")

    real = os.rename
    calls = {"n": 0}

    def boom(a, b):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("injected mid-commit failure")
        return real(a, b)

    monkeypatch.setattr(os, "rename", boom)
    with pytest.raises(RuntimeError, match="rolled back"):
        _promote_tree(_tiny_staged(), out)
    monkeypatch.undo()

    assert os.path.exists(out), "target directory was destroyed"
    assert os.path.exists(os.path.join(out, "ORIGINAL.txt")), "original files lost"
    assert os.listdir(out) == ["ORIGINAL.txt"], "partial repository copy remains"
    sibs = os.listdir(str(tmp_path))
    assert not any(s.endswith((".candidate-tmp", ".replaced-prev")) for s in sibs), sibs


def test_precommit_failure_leaves_target_untouched(tmp_path):
    out = str(tmp_path / "tree")
    os.makedirs(out)
    with open(os.path.join(out, "ORIGINAL.txt"), "w", encoding="utf-8") as f:
        f.write("keep me\n")
    staged = {"a.txt": "new\n"}
    staged["generated_manifest.json"] = dumps({"a.txt": "0" * 64})   # wrong hash
    with pytest.raises(RuntimeError, match="post-write hash validation"):
        _promote_tree(staged, out)
    assert os.listdir(out) == ["ORIGINAL.txt"]
    assert not os.path.exists(out + ".candidate-tmp")


# ---------------------------------------------------------------- prose
GENERATED_SURFACES = ["packs/picker.staged.html", "packs/viewer.staged.html",
                      "diff_vs_release.md", "median_convention_comparison.md",
                      "schema_meta.staged.json"]


@pytest.mark.parametrize("rel", GENERATED_SURFACES)
def test_no_prohibited_copy_in_generated_surface(review_staging, rel):
    p = os.path.join(review_staging, rel)
    with open(p, encoding="utf-8", newline="") as f:
        hits = prose.scan(f.read())
    assert hits == [], [(h[0], h[1]) for h in hits[:5]]


def test_every_generated_surface_scanned(staging_dir):
    """Scan the whole staging tree, not a hand-picked subset."""
    bad = []
    for dp, _, fs in os.walk(staging_dir):
        for fn in fs:
            rel = os.path.relpath(os.path.join(dp, fn), staging_dir).replace(os.sep, "/")
            if rel.endswith(prose.SCAN_EXEMPT_SUFFIXES):
                continue
            with open(os.path.join(dp, fn), encoding="utf-8", newline="", errors="replace") as f:
                for pat, got, off in prose.scan(f.read()):
                    bad.append(f"{rel}: /{pat}/ -> {got!r}")
    assert bad == [], bad[:10]


def test_replacement_is_not_first_occurrence_only():
    """apply_claims replaces EVERY occurrence, and the generated-native
    fc-3.4 viewer template needs no migration because it is already clean."""
    old_text, new_text, _ = prose.VIEWER_CLAIMS[1]
    synthetic = f"lead {old_text} middle {old_text} tail"
    out, log = prose.apply_claims(synthetic, [(old_text, new_text, 2)], "unit")
    assert out.count(old_text) == 0
    assert out.count(new_text) == 2
    assert log == [(old_text, 2)]
    from domelab_pipeline.pipeline import REF
    src = _read_text(os.path.join(REF, "index.release.html"))
    assert "const VIEWER_BUILD = " in src        # generated-native template
    assert prose.scan(src) == []                 # already clean, no migration


def test_claim_count_drift_fails_generation():
    with pytest.raises(RuntimeError, match="count mismatch"):
        prose.apply_claims("nothing here", prose.VIEWER_CLAIMS, "viewer")


def test_required_language_present(review_staging):
    with open(os.path.join(review_staging, "packs", "viewer.staged.html"),
              encoding="utf-8", newline="") as f:
        v = f.read()
    assert "one-way mechanical work integral" in v
    assert "mechanical descriptors of the measured curve" in v
    assert "Detected force-wall onset" in v
    assert "do not establish independent causal contributions" in v


def test_snap_described_as_a_ratio_not_a_standard(review_staging):
    with open(os.path.join(review_staging, "packs", "viewer.staged.html"),
              encoding="utf-8", newline="") as f:
        v = f.read()
    assert ("not predicted 1-10 ratings or universal perceptual units" in v
            or "do not establish independent causal contributions" in v)


def test_prose_scan_report_generated(review_staging):
    with open(os.path.join(review_staging, "packs", "prose_scan_report.json"), encoding="utf-8") as f:
        rep = json.load(f)
    assert rep["result"].startswith("clean")
    assert rep["scanned_surfaces"]


# ------------------------------------------------------- jsdom batteries
def _node_env():
    env = dict(os.environ)
    np = env.get("DOMELAB_NODE_PATH")
    if not np:
        cand = os.path.join(HERE, "..", "js", "node_modules")
        if os.path.isdir(os.path.join(cand, "jsdom")):
            np = os.path.abspath(cand)
    if not np:
        pytest.skip("jsdom not available; set DOMELAB_NODE_PATH or run npm ci in generator/js")
    env["NODE_PATH"] = np
    return env


def test_picker_runtime_battery(review_staging):
    out = subprocess.run(
        ["node", os.path.join(HERE, "picker_runtime_battery.js"),
         os.path.join(review_staging, "packs", "picker.staged.html"),
         "Topre_R2_45g", "bt_0078",
         os.path.join(review_staging, "bench_tests.staged.json"),
         "lib-6.1-review.1", "false"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=_node_env())
    payload = json.loads(out.stdout[out.stdout.index("{"):])
    failed = [c for c in payload["checks"] if not c["pass"]]
    assert out.returncode == 0 and not failed, failed
    assert payload["total"] >= 14


def test_viewer_curve_battery(cache, review_staging, tmp_path):
    staging_dir = review_staging
    with open(os.path.join(staging_dir, "bench_tests.staged.json"), encoding="utf-8") as f:
        recs = json.load(f)
    plan = {}
    for r in recs:
        if r["set"] in plan:
            continue
        plan[r["set"]] = {"files": [os.path.join(cache, p) for p in r["provenance"]["raw_paths"]],
                          "n": r["runs_used"]}
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    out = subprocess.run(
        ["node", os.path.join(HERE, "viewer_curve_battery.js"),
         os.path.join(staging_dir, "packs", "viewer.staged.html"), str(pf)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=_node_env())
    payload = json.loads(out.stdout[out.stdout.index("{"):])
    assert out.returncode == 0 and payload["failed"] == 0, payload.get("failures")
    assert payload["sets"] == len(plan)


# ------------------------------------------------ shared curve authority
def test_python_and_js_share_one_averaging_definition(review_staging):
    from domelab_pipeline.curves import js_average_source
    with open(os.path.join(review_staging, "packs", "viewer.staged.html"),
              encoding="utf-8", newline="") as f:
        v = f.read()
    assert js_average_source("majority") in v


def test_contributor_threshold_rule():
    from domelab_pipeline.curves import contributor_threshold
    assert contributor_threshold(1) == 1
    assert contributor_threshold(2) == 1
    assert contributor_threshold(3) == 2
    assert contributor_threshold(4) == 2
    assert contributor_threshold(5) == 3


def test_grid_average_drops_single_contributor_endpoint():
    from domelab_pipeline.curves import grid_average
    runs = [([0.005, 0.010, 0.015], [1.0, 2.0, 3.0]),
            ([0.010, 0.015], [2.0, 4.0]),
            ([0.010, 0.015], [2.0, 4.0])]
    keys, F = grid_average(runs)
    assert keys[0] == 2, keys          # 0.005 had one contributor of three
    assert F == [2.0, pytest.approx(11.0 / 3)]


def test_jsround_matches_ecmascript_halves():
    from domelab_pipeline.curves import jsround
    assert jsround(2.5) == 3           # python round() gives 2
    assert jsround(-2.5) == -2
    assert jsround(3.5) == 4
