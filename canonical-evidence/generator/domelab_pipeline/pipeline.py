"""Orchestration: pinned raw cache -> per-run metrics -> intake-qc-v1.4
-> hash-bound set/run decisions -> staged records and derived artifacts.
The generator is the only writer of derived artifacts; generated output is never
hand-patched. Serialized paths are always POSIX. Writes are atomic (temp+replace)
and validated before writing. STEP 2.x stages only; release artifacts untouched.

Legacy QC/runfilter results are diagnostic-only whenever the decision manifest
role applies intake membership (review_candidate or canonical authority).
"""
import os, re, json, hashlib, csv, io, statistics
from pathlib import PurePosixPath, Path
from . import __version__
from .core import (parse_run, split_press_return, run_metrics, config, config_hash,
                   DIVERGENCES, PER_RUN_AUDIT_FIELDS, validate_per_run_algebra)
from .qc import acquisition_qc, qc_disposition
from .medians import median_conventional, median_upper_middle_legacy
from . import registries, prose, intake_policy

def uread(p):
    """Explicit UTF-8 text read with deterministic newlines (never locale-dependent)."""
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()

def ujson(p):
    return json.loads(uread(p))

METRICS = ["collapse_force_gf", "collapse_travel_mm", "valley_force_gf", "valley_travel_mm", "snap_pct",
           "travel_mm", "full_stroke_press_work_gf_mm", "precollapse_work_gf_mm", "drop_gf", "drop_travel_mm",
           "drop_rate_gf_per_mm", "norm_drop_rate_per_mm", "steepest_drop_0p10mm_gf_per_mm", "ramp_10_90_gf_per_mm"]
PKGDIR = os.path.dirname(__file__)
REF = os.path.join(PKGDIR, "release_reference")
INTAKE_POLICY = ujson(os.path.join(PKGDIR, "config", "intake_policy.json"))
RAMP_REVIEW_FIELDS = (
    "ramp_gf_per_mm",
    "retained_median_gf_per_mm",
    "signed_deviation_pct",
    "absolute_deviation_pct",
    "threshold_pct",
)


def _ramp_review_evidence(run_decision):
    """Validate the decision boundary and return its advisory evidence.

    This deliberately performs no policy calculation.  It only fail-closes on
    a malformed core decision before that decision is copied to public records,
    reports, or the review viewer.
    """
    required = run_decision.get("ramp_review_required")
    review = run_decision.get("ramp_review")
    if type(required) is not bool:
        raise RuntimeError("intake run decision lacks boolean ramp_review_required")
    if required != (review is not None):
        raise RuntimeError(
            "intake run decision has inconsistent ramp_review_required/ramp_review"
        )
    if not required:
        return None
    if not isinstance(review, dict) or set(review) != set(RAMP_REVIEW_FIELDS):
        raise RuntimeError("intake run decision has malformed ramp_review evidence")
    return {field: review[field] for field in RAMP_REVIEW_FIELDS}

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def read_bytes(p):
    with open(p, "rb") as f:
        return f.read()


def sha256_file(p): return sha256_bytes(read_bytes(p))
def dumps(obj): return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
def posix(p): return PurePosixPath(Path(p)).as_posix()

def load_config_bundle(require_retained_decisions=True):
    C = lambda n: ujson(os.path.join(PKGDIR, "config", n))
    decision_path = os.path.join(PKGDIR, "config", "retained_run_decisions.json")
    if require_retained_decisions and not os.path.isfile(decision_path):
        raise RuntimeError("missing checked-in config/retained_run_decisions.json")
    return {"method_config": config(),
            "intake_policy": C("intake_policy.json"),
            "retained_run_decisions": (ujson(decision_path) if os.path.isfile(decision_path) else None),
            "exclusions": C("exclusions.json"),
            "dataset_manifest": C("dataset_manifest.json"),
            "metadata_registry": C("dome_metadata_registry.json"),
            "evidence_history": C("evidence_history.json"),
            "adjudications": C("adjudications.json"),
            "review_register": C("review_register.json")}

def generator_source_identity():
    out = {}
    for fn in sorted(os.listdir(PKGDIR)):
        if fn.endswith(".py"):
            out[fn] = sha256_file(os.path.join(PKGDIR, fn))
    return out

def cache_manifest(cache_root):
    out = {}
    for dp, _, fs in os.walk(cache_root):
        for fn in sorted(fs):
            p = os.path.join(dp, fn)
            out[posix(os.path.relpath(p, cache_root))] = sha256_file(p)
    return out

def release_reference_identity():
    out = {}
    for fn in sorted(os.listdir(REF)):
        out[fn] = sha256_file(os.path.join(REF, fn))
    return out

def _h(obj):
    return sha256_bytes(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())

def provenance_hashes(bundle, cache_man):
    """Distinguish scientific-epoch identity from implementation/presentation.

    ``evidence_epoch_hash`` deliberately excludes generator source and release
    reference HTML.  A later Step-3 viewer change therefore cannot masquerade
    as a change to the frozen evidence epoch.
    """
    raw_csv_manifest = {
        path: digest for path, digest in cache_man.items()
        if re.search(r"DataLog.*\.csv$", path.rsplit("/", 1)[-1], re.I)
    }
    h = {"method_hash": _h({"method_config": bundle["method_config"],
                             "intake_policy": bundle["intake_policy"]}),
         "dataset_decision_hash": _h({"dataset_manifest": bundle["dataset_manifest"],
                                      "exclusions": bundle["exclusions"],
                                      "adjudications": bundle["adjudications"],
                                      "review_register": bundle["review_register"],
                                      "retained_run_decisions": bundle["retained_run_decisions"]}),
         "metadata_authority_hash": _h(bundle["metadata_registry"]),
         "evidence_history_hash": _h(bundle["evidence_history"]),
         "generator_source_hash": _h(generator_source_identity()),
         "release_reference_hash": _h(release_reference_identity()),
         "raw_manifest_hash": _h(cache_man),
         "raw_csv_manifest_hash": _h(raw_csv_manifest)}
    h["evidence_epoch_hash"] = _h({k: h[k] for k in (
        "method_hash", "dataset_decision_hash", "metadata_authority_hash",
        "evidence_history_hash", "raw_csv_manifest_hash")})
    h["bundle_hash"] = _h(h)
    return h

def bundle_hash(bundle, cache_man):
    return provenance_hashes(bundle, cache_man)["bundle_hash"]

def pinned_inventory_rows():
    """Complete pinned Git-tree inventory keyed by normalized POSIX path."""
    with open(os.path.join(REF, "repository_file_inventory.csv"), encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    paths = [row.get("path") for row in rows]
    duplicates = sorted({path for path in paths if paths.count(path) > 1})
    if duplicates:
        raise RuntimeError(f"pinned inventory contains duplicate paths: {duplicates}")
    return {row["path"]: row for row in rows}


def pinned_inventory():
    return {path: row["sha256"] for path, row in pinned_inventory_rows().items()}


def git_blob_oid(data, object_format="sha1"):
    if object_format != "sha1":
        raise RuntimeError(f"unsupported Git object format {object_format!r}")
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def verify_inputs(cache_root, commit, bundle, cache_man):
    """Commit and cache are verified against the pinned inventory, not trusted.

    Step 2.3: verification is SYMMETRIC. Step 2.2 iterated only over files
    present on disk, so a cache holding 73 of the pinned 141 files verified
    clean while the documentation claimed "141 files, byte-verified". Missing
    files, unexpected files, hash mismatches and path mismatches are now all
    errors, and the exact expected file count is asserted.
    """
    prov = ujson(os.path.join(REF, "repo_provenance.json"))
    if commit != prov["sha"]:
        raise RuntimeError(f"commit {commit} does not match pinned provenance {prov['sha']}")
    inv_rows = pinned_inventory_rows()
    inv = {path: row["sha256"] for path, row in inv_rows.items()}
    errs = []

    inventory_path = os.path.join(REF, "repository_file_inventory.csv")
    if prov.get("repository_file_inventory_sha256") != sha256_file(inventory_path):
        errs.append("repo provenance inventory SHA-256 does not bind repository_file_inventory.csv")
    if prov.get("git_object_format") != "sha1":
        errs.append("repo provenance git_object_format must be sha1 for this frozen epoch")
    if prov.get("tracked_files") != len(inv_rows):
        errs.append(
            f"repo provenance tracked_files {prov.get('tracked_files')!r} != inventory {len(inv_rows)}"
        )
    raw_inventory_rows = {
        path: row for path, row in inv_rows.items()
        if row.get("category") == "raw_csv"
    }
    if prov.get("csvs") != len(raw_inventory_rows):
        errs.append(f"repo provenance csvs {prov.get('csvs')!r} != inventory {len(raw_inventory_rows)}")
    row_object_formats = {row.get("git_object_format") for row in inv_rows.values()}
    if row_object_formats != {prov.get("git_object_format")}:
        errs.append(
            "inventory Git object formats do not exactly match repo provenance: "
            f"{sorted(str(value) for value in row_object_formats)}"
        )

    missing = sorted(set(inv) - set(cache_man))
    unexpected = sorted(set(cache_man) - set(inv))
    for p in missing:
        errs.append(f"pinned cache file MISSING: {p}")
    for p in unexpected:
        errs.append(f"cache file not in pinned inventory: {p}")
    for p in sorted(set(inv) & set(cache_man)):
        if inv[p] != cache_man[p]:
            errs.append(f"hash mismatch vs pinned inventory: {p}")
            continue
        row = inv_rows[p]
        data = read_bytes(os.path.join(cache_root, *PurePosixPath(p).parts))
        if row.get("bytes") not in (None, "") and int(row["bytes"]) != len(data):
            errs.append(f"byte length mismatch vs pinned inventory: {p}")
        declared_oid = row.get("git_blob_oid") or row.get("git_blob")
        object_format = row.get("git_object_format") or row.get("object_format") or "sha1"
        if declared_oid and git_blob_oid(data, object_format) != declared_oid:
            errs.append(f"Git blob OID mismatch vs pinned inventory: {p}")
    if len(cache_man) != len(inv):
        errs.append(f"pinned cache file count {len(cache_man)} != expected {len(inv)}")

    dm = bundle["dataset_manifest"]
    if dm.get("repo_commit") != commit:
        raise RuntimeError("dataset_manifest.repo_commit does not match the verified commit")
    for registry_name in ("exclusions", "review_register"):
        if bundle[registry_name].get("repo_commit") != commit:
            errs.append(
                f"{registry_name}.repo_commit does not match the verified commit"
            )
    tests = dm.get("tests", [])
    test_ids = [test.get("test_id") for test in tests]
    test_sets = [test.get("set") for test in tests]
    duplicate_test_ids = sorted({value for value in test_ids if test_ids.count(value) > 1})
    duplicate_sets = sorted({value for value in test_sets if test_sets.count(value) > 1})
    if duplicate_test_ids:
        errs.append(f"dataset manifest duplicate test_id values: {duplicate_test_ids}")
    if duplicate_sets:
        errs.append(f"dataset manifest duplicate set values: {duplicate_sets}")
    man_sets = set(test_sets)
    cache_sets = {p.split("/")[0] for p in cache_man if re.search(r"DataLog.*\.csv$", p.split("/")[-1], re.I)}
    for s in sorted(cache_sets - man_sets):
        errs.append(f"raw set on disk lacks manifest metadata: {s}")
    for s in sorted(man_sets - cache_sets):
        errs.append(f"manifest names a set absent from the cache: {s}")
    all_manifest_paths = []
    for t in tests:
        for r in t["expected_runs"]:
            all_manifest_paths.append(r["path"])
            if cache_man.get(r["path"]) != r["sha256"]:
                errs.append(f"manifest run hash mismatch: {r['path']}")
            inv_row = inv_rows.get(r["path"], {})
            declared_oid = inv_row.get("git_blob_oid") or inv_row.get("git_blob")
            if r.get("git_blob_oid") != declared_oid:
                errs.append(f"manifest Git blob OID mismatch: {r['path']}")
            if inv_row.get("bytes") not in (None, "") and r.get("bytes") != int(inv_row["bytes"]):
                errs.append(f"manifest byte length mismatch: {r['path']}")
            if not re.fullmatch(r"acq_sha256:[0-9a-f]{64}", str(r.get("acquisition_id", ""))):
                errs.append(f"manifest acquisition_id invalid: {r['path']}")
            elif r["acquisition_id"] != "acq_sha256:" + r["sha256"]:
                errs.append(f"manifest acquisition_id is not bound to SHA-256: {r['path']}")
    errs += registries.require_normalized(all_manifest_paths, "dataset manifest")

    # ---- exclusion registry bindings (Step 2.3: load-bearing) ----
    errs += registries.verify_exclusion_registry(bundle["exclusions"], dm, cache_man, inv)
    # ---- Step 2.3.1: exactly one authority for exclusion, and every raw run
    #      bound to the set that declares it.
    errs += registries.verify_exclusion_bijection(bundle["exclusions"], dm)
    errs += registries.verify_run_set_binding(dm)
    errs += registries.verify_manifest_raw_coverage(dm, inv)

    raw_rows = {
        path: row for path, row in inv_rows.items()
        if (row.get("category") == "raw_csv" or
            re.search(r"DataLog.*\.csv$", path.rsplit("/", 1)[-1], re.I))
    }
    by_oid = {}
    for path, row in raw_rows.items():
        oid = row.get("git_blob_oid") or row.get("git_blob")
        by_oid.setdefault(oid, []).append(path)
    acquisition_by_path = {
        run["path"]: run.get("acquisition_id")
        for test in dm.get("tests", []) for run in test.get("expected_runs", [])
    }
    acquisition_to_oid = {}
    for oid, paths in by_oid.items():
        ids = {acquisition_by_path.get(path) for path in paths}
        if len(ids) != 1 or None in ids:
            errs.append(f"one Git blob maps to inconsistent acquisition IDs: {sorted(paths)}")
            continue
        acquisition_id = next(iter(ids))
        prior_oid = acquisition_to_oid.setdefault(acquisition_id, oid)
        if prior_oid != oid:
            errs.append(f"acquisition ID {acquisition_id!r} maps to multiple Git blobs")
    measurement_cohorts = {
        test.get("measurement_cohort_id", test.get("set")) for test in tests
    }
    workbook_record_count = sum(
        test.get("metadata", {}).get("metadata_source") == "authoritative_workbook"
        for test in tests
    )
    legacy_record_count = sum(
        test.get("metadata", {}).get("metadata_source") == "predecessor_manifest"
        for test in tests
    )
    historical_pruned_count = sum(
        len(event.get("exclusions", []))
        for event in bundle["evidence_history"].get("events", [])
    )
    computed_counts = {
        "semantic_records": len(tests),
        "independent_measurement_cohorts": len(measurement_cohorts),
        "tracked_raw_paths": len(all_manifest_paths),
        "unique_acquisitions": len(acquisition_to_oid),
        "workbook_authoritative_records": workbook_record_count,
        "legacy_lineage_only_records": legacy_record_count,
        "historically_pruned_runs": historical_pruned_count,
    }
    if dm.get("counts") != computed_counts:
        errs.append(
            f"dataset manifest counts do not match computed evidence: "
            f"declared {dm.get('counts')!r} vs computed {computed_counts!r}"
        )
    for field, computed in (
        ("semantic_sets", len(man_sets)),
        ("independent_measurement_cohorts", len(measurement_cohorts)),
        ("unique_raw_blobs", len(by_oid)),
    ):
        if prov.get(field) != computed:
            errs.append(f"repo provenance {field} {prov.get(field)!r} != computed {computed}")
    actual_duplicate_groups = {
        tuple(sorted(paths)) for paths in by_oid.values() if len(paths) > 1
    }
    declared_duplicate_groups = set()
    tests_by_id = {test["test_id"]: test for test in dm.get("tests", [])}
    specs_by_path = {
        run["path"]: (test, run)
        for test in dm.get("tests", []) for run in test.get("expected_runs", [])
    }
    seen_alias_ids = set()
    for alias in dm.get("evidence_aliases", []):
        group_id = alias.get("group_id")
        if not group_id or group_id in seen_alias_ids:
            errs.append(f"evidence alias has missing/duplicate group_id {group_id!r}")
        seen_alias_ids.add(group_id)
        alias_test_ids = set(alias.get("semantic_test_ids", []))
        if len(alias_test_ids) != 2 or any(test_id not in tests_by_id for test_id in alias_test_ids):
            errs.append(f"evidence alias {group_id!r}: semantic_test_ids invalid")
        measurement_cohort_id = alias.get("measurement_cohort_id")
        alias_roles = set()
        for test_id in alias_test_ids:
            test = tests_by_id.get(test_id, {})
            if test.get("measurement_cohort_id") != measurement_cohort_id:
                errs.append(f"evidence alias {group_id!r}: measurement-cohort binding mismatch")
            metadata = test.get("metadata", {})
            if metadata.get("evidence_alias_group") != group_id:
                errs.append(f"evidence alias {group_id!r}: record metadata group mismatch")
            if not metadata.get("evidence_alias_role"):
                errs.append(f"evidence alias {group_id!r}: semantic alias role is missing")
            else:
                alias_roles.add(metadata["evidence_alias_role"])
            expected_role = {
                "dome_baseline": "dome_semantic",
                "part_assembly": "part_assembly_semantic",
            }.get(test.get("metadata", {}).get("kind"))
            if expected_role and metadata.get("evidence_alias_role") != expected_role:
                errs.append(f"evidence alias {group_id!r}: role does not match semantic kind")
        if len(alias_roles) != len(alias_test_ids):
            errs.append(f"evidence alias {group_id!r}: semantic alias roles must be distinct")
        for pair in alias.get("run_pairs", []):
            members = tuple(sorted(member["path"] for member in pair.get("members", [])))
            if len(members) != 2:
                errs.append(f"evidence alias {alias.get('group_id')!r}: run pair must have two members")
                continue
            if members in declared_duplicate_groups:
                errs.append(f"evidence alias {group_id!r}: duplicate run-pair declaration {members}")
            declared_duplicate_groups.add(members)
            rows2 = [raw_rows.get(path) for path in members]
            if any(row is None for row in rows2):
                errs.append(f"evidence alias {alias.get('group_id')!r}: member absent from raw inventory")
            elif len({(row.get('git_blob_oid') or row.get('git_blob')) for row in rows2}) != 1:
                errs.append(f"evidence alias {alias.get('group_id')!r}: members are not one Git blob")
            if pair.get("independent_observation_count") != 1:
                errs.append(f"evidence alias {group_id!r}: each pair must count as one observation")
            pair_ids = set()
            pair_sha = set()
            for member in pair.get("members", []):
                bound = specs_by_path.get(member.get("path"))
                if bound is None:
                    continue
                test, spec = bound
                pair_ids.add(test["test_id"])
                pair_sha.add(spec["sha256"])
                for field, expected in (
                    ("test_id", test["test_id"]), ("set", test["set"]),
                    ("sha256", spec["sha256"]), ("git_blob_oid", spec["git_blob_oid"]),
                ):
                    if member.get(field) != expected:
                        errs.append(f"evidence alias {group_id!r}: member {field} binding mismatch")
                if spec.get("path_role") != "shared_alias":
                    errs.append(f"evidence alias {group_id!r}: run path is not marked shared_alias")
                if pair.get("acquisition_id") != spec.get("acquisition_id"):
                    errs.append(f"evidence alias {group_id!r}: pair acquisition binding mismatch")
            if pair_ids != alias_test_ids or len(pair_sha) != 1:
                errs.append(f"evidence alias {group_id!r}: run pair semantic/hash membership mismatch")
    if actual_duplicate_groups != declared_duplicate_groups:
        errs.append(
            "raw duplicate/alias declaration mismatch: actual "
            f"{sorted(actual_duplicate_groups)} vs declared {sorted(declared_duplicate_groups)}"
        )

    cohort_to_test_ids = {}
    for test in tests:
        cohort_to_test_ids.setdefault(test.get("measurement_cohort_id"), set()).add(test.get("test_id"))
    declared_shared_cohorts = {
        alias.get("measurement_cohort_id"): set(alias.get("semantic_test_ids", []))
        for alias in dm.get("evidence_aliases", [])
    }
    for cohort_id, cohort_test_ids in cohort_to_test_ids.items():
        if len(cohort_test_ids) > 1 and declared_shared_cohorts.get(cohort_id) != cohort_test_ids:
            errs.append(
                f"measurement cohort {cohort_id!r} is shared outside its exact alias declaration"
            )
    for cohort_id, alias_test_ids in declared_shared_cohorts.items():
        if cohort_to_test_ids.get(cohort_id) != alias_test_ids:
            errs.append(f"declared alias cohort {cohort_id!r} has unexpected semantic members")

    group_summaries = {group.get("group_id"): group for group in dm.get("shared_evidence_groups", [])}
    if set(group_summaries) != seen_alias_ids:
        errs.append("shared_evidence_groups do not exactly match evidence_aliases")
    for alias in dm.get("evidence_aliases", []):
        group_id = alias.get("group_id")
        summary = group_summaries.get(group_id, {})
        alias_test_ids = set(alias.get("semantic_test_ids", []))
        alias_sets = {tests_by_id[test_id]["set"] for test_id in alias_test_ids if test_id in tests_by_id}
        alias_acquisitions = {pair.get("acquisition_id") for pair in alias.get("run_pairs", [])}
        if set(summary.get("semantic_test_ids", [])) != alias_test_ids:
            errs.append(f"shared evidence summary {group_id!r}: semantic test IDs mismatch")
        if set(summary.get("sets", [])) != alias_sets:
            errs.append(f"shared evidence summary {group_id!r}: set membership mismatch")
        if set(summary.get("unique_acquisition_ids", [])) != alias_acquisitions:
            errs.append(f"shared evidence summary {group_id!r}: acquisition membership mismatch")
        if summary.get("unique_acquisition_count") != len(alias_acquisitions):
            errs.append(f"shared evidence summary {group_id!r}: unique acquisition count mismatch")
        if summary.get("raw_path_count") != 2 * len(alias.get("run_pairs", [])):
            errs.append(f"shared evidence summary {group_id!r}: raw path count mismatch")
        if set(summary.get("interpretations", {})) != alias_sets:
            errs.append(f"shared evidence summary {group_id!r}: semantic interpretations mismatch")

    meta = bundle["metadata_registry"]
    columns = ["display_name", "manufacturer", "brand", "style", "variant",
               "nominal_weight_g", "tested"]
    rows = meta.get("rows", [])
    workbook_source = meta.get("source_workbook", {})
    manifest_workbook_source = dm.get("metadata_source", {})
    for registry_field, manifest_field in (
        ("file_name", "file_name"), ("sha256", "sha256"),
        ("bytes", "size_bytes"), ("sheet", "sheet"), ("used_range", "used_range"),
        ("artifact_tool_snapshot_sha256", "artifact_tool_snapshot_sha256"),
    ):
        if workbook_source.get(registry_field) != manifest_workbook_source.get(manifest_field):
            errs.append(
                f"metadata workbook source binding mismatch for {registry_field}/{manifest_field}"
            )
    if meta.get("columns") != columns:
        errs.append("metadata registry columns do not match the authoritative workbook contract")
    if len(rows) != 79:
        errs.append(f"metadata registry has {len(rows)} rows, expected 79")
    row_by_name = {}
    for row in rows:
        name = row.get("display_name")
        if name in row_by_name:
            errs.append(f"metadata registry duplicate display_name {name!r}")
        row_by_name[name] = row
    aliases = meta.get("set_name_aliases", {})
    yes_sets = {
        aliases.get(row["display_name"], row["display_name"])
        for row in rows if row.get("tested") == "YES"
    }
    no_sets = {
        aliases.get(row["display_name"], row["display_name"])
        for row in rows if row.get("tested") == "NO"
    }
    manifest_sets = {test["set"] for test in dm.get("tests", [])}
    if yes_sets - manifest_sets:
        errs.append(f"tested YES metadata rows lack raw cohorts: {sorted(yes_sets - manifest_sets)}")
    if no_sets & manifest_sets:
        errs.append(f"tested NO metadata rows entered the evidence epoch: {sorted(no_sets & manifest_sets)}")
    declared_legacy = set(meta.get("legacy_metadata_sets", []))
    if manifest_sets - yes_sets != declared_legacy:
        errs.append(
            "metadata legacy-set coverage mismatch: actual "
            f"{sorted(manifest_sets - yes_sets)} vs declared {sorted(declared_legacy)}"
        )
    reverse_aliases = {mapped: name for name, mapped in aliases.items()}
    for test in dm.get("tests", []):
        md = test.get("metadata", {})
        if test["set"] in yes_sets:
            source_name = reverse_aliases.get(test["set"], test["set"])
            row = row_by_name.get(source_name)
            if row is None:
                errs.append(f"manifest [{test['set']}]: authoritative metadata row not found")
                continue
            for field in columns[:-1]:
                if md.get(field) != row.get(field):
                    errs.append(
                        f"manifest [{test['set']}]: {field} does not exactly match workbook row"
                    )
            if md.get("tested") is not True:
                errs.append(f"manifest [{test['set']}]: tested must normalize YES to true")
            if md.get("metadata_source") != "authoritative_workbook":
                errs.append(f"manifest [{test['set']}]: spreadsheet metadata is not authoritative")
            if md.get("metadata_source_locator") != row.get("locator"):
                errs.append(f"manifest [{test['set']}]: workbook row locator is not exact")
            if md.get("metadata_override_applied") is not True:
                errs.append(f"manifest [{test['set']}]: workbook override must be explicit")
            mdp = test.get("metadata_provenance", {})
            if (mdp.get("catalog_source") != workbook_source.get("file_name") or
                    mdp.get("catalog_source_sha256") != workbook_source.get("sha256") or
                    mdp.get("sheet") != workbook_source.get("sheet") or
                    mdp.get("row") != row.get("row_number")):
                errs.append(f"manifest [{test['set']}]: workbook provenance binding mismatch")
        else:
            if md.get("metadata_source") != "predecessor_manifest":
                errs.append(f"manifest [{test['set']}]: legacy metadata source is not explicit")
            if md.get("tested") is not None:
                errs.append(f"manifest [{test['set']}]: unavailable legacy tested field must be null")
            if md.get("metadata_override_applied") is not False:
                errs.append(f"manifest [{test['set']}]: legacy metadata must not claim workbook override")
            mdp = test.get("metadata_provenance", {})
            expected_locator = f"dataset_manifest.json#tests[test_id={mdp.get('legacy_test_id')}].metadata"
            if md.get("metadata_source_locator") != expected_locator:
                errs.append(f"manifest [{test['set']}]: predecessor metadata locator mismatch")
            if mdp.get("legacy_manifest_source_sha256") != dm.get("legacy_metadata_source", {}).get("sha256"):
                errs.append(f"manifest [{test['set']}]: predecessor source hash mismatch")
            if mdp.get("authoritative_fields") != []:
                errs.append(f"manifest [{test['set']}]: unavailable legacy fields cannot be authoritative")
            if "tested" not in mdp.get("catalog_fields_unavailable", []):
                errs.append(f"manifest [{test['set']}]: unavailable tested field is not declared")

    if errs:
        raise RuntimeError("input verification failed:\n  " + "\n  ".join(errs))
    raw_count = sum(1 for p in inv
                    if re.search(r"DataLog.*\.csv$", p.rsplit("/", 1)[-1], re.I))
    return {"pinned_files": len(inv), "verified_files": len(cache_man),
            "verified_raw_runs": raw_count, "unique_raw_blobs": len(by_oid),
            "semantic_sets": len(manifest_sets),
            "independent_measurement_cohorts": len({
                test.get("measurement_cohort_id", test["set"]) for test in dm["tests"]
            })}


def process_run(path, commit, rel_path=None):
    raw = read_bytes(path)
    run = parse_run(raw.decode("utf-8-sig", "replace"))
    (px, pF), _, im = split_press_return(run["x"], run["F"])
    q = acquisition_qc(run, im)
    disp, disp_flags = qc_disposition(q)
    m, flags, audit = run_metrics(px, pF, grid_conforming=q["grid_conforming"], return_audit=True)
    validate_per_run_algebra(m, audit, flags)
    if not q["millis_strictly_increasing"]: flags.append("timestamp_nonmonotonic")
    if q["phase_reversals_press"] or q["phase_reversals_return"]: flags.append("displacement_nonmonotonic")
    if q["loadcell_saturation"]: flags.append("loadcell_saturation")
    if q["incomplete_press"]: flags.append("incomplete_press")
    result = {"path": path, "rel_path": posix(rel_path) if rel_path else posix(os.path.basename(path)),
            "sha256": sha256_bytes(raw), "commit": commit, "metrics": m,
            "quality_flags": sorted(set(flags)), "metric_audit": audit, "qc": q,
            "qc_disposition": disp, "qc_disposition_flags": disp_flags,
            "split_index": im, "press_rows": im + 1}
    result["intake_qc"] = intake_policy.evaluate_run(
        run, m, result["quality_flags"], im, INTAKE_POLICY
    )
    return result

def run_binding(sname, r):
    """The identity an adjudication must bind to, derived from the run itself."""
    BARRIER = set(config()["canonical_eligibility"]["barrier_flags"])
    return {"sha256": r["sha256"],
            "raw_path": r.get("rel_path"),
            "qc_disposition": r["qc_disposition"],
            "qc_reasons": sorted(set(r["qc_disposition_flags"])),
            "barrier_flags": sorted(BARRIER & set(r["quality_flags"]))}


def canonical_eligibility(sname, r, adjud):
    """(eligible, decision-string, adjudication-or-None).

    pass / pass_with_offset_note are canonically eligible. review and
    quarantine_retest runs, and runs carrying a barrier flag, enter canonical
    aggregates only through a version-controlled adjudication whose complete
    binding has already been verified by registries.verify_adjudications.
    fail_exclude is never overridable.
    """
    b = run_binding(sname, r)
    key = (sname, posix(os.path.basename(r["path"])))
    a = adjud.get(key)
    if r["qc_disposition"] == "fail_exclude":
        if a is not None:
            raise RuntimeError(f"adjudication {key} attempts to override fail_exclude")
        return False, "ineligible: fail_exclude (not overridable)", None
    barred = b["barrier_flags"]
    if r["qc_disposition"] in ("review", "quarantine_retest") or barred:
        if a and a.get("eligible"):
            return True, f"eligible via adjudication ({a['authority']} {a['date']})", a
        why = r["qc_disposition"] if r["qc_disposition"] in ("review", "quarantine_retest") else "barrier flags"
        return (False,
                f"ineligible: {why} without adjudication" + (f" [{';'.join(barred)}]" if barred else ""),
                None)
    return True, "eligible: " + r["qc_disposition"], None


def _explicit_intake_upstream(bundle, runs_by_set, adjudications):
    """Return only owner-authored pre-intake blocks/adjudications.

    Legacy ``qc_disposition`` remains diagnostic once intake-qc-v1.4 is active;
    it cannot silently veto a run accepted by the new acquisition authority.
    Registry exclusions are set-level and are applied separately. Exact
    review-register blocks remain load-bearing. QC-bound legacy adjudications
    can appear only in development-preview mode; applied intake roles require
    that registry to be empty.
    """
    run_index = {
        (set_name, run["rel_path"]): run
        for set_name, runs in runs_by_set.items()
        for run in runs
    }
    review_blocks = {}
    for entry in bundle["review_register"].get("entries", []):
        key = (entry.get("set"), entry.get("raw_path"))
        if key in review_blocks:
            raise RuntimeError(f"duplicate review-register intake block: {key}")
        if type(entry.get("canonically_eligible")) is not bool or entry["canonically_eligible"]:
            raise RuntimeError(
                f"review-register intake block must declare canonically_eligible=false: {key}"
            )
        run = run_index.get(key)
        if run is None:
            raise RuntimeError(f"review-register intake block does not bind a manifest run: {key}")
        if entry.get("sha256") != run["sha256"]:
            raise RuntimeError(f"review-register intake block hash mismatch: {key}")
        review_blocks[key] = entry

    result = {}
    for set_name, runs in runs_by_set.items():
        for run in runs:
            raw_path = run["rel_path"]
            run_name = posix(os.path.basename(run["path"]))
            key = (set_name, raw_path)
            adjudication = adjudications.get((set_name, run_name))
            if key in review_blocks and adjudication is not None:
                raise RuntimeError(
                    f"run is simultaneously review-blocked and adjudicated; resolve one authority: {key}"
                )
            if key in review_blocks:
                block = review_blocks[key]
                result[(set_name, run_name)] = (
                    False,
                    "ineligible: exact owner review-register block — "
                    f"{block.get('classification', 'retest_required')} "
                    f"({block.get('owner_decision_date', 'date not recorded')}); "
                    "canonically ineligible, no adjudication",
                )
            elif adjudication is not None:
                allowed = bool(adjudication.get("eligible"))
                result[(set_name, run_name)] = (
                    allowed,
                    (
                        f"eligible for intake via verified owner adjudication "
                        f"({adjudication['authority']} {adjudication['date']})"
                        if allowed
                        else "ineligible via verified owner adjudication"
                    ),
                )
            else:
                result[(set_name, run_name)] = (
                    True,
                    f"eligible for {bundle['intake_policy']['policy_version']}; "
                    "legacy QC disposition is diagnostic only",
                )
    return result


def _legacy_adjudications_for_role(bundle, run_index, method_hash, artifact_role):
    """Verify/use QC-bound adjudications only in development-preview mode.

    The legacy schema binds old ``qc_disposition``/reason/barrier values.  It
    cannot safely express an intake-qc-v1.4 owner decision.  Applied
    review/canonical roles therefore require the registry to be empty; a future
    intake-native admission schema requires separate review and versioning.
    """
    if artifact_role in (intake_policy.REVIEW_ROLE, intake_policy.CANONICAL_ROLE):
        if bundle["adjudications"].get("entries"):
            raise RuntimeError(
                "legacy config/adjudications.json must be empty under "
                f"{bundle['intake_policy']['policy_version']} "
                "review/canonical authority; its semantics are bound to obsolete QC"
            )
        return {}
    adjudications, errors = registries.verify_adjudications(
        bundle["adjudications"], run_index, method_hash
    )
    if errors:
        raise RuntimeError(
            "adjudication verification failed:\n  " + "\n  ".join(errors)
        )
    return adjudications


def _build_intake_manifest(bundle, commit, runs_by_set, upstream, artifact_role):
    registry_sets = {entry["set"] for entry in bundle["exclusions"]["entries"]}
    manifest_included = {}
    for test in bundle["dataset_manifest"]["tests"]:
        manifest_included.setdefault(test["set"], True)
        manifest_included[test["set"]] = (
            manifest_included[test["set"]] and test["disposition"] == "include"
        )
    set_decisions = [
        intake_policy.evaluate_cohort(
            set_name,
            runs_by_set[set_name],
            upstream,
            bundle["intake_policy"],
            excluded_by_registry=set_name in registry_sets,
            excluded_by_manifest=not manifest_included.get(set_name, False),
        )
        for set_name in sorted(runs_by_set)
    ]
    result = intake_policy.build_decision_manifest(
        artifact_role=artifact_role,
        repo_commit=commit,
        dataset_manifest=bundle["dataset_manifest"],
        metrics_method_config=bundle["method_config"],
        exclusions=bundle["exclusions"],
        adjudications=bundle["adjudications"],
        review_register=bundle["review_register"],
        policy=bundle["intake_policy"],
        sets=set_decisions,
    )
    run_specs = {
        run["path"]: run
        for test in bundle["dataset_manifest"]["tests"]
        for run in test["expected_runs"]
    }
    for set_entry in result["sets"]:
        for run in set_entry["runs"]:
            spec = run_specs[run["raw_path"]]
            run["git_blob_oid"] = spec["git_blob_oid"]
            run["acquisition_id"] = spec["acquisition_id"]
            run["raw_bytes"] = spec["bytes"]
    result["raw_evidence_summary"] = {
        "path_count": len(run_specs),
        "unique_acquisition_count": len({
            spec["acquisition_id"] for spec in run_specs.values()
        }),
        "git_object_format": "sha1",
    }
    return result


def compute_intake_decision_manifest(cache_root, commit, artifact_role=intake_policy.PREVIEW_ROLE):
    """Deterministically evaluate any pinned cache into a reviewable manifest.

    This is the mechanical final-fleet refresh interface used by
    ``python -m domelab_pipeline.intake_cli``.  It intentionally does not
    consult the currently declared decision manifest, but every other input
    identity (commit, raw-cache inventory, dataset manifest, registries,
    adjudications, method and policy) is verified before a draft is returned.
    Normal generation subsequently recomputes and exactly verifies the checked-
    in draft, preventing manual membership edits or policy drift.
    """
    bundle = load_config_bundle(require_retained_decisions=False)
    cache_man = cache_manifest(cache_root)
    verify_inputs(cache_root, commit, bundle, cache_man)
    manifest_by_set = {}
    for test in bundle["dataset_manifest"]["tests"]:
        manifest_by_set.setdefault(test["set"], []).append(test)
    runs_by_set = {
        set_name: [
            process_run(
                os.path.join(cache_root, raw_run["path"]),
                commit,
                rel_path=raw_run["path"],
            )
            for raw_run in entries[0]["expected_runs"]
        ]
        for set_name, entries in sorted(manifest_by_set.items())
    }
    method_hash = provenance_hashes(bundle, cache_man)["method_hash"]
    run_index = {
        (set_name, posix(os.path.basename(run["path"]))): run_binding(set_name, run)
        for set_name, runs in runs_by_set.items()
        for run in runs
    }
    adjudications = _legacy_adjudications_for_role(
        bundle, run_index, method_hash, artifact_role
    )

    upstream = _explicit_intake_upstream(bundle, runs_by_set, adjudications)
    return _build_intake_manifest(
        bundle, commit, runs_by_set, upstream, artifact_role
    )


def batch_filter(per_run, centre_fn):
    """Replicate runfilter over QC-passed runs. Null-landmark runs are excluded
    as invalid_landmarks BEFORE centre computation; centres come from valid
    candidates; both thresholds apply to every valid candidate; equality retained;
    empty result fails generation."""
    t = config()["runfilter"]; EPS = 1e-9
    keep, reasons = [], []
    valid = [(r["metrics"]["collapse_force_gf"], r["metrics"]["collapse_travel_mm"]) for r in per_run
             if r["metrics"]["collapse_force_gf"] is not None and r["metrics"]["collapse_travel_mm"] is not None]
    if not valid:
        raise RuntimeError("runfilter: no run has valid collapse landmarks; generation must fail")
    cF = centre_fn([v[0] for v in valid]); cX = centre_fn([v[1] for v in valid])
    for r in per_run:
        f, x = r["metrics"]["collapse_force_gf"], r["metrics"]["collapse_travel_mm"]
        if f is None or x is None:
            keep.append(False); reasons.append("invalid_landmarks: null collapse force/position"); continue
        dF, dX = abs(f - cF), abs(x - cX)
        ok = dF <= t["fc_threshold_gf"] + EPS and dX <= t["xc_threshold_mm"] + EPS
        keep.append(ok)
        rs = []
        if dF > t["fc_threshold_gf"] + EPS: rs.append(f"collapse force dev {dF:.3f} gf > {t['fc_threshold_gf']}")
        if dX > t["xc_threshold_mm"] + EPS: rs.append(f"collapse travel dev {dX:.3f} mm > {t['xc_threshold_mm']}")
        reasons.append("; ".join(rs))
    if not any(keep):
        raise RuntimeError("runfilter excluded every run; generation must fail, not silently restore")
    return keep, reasons, cF, cX

def aggregate(per_run, keep):
    from .schema_gen import NULL_REASONS
    kept = [r for r, k in zip(per_run, keep) if k]
    agg, disp, flags = {}, {}, set()
    null_reasons = {}
    for m in METRICS:
        vals = [r["metrics"][m] for r in kept]
        valid = [v for v in vals if v is not None]
        if valid and len(valid) == len(vals):
            agg[m] = sum(valid) / len(valid)
        else:
            # Step 2.3: the null is recorded against THIS metric only. The
            # record-wide observation flag is still emitted, but it no longer
            # forces any other metric (notably travel) to be null.
            agg[m] = None
            flags.add("aggregate_contains_null_run")
            allowed = NULL_REASONS.get(m, [])
            per_flags = {f for r in kept for f in r["quality_flags"]}
            null_reasons[m] = next((f for f in allowed if f in per_flags and
                                    f != "aggregate_contains_null_run"),
                                   "aggregate_contains_null_run")
        disp[m] = {"n_valid": len(valid),
                   "mean_validonly": (sum(valid) / len(valid)) if valid else None,
                   "sd": (statistics.stdev(valid) if len(valid) >= 2 else None),  # sample SD, n-1
                   "min": (min(valid) if valid else None), "max": (max(valid) if valid else None)}
    for r in kept: flags.update(r["quality_flags"])
    return agg, disp, sorted(flags), null_reasons

def generate(cache_root, commit, outdir, write=True, viewer_html=None, picker_html=None,
             release_bench_tests=None, run_parity=True, evidence_only=False):
    bundle = load_config_bundle()
    cache_man = cache_manifest(cache_root)
    verified_inputs = verify_inputs(cache_root, commit, bundle, cache_man)
    ph = provenance_hashes(bundle, cache_man)
    bhash = ph["bundle_hash"]
    dm = bundle["dataset_manifest"]
    manifest_run_specs = {}
    for test in dm["tests"]:
        for spec in test["expected_runs"]:
            prior = manifest_run_specs.get(spec["path"])
            if prior is not None and prior != spec:
                raise RuntimeError(f"conflicting manifest run specification: {spec['path']}")
            manifest_run_specs[spec["path"]] = spec
    registry = {e["set"]: e for e in bundle["exclusions"]["entries"]}
    release = ujson(release_bench_tests or os.path.join(REF, "bench_tests.release.json"))

    mhash = ph["method_hash"]

    # ---- pass 1: process every discovered run so adjudications can be bound
    #      to the run's ACTUAL identity before any eligibility decision.
    manifest_by_set_pre = {}
    for t in dm["tests"]:
        manifest_by_set_pre.setdefault(t["set"], []).append(t)
    runs_by_set = {}
    for sname in sorted(manifest_by_set_pre):
        runs_by_set[sname] = [process_run(os.path.join(cache_root, r["path"]), commit, rel_path=r["path"])
                              for r in manifest_by_set_pre[sname][0]["expected_runs"]]
        for run in runs_by_set[sname]:
            spec = manifest_run_specs[run["rel_path"]]
            run["git_blob_oid"] = spec["git_blob_oid"]
            run["acquisition_id"] = spec["acquisition_id"]
            run["raw_bytes"] = spec["bytes"]
    run_index = {(sname, posix(os.path.basename(r["path"]))): run_binding(sname, r)
                 for sname, rs in runs_by_set.items() for r in rs}
    declared_intake = bundle["retained_run_decisions"]
    declared_role = (
        declared_intake.get("artifact_role")
        if isinstance(declared_intake, dict)
        else None
    )
    adjud = _legacy_adjudications_for_role(
        bundle, run_index, mhash, declared_role
    )

    def eligibility(sname, r):
        return canonical_eligibility(sname, r, adjud)

    # The checked-in intake decision is never trusted.  Recompute it from the
    # pinned raw bytes and exact policy, then require semantic identity before
    # either previewing or consuming membership.
    intake_upstream = _explicit_intake_upstream(bundle, runs_by_set, adjud)
    computed_intake = _build_intake_manifest(
        bundle,
        commit,
        runs_by_set,
        intake_upstream,
        declared_role,
    )
    intake_policy.verify_declared_manifest(declared_intake, computed_intake)
    intake_version = computed_intake["policy_version"]
    intake_set_index = {entry["set"]: entry for entry in computed_intake["sets"]}
    intake_run_index = {
        (entry["set"], run["raw_path"]): run
        for entry in computed_intake["sets"]
        for run in entry["runs"]
    }
    included_set_names = {
        set_name
        for set_name, entries in manifest_by_set_pre.items()
        if all(entry["disposition"] == "include" for entry in entries)
        and set_name not in registry
    }
    policy_membership = None
    if declared_intake["artifact_role"] in (
        intake_policy.REVIEW_ROLE,
        intake_policy.CANONICAL_ROLE,
    ):
        policy_membership = intake_policy.applied_membership_by_set(
            computed_intake, included_set_names
        )

    eligibility_rows = []
    per_run_rows, retention_rows, records, median_cmp = [], [], [], []
    retained_by_set = {}
    manifest_by_set = manifest_by_set_pre

    for sname in sorted(manifest_by_set):
        entries = manifest_by_set[sname]
        reg = registry.get(sname)
        runs = runs_by_set[sname]
        if policy_membership is None:
            elig = [eligibility(sname, r) for r in runs]
        else:
            # Under review/canonical intake authority, even invoking the old
            # canonical_eligibility function would retain a hidden veto: its
            # historical fail_exclude/adjudication combinations may raise.
            # Preserve only the raw legacy observations below.
            elig = [
                (None, "not evaluated: legacy QC is diagnostic only", None)
                for _ in runs
            ]
        for r, (ok, why, a) in zip(runs, elig):
            eligibility_rows.append({"set": sname, "run": posix(os.path.basename(r["path"])),
                "artifact_role": computed_intake["artifact_role"],
                "release_eligible": computed_intake["release_eligible"],
                "decision_role": "legacy_qc_diagnostic",
                "authoritative_for_output_membership": policy_membership is None,
                "sha256": r["sha256"], "qc_disposition": r["qc_disposition"],
                "qc_disposition_flags": sorted(set(r["qc_disposition_flags"])),
                "barrier_flags": run_binding(sname, r)["barrier_flags"],
                "method_hash": mhash,
                "canonical_eligible": ok, "decision": why,
                "adjudication": (dict(a) if a else None)})
        gated = [r for r, (ok, _, _) in zip(runs, elig) if ok]
        is_included = all(e["disposition"] == "include" for e in entries) and not reg
        # A failed cohort is a retest/omission decision, not a reason to block
        # unrelated accepted sets.  The full reason remains in the intake
        # artifact and per-run reports.
        if (
            is_included
            and policy_membership is not None
            and intake_set_index[sname]["status"] != "accepted"
        ):
            is_included = False
        keep_c = keep_l = [False] * len(runs); reasons = [""] * len(runs); cF = cX = cFl = cXl = None
        if is_included:
            if policy_membership is None:
                # Development-preview mode alone preserves and compares the
                # frozen legacy runfilter.  It is deliberately absent from the
                # review/canonical execution path below.
                legacy_kc, legacy_rc, cF, cX = batch_filter(
                    gated, median_conventional
                )
                kl, _, cFl, cXl = batch_filter(gated, median_upper_middle_legacy)
                keep_c, keep_l, reasons = [], [], []
                gated_index = 0
                for ok, why, _ in elig:
                    if ok:
                        keep_c.append(legacy_kc[gated_index])
                        keep_l.append(kl[gated_index])
                        reasons.append(legacy_rc[gated_index])
                        gated_index += 1
                    else:
                        keep_c.append(False)
                        keep_l.append(False)
                        reasons.append(why)
            else:
                # The declared intake policy is the sole review/canonical membership
                # authority.  Calling batch_filter here would be a hidden veto:
                # a valid heavy cohort may pass max(1 gf, 2%) while every run
                # lies more than the old fixed 1 gf from its median.
                set_decision = intake_set_index[sname]
                run_decisions = {
                    decision["raw_path"]: decision for decision in set_decision["runs"]
                }
                cF = set_decision["center"]["collapse_force_gf"]
                cX = set_decision["center"]["collapse_position_mm"]
                keep_c = [policy_membership[sname][run["rel_path"]] for run in runs]
                reasons = [
                    "; ".join(run_decisions[run["rel_path"]]["decision_reasons"])
                    for run in runs
                ]
            retained_by_set[sname] = [r for r, k in zip(runs, keep_c) if k]
            agg, dispn, aflags, nreasons = aggregate(runs, keep_c)
            if policy_membership is None:
                agg_l, _, _, _ = aggregate(runs, keep_l)
                median_cmp.append({"set": sname, "n": len(runs),
                "kept_conventional": [posix(os.path.basename(r["path"])) for r, k in zip(runs, keep_c) if k],
                "kept_legacy": [posix(os.path.basename(r["path"])) for r, k in zip(runs, keep_l) if k],
                "centre_conventional": {"fc_gf": cF, "xc_mm": cX},
                "centre_legacy": {"fc_gf": cFl, "xc_mm": cXl},
                "per_run_deviations": [
                    {"run": posix(os.path.basename(r["path"])),
                     "fc_gf": r["metrics"]["collapse_force_gf"], "xc_mm": r["metrics"]["collapse_travel_mm"],
                     "dev_fc_gf": (None if r["metrics"]["collapse_force_gf"] is None or cF is None
                                   else abs(r["metrics"]["collapse_force_gf"] - cF)),
                     "dev_xc_mm": (None if r["metrics"]["collapse_travel_mm"] is None or cX is None
                                   else abs(r["metrics"]["collapse_travel_mm"] - cX)),
                     "retained_conventional": k, "retained_legacy": kl2,
                     "decision": reasons[i] or "retained"}
                    for i, (r, k, kl2) in enumerate(zip(runs, keep_c, keep_l))],
                "agg_conventional": agg, "agg_legacy": agg_l})
            for t in entries:
                md = t["metadata"]
                rec = {"test_id": t["test_id"], "set": sname}
                rec["measurement_cohort_id"] = t.get(
                    "measurement_cohort_id", "mc_" + sname
                )
                # Step 2.3: complete record model. Every legitimate field is
                # emitted, explicitly null where appropriate. Step 2.2 dropped
                # keys whose value was None, so flag_travel vanished from 8
                # records and silencing_ring from 15.
                from .schema_gen import METADATA_FIELDS
                rec["name"] = md.get("name")
                rec["kind"] = md.get("kind")
                for k in METADATA_FIELDS:
                    rec[k] = md.get(k, None)
                rec["notes"] = rec.get("notes") or ""
                rec["is_baseline"] = bool(md.get("is_baseline", False))
                # Preserve an explicitly unknown legacy flag as null.  Treating
                # null as False would turn "not assessed" into a factual claim
                # that the record was assessed and not flagged.
                rec["flag_travel"] = md.get("flag_travel")
                rec["status"] = md.get("status") or "pending_review"
                rec["runs_used"] = sum(keep_c)
                rec.update({m: agg[m] for m in METRICS})
                rec["quality_flags"] = aflags
                rec["null_reasons"] = nreasons
                rec["intake_review_notices"] = []
                if policy_membership is not None:
                    for run, retained in zip(runs, keep_c):
                        if not retained:
                            continue
                        run_decision = intake_run_index[(sname, run["rel_path"])]
                        evidence = _ramp_review_evidence(run_decision)
                        if evidence is not None:
                            rec["intake_review_notices"].append({
                                "type": "ramp_repeatability_review",
                                "decision": "ACCEPT + RAMP REVIEW",
                                "run": run_decision["run"],
                                "raw_path": run_decision["raw_path"],
                                "sha256": run_decision["sha256"],
                                **evidence,
                            })
                rec["calc_version"] = config()["calc_version"]
                rec["provenance"] = {"repo_commit": commit,
                    "raw_paths": [r["rel_path"] for r, k in zip(runs, keep_c) if k],
                    "raw_sha256": [r["sha256"] for r, k in zip(runs, keep_c) if k],
                    "raw_git_blob_oids": [r["git_blob_oid"] for r, k in zip(runs, keep_c) if k],
                    "acquisition_ids": [r["acquisition_id"] for r, k in zip(runs, keep_c) if k],
                    "config_hash": ph["evidence_epoch_hash"], "generator_version": __version__,
                    "artifact_role": computed_intake["artifact_role"],
                    "release_eligible": computed_intake["release_eligible"],
                    "membership_authority": (
                        f"{intake_version} review candidate"
                        if computed_intake["artifact_role"] == intake_policy.REVIEW_ROLE
                        else (f"{intake_version} canonical retention authority"
                              if computed_intake["artifact_role"] == intake_policy.CANONICAL_ROLE
                              else "frozen runfilter-v1.1 development preview")
                    )}
                rec["dispersion"] = dispn
                records.append(rec)
        legacy_membership_evaluated = policy_membership is None
        for r, kc2, kl2, rs in zip(runs, keep_c, keep_l, reasons):
            intake_run = intake_run_index[(sname, r["rel_path"])]
            ramp_evidence = _ramp_review_evidence(intake_run)
            ramp_columns = {
                "intake_ramp_review_required": intake_run["ramp_review_required"],
                **{
                    f"intake_ramp_review_{field}": (
                        ramp_evidence[field] if ramp_evidence is not None else None
                    )
                    for field in RAMP_REVIEW_FIELDS
                },
            }
            row = {"set": sname, "run": posix(os.path.basename(r["path"])), "raw_path": r["rel_path"],
                   "sha256": r["sha256"], "git_blob_oid": r["git_blob_oid"],
                   "acquisition_id": r["acquisition_id"], "raw_bytes": r["raw_bytes"],
                   "excluded_by_registry": bool(reg),
                   "qc_disposition": r["qc_disposition"],
                   "qc_disposition_flags": ";".join(r["qc_disposition_flags"]),
                   # The intake-authoritative roles deliberately do not run the
                   # legacy membership algorithms.  Do not alias intake output
                   # into legacy-named fields: blank means unevaluated, not a
                   # measured rejection.
                   "legacy_membership_evaluated": legacy_membership_evaluated,
                   "retained_conventional": (
                       kc2 if legacy_membership_evaluated else None
                   ),
                   "retained_legacy": (
                       kl2 if legacy_membership_evaluated else None
                   ),
                   "retained_output": kc2,
                   "retained_review_candidate": bool(
                       kc2 and computed_intake["artifact_role"] == intake_policy.REVIEW_ROLE
                   ),
                   "retained_canonical": bool(
                       kc2 and computed_intake["artifact_role"] == intake_policy.CANONICAL_ROLE
                   ),
                   "output_membership_authority": (
                       f"{intake_version} review candidate (non-release)"
                       if computed_intake["artifact_role"] == intake_policy.REVIEW_ROLE
                       else (f"{intake_version} canonical retention authority"
                             if computed_intake["artifact_role"] == intake_policy.CANONICAL_ROLE
                             else "frozen runfilter-v1.1 development preview")
                   ),
                   "release_eligible": computed_intake["release_eligible"],
                   "intake_policy_version": intake_version,
                   "intake_implementation_parity_target": bundle["intake_policy"][
                       "implementation_parity_target"
                   ],
                   "intake_decision_manifest_version": computed_intake[
                       "decision_manifest_version"
                   ],
                   "intake_policy_role": computed_intake["artifact_role"],
                   "intake_set_status": intake_set_index[sname]["status"],
                   "intake_individually_acceptable": intake_run["intake_individually_acceptable"],
                   "intake_matches_replicate_band": intake_run["matches_replicate_band"],
                   "intake_retained": intake_run["retained"],
                   "intake_decision_reasons": ";".join(intake_run["decision_reasons"]),
                   "exclusion_reason": ("excluded_by_registry: " + reg["reason"]) if reg else rs,
                   **ramp_columns}
            row.update({m: r["metrics"][m] for m in METRICS})
            row.update({k: r["metric_audit"].get(k) for k in PER_RUN_AUDIT_FIELDS})
            row["quality_flags"] = ";".join(r["quality_flags"])
            per_run_rows.append(row)
            qcrow = {k: v for k, v in r["qc"].items() if k != "timing_gap_indices"}
            retention_rows.append({"set": sname, "run": posix(os.path.basename(r["path"])),
                "raw_path": r["rel_path"], "sha256": r["sha256"],
                "git_blob_oid": r["git_blob_oid"], "acquisition_id": r["acquisition_id"],
                "raw_bytes": r["raw_bytes"],
                "artifact_role": computed_intake["artifact_role"],
                "release_eligible": computed_intake["release_eligible"],
                "intake_policy_version": intake_version,
                "intake_implementation_parity_target": bundle["intake_policy"][
                    "implementation_parity_target"
                ],
                "intake_decision_manifest_version": computed_intake[
                    "decision_manifest_version"
                ],
                "qc_disposition": r["qc_disposition"], **ramp_columns, **qcrow})
    records.sort(key=lambda r: (r.get("test_id") or "zz", r["set"]))

    # ---- schema + validation of EVERY record before anything is written ----
    from .schema_gen import build_schema, validate_records
    schema = build_schema()
    validate_records(records, schema)

    # ---- exclusion manifest (complete, untruncated) ----
    excl_manifest = {"artifact_role": computed_intake["artifact_role"],
        "release_eligible": computed_intake["release_eligible"],
        "repo_commit": commit, "registry_hash": sha256_bytes(
        json.dumps(bundle["exclusions"], sort_keys=True, separators=(",", ":")).encode()),
        "config_hash": bhash, "entries": bundle["exclusions"]["entries"]}

    # ---- packs + reports (all generated from executable logic) ----
    from .packs import build_all_packs, build_curve_evidence_packs
    from .reports import diff_vs_release_md, median_md
    if evidence_only:
        packs = build_curve_evidence_packs(
            retained_by_set, records, bundle["exclusions"]
        )
    else:
        packs = build_all_packs(
            retained_by_set, records, dm, bundle["exclusions"],
            computed_intake,
            viewer_html or os.path.join(REF, "index.release.html"),
            picker_html or os.path.join(REF, "dome-lab-parts.release.html"),
        )

    curve_pack_provenance = []
    record_by_set = {record["set"]: record for record in records}
    for path, content in sorted(packs.items()):
        if not path.startswith("packs/curves/"):
            continue
        set_name = path[len("packs/curves/"):-len(".staged.json")]
        record = record_by_set[set_name]
        curve_pack_provenance.append({
            "path": path,
            "sha256": sha256_bytes(content.encode("utf-8")),
            "set": set_name,
            "derived_lossy_display_pack": True,
            "authoritative_metrics": False,
            "repo_commit": commit,
            "evidence_epoch_hash": ph["evidence_epoch_hash"],
            "decision_manifest_hash": _h(computed_intake),
            "raw_paths": record["provenance"]["raw_paths"],
            "raw_sha256": record["provenance"]["raw_sha256"],
            "raw_git_blob_oids": record["provenance"]["raw_git_blob_oids"],
            "acquisition_ids": record["provenance"]["acquisition_ids"],
        })

    intake_artifact_name = {
        intake_policy.PREVIEW_ROLE: "intake_decisions.preview.json",
        intake_policy.REVIEW_ROLE: "intake_decisions.review-candidate.json",
        intake_policy.CANONICAL_ROLE: "intake_retention_decisions.json",
    }[computed_intake["artifact_role"]]
    nonrelease_banner = (
        "# REVIEW CANDIDATE — NOT A CANONICAL RELEASE\n\n"
        if not computed_intake["release_eligible"]
        else ""
    )
    inventory_rows = pinned_inventory_rows()
    raw_path_manifest = []
    for path, row in sorted(inventory_rows.items()):
        if not re.search(r"DataLog.*\.csv$", path.rsplit("/", 1)[-1], re.I):
            continue
        spec = manifest_run_specs[path]
        raw_path_manifest.append({
            "path": path,
            "set": path.split("/", 1)[0],
            "file_mode": row.get("file_mode") or row.get("mode") or "100644",
            "git_object_format": row.get("git_object_format") or row.get("object_format") or "sha1",
            "git_blob_oid": row.get("git_blob_oid") or row.get("git_blob"),
            "sha256": row["sha256"],
            "bytes": int(row["bytes"]),
            "acquisition_id": spec["acquisition_id"],
        })

    unique_acquisitions = {row["acquisition_id"] for row in raw_path_manifest}
    independent_cohorts = {
        test.get("measurement_cohort_id", test["set"]) for test in dm["tests"]
    }
    staged = {"bench_tests.staged.json": dumps(records),
              "eligibility_decisions.json": dumps(eligibility_rows),
              intake_artifact_name: dumps(computed_intake),
              "per_run_full_precision.json": dumps(per_run_rows),
              "median_comparison.json": dumps(median_cmp),
              "exclusion_manifest.json": dumps(excl_manifest),
              "metadata_registry.staged.json": dumps(bundle["metadata_registry"]),
              "evidence_history.staged.json": dumps(bundle["evidence_history"]),
              "raw_path_manifest.json": dumps({
                  "repo_commit": commit,
                  "git_object_format": "sha1",
                  "path_count": len(raw_path_manifest),
                  "unique_acquisition_count": len(unique_acquisitions),
                  "rows": raw_path_manifest,
              }),
              "curve_pack_provenance.json": dumps({
                  "contract": "curve-pack-provenance-v1",
                  "repo_commit": commit,
                  "evidence_epoch_hash": ph["evidence_epoch_hash"],
                  "authoritative_metrics_artifact": "bench_tests.staged.json",
                  "pack_values_are_derived_and_lossy": True,
                  "packs": curve_pack_provenance,
              }),
              "schema_meta.staged.json": dumps({**{k: config()[k] for k in ("metrics_version", "calc_version",
                    "force_unit", "travel_unit", "nominal_sample_step_mm")},
                    "method_config": config(), "config_hash": bhash,
                    "provenance_hashes": ph,
                    "config_hash_definition": "config_hash == bundle_hash over all distinguished method, dataset-decision, metadata-authority, history, raw, generator-source, and release-reference identities; evidence_epoch_hash excludes generator source and presentation/release-reference bytes",
                    "evidence_epoch": {
                        "identity": ph["evidence_epoch_hash"],
                        "semantic_record_count": len(records),
                        "semantic_set_count": len({record["set"] for record in records}),
                        "independent_measurement_cohort_count": len(independent_cohorts),
                        "raw_path_count": len(raw_path_manifest),
                        "unique_raw_evidence_count": len(unique_acquisitions),
                        "shared_evidence_alias_group_count": len(dm.get("evidence_aliases", [])),
                        "input_verification": verified_inputs,
                        "metadata_authority_hash": ph["metadata_authority_hash"],
                        "evidence_history_hash": ph["evidence_history_hash"],
                        "curve_packs_are_derived_and_lossy": True,
                        "force_curve_bench_step3_status": "deferred_not_executed",
                        "force_curve_bench_release_eligible": False,
                    },
                    "intake_policy": {"version": computed_intake["policy_version"],
                        "implementation_parity_target": bundle["intake_policy"][
                            "implementation_parity_target"
                        ],
                        "decision_manifest_version": computed_intake[
                            "decision_manifest_version"
                        ],
                        "policy_hash": computed_intake["policy_hash"],
                        "decision_manifest_hash": _h(computed_intake),
                        "artifact_role": computed_intake["artifact_role"],
                        "membership_applied_to_outputs": computed_intake["membership_applied_to_outputs"],
                        "canonical_membership_active": computed_intake["canonical_membership_active"],
                        "release_eligible": computed_intake["release_eligible"],
                        "ramp_review_summary": computed_intake["ramp_review_summary"],
                        "ramp_review_set_summaries": {
                            entry["set"]: entry["ramp_review_summary"]
                            for entry in computed_intake["sets"]
                        },
                        "warning": ("REVIEW CANDIDATE — NOT A CANONICAL RELEASE"
                            if not computed_intake["release_eligible"] else None)},
                    "generator_version": __version__, "repo_commit": commit,
                    "dispersion_note": "sd is the sample standard deviation (n-1) via statistics.stdev",
                    "known_divergences_vs_generated_reference_js": DIVERGENCES,
                    "per_run_audit_fields": list(PER_RUN_AUDIT_FIELDS)}),
              "schemas/bench_test.schema.v42.json": dumps(schema),
              "diff_vs_release.md": nonrelease_banner + diff_vs_release_md(records, release),
              "median_convention_comparison.md": nonrelease_banner + median_md(median_cmp)}
    staged.update(packs)

    def wcsv(rows):
        if not rows: return ""
        keys = []
        for r in rows:
            for k in r:
                if k not in keys: keys.append(k)
        buf = io.StringIO(); w = csv.DictWriter(buf, keys, restval=""); w.writeheader(); w.writerows(rows)
        return buf.getvalue()
    staged["per_run_full_precision.csv"] = wcsv(per_run_rows)
    staged["acquisition_qc.csv"] = wcsv(retention_rows)
    staged["raw_path_manifest.csv"] = wcsv(raw_path_manifest)
    _edec = {(e["set"], e["run"]): e["decision"] for e in eligibility_rows}
    staged["run_retention.csv"] = wcsv([{**{k: r[k] for k in ("set", "run", "raw_path", "sha256",
        "git_blob_oid", "acquisition_id", "raw_bytes",
        "excluded_by_registry", "qc_disposition", "legacy_membership_evaluated",
        "retained_conventional", "retained_legacy",
        "retained_output", "retained_review_candidate", "retained_canonical",
        "output_membership_authority", "release_eligible", "intake_policy_version",
        "intake_implementation_parity_target", "intake_decision_manifest_version",
        "intake_policy_role",
        "intake_set_status", "intake_individually_acceptable",
        "intake_matches_replicate_band", "intake_retained", "intake_decision_reasons",
        "intake_ramp_review_required", "intake_ramp_review_ramp_gf_per_mm",
        "intake_ramp_review_retained_median_gf_per_mm",
        "intake_ramp_review_signed_deviation_pct",
        "intake_ramp_review_absolute_deviation_pct",
        "intake_ramp_review_threshold_pct", "exclusion_reason")},
        "legacy_qc_eligibility_decision": _edec.get((r["set"], r["run"]), ""),
        "eligibility_decision": _edec.get((r["set"], r["run"]), "")}
        for r in per_run_rows])

    if run_parity and not evidence_only:
        from .parity import parity_report
        parity = parity_report(
            runs_by_set, viewer_text=staged["packs/viewer.staged.html"]
        )
        parity["artifact_role"] = computed_intake["artifact_role"]
        parity["release_eligible"] = computed_intake["release_eligible"]
        staged["parity_report.json"] = dumps(parity)

    manifest = {rel: sha256_bytes(c.encode()) for rel, c in staged.items()}
    staged["generated_manifest.json"] = dumps(manifest)

    if write:
        _promote_tree(staged, outdir)
    return staged, records, per_run_rows, median_cmp


def _promote_tree(staged, outdir):
    """Build the complete candidate tree in a temporary sibling directory,
    validate and hash every artifact from disk, then promote through a
    ROLLBACK-CAPABLE transaction.

    Step 2.2 renamed the live tree aside and then renamed the candidate in. If
    the second rename failed (a cross-device move, a permissions change, a lock)
    the original target was already gone and nothing restored it: an injected
    mid-commit failure destroyed the target directory and left both the
    candidate and the aside copy behind.

    Step 2.3 records every completed step and unwinds them in reverse on any
    failure, so the original target is restored automatically, no partial tree
    is left at the target path, and temporary directories are reconciled.
    """
    import shutil
    outdir = os.path.abspath(outdir)
    cand = outdir + ".candidate-tmp"
    prev = outdir + ".replaced-prev"
    for stale in (cand, prev):
        if os.path.exists(stale):
            shutil.rmtree(stale)

    for rel, content in staged.items():
        p = os.path.join(cand, rel)
        os.makedirs(os.path.dirname(p) or cand, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    man = json.loads(staged["generated_manifest.json"])
    for rel, h in man.items():
        got = sha256_bytes(read_bytes(os.path.join(cand, rel)))
        if got != h:
            shutil.rmtree(cand, ignore_errors=True)
            raise RuntimeError(f"candidate tree failed post-write hash validation: {rel}")
    for rel in staged:
        if not os.path.exists(os.path.join(cand, rel)):
            shutil.rmtree(cand, ignore_errors=True)
            raise RuntimeError(f"candidate tree incomplete: {rel}")

    undo = []
    try:
        if os.path.exists(outdir):
            os.rename(outdir, prev)
            undo.append(("restore_target", prev, outdir))
        os.rename(cand, outdir)
        undo.append(("remove_promoted", outdir, None))
    except Exception as exc:
        for kind, src, dst in reversed(undo):
            try:
                if kind == "remove_promoted":
                    os.rename(src, cand)
                elif kind == "restore_target":
                    os.rename(src, dst)
            except Exception as unwind_exc:  # pragma: no cover - defensive
                raise RuntimeError(
                    f"promotion failed ({exc}) AND rollback failed ({unwind_exc}); "
                    f"inspect {prev!r} and {cand!r} manually") from exc
        shutil.rmtree(cand, ignore_errors=True)
        raise RuntimeError(f"candidate promotion failed and was rolled back; "
                           f"the original tree at {outdir!r} is intact: {exc}") from exc

    if os.path.exists(prev):
        shutil.rmtree(prev)
    if os.path.exists(cand):
        shutil.rmtree(cand, ignore_errors=True)


def check(cache_root, commit, outdir, **kw):
    """Non-mutating conformance check: regenerates, byte-compares every expected
    artifact including generated_manifest.json, verifies recorded hashes, and
    fails on missing, stale or unexpected files in the staging tree."""
    staged, *_ = generate(cache_root, commit, outdir, write=False, **kw)
    problems = []
    for rel, content in staged.items():
        p = os.path.join(outdir, rel)
        if not os.path.exists(p): problems.append(f"MISSING {rel}")
        elif uread(p) != content: problems.append(f"MISMATCH {rel}")
    man = json.loads(staged["generated_manifest.json"])
    for rel, h in man.items():
        if sha256_bytes(staged[rel].encode()) != h: problems.append(f"MANIFEST-HASH {rel}")
    expected = {posix(rel) for rel in staged}
    for dp, _, fs in os.walk(outdir):
        for fn in fs:
            rel = posix(os.path.relpath(os.path.join(dp, fn), outdir))
            if rel not in expected: problems.append(f"UNEXPECTED/STALE {rel}")
    return problems
