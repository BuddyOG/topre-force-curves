/* Hostile runtime checks for the fc-3.4 viewer. The embedded artifact is
 * loaded offline, then valid null states and an invalid duplicate-source state
 * are injected across curves, profile graphs, readouts, and PNG export. */
const {JSDOM, VirtualConsole} = require("jsdom");
const fs = require("fs");

const viewer = process.argv[2];
const viewerSource = fs.readFileSync(viewer, "utf8");
const pageErrors = [];
const nonFiniteCanvasCalls = [];
const paintedText = [];
const forbiddenPaintedText = [];
const FORBIDDEN_CONSUMER_TEXT = /80 is not twice 40|index scale note|wall delta|vs\s+Topre/i;
let pngExports = 0;
const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => pageErrors.push(String(error && error.message || error)));

function finiteArgs(method, args) {
  for (const value of args) {
    if (typeof value === "number" && !Number.isFinite(value)) {
      nonFiniteCanvasCalls.push(`${String(method)}(${args.map(String).join(",")})`);
    }
  }
}

function canvasContext(canvas) {
  const target = {
    canvas,
    measureText(text) { return {width: String(text).length * 6}; },
    fillText(text, ...args) {
      const value = String(text);
      paintedText.push(value);
      if (FORBIDDEN_CONSUMER_TEXT.test(value)) forbiddenPaintedText.push(value);
      finiteArgs("fillText", args);
    },
    createLinearGradient() { return {addColorStop() {}}; },
    createRadialGradient() { return {addColorStop() {}}; },
    createPattern() { return {}; },
  };
  return new Proxy(target, {
    get(object, key) {
      if (key in object) return object[key];
      return (...args) => { finiteArgs(key, args); return undefined; };
    },
    set(object, key, value) {
      if (typeof value === "number" && !Number.isFinite(value)) {
        nonFiniteCanvasCalls.push(`set ${String(key)}=${String(value)}`);
      }
      object[key] = value;
      return true;
    },
  });
}

const dom = new JSDOM(viewerSource, {
  runScripts: "dangerously",
  url: "https://review.invalid/",
  virtualConsole,
  beforeParse(window) {
    window.requestAnimationFrame = callback => setTimeout(callback, 0);
    window.cancelAnimationFrame = clearTimeout;
    window.fetch = () => Promise.reject(new Error("offline red-team run"));
    Object.defineProperty(window.HTMLCanvasElement.prototype, "clientWidth", {
      configurable: true, get() { return 1000; },
    });
    Object.defineProperty(window.HTMLCanvasElement.prototype, "clientHeight", {
      configurable: true, get() { return 625; },
    });
    window.HTMLCanvasElement.prototype.getContext = function () {
      if (!this.__redteamContext) this.__redteamContext = canvasContext(this);
      return this.__redteamContext;
    };
    window.HTMLCanvasElement.prototype.toBlob = function (callback) {
      pngExports++;
      callback(new window.Blob(["png"], {type: "image/png"}));
    };
    window.HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,";
    window.URL.createObjectURL = () => "blob:redteam";
    window.URL.revokeObjectURL = () => {};
    window.HTMLAnchorElement.prototype.click = () => {};
  },
});

const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

(async () => {
  await delay(120);
  const window = dom.window;
  const records = window.eval("VTESTS");

  // A shared curve may not silently acquire two incompatible scalar truths.
  const first = records.find(row => row.k === "dome_baseline");
  const second = {...first, id: "synthetic-divergent-duplicate", k: "part_assembly"};
  records.push(second);
  second.cg = first.cg + 0.125;
  let divergentDuplicateRejected = false;
  try {
    window.eval(`canonStats(${JSON.stringify(first.set)}, ${JSON.stringify(first.id)})`);
  } catch (error) {
    divergentDuplicateRejected = /divergent generated record scalars/.test(String(error && error.message || error));
  }
  records.pop();

  const build = window.eval("VIEWER_BUILD");
  const primary = records.find(row => row.set === "Topre_R1_45g" && row.id === "bt_0075" && row.k === "dome_baseline");
  const primarySet = primary && primary.set;
  const other = records.find(row => row.set !== primarySet && row.k === "dome_baseline" &&
    Number.isFinite(row.wi) && Number.isFinite(row.ti) && Object.values(row.pp).every(Number.isFinite));
  const parts = records.filter(row => row.k === "part_assembly").slice(0, 2);
  await window.eval(`toggleSet(${JSON.stringify(primarySet)}, ${JSON.stringify(primary.id)})`);
  const nullSet = window.eval(`sets.get(${JSON.stringify(primarySet)})`);
  const originalStats = {...nullSet.data.stats, percentiles: {...nullSet.data.stats.percentiles}};
  const originalLines = window.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const numericWallValueOnly = originalLines.some(row =>
    row[0] === "Detected force-wall onset" && row[1] === `${originalStats.travel.toFixed(2)} mm`
  );
  const noWallReferenceMetadata = !Object.keys(build).some(key => key.startsWith("force_wall_reference"));
  const noDeltaOrScaleNoteSource = !/forceWallDelta|wallDelta|force_wall_reference|80 is not twice 40|Index scale note|INDEX_SCALE_NOTE/.test(viewerSource);
  const simplePercentileCopy = viewerSource.includes(
    "Weight Index</b> is this dome’s weight percentile compared with the other domes tested."
  ) && viewerSource.includes(
    "Tactility Index</b> is this dome’s tactility percentile compared with the other domes tested."
  );

  // A missing force wall has exactly one special display state and does not
  // erase either pilot-derived index.
  nullSet.data.stats = {...originalStats, travel: null};
  window.eval('chartMode="curves"; render(); exportPNG();');
  const wallNullLines = window.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const nullLegend = window.eval(`legendStat(sets.get(${JSON.stringify(primarySet)}))`);
  const recordedTurnaround = window.eval(`recordedTurnaround(sets.get(${JSON.stringify(primarySet)}))`);
  const noWallText = wallNullLines.some(row => row[0] === "Detected force-wall onset" && row[1] === "Not detected") &&
    wallNullLines.some(row => row[0] === "Weight Index" && /\/ 100$/.test(row[1])) &&
    wallNullLines.some(row => row[0] === "Tactility Index" && /\/ 100$/.test(row[1])) &&
    !wallNullLines.some(row => row[0] !== "Detected force-wall onset" && row[1] === "Not detected") &&
    !wallNullLines.some(row => /0\.00 mm/.test(row[1]));

  // Null the primary metrics, indices, and corresponding percentile inputs.
  // They must be unavailable without imputation while the wall remains absent.
  nullSet.data.stats = {
    ...originalStats,
    Fpeak: null,
    dropF: null,
    travel: null,
    weightIndex: null,
    tactilityIndex: null,
    percentiles: {...originalStats.percentiles, cg: null, dg: null},
  };
  window.eval('chartMode="curves"; render(); exportPNG();');
  const primaryNullLines = window.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const primaryNullUnavailable = primaryNullLines.some(row => row[0] === "Collapse force" && row[1] === "Not available") &&
    primaryNullLines.some(row => row[0] === "Drop" && row[1] === "Not available") &&
    primaryNullLines.some(row => row[0] === "Weight Index" && row[1] === "Not available") &&
    primaryNullLines.some(row => row[0] === "Tactility Index" && row[1] === "Not available") &&
    !primaryNullLines.some(row => /Index$/.test(row[0]) && row[1] === "Not detected");

  // With two domes selected, the null record is omitted independently from
  // each profile; the complete record still produces every requested point.
  await window.eval(`toggleSet(${JSON.stringify(other.set)}, ${JSON.stringify(other.id)})`);
  window.eval('chartMode="profileWeight"; render(); exportPNG();');
  const weightProfilePoints = window.eval("PROFILE_PTS.map(point=>({...point}))");
  window.eval('chartMode="profileTactility"; render(); exportPNG();');
  const tactilityProfilePoints = window.eval("PROFILE_PTS.map(point=>({...point}))");
  const nullExcludedFromWeightProfile = weightProfilePoints.length === 3 &&
    weightProfilePoints.every(point => point.key === other.set && Number.isFinite(point.x) && Number.isFinite(point.y));
  const nullExcludedFromTactilityProfile = tactilityProfilePoints.length === 4 &&
    tactilityProfilePoints.every(point => point.key === other.set && Number.isFinite(point.x) && Number.isFinite(point.y));

  // The 2-D index comparison must reject the null record rather than plotting
  // it at zero or inferring either index from a supporting metric.
  paintedText.length = 0;
  window.eval('chartMode="indexScatter"; render(); exportPNG();');
  const nullScatterPoints = window.eval("SCATTER_PTS.map(point=>({...point}))");
  const nullName = window.eval(`selectedName(sets.get(${JSON.stringify(primarySet)}))`);
  const nullExcludedFromScatter = nullScatterPoints.length === 1 &&
    nullScatterPoints[0].key === other.set &&
    Number.isFinite(nullScatterPoints[0].x) && Number.isFinite(nullScatterPoints[0].y) &&
    paintedText.some(text => /^Not available:/.test(text) && text.includes(nullName));
  const scatterPoint = nullScatterPoints[0];
  const scatterStats = window.eval(`sets.get(${JSON.stringify(other.set)}).data.stats`);
  const canvas = window.document.getElementById("chart");
  const pointerMove = new window.MouseEvent("pointermove", {
    clientX: scatterPoint.x, clientY: scatterPoint.y, bubbles: true,
  });
  Object.defineProperty(pointerMove, "pointerType", {value: "mouse"});
  canvas.dispatchEvent(pointerMove);
  await delay(0);
  const scatterTooltip = window.document.getElementById("tooltip").textContent;
  const scatterHoverLinked = window.eval("hoverKey") === other.set &&
    !!window.document.querySelector(`#readout tr[data-key="${other.set}"]`)?.classList.contains("hl") &&
    scatterTooltip.includes(`Weight Index ${scatterStats.weightIndex.toFixed(1)}`) &&
    scatterTooltip.includes(`Tactility Index ${scatterStats.tactilityIndex.toFixed(1)}`) &&
    !/force-wall/i.test(scatterTooltip) && !/NaN|Infinity/.test(scatterTooltip);
  // The scatter is deliberately limited to the two indices. Force wall and
  // identity remain available through the expanded comparison table.
  window.document.getElementById("roMore").click();
  const readout = window.document.getElementById("readout").textContent;

  // Part assemblies retain their raw mechanics but the pilot indices/profile
  // are deliberately not calibrated for them.
  const partStats = window.eval("canonStats")(parts[0].set, parts[0].id);
  window.__partProbe = {key: parts[0].set, record_id: parts[0].id, data: {stats: partStats}};
  const partLines = window.eval("statLines(__partProbe)");
  const partIndicesNotCalibrated = partLines.some(row => row[0] === "Weight Index" && row[1] === "Not calibrated") &&
    partLines.some(row => row[0] === "Tactility Index" && row[1] === "Not calibrated");
  const partWallValueOnly = partLines.some(row => row[0] === "Detected force-wall onset" && row[1] ===
    (Number.isFinite(partStats.travel) ? `${partStats.travel.toFixed(2)} mm` : "Not detected"));

  const selected = window.eval("selected");
  selected.splice(0, selected.length, ...parts.map(row => row.set));
  for (const row of parts) {
    const set = window.eval(`sets.get(${JSON.stringify(row.set)})`);
    set.record_id = row.id;
    set.data = {
      runs: [], avgPress: {x: [], F: []}, avgRet: {x: [], F: []},
      stats: window.eval("canonStats")(row.set, row.id), snapshot: true,
    };
  }
  const partTextStart = paintedText.length;
  window.eval('chartMode="profileWeight"; render(); exportPNG();');
  const partWeightPoints = window.eval("PROFILE_PTS.length");
  window.eval('chartMode="profileTactility"; render(); exportPNG();');
  const partTactilityPoints = window.eval("PROFILE_PTS.length");
  window.eval('chartMode="indexScatter"; render(); exportPNG();');
  const partScatterPoints = window.eval("SCATTER_PTS.length");
  const partProfileText = paintedText.slice(partTextStart).join(" ");
  const partProfilesNotCalibrated = partWeightPoints === 0 && partTactilityPoints === 0 &&
    partScatterPoints === 0 && /not calibrated/i.test(partProfileText) &&
    /not calibrated or available for this selection/i.test(partProfileText);

  const forbiddenStatLabels = new Set([
    "Press work to force-wall", "Norm. drop rate", "Collapse-to-valley distance",
    "Collapse point", "Valley",
  ]);
  const lowAssociationValuesHidden = !wallNullLines.some(row => forbiddenStatLabels.has(row[0])) &&
    !primaryNullLines.some(row => forbiddenStatLabels.has(row[0])) &&
    !partLines.some(row => forbiddenStatLabels.has(row[0])) &&
    !/PRESS WORK TO FORCE-WALL|NORM\. DROP RATE|COLLAPSE-TO-VALLEY DISTANCE|VALLEY \(GF\)|VALLEY \(MM\)/i.test(readout) &&
    !paintedText.some(text => /PRESS WORK|NORM\. DROP|COLLAPSE-TO-VALLEY|^VALLEY$|gf\s*@\s*\d/i.test(text));

  const output = {
    divergentDuplicateRejected,
    nullForceWallText: noWallText && /wall not detected/.test(nullLegend),
    numericWallValueOnly,
    noWallReferenceMetadata,
    noDeltaOrScaleNoteSource,
    simplePercentileCopy,
    primaryNullUnavailable,
    partIndicesNotCalibrated,
    partWallValueOnly,
    recordedLimitIndependent: recordedTurnaround !== null &&
      Number.isFinite(recordedTurnaround.min) && Number.isFinite(recordedTurnaround.max) &&
      recordedTurnaround.min > 0 && recordedTurnaround.max >= recordedTurnaround.min,
    nullExcludedFromWeightProfile,
    nullExcludedFromTactilityProfile,
    nullExcludedFromScatter,
    scatterHoverLinked,
    partProfilesNotCalibrated,
    nullReadoutSafe: readout.includes("WALL (MM)") && readout.includes("Not detected") &&
      readout.includes("Not available") && readout.includes("RECORD ID") &&
      !FORBIDDEN_CONSUMER_TEXT.test(readout),
    lowAssociationValuesHidden,
    profileAndPngFinite: nonFiniteCanvasCalls.length === 0 && pngExports >= 8,
    noForbiddenCanvasText: forbiddenPaintedText.length === 0,
    noPageErrors: pageErrors.length === 0,
  };
  if (pageErrors.length) console.error(JSON.stringify({pageErrors}));
  console.log(JSON.stringify(output));
  process.exit(Object.values(output).every(Boolean) ? 0 : 1);
})().catch(error => {
  console.error(error && error.stack || error);
  process.exit(2);
});
