"""Every derived data pack the viewer/picker/repository need, generated
deterministically from generated retained runs + staged records.

Retained membership from the declared intake policy is the sole source for every
scalar, curve, run count, press trace and return trace.

Stroke pack encoding is the exact inverse of the viewer's unpackStroke():
x[i]=(x0+i)/200, F=cumsum(df)/100. Both press ("p") and return ("r") branches
are packed so the offline fallback renders complete hysteresis loops.

Step 2.3 corrections
--------------------
* Curve contract. MINI_CURVES stores samples ONCE as {x, F} (uppercase F, the
  viewer's convention). Every scalar landmark and metric comes from the
  generated TESTS record, keyed by set identity. Step 2.2 emitted
  lowercase {x, f} with no scalars at all while the picker read c.F, c.cF,
  c.tv, c.cx, c.vx, c.vF and eleven more, so prevCurveSVG() and benchValsHTML()
  both threw TypeError on every set.
* Averaging. Python and JavaScript now share one definition (curves.py); the
  JS body is generated from it. Seven sets previously differed by one return
  sample between offline and online rendering.
* SNAPSHOT_TESTS is generated from retained record snapshots instead of being a
  stale hand-maintained duplicate that displayed 177 gf.mm against 176.
* Picker exclusions come from the exclusion registry. The hardcoded
  Sony_BKE_Gray_02 RETEST set is removed.
* The picker's live "fetch every raw run, average, analyze the averaged curve"
  path is retired. It was a competing calculator.
* Prohibited copy is replaced everywhere and then re-scanned, not replaced once.
"""
import base64, hashlib, json, math, re, os
from .curves import grid_average, js_average_source
from .reference_js import js_reference_analyzer_source
from .core import config
from . import perception, prose


FONT_ASSETS = {
    "@@INTER_LATIN_WOFF2@@": (
        "inter-latin.woff2",
        "3100e775e8616cd2611beecfa23a4263d7037586789b43f035236a2e6fbd4c62",
    ),
    "@@IBM_PLEX_MONO_500_LATIN_WOFF2@@": (
        "ibm-plex-mono-500-latin.woff2",
        "01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22",
    ),
    "@@IBM_PLEX_MONO_600_LATIN_WOFF2@@": (
        "ibm-plex-mono-600-latin.woff2",
        "0d1f0b8d0722224e32e9f28261bdc86c79115be73444ae5eceb73976a1bcdf83",
    ),
}


def _embed_release_fonts(html):
    """Embed hash-pinned OFL font subsets into the generated single file."""
    root = os.path.join(
        os.path.dirname(__file__), "release_reference", "third_party", "fonts"
    )
    for marker, (filename, expected_sha256) in FONT_ASSETS.items():
        if html.count(marker) != 1:
            raise RuntimeError(f"viewer font marker is missing or ambiguous: {marker}")
        path = os.path.join(root, filename)
        with open(path, "rb") as handle:
            payload = handle.read()
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                f"viewer font asset hash mismatch for {filename}: {actual_sha256}"
            )
        html = html.replace(marker, base64.b64encode(payload).decode("ascii"))
    if "fonts.googleapis.com" in html or "fonts.gstatic.com" in html:
        raise RuntimeError("viewer retains a remote font dependency")
    return html


def _grid_average(runs, rule="majority"):
    """Kept as the module-local name; delegates to the shared authority."""
    return grid_average(runs, rule)


def pack_stroke(keys, F):
    x0 = keys[0]
    q = [round(f * 100) for f in F]
    df = [q[0]] + [q[i] - q[i - 1] for i in range(1, len(q))]
    return {"x0": x0, "df": df}


def _branches(runs):
    """Press and return traces of the RETAINED runs only. The return branch is
    re-sorted ascending in x so pack encoding matches the press convention."""
    press, ret = [], []
    for r in runs:
        im = r["split_index"]
        with open(r["path"], "rb") as f:
            raw = f.read().decode("utf-8-sig", "replace")
        lines = [l for l in raw.replace("\r\n", "\n").split("\n") if l.strip()][1:]
        x, F = [], []
        for l in lines:
            p = l.split(",")
            if len(p) >= 5:
                try:
                    x.append(float(p[2])); F.append(float(p[4]))
                except ValueError:
                    pass
        press.append((x[:im + 1], F[:im + 1]))
        pair = sorted(zip(x[im:], F[im:]))
        ret.append(([a for a, _ in pair], [b for _, b in pair]))
    return press, ret


def _pbase(p):
    return p.split("/")[-1]


R1 = lambda v: None if v is None else round(v, 1)
R3 = lambda v: None if v is None else round(v, 3)
R0 = lambda v: None if v is None else int(round(v))
RAW = lambda v: v

# Review and public-release identities share the exact same frozen scientific
# inputs.  The selected profile changes presentation/release identity only;
# data, retained membership, metrics and perception equations remain invariant.
_VIEWER_PROFILE_COMMON = {
    "data_epoch_prefix": "canonical-",
    "subjective_pilot_id": "subjective-pilot-v1",
    "subjective_pilot_workbook_sha256": (
        "d4bbaad6831ccab1003bcc7e2974ef7100ee32e083fa88f27d468e64d7a323d0"
    ),
    "perception_score_version": perception.MODEL["version"],
    # The shared press-displacement axis normally ends at 4.0 mm.  The viewer
    # expands it in 0.5 mm steps only when a released force-wall marker needs
    # the additional room; recorded turnaround/sample length does not expand it.
    "axis_data_floor_mm": 4.0,
}

VIEWER_BUILD_PROFILES = {
    "review": {
        **_VIEWER_PROFILE_COMMON,
        "mode": "review",
        "presentation_role": "review_candidate",
        "release_eligible": False,
        "bench_build": "fc-3.5-review.1",
    },
    "release": {
        **_VIEWER_PROFILE_COMMON,
        "mode": "release",
        "presentation_role": "public_release",
        "release_eligible": True,
        "bench_build": "fc-3.5",
    },
}

# Backward-compatible review identity for callers/tests that inspect the
# historical constant directly. New generation calls select a named profile.
VIEWER_BUILD_PROFILE = VIEWER_BUILD_PROFILES["review"]

PARTS_LIBRARY_BUILD_PROFILES = {
    "review": {
        "library_build": "lib-6.1-review.1",
        "release_eligible": False,
    },
    "release": {
        "library_build": "lib-6.1",
        "release_eligible": True,
    },
}


def viewer_build_profile(name):
    try:
        return VIEWER_BUILD_PROFILES[name]
    except KeyError as exc:
        raise RuntimeError(f"unknown viewer build profile: {name!r}") from exc


RAMP_REVIEW_FIELDS = (
    "ramp_gf_per_mm",
    "retained_median_gf_per_mm",
    "signed_deviation_pct",
    "absolute_deviation_pct",
    "threshold_pct",
)


def _ramp_reviews_for_viewer(intake_manifest, canonical_runs, records):
    """Copy and cross-bind warning-only RAMP evidence for the review viewer."""
    if not isinstance(intake_manifest, dict):
        raise RuntimeError("viewer build requires the computed intake decision manifest")
    top_summary = intake_manifest.get("ramp_review_summary")
    if not isinstance(top_summary, dict) or set(top_summary) != {
        "set_count", "run_count", "review_required"
    }:
        raise RuntimeError("viewer build requires the exact intake RAMP summary contract")

    reviews_by_set = {}
    for set_decision in intake_manifest.get("sets", []):
        set_name = set_decision.get("set")
        set_summary = set_decision.get("ramp_review_summary")
        if not isinstance(set_summary, dict) or set(set_summary) != {
            "numeric_retained_count", "retained_median_gf_per_mm",
            "review_count", "review_required",
        }:
            raise RuntimeError(f"viewer build has malformed RAMP summary for {set_name}")
        reviews = []
        for run_decision in set_decision.get("runs", []):
            required = run_decision.get("ramp_review_required")
            evidence = run_decision.get("ramp_review")
            if type(required) is not bool or required != (evidence is not None):
                raise RuntimeError(
                    f"viewer build has inconsistent RAMP review decision for "
                    f"{set_name}/{run_decision.get('run')}"
                )
            if not required:
                continue
            if not run_decision.get("retained"):
                raise RuntimeError("RAMP review cannot attach to an unretained run")
            if not isinstance(evidence, dict) or set(evidence) != set(RAMP_REVIEW_FIELDS):
                raise RuntimeError("viewer build has malformed RAMP review evidence")
            run_name = run_decision.get("run")
            if set_name not in canonical_runs or run_name not in canonical_runs[set_name]:
                raise RuntimeError(
                    "viewer RAMP review identity is absent from generated retained membership"
                )
            reviews.append({
                "type": "ramp_repeatability_review",
                "decision": "ACCEPT + RAMP REVIEW",
                "run": run_name,
                "raw_path": run_decision.get("raw_path"),
                "sha256": run_decision.get("sha256"),
                **{field: evidence[field] for field in RAMP_REVIEW_FIELDS},
            })
        if set_summary["review_count"] != len(reviews):
            raise RuntimeError(f"viewer RAMP review count mismatch for {set_name}")
        if set_summary["review_required"] != bool(reviews):
            raise RuntimeError(f"viewer RAMP review boolean mismatch for {set_name}")
        if reviews:
            reviews_by_set[set_name] = reviews

    review_count = sum(len(reviews) for reviews in reviews_by_set.values())
    if top_summary["run_count"] != review_count:
        raise RuntimeError("viewer RAMP run count disagrees with intake manifest")
    if top_summary["set_count"] != len(reviews_by_set):
        raise RuntimeError("viewer RAMP set count disagrees with intake manifest")
    if top_summary["review_required"] != bool(review_count):
        raise RuntimeError("viewer RAMP review boolean disagrees with intake manifest")
    if reviews_by_set and not intake_manifest.get("membership_applied_to_outputs"):
        raise RuntimeError("viewer cannot publish intake RAMP reviews without applied membership")

    for record in records:
        expected = sorted(
            reviews_by_set.get(record["set"], []), key=lambda item: item["raw_path"]
        )
        actual = sorted(
            record.get("intake_review_notices", []), key=lambda item: item["raw_path"]
        )
        if actual != expected:
            raise RuntimeError(
                f"viewer RAMP evidence disagrees with generated record {record.get('test_id')}"
            )
    return reviews_by_set

# Generated scalar key -> (record field, rounding). These land on the generated
# TESTS/VTESTS records, which are the sole scalar authority for both surfaces.
VT_METRIC = {"cg": ("collapse_force_gf", R1), "cx": ("collapse_travel_mm", R3),
             "sn": ("snap_pct", R1), "en": ("full_stroke_press_work_gf_mm", R0),
             "tv": ("travel_mm", R3), "vF": ("valley_force_gf", R1), "vx": ("valley_travel_mm", R3),
             "pcw": ("precollapse_work_gf_mm", R0), "dg": ("drop_gf", R1), "dxd": ("drop_travel_mm", R3),
             "dr": ("drop_rate_gf_per_mm", R1), "ndr": ("norm_drop_rate_per_mm", R3),
             "sd": ("steepest_drop_0p10mm_gf_per_mm", R1), "rp": ("ramp_10_90_gf_per_mm", R1)}

# The viewer's generated records are the numeric authority.  Keep their JSON
# numbers at source precision and round only at the final text-formatting
# boundary.  The picker keeps its compact display pack for now.
VIEWER_METRIC = {k: (field, RAW) for k, (field, _rounder) in VT_METRIC.items()}

# lib-5.0 library records: the retired full-stroke work, normalized drop
# rate and drop-travel keys are gone; values stay at source precision and
# round only at the display boundary (template formatters).
VT_METRIC_V2 = {k: (field, RAW) for k, (field, _rounder) in VT_METRIC.items()
                if k not in ("en", "ndr", "dxd")}


# ------------------------------------------------------------------ blobs
def _extract_blob(html, name):
    m = re.search(name + r"\s*=\s*", html)
    if not m:
        raise RuntimeError(f"blob {name} not found")
    i = m.end()
    open_c = html[i]; close_c = "}" if open_c == "{" else "]"
    depth, j, instr = 0, i, False
    while True:
        c = html[j]
        if instr:
            if c == "\\": j += 2; continue
            if c == '"': instr = False
        elif c == '"': instr = True
        elif c == open_c: depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0: break
        j += 1
    return i, j + 1, json.loads(html[i:j + 1])


def _inline_json(payload):
    """Serialize JSON safely inside a classic script element.

    Escaping '<' and '&' prevents data from terminating the script element or
    being reinterpreted as HTML. U+2028/U+2029 are escaped for older JS
    parsers. The decoded JavaScript value is unchanged.
    """
    return (json.dumps(payload, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False)
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def _replace_blob(html, name, payload):
    i, j, _ = _extract_blob(html, name)
    return html[:i] + _inline_json(payload) + html[j:]


def _replace_function(html, name, new_source):
    """Replace a whole `function NAME(...){...}` by brace matching.

    Deterministic and verifiable: the target must exist exactly once, and the
    body is located structurally rather than by fragile substring matching.
    """
    pat = re.compile(r"(?:\basync\s+)?function\s+" + re.escape(name) + r"\s*\(")
    hits = list(pat.finditer(html))
    if len(hits) != 1:
        raise RuntimeError(f"function {name}: expected exactly 1 definition, found {len(hits)}")
    start = hits[0].start()
    i = html.index("{", hits[0].end() - 1)
    depth, j, instr, quote, esc = 0, i, False, "", False
    while True:
        c = html[j]
        if instr:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == quote: instr = False
        elif c in "\"'`":
            instr, quote = True, c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    return html[:start] + new_source + html[j + 1:]


def _apply(text, old, new, what):
    if old not in text:
        raise RuntimeError(f"viewer/picker transform target not found: {what}")
    return text.replace(old, new)


# ------------------------------------------ viewer behaviour transforms
OLD_ONLINE = """    const runs=texts.map(parseCSV);
    /* runfilter-v1: exclude runs deviating >1.0 g collapse or >0.10 mm collapse
       position from the batch median before averaging (matches the bench) */
    const allStats=runs.map(r=>analyze(r.press.x,r.press.F));
    const med=a=>{const s=[...a].sort((x,y)=>x-y);return s[s.length>>1];};
    let keep=runs.map((_,i)=>true);
    const ok=allStats.filter(Boolean);
    if(ok.length>=2){
      const mF=med(ok.map(s=>s.Fpeak)), mX=med(ok.map(s=>s.xpeak));
      keep=runs.map((_,i)=>{const st=allStats[i];
        return !!st&&Math.abs(st.Fpeak-mF)<=1.0&&Math.abs(st.xpeak-mX)<=0.10;});
      if(!keep.some(Boolean))keep=runs.map(()=>true);
    }
    const kept=runs.filter((_,i)=>keep[i]);
    const avgPress=averageStrokes(kept.map(r=>r.press));
    const avgRet  =averageStrokes(kept.map(r=>r.ret));
    /* bench methodology: stats are computed per run and averaged.
       Analyzing the averaged curve instead smears the force-wall pattern across
       runs' slightly different wall positions and mis-detects travel on
       shallow-wall (light) domes. */
    const runStats=allStats.filter((st,i)=>st&&keep[i]);
    s.data={runs,avgPress,avgRet,stats:runStats.length?meanStats(runStats):analyze(avgPress.x,avgPress.F)};"""

NEW_ONLINE = """    const runs=texts.map(parseCSV);
    const branchOK=b=>b&&Array.isArray(b.x)&&Array.isArray(b.F)&&b.x.length>=50&&
      b.x.length===b.F.length&&b.x.every(Number.isFinite)&&b.F.every(Number.isFinite);
    if(runs.length!==_files.length||runs.some(r=>!branchOK(r.press)||!branchOK(r.ret)))
      throw new Error("malformed or incomplete pinned run response for "+s.key);
    /* Generated review authority: the fetched list is already restricted to
       generated retained membership, and displayed scalars come from the generated
       record snapshot in BOTH online and offline modes. Raw fetching supplies
       visualization traces only. The legacy in-browser runfilter, the
       upper-middle median, the restore-all fallback and averaged-curve metric
       calculation are all retired from authoritative operation. */
    const avgPress=averageStrokes(runs.map(r=>r.press));
    const avgRet  =averageStrokes(runs.map(r=>r.ret));
    const canonLive=canonStats(s.key,s.record_id);
    if(!canonLive)throw new Error("no generated record snapshot for "+s.key);
    s.data={runs,avgPress,avgRet,stats:canonLive};"""

OLD_FETCH = "const texts=await Promise.all(s.files.map(f=>fetch(RAW(f)).then(r=>{"
NEW_FETCH = ("const _cf=(CANONICAL_RUNS[s.key]||null);"
             "if(!_cf)throw new Error(\"set is not in generated retained membership: \"+s.key);"
             "const _files=s.files.filter(f=>_cf.includes(f.split('/').pop()));"
             "if(_files.length!==_cf.length)throw new Error(\"generated retained-run membership mismatch for \"+s.key);"
             "const texts=await Promise.all(_files.map(f=>fetch(RAW(f)).then(r=>{")

OLD_300 = ("let ti=n-1;\n"
           "  for(let i=vl+1;i<n-1;i++){const dF=(Fs[i+1]-Fs[i-1])/(x[i+1]-x[i-1]);if(dF>300){ti=i;break;}}\n"
           "  const xtravel=x[ti];let E=0;\n"
           "  for(let i=1;i<n;i++){if(x[i]>xtravel)break;E+=(F[i]+F[i-1])/2*(x[i]-x[i-1]);}\n"
           "  return {Fpeak,xpeak,travel:xtravel,E,snap:(Fpeak-Fval)/Fpeak*100};")
NEW_300 = ("let ti=null;\n"
           "  for(let i=vl+1;i<n-3;i++){if(Fs[i]<10)continue;"
           "const ok=j=>(Fs[j+1]-Fs[j])>0.01*Fs[j];if(ok(i)&&ok(i+1)&&ok(i+2)){ti=i;break;}}\n"
           "  /* travel-v3 (step1pct); no wall -> null. Legacy 300 gf/mm slope rule removed. */\n"
           "  const xtravel=ti==null?null:x[ti];let E=null;\n"
           "  if(xtravel!=null){E=0;for(let i=1;i<n;i++){if(x[i]>xtravel)break;E+=(F[i]+F[i-1])/2*(x[i]-x[i-1]);}}\n"
           "  return {Fpeak,xpeak,travel:xtravel,E,snap:(Fpeak-Fval)/Fpeak*100};")


# ------------------------------------------------ picker replacement source
PICKER_CURVE_CONTRACT = """/* ---- Step 2.3 generated curve contract ----------------------------------
   MINI_CURVES holds SAMPLES ONLY, once, as {x:[...],F:[...]}.
   Every scalar landmark and metric comes from the generated TESTS
   record via benchFor(). No scalar authority is duplicated inside MINI_CURVES.
   ------------------------------------------------------------------------ */
const BENCH_BY_SET=(()=>{const m={};for(const t of TESTS){if(t&&t.set&&!(t.set in m))m[t.set]=t;}return m;})();
function benchFor(setName){const k=curveKey(setName);return k?(BENCH_BY_SET[k]||null):null;}
function benchNum(rec,key){const v=rec?rec[key]:null;return (typeof v==="number"&&isFinite(v))?v:null;}"""

PICKER_PREVCURVE = """function prevCurveSVG(setName){
  const c=(typeof MINI_CURVES!=="undefined")?curveFor(setName):null;
  const b=benchFor(setName);
  if(!c||!b||!c.x||!c.F||!c.x.length)return "";
  const cF=benchNum(b,"cg"), cx=benchNum(b,"cx"), tv=benchNum(b,"tv");
  const vF=benchNum(b,"vF"), vx=benchNum(b,"vx");
  if(cF==null||cx==null)return "";
  const W=310,H=180,L=26,B=24,T=14,Rr=8;
  const fm=cF*1.5;                                  /* fit rule: Y max = collapse * 1.5 */
  const xEnd=(tv!=null)?Math.max(tv*1.04,Math.max(...c.x)):Math.max(...c.x);
  const X=x=>L+x/xEnd*(W-L-Rr), Y=f=>H-B-Math.min(f,fm)/fm*(H-B-T);
  const line=c.x.map((x,i)=>`${X(x).toFixed(1)},${Y(c.F[i]).toFixed(1)}`).join(" ");
  let area="";
  if(tv!=null){
    const upto=c.x.map((x,i)=>[x,c.F[i]]).filter(([x])=>x<=tv);
    if(upto.length)area=`M${X(upto[0][0]).toFixed(1)},${(H-B).toFixed(1)} L`+
      upto.map(([x,f])=>`${X(x).toFixed(1)},${Y(f).toFixed(1)}`).join(" L")+
      ` L${X(tv).toFixed(1)},${(H-B).toFixed(1)} Z`;
  }
  let g="";
  g+=`<circle cx="${X(cx).toFixed(1)}" cy="${Y(cF).toFixed(1)}" r="5" fill="#AC53FF"/>`+
     `<text x="${X(cx).toFixed(1)}" y="${(Y(cF)-9).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--ink)" font-family="var(--mono)">Collapse</text>`;
  if(vF!=null&&vx!=null){
    g+=`<circle cx="${X(vx).toFixed(1)}" cy="${Y(vF).toFixed(1)}" r="4.5" fill="#E8892B"/>`+
       `<text x="${X(vx).toFixed(1)}" y="${(Y(vF)+15).toFixed(1)}" text-anchor="middle" font-size="11" fill="#E8892B" font-family="var(--mono)">Valley</text>`;
    const bx=Math.min(X(vx)+16,W-Rr-4);
    g+=`<line x1="${bx}" y1="${Y(cF).toFixed(1)}" x2="${bx}" y2="${Y(vF).toFixed(1)}" stroke="#E8892B" stroke-width="1.6"/>`+
       `<line x1="${bx-4}" y1="${Y(cF).toFixed(1)}" x2="${bx+4}" y2="${Y(cF).toFixed(1)}" stroke="#E8892B" stroke-width="1.6"/>`+
       `<line x1="${bx-4}" y1="${Y(vF).toFixed(1)}" x2="${bx+4}" y2="${Y(vF).toFixed(1)}" stroke="#E8892B" stroke-width="1.6"/>`+
       `<line x1="${X(cx).toFixed(1)}" y1="${Y(cF).toFixed(1)}" x2="${bx}" y2="${Y(cF).toFixed(1)}" stroke="#E8892B" stroke-width="0.8" stroke-dasharray="3 3" opacity=".6"/>`+
       `<text x="${(bx+7).toFixed(1)}" y="${((Y(cF)+Y(vF))/2+4).toFixed(1)}" font-size="10.5" fill="#E8892B" font-family="var(--mono)">SNAP %</text>`;
  }
  if(tv!=null){
    g+=`<line x1="${X(tv).toFixed(1)}" y1="${T}" x2="${X(tv).toFixed(1)}" y2="${H-B}" stroke="var(--muted)" stroke-width="1" stroke-dasharray="4 3"/>`+
       `<circle cx="${X(tv).toFixed(1)}" cy="${(H-B).toFixed(1)}" r="4.5" fill="#fff"/>`+
       `<text x="${X(tv).toFixed(1)}" y="${(H-6).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--ink)" font-family="var(--mono)">Travel</text>`;
  }
  const areaLabel=(tv!=null)
    ? `<text x="${((L+X(tv))/2).toFixed(0)}" y="${(H*0.60).toFixed(0)}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--ink)" letter-spacing=".06em">PRESS WORK</text>`
    : "";
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" preserveAspectRatio="xMidYMid meet" style="display:block;margin:6px 0;width:100%;max-width:${W}px;height:auto">
    <path d="${area}" fill="rgba(172,83,255,.14)"/>
    <polyline points="${line}" fill="none" stroke="#C9CDD3" stroke-width="1.8"/>
    <line x1="${L}" y1="${H-B}" x2="${W-Rr}" y2="${H-B}" stroke="var(--muted)" stroke-width="1"/>
    <line x1="${L}" y1="${T}" x2="${L}" y2="${H-B}" stroke="var(--muted)" stroke-width="1"/>
    <text x="${L-16}" y="${T+20}" font-size="12" fill="var(--ink)" font-family="var(--mono)">g</text>
    <text x="${L+12}" y="${H-6}" font-size="12" fill="var(--ink)" font-family="var(--mono)">mm</text>
    ${areaLabel}
    ${g}
  </svg>`;
}"""

PICKER_BENCHVALS = """function benchValsHTML(setName){
  const b=benchFor(setName); if(!b)return "";
  const N=k=>benchNum(b,k);
  const row=(lab,val)=>`<tr><td>${lab}</td><td>${val}</td></tr>`;
  const fmt=(v,f,u)=>v==null?"not available":`${f(v)} ${u}`;
  return `<table class="det-props det-test bench-vals">`+
    row("Full-stroke press work",fmt(N("en"),v=>Math.round(v),"gf\\u00b7mm"))+
    row("Pre-collapse work",fmt(N("pcw"),v=>Math.round(v),"gf\\u00b7mm"))+
    row("Snap",fmt(N("sn"),v=>Math.round(v),"%"))+
    row("Drop rate",fmt(N("dr"),v=>v.toFixed(1),"gf/mm"))+
    row("Norm. drop rate",fmt(N("ndr"),v=>v.toFixed(3),"/mm"))+
    row("Steepest 0.10 mm drop",fmt(N("sd"),v=>v.toFixed(1),"gf/mm"))+
    row("Ramp",fmt(N("rp"),v=>v.toFixed(1),"gf/mm"))+
    row("Collapse force",fmt(N("cg"),v=>Math.round(v),"gf"))+
    row("Collapse point",fmt(N("cx"),v=>v.toFixed(2),"mm"))+
    row("Travel",fmt(N("tv"),v=>v.toFixed(2),"mm"))+
    row("Runs used",`${b.runs==null?"n/a":b.runs}`)+
  `</table>`;
}"""

PICKER_TESTSTAT = """function testStat(p,ix){
  if(!(p.tests&&p.tests.length))return null;
  const b=benchFor(p.tests[0].set); if(!b)return null;
  const KEYS=["cg","en","sn","cx","tv","vF","vx","pcw","dg","dxd","dr","ndr","sd","rp"];
  return benchNum(b,KEYS[ix]);
}"""

PICKER_LOADDOMES = """async function loadDomes(){
  /* Step 2.3: the picker is a CONSUMER of generated retained data, never a
     calculator. The former path fetched every raw run in the repository,
     averaged them and analyzed the averaged curve — a competing implementation
     of the metrics. It is retired. Sets, run counts and every displayed scalar
     come from the generated TESTS records; exclusions come from the generated
     exclusion registry. */
  const excluded=new Set(GENERATED_EXCLUSIONS);
  for(const t of TESTS){
    if(!t||!t.set||excluded.has(t.set))continue;
    const setName=t.set.replace(/_/g," ");
    let d=matchDome(setName);
    if(!d){
      d={id:"dm-set-"+t.set.toLowerCase(), name:setName, maker:setName.split(" ")[0],
         type:AM, version:"", style:"", wraw:"", wmin:null, wmax:null, u:"", brief:"", notes:[], tests:[], buy:""};
      CATALOG.domes.push(d);
    }
    if(!d.tests)d.tests=[];
    if(d.tests.some(x=>x.set===setName))continue;
    const sn=(typeof t.sn==="number")?Math.round(t.sn):null;
    const en=(typeof t.en==="number")?Math.round(t.en):null;
    d.tests.push({set:setName,
      stat:(sn==null||en==null)?"not available":`Snap ${sn}% \\u00b7 ${en} gf\\u00b7mm`});
  }
  renderAll();
}"""

# ---------------------------------------------- picker V3 native contract
# The generator-owned lib-5.x template carries these functions natively; the
# generated-template branch verifies byte equality instead of rewriting.
PICKER_CURVEKEY_V3 = """function curveKey(setName){
  if(!setName)return null;
  const k=String(setName).replace(/ /g,"_");
  return (typeof MINI_CURVES!=="undefined"&&Object.prototype.hasOwnProperty.call(MINI_CURVES,k))?k:null;
}"""

PICKER_TESTSTAT_V3 = """function testStat(p,ix){
  /* single-record only: metrics are per measured record and are never
     collapsed across a part\u2019s multiple assembly records */
  if(!(p.tests&&p.tests.length===1))return null;
  const b=benchFor(p.tests[0].set); if(!b)return null;
  const KEYS=["cg","wi","ti","cx","tv","pcw","dg","sd","dr","rp","sn"];
  return benchNum(b,KEYS[ix]);
}"""

PICKER_BENCHVALS_V3 = """function benchValsHTML(setName){
  const b=benchFor(setName); if(!b)return "";
  const N=k=>benchNum(b,k);
  const row=(lab,val)=>`<tr><td>${lab}</td><td>${val}</td></tr>`;
  const fmt=(v,f,u)=>v==null?"not available":`${f(v)} ${u}`;
  const wall=N("tv");
  return `<table class="det-props det-test bench-vals">`+
    row("Weight Index",fmt(N("wi"),v=>v.toFixed(1),"/ 100"))+
    row("Tactility Index",fmt(N("ti"),v=>v.toFixed(1),"/ 100"))+
    row("Collapse force",fmt(N("cg"),v=>Math.round(v),"gf"))+
    row("Ramp",fmt(N("rp"),v=>v.toFixed(1),"gf/mm"))+
    row("Pre-collapse work",fmt(N("pcw"),v=>Math.round(v),"gf\u00b7mm"))+
    row("Drop",fmt(N("dg"),v=>Math.round(v),"gf"))+
    row("Steepest 0.10 mm drop",fmt(N("sd"),v=>v.toFixed(1),"gf/mm"))+
    row("Drop rate",fmt(N("dr"),v=>v.toFixed(1),"gf/mm"))+
    row("Snap %",fmt(N("sn"),v=>Math.round(v),"%"))+
    row("Detected force-wall onset",wall==null?"Not detected":`${wall.toFixed(2)} mm`)+
    row("Recorded test turnaround (min\u2013max)",fmtTaRange(b))+
    row("Runs used",`${b.runs==null?"n/a":b.runs}`)+
    row("Canonical record",`${b.id||"?"} \u00b7 ${b.k||"?"}`)+
    row("Source set",`${b.set||"?"}`)+
    row("Assembly identity",`<span class="det-mono">${(b.acfg||"").slice(0,16)||"?"}</span>`)+
    row("Evidence-method identity",`<span class="det-mono">${(b.mcfg||"").slice(0,16)||"?"}</span> · shared across the epoch`)+
  `</table>`+
  `<div class="det-foot" style="margin-top:4px">Detected force-wall onset is an operational proxy measured on this exact assembly. It is not physical or nominal full travel, and it is not compared to any reference or baseline. The recorded test turnaround is the bench travel limit for the run set; nominal slider travel is a separate part specification.</div>`;
}"""

PICKER_LOADDOMES_V3 = """async function loadDomes(){
  /* The picker is a CONSUMER of generated canonical records, never a
     calculator. Record-to-part attachment is EXPLICIT via the generated
     RECORD_MAP (config/parts_record_map.json): no fuzzy name matching.
     dome_baseline records attach only to the dome catalog; part_assembly
     records attach only to parts. Unmapped records are surfaced, never
     silently invented or dropped into the wrong catalog. */
  const excluded=new Set(GENERATED_EXCLUSIONS);
  for(const t of TESTS){
    if(!t||!t.set||excluded.has(t.set))continue;
    const m=RECORD_MAP[t.id];
    if(!m||!m.target){reportUnmappedRecord(t,"no explicit mapping");continue;}
    if(m.kind&&m.kind!==t.k){reportUnmappedRecord(t,`mapping kind ${m.kind} != record kind ${t.k}`);continue;}
    if(t.k==="dome_baseline"&&m.target.startsWith("dome_db:")){
      const id=m.target.slice(8);
      /* authored grouping may collapse per-sample DOME_DB rows into one
         catalog entry with members:[names]; resolve by id, then by the
         mapped row name inside a grouped entry. Still explicit: the id
         comes from RECORD_MAP and the name from DOME_DB, never fuzz. */
      let d=CATALOG.domes.find(x=>x.id===id);
      if(!d){
        const row=DOME_DB.find(x=>x.id===id);
        if(row)d=CATALOG.domes.find(x=>x.members&&x.members.includes(row.name));
      }
      if(!d){reportUnmappedRecord(t,`dome ${id} not in catalog`);continue;}
      if(!d.tests)d.tests=[];
      if(!d.tests.some(x=>x.id===t.id))d.tests.push(recordTestEntry(t));
    }else if(t.k==="part_assembly"&&m.target.startsWith("part:")){
      const id=m.target.slice(5);
      const p=PARTIDX[id];
      if(!p){reportUnmappedRecord(t,`part ${id} not in catalog`);continue;}
      if(!p.tests)p.tests=[];
      if(!p.tests.some(x=>x.id===t.id))p.tests.push(recordTestEntry(t));
    }else{
      reportUnmappedRecord(t,`record kind ${t.k} does not match target ${m.target}`);
    }
  }
  renderAll();
}"""

PICKER_PREVCURVE_V2 = r"""function prevCurveSVG(setName){
  const c=(typeof MINI_CURVES!=="undefined")?curveFor(setName):null;
  const b=benchFor(setName);
  if(!c||!b||!c.x||!c.F||!c.x.length)return "";
  const cF=benchNum(b,"cg"), cx=benchNum(b,"cx"), tv=benchNum(b,"tv");
  const vF=benchNum(b,"vF"), vx=benchNum(b,"vx");
  if(cF==null||cx==null)return "";
  const W=310,H=180,L=26,B=24,T=14,Rr=8;
  const fm=cF*1.5;                                  /* fit rule: Y max = collapse * 1.5 */
  const xEnd=(tv!=null)?Math.max(tv*1.04,Math.max(...c.x)):Math.max(...c.x);
  const X=x=>L+x/xEnd*(W-L-Rr), Y=f=>H-B-Math.min(f,fm)/fm*(H-B-T);
  const line=c.x.map((x,i)=>`${X(x).toFixed(1)},${Y(c.F[i]).toFixed(1)}`).join(" ");
  let area="";
  {
    const upto=c.x.map((x,i)=>[x,c.F[i]]).filter(([x])=>x<=cx);
    if(upto.length)area=`M${X(upto[0][0]).toFixed(1)},${(H-B).toFixed(1)} L`+
      upto.map(([x,f])=>`${X(x).toFixed(1)},${Y(f).toFixed(1)}`).join(" L")+
      ` L${X(cx).toFixed(1)},${(H-B).toFixed(1)} Z`;
  }
  let g="";
  g+=`<circle cx="${X(cx).toFixed(1)}" cy="${Y(cF).toFixed(1)}" r="5" fill="#AC53FF"/>`+
     `<text x="${X(cx).toFixed(1)}" y="${(Y(cF)-9).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--ink)" font-family="var(--mono)">Collapse</text>`;
  if(vF!=null&&vx!=null){
    g+=`<circle cx="${X(vx).toFixed(1)}" cy="${Y(vF).toFixed(1)}" r="4.5" fill="#E8892B"/>`+
       `<text x="${X(vx).toFixed(1)}" y="${(Y(vF)+15).toFixed(1)}" text-anchor="middle" font-size="11" fill="#E8892B" font-family="var(--mono)">Valley</text>`;
    const bx=Math.min(X(vx)+16,W-Rr-4);
    g+=`<line x1="${bx}" y1="${Y(cF).toFixed(1)}" x2="${bx}" y2="${Y(vF).toFixed(1)}" stroke="#E8892B" stroke-width="1.6"/>`+
       `<line x1="${bx-4}" y1="${Y(cF).toFixed(1)}" x2="${bx+4}" y2="${Y(cF).toFixed(1)}" stroke="#E8892B" stroke-width="1.6"/>`+
       `<line x1="${bx-4}" y1="${Y(vF).toFixed(1)}" x2="${bx+4}" y2="${Y(vF).toFixed(1)}" stroke="#E8892B" stroke-width="1.6"/>`+
       `<line x1="${X(cx).toFixed(1)}" y1="${Y(cF).toFixed(1)}" x2="${bx}" y2="${Y(cF).toFixed(1)}" stroke="#E8892B" stroke-width="0.8" stroke-dasharray="3 3" opacity=".6"/>`+
       `<text x="${(bx+7).toFixed(1)}" y="${((Y(cF)+Y(vF))/2+4).toFixed(1)}" font-size="10.5" fill="#E8892B" font-family="var(--mono)">SNAP %</text>`;
  }
  if(tv!=null){
    g+=`<line x1="${X(tv).toFixed(1)}" y1="${T}" x2="${X(tv).toFixed(1)}" y2="${H-B}" stroke="var(--muted)" stroke-width="1" stroke-dasharray="4 3"/>`+
       `<circle cx="${X(tv).toFixed(1)}" cy="${(H-B).toFixed(1)}" r="4.5" fill="#fff"/>`+
       `<text x="${X(tv).toFixed(1)}" y="${(H-6).toFixed(1)}" text-anchor="middle" font-size="11" fill="var(--ink)" font-family="var(--mono)">Wall</text>`;
  }else{
    g+=`<text x="${W-Rr-4}" y="${(H-6).toFixed(1)}" text-anchor="end" font-size="10.5" fill="var(--muted)" font-family="var(--mono)">FORCE WALL: NOT DETECTED</text>`;
  }
  const areaLabel=`<text x="${((L+X(cx))/2).toFixed(0)}" y="${(H*0.60).toFixed(0)}" text-anchor="middle" font-size="11" font-weight="700" fill="var(--ink)" letter-spacing=".05em">PRE-COLLAPSE WORK</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" preserveAspectRatio="xMidYMid meet" style="display:block;margin:6px 0;width:100%;max-width:${W}px;height:auto">
    <path d="${area}" fill="rgba(172,83,255,.14)"/>
    <polyline points="${line}" fill="none" stroke="#C9CDD3" stroke-width="1.8"/>
    <line x1="${L}" y1="${H-B}" x2="${W-Rr}" y2="${H-B}" stroke="var(--muted)" stroke-width="1"/>
    <line x1="${L}" y1="${T}" x2="${L}" y2="${H-B}" stroke="var(--muted)" stroke-width="1"/>
    <text x="${L-16}" y="${T+20}" font-size="12" fill="var(--ink)" font-family="var(--mono)">g</text>
    <text x="${L+12}" y="${H-6}" font-size="12" fill="var(--ink)" font-family="var(--mono)">mm</text>
    ${areaLabel}
    ${g}
  </svg>`;
}"""

PICKER_SUPPORT_V3 = """function fmtTaRange(b){
  const lo=benchNum(b,"tamin"), hi=benchNum(b,"tamax");
  if(lo==null||hi==null)return "not available";
  if(Math.abs(hi-lo)<0.005)return `${lo.toFixed(2)} mm`;
  return `${lo.toFixed(2)}\u2013${hi.toFixed(2)} mm`;
}
function recordStat(t){
  const wi=(typeof t.wi==="number")?t.wi:null, ti=(typeof t.ti==="number")?t.ti:null;
  const sn=(typeof t.sn==="number")?Math.round(t.sn):null;
  if(wi!=null&&ti!=null)return `WI ${wi.toFixed(1)} \u00b7 TI ${ti.toFixed(1)}${sn==null?"":` \u00b7 Snap ${sn}%`}`;
  const cg=(typeof t.cg==="number")?Math.round(t.cg):null;
  if(cg!=null)return `${cg} gf${sn==null?"":` \u00b7 Snap ${sn}%`}`;
  return "not available";
}
function recordTestEntry(t){
  return {set:t.set,id:t.id,kind:t.k,stat:recordStat(t),cl:t.cl||t.set,acfg:t.acfg||null,mcfg:t.mcfg||null};
}
function reportUnmappedRecord(t,why){
  (window.__unmappedRecords||(window.__unmappedRecords=[])).push({id:t&&t.id,set:t&&t.set,why});
  console.warn("EC Parts Library: canonical record not attached",t&&t.id,t&&t.set,why);
}
function ridOf(p){ return p?(p.rid||p.id||null):null; }
function evEdge(pa,pb){
  const a=ridOf(pa), b=ridOf(pb);
  if(!a||!b||a===b)return null;
  const key=[a,b].sort().join("||");
  const e=COMPAT_EVIDENCE[key];
  if(e)return e;
  /* an absent edge is NEVER silent and NEVER looks compatible */
  return {st:"unknown",src:"none",nid:null,q:null,adj:"unadjudicated",
          rsn:"no compatibility evidence recorded",synth:true};
}
function evNoteText(e){
  if(!e||!e.nid)return "";
  const n=EC.NOTES[e.nid];
  return n?n.text:"";
}
function evMsg(e,aName,bName){
  if(!e)return null;
  const qual=e.q?` (${e.q})`:"";
  if(e.st==="incompatible")
    return {cls:"warn",st:e.st,txt:(evNoteText(e)||`Incompatible: ${aName} + ${bName}.`)};
  if(e.st==="conditional"){
    const base=evNoteText(e)||`Conditional: ${aName} + ${bName} work together only under the recorded conditions.`;
    const adj=e.adj==="owner_pending"?" Owner adjudication pending \u2014 treat as unconfirmed.":"";
    return {cls:"note",st:e.st,txt:base+qual+adj};
  }
  if(e.st==="pending")
    return {cls:"pend",st:e.st,txt:`Compatibility has not been confirmed for ${aName} + ${bName} (recorded as pending verification).`};
  if(e.st==="unknown")
    return {cls:"pend",st:e.st,txt:`Compatibility has not been confirmed for ${aName} + ${bName} \u2014 no compatibility evidence recorded.`};
  return null; /* compatible: explicit state, silent presentation; not_applicable: never co-selected */
}
function renderEvidenceHTML(b){
  const ev=b&&b.ev; if(!ev)return "";
  const li=(lab,arr)=>arr&&arr.length?`<div><b>${lab}</b><div class="det-mono" style="word-break:break-all">${arr.join("<br>")}</div></div>`:"";
  return `<details class="ev-block"><summary>Evidence reference \u00b7 ${b.id}</summary>`+
    `<div class="det-mono">assembly identity ${b.acfg||"?"}</div>`+
    `<div class="det-mono">evidence-method identity ${b.mcfg||"?"} (shared across the epoch)</div>`+
    li("Acquisition IDs",ev.acq)+li("Raw paths",ev.rp)+li("Raw SHA-256",ev.sh)+li("Git blob OIDs",ev.gb)+
    `<div><b>Membership authority</b> <span class="det-mono">${ev.ma||"?"}</span> \u00b7 <b>artifact role</b> <span class="det-mono">${ev.role||"?"}</span></div>`+
    `<div><b>Generator identity</b> <span class="det-mono">${ev.gen||"?"}</span> \u00b7 <b>repo commit</b> <span class="det-mono">${(PICKER_BUILD.repo_commit||"").slice(0,12)}</span></div>`+
  `</details>`;
}
function renderPickerIdentity(){
  const el=document.getElementById("buildBadge");
  if(!el||typeof PICKER_BUILD!=="object")return;
  const b=PICKER_BUILD||{};
  const bits=[b.library_build,b.bench_build,b.data_epoch].filter(Boolean);
  if(bits.length)el.textContent=bits.join(" \u00b7 ");
  const t=[
    b.metrics?`metrics ${b.metrics}`:"",
    b.perception?`indices ${b.perception}`:"",
    b.repo_commit?`pinned commit ${b.repo_commit}`:"",
    (b.records!=null)?`${b.records} canonical records \u00b7 ${b.sets} sets`:"",
    (b.retained_run_bindings!=null)?`${b.retained_run_bindings} semantic retained-run bindings \u00b7 ${b.unique_acquisitions} unique acquisitions`:"",
    b.parts_library_source_identity?`library inputs ${String(b.parts_library_source_identity).slice(0,12)}`:"",
    b.authority_split||"",
  ].filter(Boolean).join(String.fromCharCode(10));
  if(t)el.title=t;
}"""




# ------------------------------------------------ evidence-only curve packs
def build_curve_evidence_packs(retained_by_set, records, exclusions):
    """Build only compact curve JSON derivatives for a Step-2 evidence epoch.

    This path intentionally never opens, transforms, or emits a Force Curve
    Bench/parts HTML template.  The compact values are rounded display
    derivatives; authoritative metrics remain in the full-precision evidence.
    """
    excluded = {entry["set"] for entry in exclusions["entries"]}
    included_sets = sorted(
        set_name for set_name in retained_by_set
        if set_name not in excluded and any(r.get("set") == set_name for r in records)
    )
    record_by_set = {record["set"]: record for record in records}
    staged = {}
    for set_name in included_sets:
        press_runs, _return_runs = _branches(retained_by_set[set_name])
        keys, forces = _grid_average(press_runs, "majority")
        record = record_by_set[set_name]
        xs = [key / 200 for key in keys]
        sample_count = 61
        step = (len(xs) - 1) / (sample_count - 1)
        indices = [round(i * step) for i in range(sample_count)]
        curve = {
            "set": set_name,
            "runs_used": record["runs_used"],
            "calc_version": record["calc_version"],
            "derived_lossy_display_pack": True,
            "authoritative_metrics": False,
            "x_mm": [round(xs[i], 3) for i in indices],
            "force_g": [round(forces[i], 1) for i in indices],
            "collapse": {
                "x": R3(record["collapse_travel_mm"]),
                "g": R1(record["collapse_force_gf"]),
            },
            "travel_mm": R3(record["travel_mm"]),
            "snap_pct": R1(record["snap_pct"]),
            "full_stroke_press_work_gf_mm": R1(
                record["full_stroke_press_work_gf_mm"]
            ),
        }
        staged[f"packs/curves/{set_name}.staged.json"] = (
            json.dumps(curve, sort_keys=True, indent=1) + "\n"
        )
    return staged


# --------------------------------------------------------------- build
def build_all_packs(retained_by_set, records, dataset_manifest, exclusions,
                    intake_manifest, viewer_path, picker_path,
                    viewer_profile="review"):
    profile = viewer_build_profile(viewer_profile)
    method_cfg = config()
    intake_cfg = method_cfg["intake_policy"]
    if intake_cfg["version"] != intake_manifest.get("policy_version"):
        raise RuntimeError("viewer intake identity disagrees with method configuration")
    cfg_rule = "majority"
    excluded = {e["set"] for e in exclusions["entries"]}
    included_sets = sorted(s for s in retained_by_set
                           if s not in excluded and any(r.get("set") == s for r in records))
    staged = {}

    embedded, curves, turnaround_by_set = {}, {}, {}
    curve_domain_max_mm = 0.0
    for s in included_sets:
        pruns, rruns = _branches(retained_by_set[s])
        turnarounds = [max(xs) for xs, _forces in pruns if xs]
        if not turnarounds:
            raise RuntimeError(f"viewer build has no recorded press turnaround for {s}")
        turnaround_by_set[s] = {"min": min(turnarounds), "max": max(turnarounds)}
        for xs, _forces in pruns + rruns:
            if xs:
                curve_domain_max_mm = max(curve_domain_max_mm, max(xs))
        keys, F = _grid_average(pruns, cfg_rule)
        rkeys, rF = _grid_average(rruns, cfg_rule)
        embedded[s] = {"n": len(pruns), "p": pack_stroke(keys, F), "r": pack_stroke(rkeys, rF)}
        rec = next(r for r in records if r["set"] == s)
        xs = [k / 200 for k in keys]
        n = 61
        step = (len(xs) - 1) / (n - 1)
        idx = [round(i * step) for i in range(n)]
        curves[s] = {"set": s, "runs_used": rec["runs_used"], "calc_version": rec["calc_version"],
                     "x_mm": [round(xs[i], 3) for i in idx], "force_g": [round(F[i], 1) for i in idx],
                     "collapse": {"x": R3(rec["collapse_travel_mm"]), "g": R1(rec["collapse_force_gf"])},
                     "travel_mm": R3(rec["travel_mm"]), "snap_pct": R1(rec["snap_pct"]),
                     "full_stroke_press_work_gf_mm": R1(rec["full_stroke_press_work_gf_mm"])}
        staged[f"packs/curves/{s}.staged.json"] = json.dumps(curves[s], sort_keys=True, indent=1) + "\n"

    with open(viewer_path, encoding="utf-8", newline="") as f:
        viewer_src = f.read()
    viewer_src = _embed_release_fonts(viewer_src)
    with open(picker_path, encoding="utf-8", newline="") as f:
        picker_src = f.read()

    # Historical templates need one-time prose and runtime migrations.  The
    # fc-3.4 second-update template is deliberately based on a fully generated
    # viewer so the owner's accepted single-file GUI can itself be reproduced.
    # Detect that form by its generated identity block and validate it in place
    # instead of trying to replay legacy migrations over already-current code.
    viewer_is_generated_template = "const VIEWER_BUILD = " in viewer_src
    if viewer_is_generated_template:
        vlog = []
    else:
        viewer_src, vlog = prose.apply_claims(
            viewer_src, prose.VIEWER_CLAIMS, "viewer"
        )
    # The lib-5.0 library template is generator-owned and already clean;
    # detect it by its generated identity anchor and validate in place
    # instead of replaying legacy claim migrations.
    picker_is_generated_template = "const PICKER_BUILD = " in picker_src
    if picker_is_generated_template:
        plog = []
    else:
        picker_src, plog = prose.apply_claims(picker_src, prose.PICKER_CLAIMS, "picker")
    if not viewer_is_generated_template:
        viewer_src = _apply(
            viewer_src,
            "<b>intake-qc-v1.4</b> is the retention authority for this review build",
            f"<b>{intake_manifest['policy_version']}</b> is the retention authority "
            "for this review build",
            "intake policy method label",
        )
        stale_retention_copy = (
            "Every configuration is tested in multiple runs and averaged. Under runfilter-v1.1, "
            "retained runs must lie within 1.0\u00a0gf of the batch median collapse force and "
            "0.10\u00a0mm of the batch median collapse position. These are retention criteria, not "
            "claims of measurement accuracy or universal run-to-run repeatability. Calculations "
            "retain full precision; displayed values are rounded for presentation."
        )
        viewer_src = _apply(
            viewer_src, stale_retention_copy,
            "Historical retention wording removed; "
            f"{intake_manifest['policy_version']} is the generated review authority.",
            "retired runfilter-v1.1 method copy")
    canonical_runs = {s: [_pbase(r["rel_path"]) for r in retained_by_set[s]] for s in included_sets}
    ramp_reviews_by_set = _ramp_reviews_for_viewer(
        intake_manifest, canonical_runs, records
    )
    gen_excl = sorted(excluded)

    # ---- viewer test records -------------------------------------------
    _, _, vt_rel = _extract_blob(viewer_src, "VTESTS")
    vt_by_id = {(e.get("set"), e.get("n")): e for e in vt_rel}
    perception_pack = perception.build_perception_pack(records)
    perception_by_id = {
        row["test_id"]: row for row in perception_pack["records"]
    }
    vtests = []
    for r in records:
        # Visual landmark spans are derived from the same retained per-run
        # analyzer audits as the released scalars.  The viewer uses these
        # arithmetic-mean coordinates only to draw RAMP and steepest-drop
        # overlays; it never re-analyzes the averaged display trace.
        def audit_mean(field):
            values = [
                run.get("metric_audit", {}).get(field)
                for run in retained_by_set.get(r["set"], [])
            ]
            if not values or any(
                not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in values
            ):
                return None
            return sum(values) / len(values)

        base = dict(vt_by_id.get((r["set"], r.get("name")), {}))
        base.update({"k": r.get("kind"), "n": r.get("name"), "set": r["set"], "runs": r["runs_used"]})
        base.update({
            "id": r.get("test_id"),
            "source_set": r["set"],
            # UI/filter metadata is generated from the authoritative record.
            # A legacy template row is presentation scaffolding only and must
            # never be the metadata source for a newly added fleet member.
            "brand": r.get("brand"),
            "mfr": r.get("manufacturer"),
            "wt": r.get("nominal_weight_g"),
            "ver": r.get("variant"),
            "sty": r.get("style"),
            "pre": r.get("precompression_mm"),
            "sl": r.get("slider"),
            "rg": r.get("silencing_ring"),
            "h1": r.get("housing"),
            "base": bool(r.get("is_baseline")),
            "dv": r.get("travel_dev_mm"),
            "cohort": r.get("measurement_cohort_id"),
            "alias_group": r.get("evidence_alias_group"),
            "alias_role": r.get("evidence_alias_role"),
            "quality_flags": r.get("quality_flags", []),
            "null_reasons": r.get("null_reasons", {}),
            "intake_review_count": len(r.get("intake_review_notices", [])),
            "tl_min": turnaround_by_set.get(r["set"], {}).get("min"),
            "tl_max": turnaround_by_set.get(r["set"], {}).get("max"),
            "rx10": audit_mean("ramp_x10_mm"),
            "rx90": audit_mean("ramp_x90_mm"),
            "ss": audit_mean("steepest_drop_start_mm"),
            "se": audit_mean("steepest_drop_end_mm"),
        })
        for kk, (mk, rnd) in VIEWER_METRIC.items():
            base[kk] = rnd(r[mk])
        perceptual = perception_by_id.get(r.get("test_id"))
        if perceptual is None:
            raise RuntimeError(f"viewer perception score missing for {r.get('test_id')}")
        base.update({
            "wi": perceptual["weight_index"],
            "ti": perceptual["tactility_index"],
            "pp": perceptual["component_percentiles"],
        })
        vtests.append(base)
    staged["packs/viewer_embedded.json"] = json.dumps(embedded, sort_keys=True, separators=(",", ":")) + "\n"
    staged["packs/viewer_vtests.json"] = json.dumps(vtests, sort_keys=True, separators=(",", ":")) + "\n"
    staged["packs/perception_scores.json"] = (
        json.dumps(perception_pack, sort_keys=True, indent=1) + "\n"
    )

    # ---- picker test records -------------------------------------------
    if picker_is_generated_template:
        # lib-5.x contract: canonical metrics at source precision, perception
        # indices, force-wall null state, numeric turnaround min/max, raw
        # stable-ID configuration fields for exact assembly matching, the
        # canonical configuration identity, a human configuration label, and
        # a compact evidence reference. No plural translation, no defaults.
        import hashlib as _hl
        import json as _json2
        _xw = _json2.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "config", "r8_crosswalk.json"),
                               encoding="utf-8"))["records"]
        _pname = {e["r8_id"]: e["part_name"] for e in _xw.values() if e.get("r8_id")}
        def _nm(pid):
            if not pid:
                return "no ring"
            return _pname.get(pid, pid)
        def _cfg_label(r):
            core = (f"{_nm(r.get('slider'))} + {_nm(r.get('housing'))} + "
                    f"{_nm(r.get('conical_spring'))} + "
                    f"{_nm(r.get('silencing_ring')) if r.get('silencing_ring') else 'no ring'}")
            dome = _nm(r.get("dome"))
            pre = r.get("precompression_mm") or 0
            tail = f" \u00b7 dome: {dome}" + (f" \u00b7 precompression {pre} mm" if pre else "")
            return core + tail
        ptests = []
        for r in records:
            perceptual = perception_by_id.get(r.get("test_id"))
            if perceptual is None:
                raise RuntimeError(
                    f"picker perception score missing for {r.get('test_id')}")
            prov = r.get("provenance") or {}
            tlo = turnaround_by_set.get(r["set"], {}).get("min")
            thi = turnaround_by_set.get(r["set"], {}).get("max")
            base = {"id": r.get("test_id"), "k": r.get("kind"),
                    "n": r.get("name"), "set": r["set"], "runs": r["runs_used"],
                    "wi": perceptual["weight_index"],
                    "ti": perceptual["tactility_index"],
                    "tamin": tlo, "tamax": thi,
                    "sl": r.get("slider"), "h1": r.get("housing"),
                    "sp": r.get("conical_spring"),
                    "rg": r.get("silencing_ring"),
                    "dm": r.get("dome"),
                    "pre": r.get("precompression_mm"),
                    "tp": r.get("tested_part"),
                    "base": bool(r.get("is_baseline")),
                    # Two distinct identities, never conflated:
                    #   mcfg — the epoch's evidence-method configuration hash
                    #          (provenance.config_hash; identical across all
                    #          records of the epoch by construction)
                    #   acfg — this record's per-assembly configuration
                    #          identity over every assembly-defining field
                    "mcfg": prov.get("config_hash"),
                    "acfg": _hl.sha256(_json2.dumps(
                        {"kind": r.get("kind"),
                         "tested_part": r.get("tested_part"),
                         "dome": r.get("dome"),
                         "slider": r.get("slider"),
                         "housing": r.get("housing"),
                         "conical_spring": r.get("conical_spring"),
                         "silencing_ring": r.get("silencing_ring"),
                         "precompression_mm": r.get("precompression_mm")},
                        sort_keys=True).encode("utf-8")).hexdigest(),
                    "cl": _cfg_label(r),
                    "cohort": r.get("measurement_cohort_id"),
                    "alias": r.get("evidence_alias_role"),
                    "ev": {"acq": list(prov.get("acquisition_ids", [])),
                           "rp": list(prov.get("raw_paths", [])),
                           "sh": list(prov.get("raw_sha256", [])),
                           "gb": list(prov.get("raw_git_blob_oids", [])),
                           "ma": prov.get("membership_authority"),
                           "role": prov.get("artifact_role"),
                           "gen": prov.get("generator_version")}}
            for kk, (mk, rnd) in VT_METRIC_V2.items():
                base[kk] = rnd(r[mk])
            ptests.append(base)
    else:
        _, _, pk_rel = _extract_blob(picker_src, "const TESTS")
        pk_by_id = {e.get("id"): e for e in pk_rel}
        ptests = []
        for r in records:
            base = dict(pk_by_id.get(r.get("test_id"), {}))
            base.update({"id": r.get("test_id"), "k": r.get("kind"), "n": r.get("name"), "set": r["set"],
                         "runs": r["runs_used"]})
            for kk, (mk, rnd) in VT_METRIC.items():
                base[kk] = rnd(r[mk])
            ptests.append(base)

    # ---- mini curves: SAMPLES ONLY, uppercase F -------------------------
    mini = {}
    for s in included_sets:
        keys, F = _grid_average(_branches(retained_by_set[s])[0], cfg_rule)
        xs = [k / 200 for k in keys]
        stepn = max(1, round(0.075 / 0.005))
        mini[s] = {"x": [round(xs[i], 3) for i in range(0, len(xs), stepn)],
                   "F": [round(F[i], 1) for i in range(0, len(xs), stepn)]}
    staged["packs/picker_tests.json"] = json.dumps(ptests, sort_keys=True, separators=(",", ":")) + "\n"
    staged["packs/picker_mini_curves.json"] = json.dumps(mini, sort_keys=True, separators=(",", ":")) + "\n"

    # ---- viewer transform ----------------------------------------------
    v = viewer_src
    if "<b>Travel</b>" in v or "<b>Detected force-wall onset</b>" not in v:
        raise RuntimeError("viewer: public force-wall metric name is not current")
    if "from 0 to Travel" in v:
        raise RuntimeError("viewer: retired full-press-work endpoint copy remains")
    if "an operational bottom-out proxy rather than observed contact" in v or \
            "an operational test-assembly proxy rather than nominal or physical travel" not in v:
        raise RuntimeError("viewer: force-wall assembly scope is not current")
    v = v.replace("DROP TRAVEL", "COLLAPSE-TO-VALLEY DISTANCE")
    v = _replace_blob(v, "EMBEDDED", embedded)
    v = _replace_blob(v, "VTESTS", vtests)
    fallback = sorted(r["rel_path"] for s2 in included_sets for r in retained_by_set[s2])
    if viewer_is_generated_template:
        fallback_decl = (
            'const FALLBACK_CSVS=Object.entries(CANONICAL_RUNS)'
            '.flatMap(([set,files])=>files.map(f=>set+"/"+f));'
        )
        if v.count(fallback_decl) != 1:
            raise RuntimeError(
                "viewer derived FALLBACK_CSVS declaration is missing or ambiguous"
            )
        # The functions are already the generated authorities.  Verify their
        # exact bodies without rewriting the owner's surrounding source.
        generated_average = js_average_source(cfg_rule)
        if _replace_function(v, "averageStrokes", generated_average) != v:
            raise RuntimeError("viewer averageStrokes differs from generated authority")
        generated_analyzer = js_reference_analyzer_source()
        generated_analyzer = generated_analyzer[
            generated_analyzer.index("function analyze"):
        ]
        if _replace_function(v, "analyze", generated_analyzer) != v:
            raise RuntimeError("viewer analyze differs from generated reference authority")
    else:
        v = _replace_blob(v, "FALLBACK_CSVS", fallback)
        v = _apply(v, OLD_ONLINE, NEW_ONLINE, "online generated-record-authority block")
        v = _apply(v, OLD_FETCH, NEW_FETCH, "retained-only fetch filter")
        v = _replace_function(v, "averageStrokes", js_average_source(cfg_rule))
        # One generated reference analyzer remains for conformance tests. It is not
        # a display authority and has no averaged-curve production caller.
        v = _replace_function(v, "analyze", js_reference_analyzer_source())
        # Retire the two remaining averaged-curve calculators.
        # (a) group/parent aggregation invented scalars for a synthetic combined
        #     curve that has no generated record. Groups now render traces only.
        v = _apply(v,
            "              avgPress,avgRet,stats:analyze(avgPress.x,avgPress.F)};",
            "              avgPress,avgRet,stats:null,group:true};\n"
            "      /* A group is a synthetic combination with no generated record.\n"
            "         Traces render; no scalar is computed from an averaged curve. */",
            "group averaged-curve calculator")
        # (b) the offline snapshot fallback silently recomputed from the averaged
        #     curve whenever the generated-record lookup missed. A record is required.
        v = _apply(v,
            "      s.data={runs:[],avgPress,avgRet,stats:canon||analyze(avgPress.x,avgPress.F),snapshot:true};",
            "      if(!canon)throw new Error(\"no generated record snapshot for \"+s.key);\n"
            "      s.data={runs:[],avgPress,avgRet,stats:canon,snapshot:true};",
            "offline generated-record requirement")
    provenance = records[0].get("provenance", {}) if records else {}
    repo_commit = dataset_manifest.get("repo_commit") or provenance.get("repo_commit")
    if not isinstance(repo_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", repo_commit):
        raise RuntimeError("viewer build requires an exact 40-character pinned repository commit")
    config_hash = provenance.get("config_hash")
    if not isinstance(config_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", config_hash):
        raise RuntimeError("viewer build requires the generated data/config identity")
    method_identity = records[0].get("calc_version") if records else None
    if not method_identity:
        raise RuntimeError("viewer build requires the generated method identity")
    data_artifact_role = provenance.get("artifact_role")
    data_release_eligible = provenance.get("release_eligible")
    if not isinstance(data_artifact_role, str) or type(data_release_eligible) is not bool:
        raise RuntimeError("viewer build requires canonical data authority identities")
    for record in records:
        record_provenance = record.get("provenance", {})
        if (
            record_provenance.get("artifact_role") != data_artifact_role
            or record_provenance.get("release_eligible") is not data_release_eligible
            or record_provenance.get("repo_commit") != repo_commit
            or record_provenance.get("config_hash") != config_hash
        ):
            raise RuntimeError("viewer records disagree on canonical data authority")
    force_wall_values = [
        float(record["travel_mm"])
        for record in records
        if (
            isinstance(record.get("travel_mm"), (int, float))
            and not isinstance(record.get("travel_mm"), bool)
            and math.isfinite(float(record["travel_mm"]))
        )
    ]
    if not force_wall_values:
        raise RuntimeError("viewer build has no detected force-wall onset")
    force_wall_domain_max_mm = max(force_wall_values)
    measurement_cohort_ids = [record.get("measurement_cohort_id") for record in records]
    if any(not isinstance(cohort_id, str) or not cohort_id for cohort_id in measurement_cohort_ids):
        raise RuntimeError("viewer records require non-empty measurement-cohort identities")
    shared_evidence_alias_groups = {
        record.get("evidence_alias_group")
        for record in records
        if record.get("evidence_alias_group")
    }
    build_identity = {
        **profile,
        "metrics": method_cfg["metrics_version"],
        "intake": intake_manifest["policy_version"],
        "intake_parity_target": intake_cfg["parity_target"],
        "repo_commit": repo_commit,
        "data_epoch": profile["data_epoch_prefix"] + repo_commit[:7],
        "method_identity": method_identity,
        "data_identity": config_hash,
        "canonical_evidence_identity": config_hash,
        "data_artifact_role": data_artifact_role,
        "canonical_data_release_eligible": data_release_eligible,
        "record_count": len(records),
        "set_count": len(included_sets),
        "retained_run_count": sum(len(v) for v in canonical_runs.values()),
        "semantic_run_binding_count": sum(len(v) for v in canonical_runs.values()),
        "unique_acquisition_count": len({
            acquisition_id
            for record in records
            for acquisition_id in record.get("provenance", {}).get("acquisition_ids", [])
        }),
        "independent_measurement_cohort_count": len(set(measurement_cohort_ids)),
        "shared_evidence_alias_group_count": len(shared_evidence_alias_groups),
        "ramp_review_run_count": sum(len(v) for v in ramp_reviews_by_set.values()),
        "ramp_review_set_count": len(ramp_reviews_by_set),
        "ramp_review_required": bool(ramp_reviews_by_set),
        "curve_domain_max_mm": curve_domain_max_mm,
        "force_wall_domain_max_mm": force_wall_domain_max_mm,
    }
    record_ids = {}
    for r in records:
        record_ids.setdefault(r["set"], []).append(r.get("test_id"))
    inj = ("const VIEWER_BUILD = " + json.dumps(build_identity, sort_keys=True, separators=(",", ":"))
           + "; /* generated build/method/intake/data identities */\n"
           + "const PERCEPTION_MODEL = "
           + json.dumps(perception.MODEL, sort_keys=True, separators=(",", ":"))
           + "; /* pilot-derived presentation indices; canonical evidence is unchanged */\n"
           + "const RECORD_IDS_BY_SET = " + json.dumps(record_ids, sort_keys=True, separators=(",", ":"))
           + "; /* explicit record identities; a source set may back multiple records */\n"
           + "const CANONICAL_RUNS = " + json.dumps(canonical_runs, sort_keys=True, separators=(",", ":"))
           + "; /* generated retained membership per set */\n"
           + "const INTAKE_RAMP_REVIEWS_BY_SET = "
           + json.dumps(ramp_reviews_by_set, sort_keys=True, separators=(",", ":"))
           + "; /* generated warning-only evidence; never changes membership */\n"
           + "const GENERATED_EXCLUSIONS = " + json.dumps(gen_excl)
           + "; /* generated from config/exclusions.json */\n")
    if viewer_is_generated_template:
        v = _replace_blob(v, "VIEWER_BUILD", build_identity)
        v = _replace_blob(v, "PERCEPTION_MODEL", perception.MODEL)
        v = _replace_blob(v, "RECORD_IDS_BY_SET", record_ids)
        v = _replace_blob(v, "CANONICAL_RUNS", canonical_runs)
        v = _replace_blob(v, "INTAKE_RAMP_REVIEWS_BY_SET", ramp_reviews_by_set)
        v = _replace_blob(v, "GENERATED_EXCLUSIONS", gen_excl)
        retained_decl = (
            "const RETEST_SETS = new Set(GENERATED_EXCLUSIONS); "
            "/* generated exclusion registry — no hardcoded set names */"
        )
        if v.count(retained_decl) != 1:
            raise RuntimeError(
                "viewer generated RETEST_SETS declaration is missing or ambiguous"
            )
    else:
        v, n_ret = re.subn(r"const RETEST_SETS = new Set\(\[[^\]]*\]\);",
                           inj + "const RETEST_SETS = new Set(GENERATED_EXCLUSIONS); "
                           "/* generated exclusion registry — no hardcoded set names */", v)
        if n_ret != 1:
            raise RuntimeError(f"viewer RETEST_SETS injection: expected 1 site, found {n_ret}")
    staged["packs/viewer.staged.html"] = v

    # ---- picker transform ----------------------------------------------
    p = picker_src
    if picker_is_generated_template:
        # Generated-native builder template: validate the complete evidence
        # model, but inject only the narrow consumer projection used by the
        # component workflow. Full records, curves, run membership, and raw
        # provenance remain generated artifacts rather than browser payload.

        rm_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "config", "parts_record_map.json")
        with open(rm_path, encoding="utf-8") as fh:
            rm_cfg = json.load(fh)
        rm = rm_cfg["records"]
        live_ids = {r["test_id"] for r in records}
        for r in records:
            entry = rm.get(r["test_id"])
            if not entry:
                raise RuntimeError(
                    f"parts_record_map.json is missing canonical record {r['test_id']}")
            if entry.get("kind") != r["kind"] or entry.get("set") != r["set"]:
                raise RuntimeError(
                    f"parts_record_map.json is stale for {r['test_id']}: "
                    f"{entry.get('kind')}/{entry.get('set')} != {r['kind']}/{r['set']}")
        stale = sorted(set(rm) - live_ids)
        if stale:
            raise RuntimeError(
                f"parts_record_map.json names records outside the canonical fleet: {stale[:4]}")
        _, _, db_rows = _extract_blob(p, "const DOME_DB")
        _, _, ring_rows = _extract_blob(p, "RINGPARTS")
        ec_match = re.search(r"const EC=(\{.*?\});\r?\nconst DOME_DB=", p, re.S)
        if not ec_match:
            raise RuntimeError("picker template: EC product graph anchor not found")
        ec_obj = json.loads(ec_match.group(1))
        dome_ids = {d["id"] for d in db_rows}
        catalog_part_ids = ({x["id"] for x in ec_obj["PARTS"]}
                            | {x["id"] for x in ec_obj["SHELLS"]}
                            | {x["id"] for x in ring_rows})
        for tid, entry in rm.items():
            target = entry["target"]
            if target.startswith("dome_db:"):
                if target[8:] not in dome_ids:
                    raise RuntimeError(
                        f"parts_record_map target {target} for {tid} is not in DOME_DB")
            elif target.startswith("part:"):
                if target[5:] not in catalog_part_ids:
                    raise RuntimeError(
                        f"parts_record_map target {target} for {tid} is not a catalog part")
            else:
                raise RuntimeError(f"parts_record_map target {target} for {tid} is malformed")
        # Stable-ID compatibility evidence and source-backed keyboard presets.
        cfg_dir = os.path.dirname(rm_path)
        with open(os.path.join(cfg_dir, "compat_evidence.json"), encoding="utf-8") as fh:
            ce_cfg = json.load(fh)
        ce = {}
        for e in ce_cfg["pairs"]:
            key = "||".join(sorted([e["a"], e["b"]]))
            ce[key] = {"st": e["state"], "src": e["source"], "nid": e["note_id"],
                       "q": e["qualifier"], "adj": e["adjudication"],
                       "rsn": e.get("reason"), "id": e["id"],
                       "refs": e.get("source_refs", []),
                       "rev": e.get("last_reviewed")}
        if len(ce) != len(ce_cfg["pairs"]):
            raise RuntimeError("compat evidence: duplicate pair keys")
        for key, e in ce.items():
            if e["st"] not in ("compatible", "incompatible", "conditional",
                               "pending", "unknown", "not_applicable"):
                raise RuntimeError(f"compat evidence: bad state {e['st']} for {key}")
        # The complete closure is validated above and remains an auditable
        # generated artifact. A smaller public projection is selected after
        # the visible catalog has been resolved below.
        with open(os.path.join(cfg_dir, "presets.json"), encoding="utf-8") as fh:
            pr_cfg = json.load(fh)

        # Minimal, exact-specimen dome projection for the chooser. Do not
        # aggregate families or expose curve/provenance payload in the tool.
        dome_measurements = []
        rec_by_id2 = {r["test_id"]: r for r in records}
        for tid, entry in sorted(rm.items()):
            if not entry["target"].startswith("dome_db:"):
                continue
            rec = rec_by_id2[tid]
            if rec.get("kind") != "dome_baseline":
                raise RuntimeError(
                    f"dome measurement {tid} is not a dome_baseline record")
            perceptual = perception_by_id.get(tid)
            if perceptual is None:
                raise RuntimeError(f"dome measurement score missing for {tid}")
            collapse = rec.get("collapse_force_gf")
            if not isinstance(collapse, (int, float)) or isinstance(collapse, bool):
                raise RuntimeError(f"dome measurement collapse force missing for {tid}")
            force_wall = rec.get("travel_mm")
            if force_wall is not None and (
                    not isinstance(force_wall, (int, float))
                    or isinstance(force_wall, bool)
                    or not math.isfinite(force_wall)):
                raise RuntimeError(f"dome measurement force wall invalid for {tid}")
            dome_measurements.append({
                "catalog_id": entry["target"][8:],
                "specimen_id": rec.get("tested_part"),
                "label": rec.get("name") or rec.get("set"),
                "collapse_force_gf": collapse,
                "weight_index": perceptual["weight_index"],
                "tactility_index": perceptual["tactility_index"],
                # Canonical travel_mm is the detected force-wall onset. Keep
                # the source precision here and round only in the UI.
                "force_wall_mm": force_wall,
            })
        p = _replace_blob(p, "DOME_MEASUREMENTS", dome_measurements)

        with open(os.path.join(cfg_dir, "r8_crosswalk.json"), encoding="utf-8") as fh:
            xw_cfg = json.load(fh)["records"]
        dome_r8 = {e["catalog_id"]: e["r8_id"] for e in xw_cfg.values()
                   if e.get("category") == "dome" and e.get("r8_id")}
        r8_dome_vals = set(dome_r8.values())
        for r in records:
            if r.get("kind") == "part_assembly" and r.get("dome") not in r8_dome_vals:
                raise RuntimeError(
                    f"assembly dome {r.get('dome')} has no catalog identity")
        # The catalog remains data-driven. MODPARTS and KEYBOARDS regenerate
        # from the vendored r8 source plus the authored presentation overlay.
        with open(os.path.join(cfg_dir, "r8", "parts.json"), encoding="utf-8") as fh:
            r8_parts_full = json.load(fh)
        with open(os.path.join(cfg_dir, "r8", "keyboards.json"), encoding="utf-8") as fh:
            r8_kbd_full = json.load(fh)
        with open(os.path.join(cfg_dir, "catalog_overlay.json"), encoding="utf-8") as fh:
            cat_ov = json.load(fh)
        with open(os.path.join(cfg_dir, "stabilizer_assemblies.json"), encoding="utf-8") as fh:
            assembly_cfg = json.load(fh)
        with open(os.path.join(cfg_dir, "owner_starting_point_defaults.json"), encoding="utf-8") as fh:
            owner_defaults_cfg = json.load(fh)
        if assembly_cfg.get("schema") != "stabilizer-assemblies-v1":
            raise RuntimeError("unsupported stabilizer assembly schema")
        if owner_defaults_cfg.get("schema") != "owner-starting-point-defaults-v1":
            raise RuntimeError("unsupported owner starting-point defaults schema")
        explicit_none_cfg = owner_defaults_cfg.get("explicit_none_parts")
        if not isinstance(explicit_none_cfg, dict) or not explicit_none_cfg:
            raise RuntimeError("owner starting-point defaults need explicit-none records")
        explicit_none_parts = [
            {"id": part_id, "name": row.get("name") or part_id,
             "slot": row.get("slot"), "meaning": row.get("meaning") or ""}
            for part_id, row in sorted(explicit_none_cfg.items())
        ]
        if (any(row["slot"] not in ("dome", "sb") for row in explicit_none_parts)
                or len({row["id"] for row in explicit_none_parts}) != len(explicit_none_parts)):
            raise RuntimeError("owner explicit-none records have invalid or duplicate ids")
        explicit_none_ids = {row["id"] for row in explicit_none_parts}
        public_assemblies = assembly_cfg.get("assemblies")
        if not isinstance(public_assemblies, list) or not public_assemblies:
            raise RuntimeError("stabilizer assembly catalog is empty")
        assembly_ids = [row.get("id") for row in public_assemblies]
        if (any(not isinstance(value, str) or not value for value in assembly_ids)
                or len(assembly_ids) != len(set(assembly_ids))):
            raise RuntimeError("stabilizer assembly ids must be unique strings")

        # Synchronize the browser catalog with the stable r8 source. The
        # single-file template carries the previous rows as review scaffolding;
        # generation updates them by rid and appends newly authored records.
        category_to_catalog = {
            "slider": "Sliders",
            "stabilizer_slider": "Stabilizer Sliders",
            "stabilizer_housing": "Stabilizer Housings",
            "housing": "Housings",
            "spacebar_stabilizer": "Spacebar Stabilizer",
            "conical_spring": "Conical Springs",
        }
        part_issue_states = {
            "incompatible": ("bad", "Does not work"),
            "pending": ("unverified", "Not verified"),
        }
        part_issues = {}
        for rid, src in sorted(r8_parts_full.items()):
            raw_issue = src.get("part_issue")
            if raw_issue is None:
                continue
            if (not isinstance(raw_issue, dict)
                    or set(raw_issue) != {"scope", "status", "reason"}
                    or raw_issue.get("scope") != "part"
                    or raw_issue.get("status") not in part_issue_states
                    or not isinstance(raw_issue.get("reason"), str)
                    or not raw_issue["reason"].strip()):
                raise RuntimeError(f"r8 part issue is malformed for {rid}")
            state, label = part_issue_states[raw_issue["status"]]
            part_issues[rid] = {
                "scope": "part",
                "state": state,
                "label": label,
                "text": raw_issue["reason"].strip(),
            }
        part_issue_rids = set(part_issues)
        ec_by_rid = {row.get("rid") or row["id"]: row
                     for row in ec_obj["PARTS"]}
        for rid, src in sorted(r8_parts_full.items()):
            category = src.get("category")
            if category not in category_to_catalog or src.get("tier") != "builder":
                continue
            catalog_id = xw_cfg[rid]["catalog_id"]
            row = ec_by_rid.get(rid)
            if row is None:
                row = {"id": catalog_id, "rid": rid}
                ec_obj["PARTS"].append(row)
                ec_by_rid[rid] = row
            row.update({
                "id": catalog_id,
                "rid": rid,
                "name": src["part_name"],
                "cat": category_to_catalog[category],
                "mfr": src.get("manufacturer") or src.get("brand") or "",
                "type": ("OEM TOPRE" if src.get("manufacturer") == "Topre"
                         else "AFTERMARKET"),
                "stem": src.get("stem") or "",
                "seat": src.get("ring_seat_mm"),
                "off": src.get("ring_offset_mm", 0),
                "travel": src.get("travel_mm"),
                "hideTravel": bool(src.get("hide_nominal_travel", False)),
                "style": src.get("version") or "",
                "u": src.get("source_url") or "",
                "notes": list(src.get("notes") or []),
                "ringFit": src.get("ring_fit_policy"),
            })
            # Legacy templates carried the spring reliability warning as a
            # presentation-only string. Part-scoped compatibility findings are
            # now structured source data and must be the sole public form.
            row.pop("springWarn", None)
            row.pop("partIssue", None)
            if rid in part_issues:
                row["partIssue"] = part_issues[rid]
        ec_obj["PARTS"].sort(key=lambda row: row["id"])

        ring_by_id = {row["id"]: row for row in ring_rows}
        for rid, src in sorted(r8_parts_full.items()):
            if src.get("category") != "silencing_ring" or src.get("tier") != "builder":
                continue
            row = ring_by_id.get(rid)
            if row is None:
                row = {"id": rid}
                ring_rows.append(row)
                ring_by_id[rid] = row
            material = str(src.get("material") or "")
            row.update({
                "id": rid,
                "name": src["part_name"],
                "t": src.get("thickness_mm"),
                "mat": material.title(),
                "brand": src.get("brand") or "",
                "hard": src.get("hardness") or "",
                "mfr": src.get("manufacturer") or src.get("brand") or "",
                "u": src.get("source_url") or "",
                "notes": list(src.get("notes") or []),
            })
        ring_rows.sort(key=lambda row: row["id"])

        db_by_id = {row["id"]: row for row in db_rows}
        for rid, src in sorted(r8_parts_full.items()):
            if src.get("category") != "dome":
                continue
            catalog_id = xw_cfg[rid]["catalog_id"]
            if catalog_id in db_by_id:
                continue
            weight = src.get("weight")
            if isinstance(weight, dict):
                values = [value for value in weight.values()
                          if isinstance(value, (int, float))
                          and not isinstance(value, bool)]
                wmin = min(values) if values else None
                wmax = max(values) if values else None
                wraw = src.get("weight_label") or "Variable"
            else:
                wmin = wmax = (weight if isinstance(weight, (int, float))
                               and not isinstance(weight, bool) else None)
                wraw = (src.get("weight_label")
                        or (f"{weight:g}g" if wmin is not None else ""))
            row = {
                "id": catalog_id,
                "name": src["part_name"],
                "maker": src.get("manufacturer") or src.get("brand") or "",
                "brand": src.get("brand") or "",
                "wraw": wraw,
                "wmin": wmin,
                "wmax": wmax,
                "type": ("OEM TOPRE" if src.get("manufacturer") == "Topre"
                         else "AFTERMARKET"),
                "u": src.get("source_url") or "",
                "version": src.get("version") or "",
                "style": src.get("style") or "",
            }
            db_rows.append(row)
            db_by_id[catalog_id] = row
        db_rows.sort(key=lambda row: row["id"])
        dome_ids = {row["id"] for row in db_rows}
        display_names = cat_ov.get("dome_display_names", {})
        unknown_display_ids = sorted(set(display_names) - dome_ids)
        if unknown_display_ids:
            raise RuntimeError(
                f"catalog overlay names unknown DOME_DB ids: {unknown_display_ids}")
        for row in db_rows:
            if row["id"] in display_names:
                row["name"] = display_names[row["id"]]
        dome_public_fields = (
            "id", "name", "maker", "brand", "version", "style",
            "wraw", "wmin", "wmax", "type", "u",
        )
        public_domes = [
            {key: row[key] for key in dome_public_fields if key in row}
            for row in db_rows
        ]
        p = _replace_blob(p, "const DOME_DB", public_domes)
        cat_labels = cat_ov["category_labels"]
        modparts = []
        for rid, e in sorted(xw_cfg.items()):
            if e["disposition"] != "integrated_round2":
                continue
            src = r8_parts_full[rid]
            # lib-6.0 has no public catch-all parts list. Only records that
            # fill a visible builder slot belong in the consumer payload;
            # today, the r8 additions used by that workflow are keycaps.
            if src.get("category") != "keycap":
                continue
            modparts.append({
                "id": rid, "rid": rid, "name": src["part_name"],
                "cat": cat_labels[src["category"]],
                "brand": src.get("brand") or "",
                "mfr": src.get("manufacturer") or "",
                "stem": src.get("stem") or "",
                "notes": list(src.get("notes") or []),
                "u": src.get("source_url") or ""})
        public_keyboard_ids = cat_ov.get("public_keyboard_ids")
        if not isinstance(public_keyboard_ids, list) or not public_keyboard_ids:
            raise RuntimeError(
                "catalog overlay: public_keyboard_ids must be a non-empty list")
        if len(public_keyboard_ids) != len(set(public_keyboard_ids)):
            raise RuntimeError("catalog overlay: duplicate public keyboard id")
        public_brand_kit_ids = cat_ov.get("public_brand_kit_ids", [
            "kit::deskeys", "kit::dynacaps", "kit::klc", "kit::metakeebs",
        ])
        if (not isinstance(public_brand_kit_ids, list)
                or len(public_brand_kit_ids) != len(set(public_brand_kit_ids))):
            raise RuntimeError("catalog overlay: invalid public brand-kit ids")
        preset_by_id = {row.get("id"): row for row in pr_cfg["presets"]}
        public_presets = []
        kbrows = []
        for starter_id in public_keyboard_ids + public_brand_kit_ids:
            is_keyboard = starter_id in public_keyboard_ids
            if is_keyboard and starter_id not in r8_kbd_full:
                raise RuntimeError(
                    f"catalog overlay: public keyboard {starter_id} is absent from r8")
            preset = preset_by_id.get(starter_id)
            if not preset:
                raise RuntimeError(
                    f"catalog overlay: public starter {starter_id} has no preset")
            expected_source = ("r8_keyboard_registry" if is_keyboard
                               else "authored_brand_kit")
            if preset.get("source") != expected_source:
                raise RuntimeError(
                    f"catalog overlay: public starter {starter_id} has source "
                    f"{preset.get('source')!r}, expected {expected_source!r}")
            if not preset.get("slots"):
                raise RuntimeError(
                    f"catalog overlay: public starter {starter_id} has no usable slots")
            # The browser needs only the starter identity, visible label, and
            # selections. Source/adjudication/omission records remain in the
            # generator-owned preset registry where they are validated.
            public_preset = {
                "id": preset["id"],
                "label": preset["label"],
                "brand": preset.get("brand") or "",
                "kind": "keyboard" if is_keyboard else "kit",
                "notes": preset.get("notes") or "",
                "slots": {
                    slot: {"part": selection["part"]}
                    for slot, selection in preset["slots"].items()
                },
            }
            empty = preset.get("empty") or {}
            notice_keys = ("dome", "ring", "stab2uAssembly", "ring2u", "sb")
            notices = []
            if not is_keyboard:
                notices.append(
                    "Loads this manufacturer's catalog parts as a shortcut; "
                    "it is not a verified working configuration."
                )
            generic_prefixes = ("not specified by the r8 keyboard registry",
                                "not specified by this brand kit",
                                "represented by the selected")
            for key in notice_keys:
                reason = empty.get(key)
                if (not reason or key in preset["slots"]
                        or str(reason).startswith(generic_prefixes)):
                    continue
                cleaned = re.sub(r"\b(\d+)g\b", r"\1 g", str(reason)).strip()
                if cleaned and cleaned[-1] not in ".!?":
                    cleaned += "."
                notices.append(cleaned)
            if notices:
                public_preset["notice"] = " ".join(dict.fromkeys(notices))
            public_presets.append(public_preset)
            if not is_keyboard:
                continue
            k = r8_kbd_full[starter_id]
            consumer_notes = k.get("notes") or ""
            for note_id, note in ec_obj.get("NOTES", {}).items():
                consumer_notes = re.sub(
                    rf"\bSee\s+{re.escape(note_id)}\.",
                    str(note.get("text") or ""),
                    consumer_notes,
                    flags=re.IGNORECASE,
                )
            consumer_notes = re.sub(r"\s+", " ", consumer_notes).strip()
            kbrows.append({
                "id": starter_id, "rid": starter_id, "name": k["display_name"],
                "brand": k.get("brand") or "", "kind": k.get("kind") or "",
                "notes": consumer_notes,
                "u": k.get("source_url") or k.get("url") or ""})

        # Validate every public preset target against the exact catalog that
        # will ship. Dome IDs address DOME_DB; all other selections address
        # either a catalog ID or its stable compatibility rid.
        public_part_ids = set()
        public_part_ids.add(cat_ov["ring_none"]["id"])
        for row in ec_obj["PARTS"] + ec_obj["SHELLS"]:
            public_part_ids.add(row["id"])
            public_part_ids.add(row.get("rid") or row["id"])
        for row in ring_rows + modparts:
            public_part_ids.add(row["id"])
            public_part_ids.add(row.get("rid") or row["id"])
        for assembly in public_assemblies:
            if assembly.get("housingMode") not in ("shell", "loose"):
                raise RuntimeError(
                    f"2u assembly {assembly.get('id')} has invalid housingMode")
            slots = assembly.get("slots")
            if not isinstance(slots, dict) or set(slots) != {"h2", "sl2", "ring2u"}:
                raise RuntimeError(
                    f"2u assembly {assembly.get('id')} must define h2/sl2/ring2u")
            if assembly["housingMode"] == "shell" and slots["h2"] is not None:
                raise RuntimeError(
                    f"shell-owned 2u assembly {assembly['id']} cannot load loose h2")
            if assembly["housingMode"] == "loose" and slots["h2"] is None:
                raise RuntimeError(
                    f"loose 2u assembly {assembly['id']} must load h2")
            for slot, part_id in slots.items():
                if part_id is not None and part_id not in public_part_ids:
                    raise RuntimeError(
                        f"2u assembly {assembly['id']} references unavailable "
                        f"{slot} part {part_id}")
            public_part_ids.add(assembly["id"])
        public_part_ids.update(explicit_none_ids)
        for preset in public_presets:
            for slot, selection in preset["slots"].items():
                part_id = selection.get("part")
                known = part_id in ((dome_ids | explicit_none_ids)
                                    if slot == "dome" else public_part_ids)
                if not known:
                    raise RuntimeError(
                        f"public preset {preset['id']} references unavailable "
                        f"{slot} part {part_id}")

        # The public tool never co-selects two alternatives from one slot,
        # and its shell replaces the housing/stabilizer slots. Accordingly,
        # not_applicable closure rows cannot be queried. Explicit unknown rows
        # are also equivalent to the runtime's visible Not verified fallback.
        # Keep only decision-changing evidence for pairs of parts that can
        # actually appear in this builder; the full 3,403-pair audit closure
        # stays in compat_evidence.json.
        public_rids = ({row.get("rid") or row["id"] for row in ec_obj["PARTS"]}
                       | {row.get("rid") or row["id"] for row in ec_obj["SHELLS"]}
                       | {row["id"] for row in ring_rows}
                       | {row.get("rid") or row["id"] for row in modparts})
        ce_runtime = {
            key: {
                "st": evidence["st"],
                "nid": evidence["nid"],
                "q": evidence["q"],
                "adj": evidence["adj"],
                "rsn": evidence["rsn"],
            }
            for key, evidence in ce.items()
            if evidence["st"] not in ("unknown", "not_applicable")
            and set(key.split("||")) <= public_rids
            and not (set(key.split("||")) & part_issue_rids)
        }
        part_fields = (
            "id", "rid", "name", "cat", "mfr", "type", "stem",
            "seat", "off", "travel", "hideTravel", "style", "u", "notes",
            "partIssue", "ringFit",
        )
        shell_fields = (
            "id", "rid", "name", "mfr", "type", "off", "u", "addsSb", "shellNote",
        )
        def consumer_note_text(value):
            text = str(value or "")
            text = text.replace(
                "Effect = ring - (slider seat + 0.2).",
                "Fit delta = (slider seat + housing seat) - ring thickness.",
            )
            text = re.sub(
                r"(?:;\s*)?owner adjudication (?:is )?pending[^.]*\.?",
                ". This pairing has not been independently confirmed.",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(
                r"The r8 source records that claim as a conditional exception, "
                r"not a per-pairing verification\.?",
                "The claim is recorded as a condition rather than a verified "
                "result for every pairing.",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(r"^Warning:\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\.\*\s*\|\s*\*\s*", ". ", text)
            text = re.sub(
                r"\s*Omitted from product page\.?", "", text,
                flags=re.IGNORECASE,
            )
            text = re.sub(r"\s+([.,;:])", r"\1", text)
            return re.sub(r"\.{2,}", ".", text).strip()
        runtime_note_ids = {
            evidence["nid"] for evidence in ce_runtime.values()
            if evidence.get("nid")
        } | {"note_deskeys_housing", "note_dynacaps_housing"}
        public_ec = {
            "PARTS": [
                {key: row[key] for key in part_fields if key in row}
                for row in ec_obj["PARTS"]
            ],
            "SHELLS": [
                {key: row[key] for key in shell_fields if key in row}
                for row in ec_obj["SHELLS"]
            ],
            "NOTES": {
                note_id: {"text": consumer_note_text(note.get("text"))}
                for note_id, note in ec_obj.get("NOTES", {}).items()
                if note_id in runtime_note_ids
            },
        }
        p = _replace_blob(p, "const EC", public_ec)
        p = _replace_blob(p, "RINGPARTS", ring_rows)
        p = _replace_blob(p, "COMPAT_EVIDENCE", ce_runtime)
        p = _replace_blob(p, "const PRESETS", public_presets)
        p = _replace_blob(p, "STABILIZER_ASSEMBLIES_2U", public_assemblies)
        p = _replace_blob(p, "const NONE_PARTS", explicit_none_parts)
        p = _replace_blob(p, "const MODPARTS", modparts)
        p = _replace_blob(p, "const KEYBOARDS", kbrows)
        from .pipeline import parts_library_source_identity, _h
        plsi = _h(parts_library_source_identity())
        parts_profile = PARTS_LIBRARY_BUILD_PROFILES[profile["mode"]]
        picker_build = {
            "library_build": parts_profile["library_build"],
            "mode": profile["mode"],
            "presentation_role": profile["presentation_role"],
            "release_eligible": parts_profile["release_eligible"],
            "repo_commit": dataset_manifest["repo_commit"],
            "parts_library_source_identity": plsi,
        }
        p = _replace_blob(p, "PICKER_BUILD", picker_build)

        if "function assessCandidate(" not in p or "function assessBuild(" not in p:
            raise RuntimeError("picker compatibility presentation contract is missing")
    else:
        p = _replace_blob(p, "const TESTS", ptests)
        p = _replace_blob(p, "MINI_CURVES", mini)
        p = _replace_function(p, "averageStrokes", js_average_source(cfg_rule))
        p = _replace_function(p, "analyze",
            "/* Retired in metrics-v4.2: the picker consumes generated records and contains no metric analyzer. */")

        # SNAPSHOT_TESTS: generated from retained record snapshots, not a hand duplicate.
        snapshot = []
        for r in records:
            if r["set"] in excluded:
                continue
            sn, en = r.get("snap_pct"), r.get("full_stroke_press_work_gf_mm")
            stat = ("not available" if sn is None or en is None
                    else f"Snap {int(round(sn))}% \u00b7 {int(round(en))} gf\u00b7mm")
            snapshot.append([r.get("name") or r["set"].replace("_", " "), stat])
        snapshot.sort()
        p, n_sn = re.subn(r"const SNAPSHOT_TESTS=\[.*?\];",
                          "const SNAPSHOT_TESTS=" +
                          json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) +
                          "; /* generated from retained record snapshots */",
                          p, count=1, flags=re.S)
        if n_sn != 1:
            raise RuntimeError("picker SNAPSHOT_TESTS: generation target not found")

        # Generated exclusions + retained-run membership, and the curve contract.
        pinj = ("const CANONICAL_RUNS = " + json.dumps(canonical_runs, sort_keys=True, separators=(",", ":"))
                + "; /* generated retained membership per set */\n"
                + "const GENERATED_EXCLUSIONS = " + json.dumps(gen_excl)
                + "; /* generated from config/exclusions.json */\n")
        anchor = "const FCURL="
        if p.count(anchor) != 1:
            raise RuntimeError("picker: FCURL anchor not unique")
        p = p.replace(anchor, pinj + anchor, 1)

        p = _replace_function(p, "prevCurveSVG", PICKER_PREVCURVE)
        p = _replace_function(p, "benchValsHTML", PICKER_BENCHVALS)
        p = _replace_function(p, "testStat", PICKER_TESTSTAT)
        p = _replace_function(p, "loadDomes", PICKER_LOADDOMES)
        # curve contract helpers must follow curveKey/curveFor definitions
        p = p.replace("function curveFor(setName){ const k=curveKey(setName); return k?MINI_CURVES[k]:null; }",
                      "function curveFor(setName){ const k=curveKey(setName); return k?MINI_CURVES[k]:null; }\n"
                      + PICKER_CURVE_CONTRACT, 1)

        # Detail-panel bench table: route through the generated-record accessors.
        p, n_det = re.subn(r"const t=p\.tests\[0\], c=curveFor\(t\.set\);",
                           "const t=p.tests[0], c=benchFor(t.set);", p, count=1)
        if n_det != 1:
            raise RuntimeError("picker detail-panel accessor: target not found")
        old_det_start = p.index('d+=`<table class="det-props det-test">')
        old_det_end = p.index("</table>`+prevCurveSVG(t.set)+", old_det_start)
        p = p[:old_det_start] + "d+=benchValsHTML(t.set)" + p[old_det_end + len("</table>`"):]

    staged["packs/picker.staged.html"] = p

    # ---- prohibited-copy scan across EVERY generated surface ------------
    surfaces = {k: val for k, val in staged.items() if isinstance(val, str)}
    # The prohibited-copy gate governs presentation copy; prose.scan masks
    # the labeled verbatim r8 source layer itself (see
    # prose.mask_verbatim_source), so every authored and generated
    # presentation string is scanned in full through the one shared
    # definition. The exempted span is recorded in the report.
    r8_span = 0
    pk_key = next((k for k in surfaces if k.endswith("picker.staged.html")), None)
    if pk_key:
        r8_span = prose.mask_verbatim_source(surfaces[pk_key])[1]
    prose.assert_clean(surfaces)
    staged["packs/prose_scan_report.json"] = json.dumps({
        "scanned_surfaces": sorted(surfaces),
        "prohibited_patterns": prose.PROHIBITED,
        "viewer_rewrites": [{"target": o[:80], "occurrences_replaced": n} for o, n in vlog],
        "picker_rewrites": [{"target": o[:80], "occurrences_replaced": n} for o, n in plog],
        "r8_src_verbatim_exempt_chars": r8_span,
        "result": "clean — zero prohibited matches in any generated "
                  "presentation surface (the labeled verbatim r8 source "
                  "layer is exempt by design)",
    }, sort_keys=True, indent=1) + "\n"
    return staged
