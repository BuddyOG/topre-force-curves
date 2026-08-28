"""Diff-vs-release and median reports, generated from executable logic."""
METRICS = ["collapse_force_gf", "collapse_travel_mm", "valley_force_gf", "valley_travel_mm", "snap_pct",
           "travel_mm", "full_stroke_press_work_gf_mm", "precollapse_work_gf_mm", "drop_gf", "drop_travel_mm",
           "drop_rate_gf_per_mm", "norm_drop_rate_per_mm", "steepest_drop_0p10mm_gf_per_mm", "ramp_10_90_gf_per_mm"]
POSITION = {"collapse_travel_mm", "valley_travel_mm", "travel_mm", "drop_travel_mm"}
IDENTICAL_TOL = 1e-9  # disclosed tolerance for "identical"

def _dp(v):
    s = repr(float(v))
    return len(s.split(".")[1]) if "." in s else 0

def _is_release_rounding(staged, release):
    for d in range(0, _dp(release) + 1):
        if round(staged, d) == release: return True
    return False

def diff_vs_release_md(records, release):
    rel = {t["test_id"]: t for t in release}
    counts = {"identical": 0, "release-rounding": 0, "median-change": 0,
              "small legacy position delta \u2014 cause unadjudicated": 0, "REVIEW": 0}
    lines = ["# Generated-output diff — staged metrics-v4.2 vs current release artifacts", "",
        f"Classes (generated programmatically; 'identical' tolerance {IDENTICAL_TOL:g}):",
        "`release-rounding` — the staged full-precision value rounds back to the stored release",
        "value at (or below) its stored precision. Full-fleet JS/Python parity shows the two work",
        "implementations are exactly equal on this fleet (endpoints fall on recorded knots), so",
        "endpoint interpolation is a forward-looking safeguard, not a cause of current changes.",
        "`median-change` — runfilter-v1.1 conventional-median membership change (Topre_45g only).",
        "`small legacy position delta \u2014 cause unadjudicated` — a position aggregate differs from",
        "the stored release value by <=0.003 mm. Step 2.2 labelled this `release-history drift`,",
        "asserting a historical cause. No historical provenance proves that cause, so the label is",
        "now neutral: the delta is observed, its origin is not adjudicated. Per-run JS/Python parity",
        "is exact today; staged values are the corrected candidates.", ""]
    for r in records:
        old = rel.get(r.get("test_id"))
        if not old: continue
        hdr = False
        for m in METRICS:
            ov, nv = old.get(m), r.get(m)
            if ov is None and nv is None: continue
            if ov is None or nv is None:
                cls = "REVIEW (availability-change)"
            elif abs(nv - ov) < IDENTICAL_TOL:
                cls = "identical"
            elif old["set"] == "Topre_45g":
                cls = "median-change"
            elif _is_release_rounding(nv, ov):
                cls = "release-rounding"
            elif m in POSITION and abs(nv - ov) <= 0.003:
                cls = "small legacy position delta \u2014 cause unadjudicated"
            else:
                cls = f"REVIEW (|d|={abs(nv - ov):.4g})"
            counts[cls.split(" (")[0]] = counts.get(cls.split(" (")[0], 0) + 1
            if cls not in ("identical", "release-rounding"):
                if not hdr:
                    lines.append(f"## {old.get('name')} ({r['set']}, {r['test_id']})"); hdr = True
                lines.append(f"- {m}: {ov} -> {nv!r}  [{cls}]")
    lines += ["", "Summary: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + "."]
    return "\n".join(lines) + "\n"

def median_md(median_cmp):
    L = ["# Conventional vs legacy median — runfilter centre comparison", "",
         "runfilter-v1.1 adopts `median_conventional` (even n: average of the middle pair);",
         "`median_upper_middle_legacy` (sorted[n//2]) is retained for this comparison only.",
         "Centres, per-run deviations and threshold decisions are in median_comparison.json.", "",
         "| Set | n | Fc centre conv / legacy (gf) | xc centre conv / legacy (mm) | membership change |",
         "|---|---|---|---|---|"]
    for c in median_cmp:
        ch = "**yes**" if c["kept_conventional"] != c["kept_legacy"] else "no"
        L.append(f"| {c['set']} | {c['n']} | {c['centre_conventional']['fc_gf']:.4f} / "
                 f"{c['centre_legacy']['fc_gf']:.4f} | {c['centre_conventional']['xc_mm']:.4f} / "
                 f"{c['centre_legacy']['xc_mm']:.4f} | {ch} |")
    L += ["", "## Membership changes"]
    for c in median_cmp:
        if c["kept_conventional"] != c["kept_legacy"]:
            ex = sorted(set(c["kept_legacy"]) - set(c["kept_conventional"]))
            L += [f"### {c['set']}", f"Conventional centre excludes: {ex}",
                  "Per-run threshold decisions:"]
            for d in c["per_run_deviations"]:
                L.append(f"- {d['run']}: Fc dev {d['dev_fc_gf']:.4f} gf, xc dev {d['dev_xc_mm']:.4f} mm -> "
                         f"{'retained' if d['retained_conventional'] else d['decision']}")
            L.append("Full-precision canonical aggregate changes:")
            for m in METRICS:
                a, b = c["agg_legacy"][m], c["agg_conventional"][m]
                if a is not None and b is not None and abs(a - b) > 1e-12:
                    L.append(f"- {m}: {a!r} -> {b!r}")
    L += ["", "Only even-run sets can differ between conventions."]
    return "\n".join(L) + "\n"
