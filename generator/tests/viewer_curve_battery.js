/* Step 2.3 fleet-wide viewer curve battery.
 *
 * Step 2.2 shipped two different averaging rules: the Python generator admitted
 * any 0.005 mm bucket with one contributing run, the viewer required a
 * contributor majority. Seven sets therefore rendered one extra return sample
 * offline that never appeared online.
 *
 * This battery compares, for every set in the generated review plan:
 *   - press arrays (length and every value)
 *   - return arrays (length and every value)
 *   - endpoint inclusion (first and last bucket)
 *   - contributor counts
 *   - packed/unpacked values (EMBEDDED round-trip)
 *   - online (fetched-and-averaged) vs offline (EMBEDDED) rendered data
 * and asserts the canonical scalar readouts come from the generated record in
 * both modes.
 *
 * Usage: node viewer_curve_battery.js <viewer.staged.html> <plan.json>
 * plan.json: {set: {files: [abs paths], n: <retained count>}, ...}
 */
const { JSDOM } = require("jsdom");
const fs = require("fs");

const [viewerPath, planPath] = process.argv.slice(2);
const plan = JSON.parse(fs.readFileSync(planPath, "utf8"));
const checks = [];
function check(name, fn) {
  try { const d = fn(); checks.push({ name, pass: true, detail: d === undefined ? null : d }); }
  catch (e) { checks.push({ name, pass: false, detail: `${e.constructor.name}: ${e.message}` }); }
}
function assert(c, m) { if (!c) throw new Error(m); }
const EPS = 1e-9;

const dom = new JSDOM(fs.readFileSync(viewerPath, "utf8"), {
  runScripts: "dangerously", url: "https://x.test/",
  beforeParse(w) {
    w.requestAnimationFrame = cb => setTimeout(cb, 0);
    w.cancelAnimationFrame = clearTimeout;
    w.fetch = () => Promise.reject(new Error("offline"));
    w.HTMLCanvasElement.prototype.getContext = () =>
      new Proxy({}, { get: () => () => ({ width: 10 }), set: () => true });
  },
});

setTimeout(() => {
  const w = dom.window;
  const EMBEDDED = w.eval("EMBEDDED");
  const VTESTS = w.eval("VTESTS");
  const parseCSV = w.eval("parseCSV");
  const averageStrokes = w.eval("averageStrokes");

  // unpackStroke inverse, matching packs.pack_stroke
  function unpack(p) {
    const x = [], F = [];
    let acc = 0;
    for (let i = 0; i < p.df.length; i++) {
      acc += p.df[i];
      x.push((p.x0 + i) / 200);
      F.push(acc / 100);
    }
    return { x, F };
  }

  const sets = Object.keys(plan).sort();
  check(`all ${sets.length} sets present in EMBEDDED`, () => {
    for (const s of sets) assert(s in EMBEDDED, `EMBEDDED missing ${s}`);
    assert(Object.keys(EMBEDDED).length === sets.length,
           `EMBEDDED has ${Object.keys(EMBEDDED).length} sets, plan has ${sets.length}`);
    return { sets: sets.length };
  });

  const report = {};
  for (const s of sets) {
    const files = plan[s].files;
    const runs = files.map(f => parseCSV(fs.readFileSync(f, "utf8")));
    const online = { p: averageStrokes(runs.map(r => r.press)), r: averageStrokes(runs.map(r => r.ret)) };
    const offline = { p: unpack(EMBEDDED[s].p), r: unpack(EMBEDDED[s].r) };
    report[s] = {
      press_online: online.p.x.length, press_offline: offline.p.x.length,
      ret_online: online.r.x.length, ret_offline: offline.r.x.length,
      contributors: EMBEDDED[s].n, retained: plan[s].n,
    };

    check(`${s}: press array length matches`, () => {
      assert(online.p.x.length === offline.p.x.length,
             `online ${online.p.x.length} vs offline ${offline.p.x.length}`);
      return online.p.x.length;
    });
    check(`${s}: return array length matches`, () => {
      assert(online.r.x.length === offline.r.x.length,
             `online ${online.r.x.length} vs offline ${offline.r.x.length}`);
      return online.r.x.length;
    });
    check(`${s}: press endpoints match`, () => {
      assert(Math.abs(online.p.x[0] - offline.p.x[0]) < EPS, "first press bucket differs");
      assert(Math.abs(online.p.x[online.p.x.length - 1] - offline.p.x[offline.p.x.length - 1]) < EPS,
             "last press bucket differs");
    });
    check(`${s}: return endpoints match`, () => {
      assert(Math.abs(online.r.x[0] - offline.r.x[0]) < EPS,
             `first return bucket ${online.r.x[0]} vs ${offline.r.x[0]}`);
      assert(Math.abs(online.r.x[online.r.x.length - 1] - offline.r.x[offline.r.x.length - 1]) < EPS,
             "last return bucket differs");
    });
    check(`${s}: press values match (packed round-trip)`, () => {
      let worst = 0;
      for (let i = 0; i < online.p.x.length; i++) {
        assert(Math.abs(online.p.x[i] - offline.p.x[i]) < EPS, `x differs at ${i}`);
        worst = Math.max(worst, Math.abs(online.p.F[i] - offline.p.F[i]));
      }
      // packing quantizes to 0.01 gf; anything larger is an algorithm difference
      assert(worst <= 0.005 + EPS, `max force delta ${worst} exceeds pack quantization`);
      return { max_force_delta: worst };
    });
    check(`${s}: return values match (packed round-trip)`, () => {
      let worst = 0;
      for (let i = 0; i < online.r.x.length; i++) {
        assert(Math.abs(online.r.x[i] - offline.r.x[i]) < EPS, `x differs at ${i}`);
        worst = Math.max(worst, Math.abs(online.r.F[i] - offline.r.F[i]));
      }
      assert(worst <= 0.005 + EPS, `max force delta ${worst} exceeds pack quantization`);
      return { max_force_delta: worst };
    });
    check(`${s}: contributor count equals retained run count`, () => {
      assert(EMBEDDED[s].n === plan[s].n,
             `EMBEDDED n=${EMBEDDED[s].n} vs retained ${plan[s].n}`);
      assert(files.length === plan[s].n, `plan supplied ${files.length} files for ${plan[s].n} retained runs`);
    });
    check(`${s}: canonical scalar readout comes from the generated record`, () => {
      const rec = VTESTS.find(t => t.set === s);
      assert(rec, `no VTESTS record for ${s}`);
      assert(rec.runs === plan[s].n, `record runs ${rec.runs} vs retained ${plan[s].n}`);
      for (const k of ["cg", "cx", "sn", "en", "tv"]) assert(k in rec, `record missing scalar ${k}`);
    });
  }

  check("no browser-side runfilter, legacy median or restore-all fallback remains", () => {
    const src = fs.readFileSync(viewerPath, "utf8");
    assert(!/runfilter-v1: exclude runs deviating/.test(src), "legacy in-browser runfilter present");
    assert(!/if\(!keep\.some\(Boolean\)\)keep=runs\.map\(\(\)=>true\)/.test(src),
           "restore-all fallback present");
    assert(!/s\[s\.length>>1\]/.test(src), "upper-middle median helper present");
    assert(!/analyze\(avgPress\.x,avgPress\.F\)/.test(src),
           "averaged-curve metric calculation present");
  });

  check("averageStrokes is the generated shared definition", () => {
    const src = fs.readFileSync(viewerPath, "utf8");
    assert(/Generated from domelab_pipeline\.curves/.test(src),
           "viewer averageStrokes is not the generated shared definition");
    assert(/const need=Math\.ceil\(strokes\.length\/2\)/.test(src),
           "contributor threshold not present in generated source");
  });

  const failed = checks.filter(c => !c.pass);
  console.log(JSON.stringify({
    battery: "viewer_curves", artifact: viewerPath,
    sets: sets.length, total: checks.length,
    passed: checks.length - failed.length, failed: failed.length,
    per_set: report,
    failures: failed,
  }, null, 1));
  process.exit(failed.length ? 1 : 0);
}, 1400);
