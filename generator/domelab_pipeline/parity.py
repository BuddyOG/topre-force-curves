"""Full-fleet JS/Python parity: all runs x all 14 metrics via the generated reference analyzer
in jsdom. Deterministic serialization of exact deltas; persisted as a generated
artifact rather than relying on broad test tolerances."""
import json, os, subprocess, tempfile
from .core import PER_RUN_AUDIT_FIELDS

JS = r"""
const {JSDOM}=require('jsdom');const fs=require('fs');
const [viewer,listfile]=process.argv.slice(2);
const files=JSON.parse(fs.readFileSync(listfile,'utf8'));
const dom=new JSDOM(fs.readFileSync(viewer,'utf8'),{runScripts:'dangerously',url:'https://x.test/',
 beforeParse(w){w.requestAnimationFrame=cb=>setTimeout(cb,16);w.cancelAnimationFrame=clearTimeout;
  w.fetch=()=>Promise.reject(new Error('x'));
  w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>()=>({width:10}),set:()=>true});}});
setTimeout(()=>{const w=dom.window;
const out=files.map(f=>{const t=fs.readFileSync(f,'utf8');
  return w.eval(`(function(t){const r=parseCSV(t);return analyze(r.press.x,r.press.F);})`)(t);});
process.stdout.write(JSON.stringify(out)+"\n",()=>process.exit(0));},1400);
"""
def _node_modules():
    """jsdom resolution: env override, packaged js/, then walk up from cwd."""
    cand = [os.environ.get("DOMELAB_NODE_PATH")]
    pkg = os.path.dirname(os.path.abspath(__file__))
    cand.append(os.path.join(os.path.dirname(pkg), "js", "node_modules"))
    d = os.getcwd()
    while True:
        cand.append(os.path.join(d, "node_modules"))
        nd = os.path.dirname(d)
        if nd == d: break
        d = nd
    for c in cand:
        if c and os.path.isdir(os.path.join(c, "jsdom")):
            return c
    raise RuntimeError("jsdom not found: set DOMELAB_NODE_PATH or run npm ci in generator/js")

PAIRS = [("collapse_force_gf", "Fpeak"), ("collapse_travel_mm", "xpeak"),
         ("valley_force_gf", "Fval"), ("valley_travel_mm", "xval"), ("snap_pct", "snap"),
         ("travel_mm", "travel"), ("full_stroke_press_work_gf_mm", "E"),
         ("precollapse_work_gf_mm", "Epc"), ("drop_gf", "dropF"), ("drop_travel_mm", "dropX"),
         ("drop_rate_gf_per_mm", "dropRate"), ("norm_drop_rate_per_mm", "ndr"),
         ("steepest_drop_0p10mm_gf_per_mm", "steep"), ("ramp_10_90_gf_per_mm", "ramp")]

def parity_report(runs_by_set, viewer_path=None, viewer_text=None):
    order, files = [], []
    for s in sorted(runs_by_set):
        for r in runs_by_set[s]:
            order.append((s, r)); files.append(os.path.abspath(r["path"]))
    with tempfile.TemporaryDirectory() as td:
        harness = os.path.join(td, "h.js"); listf = os.path.join(td, "l.json")
        with open(harness, "w", encoding="utf-8", newline="\n") as fh: fh.write(JS)
        with open(listf, "w", encoding="utf-8", newline="\n") as fh: fh.write(json.dumps(files))
        if viewer_text is not None:
            viewer_path = os.path.join(td, "viewer.generated.html")
            with open(viewer_path, "w", encoding="utf-8", newline="\n") as fh: fh.write(viewer_text)
        if viewer_path is None:
            raise ValueError("viewer_path or viewer_text is required")
        env = dict(os.environ)
        env["NODE_PATH"] = _node_modules()
        env["PYTHONUTF8"] = "1"   # deterministic child text I/O regardless of host locale
        out = subprocess.run(["node", harness, os.path.abspath(viewer_path), listf],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                             cwd=os.path.dirname(os.path.abspath(__file__)))
        if out.returncode != 0:
            raise RuntimeError("parity harness failed: " + out.stderr[-500:])
        js = json.loads(out.stdout)
    rows, mx, amx = [], 0.0, 0.0
    for (s, r), j in zip(order, js):
        row = {"set": s, "run": r["rel_path"], "deltas": {}, "audit_deltas": {}}
        for pk, jk in PAIRS:
            a, b = r["metrics"][pk], (j or {}).get(jk)
            if a is None or b is None:
                row["deltas"][pk] = None if (a is None and b is None) else "null-mismatch"
            else:
                d = abs(a - b); row["deltas"][pk] = d; mx = max(mx, d)
        pyflags, jsflags = sorted(r["quality_flags"]), sorted((j or {}).get("flags") or [])
        row["flag_match"] = pyflags == jsflags
        if not row["flag_match"]:
            row["python_flags"], row["js_flags"] = pyflags, jsflags
        ja = (j or {}).get("audit") or {}
        exact_bool = {"force_wall_found", "ramp_band_complete"}
        exact_count = {k for k in PER_RUN_AUDIT_FIELDS if k.endswith("_count")}
        for key in PER_RUN_AUDIT_FIELDS:
            a, b = r["metric_audit"].get(key), ja.get(key)
            if key in exact_bool:
                row["audit_deltas"][key] = None if type(a) is bool and type(b) is bool and a == b else "exact-mismatch"
            elif key in exact_count:
                row["audit_deltas"][key] = None if type(a) is int and type(b) is int and a == b else "exact-mismatch"
            elif a is None or b is None:
                row["audit_deltas"][key] = None if a is None and b is None else "null-mismatch"
            else:
                d = abs(a - b); row["audit_deltas"][key] = d; amx = max(amx, d)
        rows.append(row)
    exact = all(r["flag_match"] and not any(isinstance(v, str) for v in r["deltas"].values())
                and not any(isinstance(v, str) for v in r["audit_deltas"].values()) for r in rows)
    return {"runs": len(rows), "metrics_per_run": len(PAIRS),
            "audit_fields_per_run": len(PER_RUN_AUDIT_FIELDS), "exact_null_flag_audit_match": exact,
            "max_abs_delta": mx, "max_audit_abs_delta": amx,
            "note": "Generated reference JavaScript and normative Python share null and edge-case behavior; displayed scalars come from canonical records.",
            "rows": rows}
