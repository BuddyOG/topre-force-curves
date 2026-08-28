"""Draft 2020-12 JSON Schema generated from the same method configuration as the
metrics-v4.2 calculations.

Step 2.3 corrections
--------------------
* Complete record model. Step 2.2's changelog claimed one, but `flag_travel` was
  absent from 8 records and `silencing_ring` from 15 because the pipeline
  dropped keys whose value was None. Every legitimate field is now required.
  Fields may be explicitly null where that is scientifically appropriate; they
  may not disappear.
* Path rules reject `..`, `./run.csv`, `a/./b.csv`, `a//b.csv`, backslashes,
  absolute paths, drive-letter paths, URI/file paths, empty segments and any
  non-normalized POSIX form. Step 2.2 accepted five of these.
* Uniqueness enforced on quality_flags, intake review notices, raw_paths and
  raw_sha256.
* Null semantics: a null metric requires exactly one permitted metric-specific
  reason, that reason must appear in quality_flags, a non-null metric must not
  carry a null reason, and the generic aggregate_contains_null_run flag no
  longer forces travel to be null when only RAMP (or another metric) is null.
* snap_pct is nullable, because the core emits null for nonpositive collapse
  force. Step 2.2 declared a null reason for it while the schema forbade the
  value, so the path was unreachable-by-schema yet reachable-by-code.
"""
from .core import config, config_hash
from . import __version__

METRICS = ["collapse_force_gf", "collapse_travel_mm", "valley_force_gf", "valley_travel_mm", "snap_pct",
           "travel_mm", "full_stroke_press_work_gf_mm", "precollapse_work_gf_mm", "drop_gf", "drop_travel_mm",
           "drop_rate_gf_per_mm", "norm_drop_rate_per_mm", "steepest_drop_0p10mm_gf_per_mm", "ramp_10_90_gf_per_mm"]

# snap_pct added in Step 2.3: run_metrics() leaves it None when Fc <= 0.
NULLABLE = {"snap_pct", "travel_mm", "full_stroke_press_work_gf_mm", "drop_rate_gf_per_mm",
            "norm_drop_rate_per_mm", "steepest_drop_0p10mm_gf_per_mm", "ramp_10_90_gf_per_mm"}

LEGACY = ["collapse_g", "collapse_mm", "valley_g", "valley_mm", "press_work_gfmm", "precollapse_work_gfmm",
          "steepest_drop_gf_per_mm", "ramp_gf_per_mm", "bottom_g", "bottom_mm", "energy_gfmm"]

FLAGS = ["collapse_not_found", "valley_not_found", "bottomout_not_found", "nonpositive_drop",
         "nonpositive_drop_travel", "nonpositive_collapse_force", "drop_travel_below_0p10mm",
         "ramp_baseline_unavailable", "ramp_baseline_band_incomplete",
         "ramp_reference_band_overlaps_collapse",
         "ramp_crossing_missing", "ramp_event_order_invalid", "ramp_span_too_small",
         "loadcell_saturation", "incomplete_press", "incomplete_return", "displacement_nonmonotonic",
         "timestamp_nonmonotonic", "grid_nonconforming", "collapse_fallback_used",
         "tactile_event_not_found", "valley_iteration_nonconverged", "aggregate_contains_null_run",
         "invalid_turnaround", "missing_duplicate_turnaround", "bad_origin", "bad_return_endpoint",
         "cropped_stroke", "malformed_rows", "phase_reversal"]

# Metric-specific null reasons. aggregate_contains_null_run is the aggregation-
# level reason: it says "a retained run was null for THIS metric", and it is
# recorded per metric rather than as a record-wide assertion.
NULL_REASONS = {
    "snap_pct": ["nonpositive_collapse_force", "aggregate_contains_null_run"],
    "travel_mm": ["bottomout_not_found", "grid_nonconforming", "aggregate_contains_null_run"],
    "full_stroke_press_work_gf_mm": ["bottomout_not_found", "grid_nonconforming", "aggregate_contains_null_run"],
    "drop_rate_gf_per_mm": ["nonpositive_drop", "nonpositive_drop_travel", "nonpositive_collapse_force", "aggregate_contains_null_run"],
    "norm_drop_rate_per_mm": ["nonpositive_drop", "nonpositive_drop_travel", "nonpositive_collapse_force", "aggregate_contains_null_run"],
    "steepest_drop_0p10mm_gf_per_mm": ["drop_travel_below_0p10mm", "nonpositive_drop_travel", "aggregate_contains_null_run"],
    "ramp_10_90_gf_per_mm": ["ramp_baseline_unavailable", "ramp_baseline_band_incomplete",
                              "ramp_reference_band_overlaps_collapse",
                              "ramp_crossing_missing", "ramp_event_order_invalid",
                              "ramp_span_too_small", "aggregate_contains_null_run"],
}

# Every field a complete canonical record must carry. Nullable-but-required.
METADATA_FIELDS = [
    "display_name", "manufacturer", "brand", "style", "variant",
    "nominal_weight_g", "tested", "metadata_source", "metadata_source_locator",
    "metadata_override_applied", "evidence_alias_group", "evidence_alias_role",
    "tested_part", "dome", "slider", "silencing_ring", "housing", "conical_spring",
    "is_baseline", "travel_dev_mm", "precompression_mm", "flag_travel", "status", "notes",
]

# Normalized relative POSIX path. Rejects absolute, drive-letter, backslash,
# URI/file, '.', '..', empty segments and trailing slash.
PATH_PATTERN = (
    r"^(?!.*[\\\\])"            # no backslashes
    r"(?!.*://)"                 # no URI scheme
    r"(?![A-Za-z]:)"             # no drive letter
    r"(?!/)"                     # not absolute
    r"(?!\.{1,2}(?:/|$))"        # no leading . or ..
    r"(?!.*/\.{1,2}(?:/|$))"     # no interior/trailing . or ..
    r"(?!.*//)"                  # no empty interior segment
    r"(?!.*/$)"                  # no trailing slash
    r"[^\\\\]+$"
)


def build_schema():
    c = config()
    DOMAIN = {"collapse_force_gf": (0, 2000), "collapse_travel_mm": (0, 10),
              "valley_force_gf": (0, 2000), "valley_travel_mm": (0, 10), "snap_pct": (-1000, 100),
              "travel_mm": (0, 10), "full_stroke_press_work_gf_mm": (0, 100000),
              "precollapse_work_gf_mm": (0, 100000), "drop_gf": (-2000, 2000),
              "drop_travel_mm": (-10, 10), "drop_rate_gf_per_mm": (0, 100000),
              "norm_drop_rate_per_mm": (0, 1000), "steepest_drop_0p10mm_gf_per_mm": (-100000, 100000),
              "ramp_10_90_gf_per_mm": (0, 100000)}

    def dom_schema(m, nullable):
        lo, hi = DOMAIN[m]
        return {"type": ["number", "null"] if nullable else "number", "minimum": lo, "maximum": hi}

    props = {m: dom_schema(m, m in NULLABLE) for m in METRICS}
    props.update({
        "test_id": {"type": "string", "pattern": "^bt_[0-9]{4}$"},
        "kind": {"enum": ["dome_baseline", "part_assembly"]},
        "name": {"type": "string", "minLength": 1},
        "set": {"type": "string", "pattern": "^[A-Za-z0-9_.-]+$"},
        "measurement_cohort_id": {"type": "string", "pattern": "^mc_[A-Za-z0-9_.-]+$"},
        "display_name": {"type": "string", "minLength": 1},
        "manufacturer": {"type": ["string", "null"]},
        "brand": {"type": ["string", "null"]},
        "style": {"type": ["string", "null"]},
        "variant": {"type": ["string", "null"]},
        "nominal_weight_g": {"type": ["number", "null"], "minimum": 0},
        "tested": {"type": ["boolean", "null"]},
        "metadata_source": {"enum": ["authoritative_workbook", "predecessor_manifest"]},
        "metadata_source_locator": {"type": "string", "minLength": 1},
        "metadata_override_applied": {"type": "boolean"},
        "evidence_alias_group": {"type": ["string", "null"]},
        "evidence_alias_role": {"type": ["string", "null"]},
        "tested_part": {"type": ["string", "null"]},
        "dome": {"type": ["string", "null"]},
        "slider": {"type": ["string", "null"]},
        "silencing_ring": {"type": ["string", "null"]},
        "housing": {"type": ["string", "null"]},
        "conical_spring": {"type": ["string", "null"]},
        "is_baseline": {"type": "boolean"},
        "runs_used": {"type": "integer", "minimum": 1},
        "travel_dev_mm": {"type": ["number", "null"]},
        "precompression_mm": {"type": ["number", "null"]},
        "flag_travel": {"type": ["boolean", "null"]},
        "calc_version": {"const": c["calc_version"]},
        "status": {"enum": ["pending_review", "verified", "retest_required"]},
        "notes": {"type": "string"},
        "quality_flags": {"type": "array", "items": {"enum": FLAGS}, "uniqueItems": True},
        "intake_review_notices": {
            "type": "array",
            "uniqueItems": True,
            "description": (
                "Advisory intake review evidence for retained runs. Notices do not "
                "change retention, metrics, quality_flags, or null semantics."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {"const": "ramp_repeatability_review"},
                    "decision": {"const": "ACCEPT + RAMP REVIEW"},
                    "run": {"type": "string", "minLength": 1, "pattern": "^[^/\\\\]+$"},
                    "raw_path": {"type": "string", "pattern": PATH_PATTERN},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "ramp_gf_per_mm": {"type": "number"},
                    "retained_median_gf_per_mm": {
                        "type": "number", "exclusiveMinimum": 0
                    },
                    "signed_deviation_pct": {"type": "number"},
                    "absolute_deviation_pct": {"type": "number", "minimum": 0},
                    "threshold_pct": {"type": "number", "exclusiveMinimum": 0},
                },
                "required": [
                    "type", "decision", "run", "raw_path", "sha256",
                    "ramp_gf_per_mm", "retained_median_gf_per_mm",
                    "signed_deviation_pct", "absolute_deviation_pct",
                    "threshold_pct",
                ],
            },
        },
        "null_reasons": {
            "type": "object", "additionalProperties": False,
            "properties": {m: {"enum": rs} for m, rs in NULL_REASONS.items()},
            "description": "exactly one permitted metric-specific reason flag for every null canonical metric"},
        "provenance": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "repo_commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
                "raw_paths": {"type": "array", "minItems": 1, "uniqueItems": True,
                              "items": {"type": "string", "pattern": PATH_PATTERN,
                                        "description": "normalized relative POSIX path"}},
                "raw_sha256": {"type": "array", "minItems": 1, "uniqueItems": True,
                               "items": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
                "raw_git_blob_oids": {"type": "array", "minItems": 1, "uniqueItems": True,
                                      "items": {"type": "string", "pattern": "^[0-9a-f]{40}$"}},
                "acquisition_ids": {"type": "array", "minItems": 1, "uniqueItems": True,
                                    "items": {"type": "string", "pattern": "^acq_sha256:[0-9a-f]{64}$"}},
                "config_hash": {
                    "type": "string", "pattern": "^[0-9a-f]{64}$",
                    "description": "presentation-independent evidence_epoch_hash; retained key name is for schema compatibility",
                },
                "generator_version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"},
                "artifact_role": {"enum": ["development_preview", "review_candidate",
                                              "canonical_retention_authority"]},
                "release_eligible": {"type": "boolean"},
                "membership_authority": {"type": "string", "minLength": 1}},
            "required": ["repo_commit", "raw_paths", "raw_sha256", "raw_git_blob_oids",
                         "acquisition_ids", "config_hash",
                         "generator_version", "artifact_role", "release_eligible",
                         "membership_authority"]},
        "dispersion": {
            "type": "object", "additionalProperties": False,
            "properties": {m: {"type": "object", "additionalProperties": False,
                               "properties": {"n_valid": {"type": "integer", "minimum": 0},
                                              "mean_validonly": {"type": ["number", "null"]},
                                              "sd": {"type": ["number", "null"],
                                                     "description": "sample standard deviation (n-1)"},
                                              "min": {"type": ["number", "null"]},
                                              "max": {"type": ["number", "null"]}},
                               "required": ["n_valid", "mean_validonly", "sd", "min", "max"]}
                           for m in METRICS},
            "required": METRICS},
    })
    required = (["test_id", "kind", "name", "set", "measurement_cohort_id", "runs_used", "calc_version", "quality_flags",
                 "intake_review_notices", "null_reasons", "provenance", "dispersion"]
                + METADATA_FIELDS + METRICS)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "https://unrealkeyboards.com/dome-lab/schemas/bench_test.v42.epoch2.json",
            "title": "Dome Lab bench test record (metrics-v4.2)",
            "type": "object", "additionalProperties": False,
            "properties": props,
            "required": sorted(set(required)),
            "not": {"anyOf": [{"required": [k]} for k in LEGACY]},
            "x-method-config-hash": config_hash(), "x-generator-version": __version__,
            "x-evidence-metadata-contract": "epoch-metadata-v1"}


def validate_records(records, schema):
    """Every generated record must validate; generation fails before writing.

    Also enforces the cross-field and null relationships the schema cannot
    express. Each metric's nullity is checked against ITS OWN reason; a null in
    one metric never forces a null in another.
    """
    import jsonschema
    v = jsonschema.Draft202012Validator(schema)
    errs = []
    for r in records:
        rid = r.get("test_id") or r.get("set")
        for e in v.iter_errors(r):
            errs.append(f"{rid}: {e.message[:140]}")
        fl = set(r.get("quality_flags", []))
        nr = r.get("null_reasons", {})

        for m in METRICS:
            is_null = r.get(m) is None
            has_reason = m in nr
            if is_null and m not in NULL_REASONS:
                errs.append(f"{rid}: {m} is null but is not a nullable metric")
                continue
            if is_null and not has_reason:
                errs.append(f"{rid}: null {m} lacks a metric-specific null reason")
            if has_reason and not is_null:
                errs.append(f"{rid}: non-null {m} carries null reason {nr[m]!r}")
            if has_reason and nr[m] not in NULL_REASONS.get(m, []):
                errs.append(f"{rid}: null reason {nr[m]!r} is not permitted for {m}")
            if has_reason and nr[m] not in fl:
                errs.append(f"{rid}: null reason {nr[m]} for {m} not present in quality_flags")

        # ---- mechanically coherent null states -----------------------------
        # travel and full-stroke work are mechanically coupled BOTH WAYS: work
        # to a bottom-out onset cannot exist when the onset does not, and an
        # onset that was detected must yield an integral. Step 2.3 enforced only
        # one direction, so "null work with valid travel" validated cleanly.
        tv, fw = r.get("travel_mm"), r.get("full_stroke_press_work_gf_mm")
        if tv is None and fw is not None:
            errs.append(f"{rid}: full-stroke work must be null when travel is null")
        if tv is not None and fw is None:
            errs.append(f"{rid}: force-wall press work cannot be null when travel is numeric "
                        f"(travel_mm={tv!r}) \u2014 a detected force-wall onset has an integral")

        # DROP and DROP TRAVEL are linear differences and therefore retain
        # their defining identities after arithmetic aggregation. SNAP, DROP
        # RATE and NDR are means of per-run nonlinear values: deliberately do
        # not compare them with ratios formed from aggregate landmarks.
        cf, vf = r.get("collapse_force_gf"), r.get("valley_force_gf")
        cx, vx = r.get("collapse_travel_mm"), r.get("valley_travel_mm")
        dg, dx = r.get("drop_gf"), r.get("drop_travel_mm")
        import math
        if None not in (cf, vf, dg) and not math.isclose(dg, cf - vf, rel_tol=1e-12, abs_tol=1e-10):
            errs.append(f"{rid}: aggregate DROP != aggregate Fc - aggregate Fv")
        if None not in (cx, vx, dx) and not math.isclose(dx, vx - cx, rel_tol=1e-12, abs_tol=1e-10):
            errs.append(f"{rid}: aggregate DROP TRAVEL != aggregate xv - aggregate xc")

        # Every null_reasons key must name a metric that is actually null. The
        # per-metric loop above catches a reason on a non-null CANONICAL metric;
        # this catches a reason keyed to something that is not a metric at all.
        for k in nr:
            if k not in METRICS:
                errs.append(f"{rid}: null_reasons key {k!r} is not a canonical metric")

        # nonpositive_collapse_force may justify a null SNAP only when the
        # collapse-force state actually satisfies that condition.
        cf = r.get("collapse_force_gf")
        if nr.get("snap_pct") == "nonpositive_collapse_force":
            if cf is not None and cf > 0:
                errs.append(f"{rid}: snap_pct is null for 'nonpositive_collapse_force' but "
                            f"collapse_force_gf={cf!r} is positive")
        if r.get("snap_pct") is None and cf is not None and cf > 0 and \
                nr.get("snap_pct") == "nonpositive_collapse_force":
            errs.append(f"{rid}: null SNAP is not justified while collapse force is positive")

        # aggregate_contains_null_run is an aggregation-level observation. It
        # cannot appear when no canonical metric is null.
        if "aggregate_contains_null_run" in fl and not any(r.get(m) is None for m in METRICS):
            errs.append(f"{rid}: quality flag 'aggregate_contains_null_run' is present but "
                        f"no canonical metric is null")

        pv = r.get("provenance", {})
        rp, rs = pv.get("raw_paths", []), pv.get("raw_sha256", [])
        if len(rp) != len(rs):
            errs.append(f"{rid}: raw_paths/raw_sha256 length mismatch")
        if len(set(rp)) != len(rp):
            errs.append(f"{rid}: duplicate raw_paths")
        if len(set(rs)) != len(rs):
            errs.append(f"{rid}: duplicate raw_sha256")
        if r.get("runs_used") != len(rp):
            errs.append(f"{rid}: runs_used != len(raw_paths)")
        if len(set(r.get("quality_flags", []))) != len(r.get("quality_flags", [])):
            errs.append(f"{rid}: duplicate quality_flags")

        # Warning-only RAMP review evidence must bind one-to-one to a retained
        # raw identity and remain completely separate from metric quality/null
        # semantics.  Recompute only evidence algebra here; retention itself is
        # owned by the intake decision manifest.
        notices = r.get("intake_review_notices", [])
        notice_paths = [notice.get("raw_path") for notice in notices]
        notice_hashes = [notice.get("sha256") for notice in notices]
        notice_runs = [notice.get("run") for notice in notices]
        if len(set(notice_paths)) != len(notice_paths):
            errs.append(f"{rid}: duplicate intake review notice raw_path")
        if len(set(notice_hashes)) != len(notice_hashes):
            errs.append(f"{rid}: duplicate intake review notice sha256")
        if len(set(notice_runs)) != len(notice_runs):
            errs.append(f"{rid}: duplicate intake review notice run")
        retained_identity = dict(zip(rp, rs))
        for notice in notices:
            raw_path = notice.get("raw_path")
            if raw_path not in retained_identity:
                errs.append(f"{rid}: intake review notice does not bind a retained raw_path")
            elif retained_identity[raw_path] != notice.get("sha256"):
                errs.append(f"{rid}: intake review notice hash does not match retained provenance")
            if notice.get("run") != str(raw_path).rsplit("/", 1)[-1]:
                errs.append(f"{rid}: intake review notice run/raw_path mismatch")
            evidence = [
                notice.get("ramp_gf_per_mm"),
                notice.get("retained_median_gf_per_mm"),
                notice.get("signed_deviation_pct"),
                notice.get("absolute_deviation_pct"),
                notice.get("threshold_pct"),
            ]
            if not all(type(value) in (int, float) and math.isfinite(value)
                       for value in evidence):
                errs.append(f"{rid}: intake review evidence must be finite numeric values")
                continue
            ramp, median, signed, absolute, threshold = evidence
            expected_signed = 100.0 * (ramp - median) / abs(median)
            if not math.isclose(signed, expected_signed, rel_tol=1e-12, abs_tol=1e-10):
                errs.append(f"{rid}: intake review signed deviation is inconsistent")
            if not math.isclose(absolute, abs(signed), rel_tol=1e-12, abs_tol=1e-10):
                errs.append(f"{rid}: intake review absolute deviation is inconsistent")
            if absolute <= threshold or math.isclose(
                absolute, threshold, rel_tol=1e-12, abs_tol=1e-12
            ):
                errs.append(f"{rid}: intake review does not exceed its strict threshold")
        if notices and pv.get("artifact_role") == "development_preview":
            errs.append(f"{rid}: development preview cannot publish applied intake reviews")
    if errs:
        raise RuntimeError("record validation failed:\n  " + "\n  ".join(errs[:20]))
    return True
