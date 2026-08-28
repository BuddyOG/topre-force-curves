"""metrics-v4.2 calculation core. Pure functions; no I/O side effects.

The Python implementation is normative. The generated viewer contains one
explicit reference implementation whose edge cases are tested against this
module; production viewer and picker scalars always come from generated
canonical records.
"""
import hashlib, json, os

DIVERGENCES = []

PER_RUN_AUDIT_FIELDS = (
    "force_wall_travel_mm", "force_wall_found",
    "steepest_drop_start_mm", "steepest_drop_end_mm",
    "ramp_baseline_force_gf", "ramp_x10_mm", "ramp_x90_mm",
    "ramp_x10_cross_count", "ramp_x90_cross_count",
    "ramp_x10_eligible_cross_count", "ramp_x90_eligible_cross_count",
    "ramp_band_sample_count", "ramp_band_complete",
)

def _load_config():
    """Explicit UTF-8 read (Step 2.3.1).

    Step 2.3 declared a UTF-8 policy but loaded method_config.json through a
    bare open(), so the authoritative configuration was decoded with the host's
    preferred encoding. The old regex-based source check could not see the call
    because it was nested inside json.load(open(...)).
    """
    path = os.path.join(os.path.dirname(__file__), "config", "method_config.json")
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return json.load(fh)


_CFG = _load_config()
def config(): return _CFG
def coherence_contract(): return _CFG["per_run_coherence"]
def config_hash():
    return hashlib.sha256(json.dumps(_CFG, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def parse_run(text):
    """Raw CSV -> column dict. Strict: exact-header check, malformed rows and
    nonfinite tokens are counted (never silently discarded), values never mutated."""
    import math
    n_expected = len(_CFG["acquisition"]["expected_header"])
    lines = [l for l in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if l.strip()]
    hdr = [h.strip() for h in lines[0].split(",")] if lines else []
    header_exact = hdr == _CFG["acquisition"]["expected_header"]
    rows, bad, nonfinite, width = [], 0, 0, 0
    for l in lines[1:]:
        p = l.split(",")
        # Step 2.3.1: EXACT field count. Step 2.3 tested `len(p) < 5` and then
        # sliced p[:5], so a six-column row was silently truncated and accepted
        # as valid. Neither missing nor extra fields may pass, and no field may
        # be empty: an empty numeric column is missing data, not a zero.
        if len(p) != n_expected:
            bad += 1; width += 1; continue
        if any(v.strip() == "" for v in p):
            bad += 1; continue
        try:
            vals = tuple(float(v) for v in p)
        except ValueError:
            bad += 1; continue
        if any(not math.isfinite(v) for v in vals):
            nonfinite += 1; continue
        rows.append(vals)
    M, S, X, R, F = (list(c) for c in zip(*rows)) if rows else ([], [], [], [], [])
    return {"headers": hdr, "header_exact": header_exact, "millis": M, "steps": S,
            "x": X, "raw": R, "F": F, "bad_rows": bad, "nonfinite": nonfinite,
            "field_count_violations": width, "expected_fields": n_expected}

def split_press_return(x, F):
    """First occurrence of max Travel ends press; the shared turnaround sample
    also begins return (matches the release viewer)."""
    im = 0
    for i in range(1, len(x)):
        if x[i] > x[im]: im = i
    return (x[:im + 1], F[:im + 1]), (x[im:], F[im:]), im

def moving_avg(F, k):
    n = len(F); h = k // 2; out = [0.0] * n
    for i in range(n):
        lo, hi = max(0, i - h), min(n - 1, i + h)
        out[i] = sum(F[lo:hi + 1]) / (hi - lo + 1)
    return out

def _interp(xs, ys, xq):
    """Piecewise-linear interpolant on the recorded knots (monotonic xs assumed)."""
    if xq <= xs[0]: return ys[0]
    if xq >= xs[-1]: return ys[-1]
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= xq: lo = mid
        else: hi = mid
    if xs[hi] == xs[lo]: return ys[lo]
    t = (xq - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + t * (ys[hi] - ys[lo])

def _trapz_to(x, F, endpoint):
    """Raw-force trapezoid from stroke zero to an interpolated endpoint."""
    if endpoint is None: return None
    W = 0.0
    for i in range(1, len(x)):
        if x[i] <= endpoint:
            W += (F[i] + F[i - 1]) / 2.0 * (x[i] - x[i - 1])
        else:
            Fe = _interp(x, F, endpoint)
            W += (Fe + F[i - 1]) / 2.0 * (endpoint - x[i - 1])
            break
    return W


def ramp_metric(x, analysis_force, collapse_index, collapse_force, collapse_travel, ramp_config=None):
    """Calculate ramp-v3-post-seating and return ``(value, flags, audit)``.

    Exposing the event calculation separately makes every coordinate-domain
    boundary directly testable without relying on a synthetic collapse finder.
    """
    from .medians import median_conventional
    r = ramp_config or _CFG["ramp"]
    Fs, pk, Fc, xc, n = analysis_force, collapse_index, collapse_force, collapse_travel, len(x)
    flags = []
    audit = {
        "ramp_baseline_force_gf": None, "ramp_x10_mm": None, "ramp_x90_mm": None,
        "ramp_x10_cross_count": 0, "ramp_x90_cross_count": 0,
        "ramp_x10_eligible_cross_count": 0, "ramp_x90_eligible_cross_count": 0,
        "ramp_band_sample_count": 0, "ramp_band_complete": False,
    }
    xs = r["seating_end_mm"]
    blo, bhi = r["reference_band_low_mm"], r["reference_band_high_mm"]
    tol = r["coordinate_tolerance_mm"]
    band_i = [i for i in range(n) if blo <= x[i] <= bhi]
    band = [Fs[i] for i in band_i]
    audit["ramp_band_sample_count"] = len(band)
    # Coverage is about the press trace spanning the complete reference
    # interval. Recorded samples need not land exactly on either bound.
    complete = bool(band_i and x[0] <= blo + tol and x[-1] >= bhi - tol)
    audit["ramp_band_complete"] = complete
    if not complete:
        flags.append("ramp_baseline_band_incomplete"); return None, flags, audit
    if len(band) < r["minimum_band_samples"]:
        flags.append("ramp_baseline_unavailable"); return None, flags, audit
    Fb = median_conventional(band)
    audit["ramp_baseline_force_gf"] = Fb
    if xc <= bhi + tol:
        flags.append("ramp_reference_band_overlaps_collapse"); return None, flags, audit
    if Fc <= Fb + r["min_rise_gf"]:
        flags.append("ramp_baseline_unavailable"); return None, flags, audit
    T10 = Fb + r["low_fraction"] * (Fc - Fb)
    T90 = Fb + r["high_fraction"] * (Fc - Fb)
    def crossings(T):
        all_cross, eligible = [], []
        for i in range(1, pk + 1):
            if Fs[i - 1] < T <= Fs[i]:
                cx = x[i - 1] + (T - Fs[i - 1]) / (Fs[i] - Fs[i - 1]) * (x[i] - x[i - 1])
                all_cross.append(cx)
                if xs - tol <= cx <= xc + tol:
                    eligible.append(cx)
        return all_cross, eligible
    all10, eligible10 = crossings(T10)
    all90, eligible90 = crossings(T90)
    audit["ramp_x10_cross_count"] = len(all10)
    audit["ramp_x90_cross_count"] = len(all90)
    audit["ramp_x10_eligible_cross_count"] = len(eligible10)
    audit["ramp_x90_eligible_cross_count"] = len(eligible90)
    x10 = eligible10[-1] if eligible10 else None
    x90 = eligible90[-1] if eligible90 else None
    audit["ramp_x10_mm"], audit["ramp_x90_mm"] = x10, x90
    if x10 is None or x90 is None:
        flags.append("ramp_crossing_missing"); return None, flags, audit
    if x10 + tol >= x90:
        flags.append("ramp_event_order_invalid"); return None, flags, audit
    if (x90 - x10) + tol < r["min_span_mm"]:
        flags.append("ramp_span_too_small"); return None, flags, audit
    value = (r["high_fraction"] - r["low_fraction"]) * (Fc - Fb) / (x90 - x10)
    return value, flags, audit

def run_metrics(x, F, grid_conforming=True, return_audit=False):
    """All metrics-v4.2 scalars for one press run. x,F = raw press branch.

    ``return_audit=True`` adds a third return value containing non-headline
    event evidence. The default two-value API is retained for compatibility.

    grid_conforming=False (off-nominal acquisition grid) nulls travel-v3 and
    full-stroke work with grid_nonconforming — quarantine, never a silent respan.
    Tie-breaking: strictly-greater/lesser comparisons keep the earliest index
    among exactly equal peak/valley values."""
    c = _CFG; n = len(x)
    out = {k: None for k in ("collapse_force_gf", "collapse_travel_mm", "valley_force_gf", "valley_travel_mm",
        "snap_pct", "travel_mm", "full_stroke_press_work_gf_mm", "precollapse_work_gf_mm", "drop_gf",
        "drop_travel_mm", "drop_rate_gf_per_mm", "norm_drop_rate_per_mm",
        "steepest_drop_0p10mm_gf_per_mm", "ramp_10_90_gf_per_mm")}
    audit = {k: None for k in PER_RUN_AUDIT_FIELDS}
    audit.update(force_wall_found=False, ramp_x10_cross_count=0, ramp_x90_cross_count=0,
                 ramp_x10_eligible_cross_count=0, ramp_x90_eligible_cross_count=0,
                 ramp_band_sample_count=0, ramp_band_complete=False)
    flags = []
    def done():
        return (out, flags, audit) if return_audit else (out, flags)
    if n < 50:
        flags.append("incomplete_press")
        return done()
    k = c["smoothing"]["k"]
    Fs = moving_avg(F, k)
    cd = c["collapse_detect"]
    lim = int(n * cd["search_fraction"])
    pk, best = -1, -1.0
    for i in range(cd["edge_margin_samples"], lim - cd["edge_margin_samples"]):
        lo, hi = max(0, i - cd["local_max_halfwin_samples"]), min(lim, i + cd["local_max_halfwin_samples"])
        if any(Fs[j] > Fs[i] for j in range(lo, hi)): continue
        fmin = min(Fs[i:min(lim, i + cd["drop_lookahead_samples"])])
        if Fs[i] - fmin > cd["min_prominence_gf"] and Fs[i] > best:
            best, pk = Fs[i], i
    fallback = pk < 0
    if fallback:
        for i in range(lim):
            if Fs[i] > best: best, pk = Fs[i], i
        if pk < 0:
            flags.append("collapse_not_found")
            return done()
        flags += ["collapse_fallback_used", "tactile_event_not_found"]
    Fc, xc = Fs[pk], x[pk]
    vwin = c["valley"]["seed_window_mm"]
    vl, vmin = -1, float("inf")
    for i in range(pk + 1, n):
        if x[i] > xc + vwin: break
        if Fs[i] < vmin: vmin, vl = Fs[i], i
    if vl < 0:
        flags.append("valley_not_found")
        return done()
    tcfg = c["travel"]
    if not grid_conforming:
        flags.append("grid_nonconforming")
    def wall_from(vi):
        if not grid_conforming:
            return None
        # normative: least i strictly after the valley, through i = n-4 inclusive
        for i in range(vi + 1, n - 3):
            if Fs[i] < tcfg["floor_gf"]: continue
            if all(Fs[j + 1] - Fs[j] > tcfg["step_fraction"] * Fs[j] for j in (i, i + 1, i + 2)):
                return i
        return None
    ti = wall_from(vl)
    converged = False
    for _ in range(c["valley"]["fixed_point_max_passes"]):
        stop = ti if ti is not None else n - 1
        v2, m2 = -1, float("inf")
        for i in range(pk + 1, stop + 1):
            if Fs[i] < m2: m2, v2 = Fs[i], i
        if v2 == vl:
            converged = True; break
        vl = v2; ti = wall_from(vl)
    if not converged:
        flags.append("valley_iteration_nonconverged")
    Fv, xv = Fs[vl], x[vl]
    out.update(collapse_force_gf=Fc, collapse_travel_mm=xc, valley_force_gf=Fv, valley_travel_mm=xv)
    if Fc > 0:
        out["snap_pct"] = (Fc - Fv) / Fc * 100.0
    else:
        flags.append("nonpositive_collapse_force")
    if ti is None:
        if grid_conforming:
            flags.append("bottomout_not_found")
    else:
        out["travel_mm"] = x[ti]
        audit["force_wall_travel_mm"] = x[ti]
        audit["force_wall_found"] = True
    out["precollapse_work_gf_mm"] = _trapz_to(x, F, xc)
    out["full_stroke_press_work_gf_mm"] = _trapz_to(x, F, out["travel_mm"]) if out["travel_mm"] is not None else None
    dF, dX = Fc - Fv, xv - xc
    out["drop_gf"], out["drop_travel_mm"] = dF, dX
    if dF <= 0: flags.append("nonpositive_drop")
    if dX <= 0: flags.append("nonpositive_drop_travel")
    if dF > 0 and dX > 0 and Fc > 0:
        out["drop_rate_gf_per_mm"] = dF / dX
        out["norm_drop_rate_per_mm"] = dF / (Fc * dX)
    h = c["steepest_drop"]["window_mm"]
    if dX < h:
        flags.append("drop_travel_below_0p10mm")
    elif dX > 0:
        cand = {xc, xv - h}
        for xx in x[pk:vl + 1]:
            if xc <= xx <= xv - h: cand.add(xx)
            if xc <= xx - h <= xv - h: cand.add(xx - h)
        Ffn = lambda q: _interp(x, Fs, q)
        slopes = [(q, (Ffn(q) - Ffn(q + h)) / h) for q in sorted(cand)]
        # The scalar remains the exact mathematical maximum, preserving the
        # v4.1 value bit-for-bit.  Tolerance affects audit tie selection only:
        # choose the earliest interval indistinguishable from that maximum.
        best_s = max(s for _, s in slopes)
        tie_tol = c["steepest_drop"]["tie_tolerance_gf_per_mm"]
        best_q = next(q for q, s in slopes if best_s - s <= tie_tol)
        out["steepest_drop_0p10mm_gf_per_mm"] = best_s
        audit["steepest_drop_start_mm"] = best_q
        audit["steepest_drop_end_mm"] = best_q + h
    ramp, ramp_flags, ramp_audit = ramp_metric(x, Fs, pk, Fc, xc)
    out["ramp_10_90_gf_per_mm"] = ramp
    flags.extend(ramp_flags)
    audit.update(ramp_audit)
    return done()


def validate_per_run_algebra(metrics, audit=None, flags=(), rel_tol=1e-12, abs_tol=1e-10):
    """Validate the complete per-run metric/null/flag/audit contract.

    This fail-closed gate is intentionally per-run.  It validates shared
    landmark algebra and bidirectional null-domain coherence; nonlinear
    identities are *not* imposed on arithmetic-mean aggregate records.
    """
    import math
    a = audit or {}
    fl = list(flags)
    fset = set(fl)
    contract = coherence_contract()
    terminal_flags = set(contract["terminal_event_flags"])
    wall_null_flags = set(contract["force_wall_null_flags"])
    ramp_null_flags = set(contract["ramp_null_flags"])
    errs = []

    def numeric(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    def close(got, want):
        return numeric(got) and numeric(want) and math.isclose(got, want, rel_tol=rel_tol, abs_tol=abs_tol)

    missing_audit = [k for k in PER_RUN_AUDIT_FIELDS if k not in a]
    if missing_audit:
        errs.append("missing audit fields: " + ",".join(missing_audit))
    if len(fl) != len(fset):
        errs.append("duplicate quality flags")
    for name, value in metrics.items():
        if value is not None and not numeric(value):
            errs.append(f"{name} is not a finite number or null")

    Fc, xc = metrics.get("collapse_force_gf"), metrics.get("collapse_travel_mm")
    Fv, xv = metrics.get("valley_force_gf"), metrics.get("valley_travel_mm")
    collapse_pair = numeric(Fc) and numeric(xc)
    valley_pair = numeric(Fv) and numeric(xv)
    if (Fc is None) != (xc is None):
        errs.append("collapse landmark pair is partial")
    if (Fv is None) != (xv is None):
        errs.append("valley landmark pair is partial")
    if valley_pair and not collapse_pair:
        errs.append("valley landmarks exist without collapse landmarks")
    events_ready = collapse_pair and valley_pair
    terminal_present = fset & terminal_flags

    # Before a complete collapse/valley event, every downstream scalar and
    # audit datum remains null/default and exactly one terminal reason explains
    # why.  This also keeps a partial record from masquerading as a metric-local
    # null such as a missing wall or RAMP crossing.
    if not events_ready:
        if len(terminal_present) != 1:
            errs.append("unavailable collapse/valley stage requires exactly one terminal event flag")
        if any(v is not None for v in metrics.values()):
            errs.append("terminal event failure has non-null downstream metric")
        expected_defaults = {k: None for k in PER_RUN_AUDIT_FIELDS}
        expected_defaults.update(force_wall_found=False, ramp_x10_cross_count=0,
                                 ramp_x90_cross_count=0, ramp_x10_eligible_cross_count=0,
                                 ramp_x90_eligible_cross_count=0, ramp_band_sample_count=0,
                                 ramp_band_complete=False)
        if any(a.get(k) != v for k, v in expected_defaults.items()):
            errs.append("terminal event failure has non-default audit evidence")
        if fset & (wall_null_flags | ramp_null_flags | {"drop_travel_below_0p10mm"}):
            errs.append("metric-local null flag leaked into terminal event failure")
        if errs:
            raise RuntimeError("per-run algebra validation failed: " + "; ".join(errs))
        return True

    if terminal_present:
        errs.append("terminal event flag present with complete landmarks")
    dF, dX = Fc - Fv, xv - xc
    if not close(metrics.get("drop_gf"), dF):
        errs.append("DROP != Fc - Fv")
    if not close(metrics.get("drop_travel_mm"), dX):
        errs.append("DROP TRAVEL != xv - xc")
    if not numeric(metrics.get("precollapse_work_gf_mm")):
        errs.append("complete collapse event requires numeric pre-collapse work")

    # The three domain flags are exact declarations, not merely permissible
    # explanations that may leak onto an otherwise numeric result.
    for flag, condition in (("nonpositive_collapse_force", Fc <= 0),
                            ("nonpositive_drop", dF <= 0),
                            ("nonpositive_drop_travel", dX <= 0)):
        if (flag in fset) != condition:
            errs.append(f"{flag} does not match its declared domain")
    snap = metrics.get("snap_pct")
    if Fc > 0:
        if not close(snap, 100.0 * dF / Fc):
            errs.append("SNAP != 100*DROP/Fc")
    elif snap is not None:
        errs.append("SNAP must be null for nonpositive Fc")
    dr, ndr = metrics.get("drop_rate_gf_per_mm"), metrics.get("norm_drop_rate_per_mm")
    rates_defined = dF > 0 and dX > 0 and Fc > 0
    if rates_defined:
        if not close(dr, dF / dX):
            errs.append("DROP RATE != DROP/DROP TRAVEL")
        if not close(ndr, dF / (Fc * dX)):
            errs.append("NDR != DROP RATE/Fc")
    elif dr is not None or ndr is not None:
        errs.append("DROP RATE/NDR must be null outside their positive domain")

    # Force-wall evidence, travel and full-stroke work are all-or-none.  A
    # reached but absent event carries exactly one wall-specific reason.
    wall_found = a.get("force_wall_found")
    wall = a.get("force_wall_travel_mm")
    travel = metrics.get("travel_mm")
    full_work = metrics.get("full_stroke_press_work_gf_mm")
    wall_reasons = fset & wall_null_flags
    if type(wall_found) is not bool:
        errs.append("force_wall_found must be boolean")
    elif wall_found:
        if not (numeric(wall) and numeric(travel) and numeric(full_work)):
            errs.append("found force wall requires numeric wall/travel/full-work")
        elif not close(travel, wall):
            errs.append("travel != audited force-wall position")
        if wall_reasons:
            errs.append("force-wall null reason present for numeric wall")
    else:
        if any(v is not None for v in (wall, travel, full_work)):
            errs.append("absent force wall requires null wall/travel/full-work")
        if len(wall_reasons) != 1:
            errs.append("absent force wall requires exactly one force-wall null flag")

    # The fixed-span steepest-drop scalar and its audited endpoints share one
    # exact domain: the collapse-to-valley travel must contain the full window.
    steep = metrics.get("steepest_drop_0p10mm_gf_per_mm")
    s0, s1 = a.get("steepest_drop_start_mm"), a.get("steepest_drop_end_mm")
    h = _CFG["steepest_drop"]["window_mm"]
    below_window = dX < h
    if ("drop_travel_below_0p10mm" in fset) != below_window:
        errs.append("drop_travel_below_0p10mm does not match the steepest-drop domain")
    if below_window:
        if steep is not None or s0 is not None or s1 is not None:
            errs.append("sub-window drop travel requires null steepest-drop scalar/audit")
    else:
        if not (numeric(steep) and numeric(s0) and numeric(s1)):
            errs.append("defined steepest drop requires numeric scalar and audit endpoints")
        else:
            tol = _CFG["ramp"]["coordinate_tolerance_mm"]
            if not close(s1 - s0, h):
                errs.append("steepest-drop audit interval != configured window")
            if not (xc - tol <= s0 <= xv - h + tol and xc + h - tol <= s1 <= xv + tol):
                errs.append("steepest-drop audit interval outside [xc,xv]")

    # RAMP audit counters and coordinates have a bidirectional relationship to
    # the metric and its *one* method-local null reason.
    r = _CFG["ramp"]
    tol = r["coordinate_tolerance_mm"]
    count_names = ("ramp_band_sample_count", "ramp_x10_cross_count", "ramp_x90_cross_count",
                   "ramp_x10_eligible_cross_count", "ramp_x90_eligible_cross_count")
    counts = {k: a.get(k) for k in count_names}
    for name, value in counts.items():
        if type(value) is not int or value < 0:
            errs.append(f"{name} must be a nonnegative integer")
    if all(type(v) is int and v >= 0 for v in counts.values()):
        if counts["ramp_x10_eligible_cross_count"] > counts["ramp_x10_cross_count"]:
            errs.append("eligible x10 crossings exceed all x10 crossings")
        if counts["ramp_x90_eligible_cross_count"] > counts["ramp_x90_cross_count"]:
            errs.append("eligible x90 crossings exceed all x90 crossings")
    complete = a.get("ramp_band_complete")
    if type(complete) is not bool:
        errs.append("ramp_band_complete must be boolean")
    Fb, x10, x90 = (a.get("ramp_baseline_force_gf"), a.get("ramp_x10_mm"), a.get("ramp_x90_mm"))
    e10, e90 = counts.get("ramp_x10_eligible_cross_count"), counts.get("ramp_x90_eligible_cross_count")
    if type(e10) is int and ((x10 is None) != (e10 == 0)):
        errs.append("x10 coordinate/eligible-count mismatch")
    if type(e90) is int and ((x90 is None) != (e90 == 0)):
        errs.append("x90 coordinate/eligible-count mismatch")
    for name, coordinate in (("x10", x10), ("x90", x90)):
        if coordinate is not None and (not numeric(coordinate) or
                not (r["seating_end_mm"] - tol <= coordinate <= xc + tol)):
            errs.append(f"RAMP {name} outside configured crossing domain")
    ramp = metrics.get("ramp_10_90_gf_per_mm")
    ramp_reasons = fset & ramp_null_flags
    if ramp is not None:
        if ramp_reasons:
            errs.append("RAMP null reason present for numeric RAMP")
        band_count = counts.get("ramp_band_sample_count")
        if not complete or type(band_count) is not int or band_count < r["minimum_band_samples"]:
            errs.append("numeric RAMP lacks complete baseline-band evidence")
        if not (numeric(Fb) and numeric(x10) and numeric(x90)):
            errs.append("numeric RAMP lacks audited Fb/x10/x90")
        else:
            if not (xc > r["reference_band_high_mm"] + tol and Fc > Fb + r["min_rise_gf"]):
                errs.append("numeric RAMP violates reference-band/rise preconditions")
            if not (x10 + tol < x90 and (x90 - x10) + tol >= r["min_span_mm"]):
                errs.append("numeric RAMP event order/span invalid")
            else:
                expected = (r["high_fraction"] - r["low_fraction"]) * (Fc - Fb) / (x90 - x10)
                if not close(ramp, expected):
                    errs.append("RAMP != configured rise/span")
    else:
        if len(ramp_reasons) != 1:
            errs.append("null RAMP requires exactly one approved RAMP null reason")
        elif len(ramp_reasons) == 1:
            reason = next(iter(ramp_reasons))
            count = counts.get("ramp_band_sample_count", -1)
            crossing_counts_zero = all(counts.get(k) == 0 for k in count_names if k != "ramp_band_sample_count")
            if reason == "ramp_baseline_band_incomplete":
                if complete or Fb is not None or x10 is not None or x90 is not None or not crossing_counts_zero:
                    errs.append("band-incomplete RAMP reason contradicts audit evidence")
            elif reason == "ramp_baseline_unavailable":
                too_few = complete and type(count) is int and count < r["minimum_band_samples"] and Fb is None
                low_rise = (complete and type(count) is int and count >= r["minimum_band_samples"] and
                            numeric(Fb) and Fc <= Fb + r["min_rise_gf"])
                if (not (too_few or low_rise) or x10 is not None or x90 is not None or
                        not crossing_counts_zero):
                    errs.append("baseline-unavailable RAMP reason contradicts audit evidence")
            elif reason == "ramp_reference_band_overlaps_collapse":
                if not (complete and type(count) is int and count >= r["minimum_band_samples"] and
                        numeric(Fb) and xc <= r["reference_band_high_mm"] + tol and
                        x10 is None and x90 is None and crossing_counts_zero):
                    errs.append("band-overlap RAMP reason contradicts audit evidence")
            elif reason == "ramp_crossing_missing":
                prerequisites = (complete and type(count) is int and count >= r["minimum_band_samples"] and
                                  numeric(Fb) and xc > r["reference_band_high_mm"] + tol and
                                  Fc > Fb + r["min_rise_gf"])
                if not prerequisites or (x10 is not None and x90 is not None):
                    errs.append("crossing-missing RAMP reason contradicts audit evidence")
            elif reason == "ramp_event_order_invalid":
                if not (numeric(x10) and numeric(x90) and x10 + tol >= x90):
                    errs.append("event-order RAMP reason contradicts audit evidence")
            elif reason == "ramp_span_too_small":
                if not (numeric(x10) and numeric(x90) and x10 + tol < x90 and
                        (x90 - x10) + tol < r["min_span_mm"]):
                    errs.append("span-too-small RAMP reason contradicts audit evidence")

    if errs:
        raise RuntimeError("per-run algebra validation failed: " + "; ".join(errs))
    return True
