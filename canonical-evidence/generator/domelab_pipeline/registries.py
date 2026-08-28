"""Exclusion-registry and adjudication binding validation.

Step 2.2 excluded sets by NAME only: the registry's raw paths and hashes were
carried in the config but never checked, so a stale hash, a removed path or a
path naming a nonexistent file all generated successfully. Adjudications bound
optionally on SHA-256 alone, so duplicate keys silently last-won, extraneous
entries were ignored, and an override survived a method change that widened
what it covered.

Step 2.3 makes both registries load-bearing. Every binding is verified during
input verification, before any run is processed, and a mismatch fails
generation.
"""
import os
import re
from pathlib import PurePosixPath


# ------------------------------------------------------------------ paths
def normalized_posix_problems(p):
    """Return a list of reasons `p` is not a normalized relative POSIX path."""
    probs = []
    if not isinstance(p, str) or p == "":
        return ["empty or non-string path"]
    if "\\" in p:
        probs.append("backslash separator")
    if "://" in p or p.lower().startswith("file:"):
        probs.append("URI/file scheme")
    if p.startswith("/"):
        probs.append("absolute path")
    if len(p) >= 2 and p[1] == ":" and p[0].isalpha():
        probs.append("drive-letter path")
    segs = p.split("/")
    if any(s == "" for s in segs):
        probs.append("empty path segment")
    if any(s == "." for s in segs):
        probs.append("'.' segment (non-normalized)")
    if any(s == ".." for s in segs):
        probs.append("'..' segment")
    if p != PurePosixPath(p).as_posix():
        probs.append("non-normalized POSIX form")
    return probs


def require_normalized(paths, what):
    errs = []
    for p in paths:
        for why in normalized_posix_problems(p):
            errs.append(f"{what}: rejected path {p!r} — {why}")
    return errs


# -------------------------------------------------------------- exclusions
def verify_exclusion_registry(exclusions, dataset_manifest, cache_man, pinned_inventory):
    """Every excluded set must exist, and its raw-run bindings must exactly
    reproduce the complete manifest run set for that set, present in the cache
    and matching the pinned inventory. Returns a list of error strings."""
    errs = []
    entries = exclusions.get("entries", [])
    seen_sets = set()
    manifest_runs = {}
    for t in dataset_manifest["tests"]:
        manifest_runs.setdefault(t["set"], {})
        for r in t["expected_runs"]:
            manifest_runs[t["set"]][r["path"]] = r["sha256"]

    for e in entries:
        s = e.get("set")
        if not s:
            errs.append("exclusion registry: entry without a set identity")
            continue
        if s in seen_sets:
            errs.append(f"exclusion registry: duplicate excluded-set entry {s!r}")
            continue
        seen_sets.add(s)
        if s not in manifest_runs:
            errs.append(f"exclusion registry: excluded set {s!r} does not exist in the dataset manifest")
            continue
        declared = e.get("raw_runs", [])
        errs += require_normalized([r.get("path", "") for r in declared],
                                   f"exclusion registry [{s}]")
        dpaths = [r.get("path") for r in declared]
        if len(dpaths) != len(set(dpaths)):
            errs.append(f"exclusion registry [{s}]: duplicate run bindings")
        expected = manifest_runs[s]
        missing = sorted(set(expected) - set(dpaths))
        extra = sorted(set(dpaths) - set(expected))
        for p in missing:
            errs.append(f"exclusion registry [{s}]: incomplete path list — manifest run {p} not bound")
        for p in extra:
            errs.append(f"exclusion registry [{s}]: path {p} is not part of this set's manifest run list")
        for r in declared:
            p, h = r.get("path"), r.get("sha256")
            if p in extra:
                continue
            if p not in cache_man:
                errs.append(f"exclusion registry [{s}]: bound path absent from cache: {p}")
                continue
            if cache_man[p] != h:
                errs.append(f"exclusion registry [{s}]: stale SHA-256 for {p} "
                            f"(registry {str(h)[:12]}… vs cache {cache_man[p][:12]}…)")
            if pinned_inventory.get(p) != cache_man[p]:
                errs.append(f"exclusion registry [{s}]: {p} does not match the pinned inventory")
    return errs


def exclusion_manifest_matches(staged_entries, verified_entries):
    """The staged exclusion manifest must exactly reproduce the verified registry."""
    if staged_entries != verified_entries:
        return ["staged exclusion manifest does not exactly reproduce the verified registry"]
    return []


# ------------------------------------------------------------ adjudications
ADJUDICATION_REQUIRED = ("set", "run", "raw_path", "sha256", "method_hash",
                         "overrides_disposition", "qc_reasons", "barrier_flags",
                         "eligible", "authority", "date", "rationale")


def verify_adjudications(adjudications, run_index, method_hash):
    """run_index maps (set, run) -> {sha256, qc_disposition, qc_reasons,
    barrier_flags}. Returns (bindings, errors).

    Rejects: hash mismatch, method mismatch, disposition mismatch, reason
    mismatch, barrier mismatch, duplicate keys, extraneous adjudications,
    adjudications for nonexistent files, and any attempt to override
    fail_exclude.
    """
    errs, bindings, seen = [], {}, set()
    for a in adjudications.get("entries", []):
        missing = [k for k in ADJUDICATION_REQUIRED if k not in a]
        key = (a.get("set"), a.get("run"))
        if missing:
            errs.append(f"adjudication {key}: missing required binding field(s) {missing}")
            continue
        if key in seen:
            errs.append(f"adjudication {key}: duplicate adjudication key")
            continue
        seen.add(key)
        errs += require_normalized([a["raw_path"]], f"adjudication {key}")
        # Step 2.3.1: `eligible` must be a real JSON Boolean. Step 2.3 accepted
        # "false", 0 and 1, so a string "false" was truthy and ADMITTED the run.
        if not isinstance(a["eligible"], bool):
            errs.append(f"adjudication {key}: 'eligible' must be a JSON boolean, "
                        f"got {type(a['eligible']).__name__} {a['eligible']!r}")
            continue
        info = run_index.get(key)
        if info is None:
            errs.append(f"adjudication {key}: adjudication for a nonexistent file")
            continue
        # Step 2.3.1: the declared raw_path must be the run's real path. Step 2.3
        # normalized the path but never compared it, so a correct hash attached
        # to a wrong-but-syntactically-valid path was accepted.
        expected_path = info.get("raw_path")
        if expected_path is not None and a["raw_path"] != expected_path:
            errs.append(f"adjudication {key}: raw_path {a['raw_path']!r} is not this run's "
                        f"declared path {expected_path!r}")
        if a["sha256"] != info["sha256"]:
            errs.append(f"adjudication {key}: raw SHA-256 mismatch")
        if a["method_hash"] != method_hash:
            errs.append(f"adjudication {key}: method hash mismatch — the method changed since "
                        f"this ruling was made; it must be re-adjudicated rather than silently widened")
        if info["qc_disposition"] == "fail_exclude":
            errs.append(f"adjudication {key}: fail_exclude is never overridable")
            continue
        if a["overrides_disposition"] != info["qc_disposition"]:
            errs.append(f"adjudication {key}: disposition mismatch "
                        f"(binds {a['overrides_disposition']!r}, run is {info['qc_disposition']!r})")
        if sorted(a["qc_reasons"]) != sorted(info["qc_reasons"]):
            errs.append(f"adjudication {key}: QC-reason set mismatch "
                        f"(binds {sorted(a['qc_reasons'])}, run has {sorted(info['qc_reasons'])})")
        if sorted(a["barrier_flags"]) != sorted(info["barrier_flags"]):
            errs.append(f"adjudication {key}: barrier-flag set mismatch "
                        f"(binds {sorted(a['barrier_flags'])}, run has {sorted(info['barrier_flags'])})")
        needs = (info["qc_disposition"] in ("review", "quarantine_retest")) or bool(info["barrier_flags"])
        if not needs:
            errs.append(f"adjudication {key}: extraneous — the run is already eligible "
                        f"({info['qc_disposition']}, no barrier flags) and needs no override")
            continue
        bindings[key] = dict(a)
    return bindings, errs


# --------------------------------------------------- exclusion bijection
def verify_exclusion_bijection(exclusions, dataset_manifest):
    """Exactly one exclusion-registry entry per registry-excluded dataset entry.

    Step 2.3 let a set stay excluded through a SECOND independent authority:
    the dataset manifest's own `disposition: "exclude_registry"`. Deleting the
    Gray-02 registry entry still produced 22 records with Gray-02 absent, while
    the generated exclusion manifest silently became empty and the set vanished
    from the UI with no recorded reason. The two authorities must agree or
    generation must fail.
    """
    errs = []
    declared = [t["set"] for t in dataset_manifest["tests"]
                if t.get("disposition") == "exclude_registry" or t.get("exclude_registry")]
    registry = [e.get("set") for e in exclusions.get("entries", [])]

    for s in sorted(set(declared)):
        if declared.count(s) > 1:
            errs.append(f"exclusion bijection: dataset manifest declares {s!r} "
                        f"exclude_registry {declared.count(s)} times")
        n = registry.count(s)
        if n == 0:
            errs.append(f"exclusion bijection: dataset entry {s!r} is marked exclude_registry "
                        f"but has NO exclusion-registry entry")
        elif n > 1:
            errs.append(f"exclusion bijection: {n} exclusion-registry entries for {s!r}")
    for s in sorted(set(registry)):
        if s not in declared:
            errs.append(f"exclusion bijection: exclusion-registry entry {s!r} does not "
                        f"correspond to any dataset entry marked exclude_registry")
    return errs


# ------------------------------------------------- run <-> set binding
def verify_run_set_binding(dataset_manifest):
    """Every raw run belongs to the set that declares it, and a repeated source
    set uses one identical, ordered, path/hash-bound run list.

    Step 2.3 validated path SYNTAX but never path OWNERSHIP, so a NiZ path could
    be declared as a Topre 30g run, an undeclared fourth run could be added to a
    second record for the same source set, and duplicate identities passed.
    """
    errs = []
    by_set = {}
    seen_identities = set()
    for t in dataset_manifest["tests"]:
        sname = t["set"]
        runs = t.get("expected_runs", [])
        paths = [r.get("path", "") for r in runs]
        errs += require_normalized(paths, f"dataset manifest [{sname}]")

        for r in runs:
            path = r.get("path", "")
            owner = path.split("/")[0] if "/" in path else ""
            if owner != sname:
                errs.append(f"run/set binding [{sname}]: run path {path!r} belongs to set "
                            f"{owner!r}, not to the declaring set")
            ident = (sname, path, r.get("sha256"))
            if ident in seen_identities and paths.count(path) > 1:
                errs.append(f"run/set binding [{sname}]: duplicate set/run/path identity {path!r}")
            seen_identities.add(ident)

        if len(paths) != len(set(paths)):
            dupes = sorted({p for p in paths if paths.count(p) > 1})
            errs.append(f"run/set binding [{sname}]: duplicate run path(s) {dupes}")

        signature = tuple((r.get("path"), r.get("sha256")) for r in runs)
        if sname in by_set and by_set[sname] != signature:
            prev = {p for p, _ in by_set[sname]}
            now = {p for p, _ in signature}
            detail = []
            if now - prev:
                detail.append(f"undeclared extra run(s) {sorted(now - prev)}")
            if prev - now:
                detail.append(f"missing run(s) {sorted(prev - now)}")
            if not detail:
                detail.append("same paths in a different order or with different hashes")
            errs.append(f"run/set binding [{sname}]: conflicting run lists for one source set "
                        f"\u2014 {'; '.join(detail)}")
        by_set.setdefault(sname, signature)
    return errs


def verify_manifest_raw_coverage(dataset_manifest, pinned_inventory):
    """Require the manifest to cover every pinned raw CSV, exactly.

    Repeated records may legitimately reference the same source-set run list,
    so comparison is performed on the unique path union.  Hash and ownership
    checks remain separate; this guard closes the missing-path direction that
    otherwise lets a run disappear while the 141-file cache still verifies.
    ``pinned_inventory`` may be a path->hash mapping or any path iterable.
    """
    inventory_paths = set(pinned_inventory)

    def is_raw_run(path):
        name = path.rsplit("/", 1)[-1]
        return bool(re.search(r"DataLog.*\.csv$", name, re.IGNORECASE))

    expected = {p for p in inventory_paths if is_raw_run(p)}
    declared = {
        r.get("path", "")
        for test in dataset_manifest.get("tests", [])
        for r in test.get("expected_runs", [])
    }
    errs = []
    for path in sorted(expected - declared):
        errs.append(f"raw manifest coverage: pinned raw run MISSING from manifest: {path}")
    for path in sorted(declared - expected):
        errs.append(f"raw manifest coverage: manifest path is not a pinned raw run: {path}")
    if len(declared) != len(expected):
        errs.append(f"raw manifest coverage: {len(declared)} unique manifest raw paths != "
                    f"{len(expected)} pinned raw paths")
    return errs
