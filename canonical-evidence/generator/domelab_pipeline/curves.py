"""Single normative definition of stroke-averaging, shared by the Python
generator and the JavaScript viewer.

Step 2.2 carried two subtly different implementations: Python admitted any
0.005 mm bucket with at least one contributing run, while the release viewer
required a contributor majority. The result was a one-sample difference on the
leading edge of the return branch for seven sets, so offline EMBEDDED curves and
online fetched curves disagreed.

Step 2.3 adopts the viewer's contributor-majority rule as normative on BOTH
sides and states it once, here. The threshold is read from method_config
(`curve_average.contributor_rule`) and the JavaScript is generated from the same
configuration, so the two cannot drift again without the fleet-wide parity test
failing.

Normative rule
--------------
1. Bucket key is `round(x * 200)` — the 0.005 mm nominal grid.
2. A bucket's value is the arithmetic mean of every contributing sample.
3. A bucket is emitted only when `contributors >= ceil(n_runs / 2)`.
4. Buckets are truncated at the smallest per-run maximum travel
   (`key <= round(min_of_per_run_max * 200)`).
5. Endpoint inclusion follows from 3 and 4 alone; no branch-specific exception.
"""
import math


def contributor_threshold(n_runs, rule="majority"):
    """Minimum contributing runs for a bucket to be emitted."""
    if rule == "majority":
        return math.ceil(n_runs / 2)
    if rule == "any":
        return 1
    if rule == "all":
        return n_runs
    raise ValueError(f"unknown contributor rule: {rule!r}")


def jsround(v):
    """ECMAScript Math.round semantics: halves go toward +Infinity.

    Python's built-in round() is banker's rounding, so round(2.5) == 2 while
    Math.round(2.5) === 3. On a conforming 0.005 mm grid x*200 is integral and
    the two agree, but an off-grid or resampled acquisition would silently
    bucket differently in the two languages. Bucket keys are therefore computed
    with the JavaScript rule on both sides.
    """
    return int(math.floor(v + 0.5))


def grid_average(runs, rule="majority"):
    """runs = [(x_list, F_list), ...] -> (bucket_keys, mean_forces).

    Identical semantics to the generated JavaScript averageStrokes().
    """
    if not runs:
        return [], []
    need = contributor_threshold(len(runs), rule)
    acc = {}
    min_max = min(max(r_x) for r_x, _ in runs if r_x)
    for r_x, r_F in runs:
        for x, F in zip(r_x, r_F):
            k = jsround(x * 200)
            s, c = acc.get(k, (0.0, 0))
            acc[k] = (s + F, c + 1)
    kmax = jsround(min_max * 200)
    keys = sorted(k for k in acc if k <= kmax and acc[k][1] >= need)
    return keys, [acc[k][0] / acc[k][1] for k in keys]


JS_AVERAGE_TEMPLATE = """function averageStrokes(strokes){
  /* Generated from domelab_pipeline.curves — normative contributor rule
     "%(rule)s": a 0.005 mm bucket is emitted only when at least
     ceil(n/2) runs contribute, truncated at the smallest per-run max travel.
     The Python generator uses the identical rule; generator/tests enforce
     fleet-wide equality of every press and return array. */
  const key=v=>Math.round(v*200);const acc=new Map();let minMax=Infinity;
  const need=Math.ceil(strokes.length/2);
  for(const s of strokes){let mx=0;for(const v of s.x)if(v>mx)mx=v;if(mx<minMax)minMax=mx;
    for(let i=0;i<s.x.length;i++){const k=key(s.x[i]);const a=acc.get(k)||{s:0,c:0};a.s+=s.F[i];a.c++;acc.set(k,a);}}
  const ks=[...acc.keys()].sort((a,b)=>a-b);const x=[],F=[];
  for(const k of ks){const xv=k/200;if(k>key(minMax))break;const a=acc.get(k);
    if(a.c>=need){x.push(xv);F.push(a.s/a.c);}}
  return {x,F};
}"""


def js_average_source(rule="majority"):
    """The exact averageStrokes() body injected into viewer and picker."""
    return JS_AVERAGE_TEMPLATE % {"rule": rule}
