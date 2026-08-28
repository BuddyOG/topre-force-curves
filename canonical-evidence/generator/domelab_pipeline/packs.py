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
import json, re, os
from .curves import grid_average, js_average_source
from .reference_js import js_reference_analyzer_source
from .core import config
from . import prose


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

# One switch controls the review-only chrome.  The final fleet regeneration can
# mechanically change these identities and set ``mode`` to ``release`` without
# editing the HTML template or its runtime logic.
VIEWER_BUILD_PROFILE = {
    "mode": "review",
    "bench_build": "fc-3.1-review.2",
    "data_epoch_prefix": "preview-",
    # Known generated/reference packs include samples at 4.500 mm.  The axis
    # still expands from actual data; this floor prevents a review build from
    # regressing to the old 4.0/4.04 mm assumption when a filtered preview has
    # a shorter current endpoint.
    "axis_data_floor_mm": 4.5,
}

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


def _replace_blob(html, name, payload):
    i, j, _ = _extract_blob(html, name)
    return html[:i] + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + html[j:]


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
                    intake_manifest, viewer_path, picker_path):
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
    with open(picker_path, encoding="utf-8", newline="") as f:
        picker_src = f.read()

    # Scientific copy is corrected on the RAW templates first, so that later
    # structural transforms operate on already-clean text and the declared
    # occurrence counts refer to the release template rather than to whatever
    # a preceding transform happened to leave behind.
    viewer_src, vlog = prose.apply_claims(viewer_src, prose.VIEWER_CLAIMS, "viewer")
    picker_src, plog = prose.apply_claims(picker_src, prose.PICKER_CLAIMS, "picker")
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
    vtests = []
    for r in records:
        base = dict(vt_by_id.get((r["set"], r.get("name")), {}))
        base.update({"k": r.get("kind"), "n": r.get("name"), "set": r["set"], "runs": r["runs_used"]})
        base.update({
            "id": r.get("test_id"),
            "source_set": r["set"],
            "quality_flags": r.get("quality_flags", []),
            "null_reasons": r.get("null_reasons", {}),
            "intake_review_count": len(r.get("intake_review_notices", [])),
            "tl_min": turnaround_by_set.get(r["set"], {}).get("min"),
            "tl_max": turnaround_by_set.get(r["set"], {}).get("max"),
        })
        for kk, (mk, rnd) in VIEWER_METRIC.items():
            base[kk] = rnd(r[mk])
        vtests.append(base)
    staged["packs/viewer_embedded.json"] = json.dumps(embedded, sort_keys=True, separators=(",", ":")) + "\n"
    staged["packs/viewer_vtests.json"] = json.dumps(vtests, sort_keys=True, separators=(",", ":")) + "\n"

    # ---- picker test records -------------------------------------------
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
    v = _apply(v, "<b>Travel</b> is detected where the force-wall pattern begins",
               "<b>Detected force-wall onset</b> is the first point where the force-wall pattern begins",
               "public force-wall metric name")
    if v.count("from 0 to Travel") != 2:
        raise RuntimeError("viewer: expected two legacy Travel endpoints after prose control")
    v = v.replace("from 0 to Travel", "from 0 to detected force-wall onset")
    v = _apply(v, "an operational bottom-out proxy rather than observed contact",
               "an operational test-assembly proxy rather than nominal or physical travel",
               "force-wall assembly scope")
    v = v.replace("DROP TRAVEL", "COLLAPSE-TO-VALLEY DISTANCE")
    v = _replace_blob(v, "EMBEDDED", embedded)
    v = _replace_blob(v, "VTESTS", vtests)
    fallback = sorted(r["rel_path"] for s2 in included_sets for r in retained_by_set[s2])
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
    build_identity = {
        **VIEWER_BUILD_PROFILE,
        "metrics": method_cfg["metrics_version"],
        "intake": intake_manifest["policy_version"],
        "intake_parity_target": intake_cfg["parity_target"],
        "repo_commit": repo_commit,
        "data_epoch": VIEWER_BUILD_PROFILE["data_epoch_prefix"] + repo_commit[:7],
        "method_identity": method_identity,
        "data_identity": config_hash,
        "record_count": len(records),
        "set_count": len(included_sets),
        "retained_run_count": sum(len(v) for v in canonical_runs.values()),
        "ramp_review_run_count": sum(len(v) for v in ramp_reviews_by_set.values()),
        "ramp_review_set_count": len(ramp_reviews_by_set),
        "ramp_review_required": bool(ramp_reviews_by_set),
        "curve_domain_max_mm": curve_domain_max_mm,
    }
    record_ids = {}
    for r in records:
        record_ids.setdefault(r["set"], []).append(r.get("test_id"))
    inj = ("const VIEWER_BUILD = " + json.dumps(build_identity, sort_keys=True, separators=(",", ":"))
           + "; /* generated build/method/intake/data identities */\n"
           + "const RECORD_IDS_BY_SET = " + json.dumps(record_ids, sort_keys=True, separators=(",", ":"))
           + "; /* explicit record identities; a source set may back multiple records */\n"
           + "const CANONICAL_RUNS = " + json.dumps(canonical_runs, sort_keys=True, separators=(",", ":"))
           + "; /* generated retained membership per set */\n"
           + "const INTAKE_RAMP_REVIEWS_BY_SET = "
           + json.dumps(ramp_reviews_by_set, sort_keys=True, separators=(",", ":"))
           + "; /* generated warning-only evidence; never changes membership */\n"
           + "const GENERATED_EXCLUSIONS = " + json.dumps(gen_excl)
           + "; /* generated from config/exclusions.json */\n")
    v, n_ret = re.subn(r"const RETEST_SETS = new Set\(\[[^\]]*\]\);",
                       inj + "const RETEST_SETS = new Set(GENERATED_EXCLUSIONS); "
                       "/* generated exclusion registry — no hardcoded set names */", v)
    if n_ret != 1:
        raise RuntimeError(f"viewer RETEST_SETS injection: expected 1 site, found {n_ret}")
    staged["packs/viewer.staged.html"] = v

    # ---- picker transform ----------------------------------------------
    p = picker_src
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
    prose.assert_clean(surfaces)
    staged["packs/prose_scan_report.json"] = json.dumps({
        "scanned_surfaces": sorted(surfaces),
        "prohibited_patterns": prose.PROHIBITED,
        "viewer_rewrites": [{"target": o[:80], "occurrences_replaced": n} for o, n in vlog],
        "picker_rewrites": [{"target": o[:80], "occurrences_replaced": n} for o, n in plog],
        "result": "clean — zero prohibited matches in any generated surface",
    }, sort_keys=True, indent=1) + "\n"
    return staged
