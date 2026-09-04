#!/usr/bin/env node
/* EC Parts Builder runtime battery -- lib-6.1 review single-tool contract.
 *
 * Usage:
 *   node picker_runtime_battery.js <picker.html> <refSet> <refId>
 *     <bench_tests.json> [expectedBuild] [expectedEligible]
 *
 * The battery boots the generated single-file tool under jsdom. It exercises
 * the public builder and chooser through the same DOM and window.__EC_BUILDER__
 * API used by the browser acceptance test while retaining the canonical-data
 * assertions that remain part of this consumer surface.
 */
"use strict";

const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");

const [,, pickerPath, refSet, refId, benchPath,
  expectedBuild = "lib-6.1-review.1", expectedEligibleRaw = "false"] = process.argv;
const expectedEligible = expectedEligibleRaw === "true";
if (!pickerPath || !refSet || !refId || !benchPath) {
  console.error("usage: picker_runtime_battery.js <picker.html> <refSet> <refId> <bench_tests.json>");
  process.exit(2);
}

const html = fs.readFileSync(pickerPath, "utf8");
const bench = JSON.parse(fs.readFileSync(benchPath, "utf8"));
const checks = [];
const pageErrors = [];
const check = (name, pass, detail = null) => checks.push({name, pass: !!pass, detail});
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => pageErrors.push(String(error && error.message || error)));
virtualConsole.on("error", error => pageErrors.push(String(error)));

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  url: "https://battery.invalid/ec-parts-builder",
  pretendToBeVisual: true,
  virtualConsole,
  beforeParse(w) {
    w.__fetchCalls = [];
    w.__historyWrites = [];
    w.fetch = (...args) => {
      w.__fetchCalls.push(String(args[0]));
      return Promise.reject(new Error("runtime battery is offline"));
    };
    w.requestAnimationFrame = callback => setTimeout(() => callback(Date.now()), 0);
    w.cancelAnimationFrame = clearTimeout;
    const hp = w.History && w.History.prototype;
    if (hp) {
      for (const method of ["pushState", "replaceState"]) {
        const original = hp[method];
        hp[method] = function(...args) {
          w.__historyWrites.push({method, url: args[2] == null ? null : String(args[2])});
          return original.apply(this, args);
        };
      }
    }
    if (w.HTMLDialogElement) {
      if (!w.HTMLDialogElement.prototype.showModal) {
        w.HTMLDialogElement.prototype.showModal = function() {
          this.setAttribute("open", "");
        };
      }
      if (!w.HTMLDialogElement.prototype.close) {
        w.HTMLDialogElement.prototype.close = function() {
          this.removeAttribute("open");
          this.dispatchEvent(new w.Event("close"));
        };
      }
    }
  },
});

(async function run() {
  await wait(80);
  const w = dom.window;
  const d = w.document;
  const E = expression => w.eval(expression);
  const api = w.__EC_BUILDER__;
  const click = selector => {
    const element = d.querySelector(selector);
    if (!element) throw new Error("missing click target: " + selector);
    element.click();
    return element;
  };

  try {
    check("boot completes with zero page errors", pageErrors.length === 0, {pageErrors});
    check("no network activity (consumer never fetches)", w.__fetchCalls.length === 0,
      {calls: w.__fetchCalls});
    check("lib-6.1 runtime API is present",
      !!api && Array.isArray(api.SLOT_DEFS) && typeof api.assessBuild === "function"
      && Array.isArray(api.STABILIZER_ASSEMBLIES_2U)
      && typeof api.applyStabilizerAssembly === "function"
      && typeof api.stabilizerRingGeometryNote === "function"
      && typeof api.forceWallText === "function"
      && typeof api.domeMetricSummary === "function"
      && typeof api.mainSwitchDimensions === "function"
      && typeof api.relationFor === "function"
      && typeof api.partScopedFinding === "function"
      && typeof api.sameManufacturerKey === "function");
    check("single-tool architecture has no retired local views",
      !!d.getElementById("buildView") && !!d.getElementById("chooseView")
      && !d.querySelector("nav,.tab,#view-home,#view-library,#view-workshop,#themeToggle")
      && !/EC Switch Explorer|Force Curve Bench/.test(d.body.textContent));

    const initialUrl = w.location.href;
    const blankValues = Object.values(api.build);
    check("builder starts blank without inferred components",
      blankValues.every(value => value === null)
      && !d.getElementById("buildView").hidden
      && d.getElementById("chooseView").hidden
      && d.getElementById("statusTitle").textContent === "Choose parts to begin"
      && d.querySelectorAll("[data-slot-row]").length === api.SLOT_DEFS.length,
      {build: api.build});
    check("builder exposes separate 2u assembly and 2u ring slots",
      JSON.stringify(api.SLOT_DEFS.map(slot => slot.key)) === JSON.stringify([
        "dome", "slider", "h1", "spring", "ring", "keycap",
        "stab2uAssembly", "h2", "sl2", "ring2u", "sb"
      ]));
    check("blank build exposes one keyboard action without a redundant toolbar control",
      d.querySelectorAll('[data-choose="kbd"]').length === 1
      && !d.getElementById("startKeyboard")
      && d.getElementById("buildToolbar").hidden);

    // The public page deliberately projects only exact dome specimens and the
    // small set of consumer metrics needed here. Full curves and assembly
    // records remain in the frozen evidence package, not in this tool.
    const projected = api.DOME_MEASUREMENTS;
    const domeRecords = bench.filter(record => record.kind === "dome_baseline");
    check("dome measurement projection covers every canonical dome baseline",
      projected.length === domeRecords.length
      && projected.every(measurement => domeRecords.some(record =>
        record.tested_part === measurement.specimen_id
        && record.collapse_force_gf === measurement.collapse_force_gf
        // Exact equality pins the full-precision canonical aggregate: only
        // the formatter may round the force-wall value for display.
        && record.travel_mm === measurement.force_wall_mm)),
      {projected: projected.length, domeRecords: domeRecords.length});
    check("projected dome metrics preserve force-wall nullability and finite fleet percentiles",
      projected.every(measurement =>
        Number.isFinite(measurement.collapse_force_gf)
        && Object.prototype.hasOwnProperty.call(measurement, "force_wall_mm")
        && (measurement.force_wall_mm === null || Number.isFinite(measurement.force_wall_mm))
        && Number.isFinite(measurement.weight_index)
        && measurement.weight_index >= 0 && measurement.weight_index <= 100
        && Number.isFinite(measurement.tactility_index)
        && measurement.tactility_index >= 0 && measurement.tactility_index <= 100));
    const reference = bench.find(record => record.set === refSet);
    const referenceProjected = !!reference && projected.some(measurement =>
      measurement.specimen_id === reference.tested_part
      && measurement.collapse_force_gf === reference.collapse_force_gf);
    // Keep this check name and detail key stable: the Python launcher compares
    // it directly with bench_tests.staged.json.
    check("reference set exposes the generated TESTS run count",
      !!reference && referenceProjected && Number.isInteger(reference.runs_used),
      {runs: reference ? reference.runs_used : null});
    check("reference record identity matches",
      !!reference && reference.test_id === refId && reference.kind === "dome_baseline",
      {id: reference && reference.test_id, kind: reference && reference.kind});

    const qualified = api.qualifiedKeyboardPresets();
    const keyboardStarters = qualified.filter(preset => preset.id.startsWith("kbd::"));
    const brandKits = qualified.filter(preset => preset.id.startsWith("kit::"));
    check("exactly 28 keyboard starters and four manufacturer kits are public",
      keyboardStarters.length === 28 && brandKits.length === 4
      && qualified.length === 32
      && qualified.every(preset =>
        Object.keys(preset).every(key =>
          ["id","label","brand","kind","notes","slots","notice"].includes(key))
        && Object.keys(preset.slots || {}).length > 0
        && Object.values(preset.slots).every(selection =>
          JSON.stringify(Object.keys(selection)) === JSON.stringify(["part"]))),
      {ids: qualified.map(preset => preset.id)});
    const rc1 = keyboardStarters.find(preset => preset.id === "kbd::realforce_rc1");
    api.applyKeyboardPreset(rc1);
    E("renderBuild()");
    check("RC1 loads the exact owner-confirmed 45g silenced configuration",
      api.build.kbd === "kbd::realforce_rc1"
      && api.build.shell === "shell::rc1"
      && api.build.h1 === "shell::rc1" && api.build.h2 === "shell::rc1"
      && api.build.sb === "shell::rc1"
      && api.build.dome === "dm-topre-45g" && api.build.domeSpec === null
      && api.build.slider === "slider::topre_silenced_purple"
      && api.build.spring === "conical_springs::topre"
      && api.build.ring === "silencing_ring::topre_poron_0_5"
      && api.build.keycap === "keycap::topre"
      && api.build.stab2uAssembly === "assembly2u::realforce_rc1"
      && api.build.sl2 === "stabilizer_slider_2u::realforce_rc1_silenced_purple"
      && api.build.ring2u === "silencing_ring::topre_poron_0_5",
      {build: JSON.parse(JSON.stringify(api.build))});
    check("consumer keyboard copy contains no internal note identifiers",
      api.CATALOG.keyboards.every(keyboard =>
        !(keyboard.notes || []).join(" ").includes("note_hhkb_mx")));
    check("generic MX keycaps are not mislabeled as aftermarket",
      api.CATALOG.keycaps.find(part => part.id === "keycap::mx").type === "");

    const starter = keyboardStarters.find(preset => preset.id === "kbd::hhkb_hybrid_type_s");
    api.applyKeyboardPreset(starter);
    E("renderBuild()");
    check("keyboard starter fills its exact owner-confirmed configuration",
      api.build.kbd === "kbd::hhkb_hybrid_type_s"
      && api.build.shell === "shell::hhkb"
      && api.build.h1 === "shell::hhkb" && api.build.h2 === "shell::hhkb"
       && api.build.dome === "dm-topre-45g" && api.build.domeSpec === null
       && api.build.slider === "slider::hhkb_type_s"
       && api.build.stab2uAssembly === "assembly2u::hhkb_type_s"
       && api.build.sl2 === "stabilizer_slider_2u::hhkb_type_s"
       && api.build.ring === "silencing_ring::topre_poron_0_5"
       && api.build.ring2u === "silencing_ring::topre_poron_0_5"
       && api.build.spring === "conical_springs::topre"
       && api.build.keycap === "keycap::topre"
       && api.build.sb === "spacebar_stabilizer::topre",
      {build: JSON.parse(JSON.stringify(api.build))});
    check("source-backed starter is initially unmodified",
      E("isPresetModified()") === false
      && api.isAssemblyModified() === false
      && !d.getElementById("platformCard").textContent.includes("Modified"));
    const integratedRow = d.querySelector('[data-slot-row="h1"]');
    check("integrated rows disclose their cascade and defer removal to keyboard context",
      integratedRow.textContent.includes("Choosing a loose part removes the keyboard starting point")
      && integratedRow.querySelector('[data-choose="h1"]').textContent === "Use loose part"
      && !integratedRow.querySelector('[data-remove="h1"]'));

    api.openChooser("ring", d.querySelector('[data-choose="ring"]'));
    api.selectCandidate(E('currentCandidates.get("ring::none")'));
    await wait(20);
    check("changing a starter component keeps its context and marks it Modified",
      api.build.kbd === starter.id && api.build.ring === "ring::none"
      && E("isPresetModified()") === true
      && d.getElementById("platformCard").textContent.includes("Modified"));

    api.openChooser("h1", d.querySelector('[data-choose="h1"]'));
    api.selectCandidate(E('currentCandidates.get("housings::topre")'));
    await wait(20);
    check("replacing an integrated row removes the keyboard context and all other integrated slots",
      api.build.kbd === null && api.build.shell === null
      && api.build.h1 === "housings::topre" && api.build.h2 === null
      && api.build.sb === "spacebar_stabilizer::topre"
      && d.getElementById("liveStatus").textContent.includes("integrated parts were removed")
      && d.activeElement === d.getElementById("undoAction"),
      {build: JSON.parse(JSON.stringify(api.build))});
    click("#undoAction");
    check("multi-part replacement offers an immediate working Undo",
      api.build.kbd === starter.id && api.build.shell === "shell::hhkb"
      && api.build.h1 === "shell::hhkb" && api.build.h2 === "shell::hhkb"
      && api.build.ring === "ring::none"
      && api.build.sb === "spacebar_stabilizer::topre"
      && d.getElementById("undoBar").hidden);

    const hhkb30th = keyboardStarters.find(preset => preset.id === "kbd::hhkb_30th");
    api.applyKeyboardPreset(hhkb30th);
    check("HHKB 30th keeps Type-S 1u parts but the standard HHKB 2u assembly",
      api.build.dome === "dm-topre-30g"
      && api.build.slider === "slider::hhkb_type_s"
      && api.build.ring === "silencing_ring::topre_poron_0_5"
      && api.build.stab2uAssembly === "assembly2u::hhkb"
      && api.build.h2 === "shell::hhkb"
      && api.build.sl2 === "stabilizer_slider_2u::topre"
      && api.build.ring2u === "ring::none"
      && api.build.spring === "conical_springs::topre"
      && api.build.keycap === "keycap::topre"
      && api.build.sb === "spacebar_stabilizer::topre",
      {build: JSON.parse(JSON.stringify(api.build))});

    E("resetBuildState();renderBuild()");
    const topSilenced = api.CATALOG.stabilizerAssemblies2u.find(
      assembly => assembly.id === "assembly2u::topre_silenced");
    api.applyStabilizerAssembly(topSilenced);
    E("renderBuild()");
    check("Topre Silenced assembly loads its exact three-part 1.0 mm configuration",
      api.build.stab2uAssembly === "assembly2u::topre_silenced"
      && api.build.h2 === "stabilizer_housing_2u::topre_silenced"
      && api.build.sl2 === "stabilizer_slider_2u::topre_silenced"
      && api.build.ring2u === "silencing_ring::topre_2u_poron_1_0"
      && /seats flush/.test(api.stabilizerRingGeometryNote() || "")
      && /1\.00 mm total ring seat \(0\.00 mm slider seat \+ 1\.00 mm housing seat\) versus 1\.00 mm ring thickness/.test(
        api.stabilizerRingGeometryNote() || ""),
      {build: JSON.parse(JSON.stringify(api.build)), geometry: api.stabilizerRingGeometryNote()});
    api.openChooser("ring2u", d.querySelector('[data-choose="ring2u"]'));
    api.selectCandidate(E('currentCandidates.get("silencing_ring::topre_poron_0_5")'));
    await wait(20);
    check("a thinner 2u ring is flagged as chatter risk and modifies the assembly",
      /0\.50 mm top-out clearance \(chatter risk\)/.test(
        api.stabilizerRingGeometryNote() || "")
      && api.isAssemblyModified() === true,
      {geometry: api.stabilizerRingGeometryNote()});
    api.openChooser("ring2u", d.querySelector('[data-choose="ring2u"]'));
    api.selectCandidate(E('currentCandidates.get("ring::none")'));
    await wait(20);
    check("an explicit no-ring selection still evaluates nonzero ring-seat space",
      /1\.00 mm top-out clearance \(chatter risk\)/.test(
        api.stabilizerRingGeometryNote() || ""),
      {geometry: api.stabilizerRingGeometryNote()});

    E("resetBuildState();renderBuild()");
    const hhkbTypeSAssembly = api.CATALOG.stabilizerAssemblies2u.find(
      assembly => assembly.id === "assembly2u::hhkb_type_s");
    api.applyStabilizerAssembly(hhkbTypeSAssembly);
    E("renderBuild()");
    check("a shell-owned 2u assembly never invents a loose housing",
      api.build.stab2uAssembly === "assembly2u::hhkb_type_s"
      && api.build.h2 === null
      && api.build.sl2 === "stabilizer_slider_2u::hhkb_type_s"
      && api.build.ring2u === "silencing_ring::topre_poron_0_5"
      && /seats flush/.test(api.stabilizerRingGeometryNote() || ""));
    api.openChooser("ring2u", d.querySelector('[data-choose="ring2u"]'));
    api.selectCandidate(E('currentCandidates.get("silencing_ring::topre_2u_poron_1_0")'));
    await wait(20);
    check("a thicker available 2u ring is flagged as compression",
      /0\.50 mm compression/.test(api.stabilizerRingGeometryNote() || ""),
      {geometry: api.stabilizerRingGeometryNote()});

    const novatouch = keyboardStarters.find(preset => preset.id === "kbd::novatouch");
    api.applyKeyboardPreset(novatouch);
    E("renderBuild()");
    check("NovaTouch starter loads the complete owner-specified setup",
      api.build.kbd === "kbd::novatouch"
      && api.build.dome === "dm-topre-45g"
      && api.build.slider === "slider::novatouch"
      && api.build.h1 === "housings::topre"
      && api.build.spring === "conical_springs::topre"
      && api.build.ring === "ring::none"
      && api.build.stab2uAssembly === "assembly2u::novatouch"
      && api.build.h2 === "stabilizer_housing_2u::novatouch"
      && api.build.sl2 === "stabilizer_slider_2u::novatouch"
      && api.build.ring2u === "ring::none"
      && api.build.sb === "spacebar_stabilizer::novatouch",
      {build: JSON.parse(JSON.stringify(api.build))});
    const novatouchAssessment = api.assessBuild();
    const novatouchSpringRelations = novatouchAssessment.relations.filter(relation =>
      relation.a === "Topre Conical Springs" || relation.b === "Topre Conical Springs");
    const novatouchCrossSlot = novatouchAssessment.relations.find(relation =>
      [relation.a, relation.b].includes("NovaTouch Slider")
      && [relation.a, relation.b].includes("NovaTouch 2u Housing"));
    check("untouched NovaTouch starter has no false cross-slot conflicts",
      novatouchAssessment.counts.bad === 0
      && !/conflict/i.test(novatouchAssessment.title)
      && !!novatouchCrossSlot && novatouchCrossSlot.state === "works"
      && novatouchSpringRelations.length >= 4
      && novatouchSpringRelations.every(relation => relation.state === "works"),
      {assessment: novatouchAssessment});
    api.openChooser("slider", d.querySelector('[data-choose="slider"]'));
    api.selectCandidate(E('currentCandidates.get("slider::dynacaps")'));
    await wait(20);
    const modifiedNovaAssessment = api.assessBuild();
    const unchangedNovaPair = modifiedNovaAssessment.relations.find(relation =>
      [relation.a, relation.b].includes("Topre Conical Springs")
      && [relation.a, relation.b].includes("NovaTouch 2u Housing"));
    const changedNovaPairs = modifiedNovaAssessment.relations.filter(relation =>
      [relation.a, relation.b].includes("DynaCaps Slider"));
    check("modifying one NovaTouch part preserves only unchanged baseline pair evidence",
      api.build.kbd === "kbd::novatouch" && E("isPresetModified()") === true
      && !!unchangedNovaPair && unchangedNovaPair.state === "works"
      && /Recorded together in the selected keyboard/.test(unchangedNovaPair.text)
      && changedNovaPairs.length >= 4
      && changedNovaPairs.every(relation =>
        !/Recorded together in the selected keyboard/.test(relation.text)),
      {unchangedNovaPair, changedNovaPairs});

    const generationExpected = {
      "kbd::realforce_r2": {
        dome:"dm-topre-45g",slider:"slider::topre",ring:"ring::none",
        stab2uAssembly:"assembly2u::topre",
        h2:"stabilizer_housing_2u::topre_standard",
        sl2:"stabilizer_slider_2u::topre",ring2u:"ring::none"
      },
      "kbd::realforce_r3": {
        dome:"dm-topre-45g",slider:"slider::topre_silenced_purple",
        ring:"silencing_ring::topre_poron_0_5",
        stab2uAssembly:"assembly2u::topre_silenced",
        h2:"stabilizer_housing_2u::topre_silenced",
        sl2:"stabilizer_slider_2u::topre_silenced",
        ring2u:"silencing_ring::topre_2u_poron_1_0"
      },
      "kbd::realforce_r4": {
        dome:"dm-topre-45g",slider:"slider::topre_silenced_purple",
        ring:"silencing_ring::topre_poron_0_5",
        stab2uAssembly:"assembly2u::topre_silenced",
        h2:"stabilizer_housing_2u::topre_silenced",
        sl2:"stabilizer_slider_2u::topre_silenced",
        ring2u:"silencing_ring::topre_2u_poron_1_0"
      }
    };
    const generationResults = Object.entries(generationExpected).map(([id, expected]) => {
      api.applyKeyboardPreset(keyboardStarters.find(row => row.id === id));
      return {
        id,
        matches:Object.entries(expected).every(([slot, part]) => api.build[slot] === part),
        shared:api.build.h1 === "housings::topre"
          && api.build.spring === "conical_springs::topre"
          && api.build.keycap === "keycap::topre"
          && api.build.sb === "spacebar_stabilizer::topre",
        build:JSON.parse(JSON.stringify(api.build))
      };
    });
    check("R2 is standard and R3/R4 load the owner-confirmed silenced hardware",
      generationResults.every(row => row.matches && row.shared),
      {generationResults});

    const olderRealforceIds = [
      "kbd::realforce_101u","kbd::realforce_103u","kbd::realforce_104u",
      "kbd::realforce_106u","kbd::realforce_108u","kbd::realforce_86u",
      "kbd::realforce_87u","kbd::realforce_89u","kbd::realforce_91u"
    ];
    const noSeparateSpacebar = new Set([
      "kbd::realforce_106u","kbd::realforce_108u",
      "kbd::realforce_89u","kbd::realforce_91u"
    ]);
    const olderResults = olderRealforceIds.map(id => {
      api.applyKeyboardPreset(keyboardStarters.find(row => row.id === id));
      E("renderBuild()");
      const assessment = api.assessBuild();
      const sbText = d.querySelector('[data-slot-row="sb"]').textContent;
      return {
        id,
        shared:api.build.dome === "dm-topre-realforce-variable"
          && api.build.slider === "slider::topre"
          && api.build.h1 === "housings::topre"
          && api.build.spring === "conical_springs::topre"
          && api.build.ring === "ring::none"
          && api.build.keycap === "keycap::topre"
          && api.build.stab2uAssembly === "assembly2u::topre"
          && api.build.h2 === "stabilizer_housing_2u::topre_standard"
          && api.build.sl2 === "stabilizer_slider_2u::topre"
          && api.build.ring2u === "ring::none",
        sb:api.build.sb,
        sbText,
        relationNames:assessment.relations.flatMap(relation => [relation.a,relation.b])
      };
    });
    check("older Realforce starters use the variable dome and explicit spacebar state",
      olderResults.every(row => row.shared
        && row.sb === (noSeparateSpacebar.has(row.id)
          ? "none::spacebar_stabilizer" : "spacebar_stabilizer::topre")
        && (!noSeparateSpacebar.has(row.id)
          || (/intentionally loads no separate spacebar stabilizer/i.test(row.sbText)
            && !/Not selected/.test(row.sbText)))
        && row.relationNames.every(name => !/no separate spacebar stabilizer/i.test(name))),
      {olderResults});

    const kitExpected = {
      "kit::deskeys": {
        slider:"slider::deskeys",h1:"housings::deskeys",
        spring:"conical_springs::deskeys_conical",
        ring:"silencing_ring::des_poron_0_7",keycap:"keycap::mx",
        stab2uAssembly:"assembly2u::deskeys",
        h2:"stabilizer_housing_2u::deskeys",sl2:"stabilizer_slider_2u::deskeys",
        ring2u:"silencing_ring::des_poron_0_7",sb:"spacebar_stabilizer::deskeys"
      },
      "kit::dynacaps": {
        slider:"slider::dynacaps",h1:"housings::dynacaps",
        spring:"conical_springs::dynacaps",
        ring:"silencing_ring::dynacaps_silicone_0_5",keycap:"keycap::mx",
        stab2uAssembly:"assembly2u::dynacaps",
        h2:"stabilizer_housing_2u::dynacaps",sl2:"stabilizer_slider_2u::dynacaps",
        ring2u:"silencing_ring::dynacaps_silicone_0_5",sb:"spacebar_stabilizer::dynacaps"
      },
      "kit::klc": {
        slider:"slider::klc_playground",h1:"housings::klc_playground",
        spring:"conical_springs::klc_playground",ring:"ring::none",keycap:"keycap::mx",
        stab2uAssembly:"assembly2u::klc",
        h2:"stabilizer_housing_2u::klc_playground",
        sl2:"stabilizer_slider_2u::klc_playground",ring2u:"ring::none",
        sb:"spacebar_stabilizer::klc_playground"
      },
      "kit::metakeebs": {
        slider:"slider::metapulse",h1:"housings::metapulse",
        spring:"conical_springs::metapulse",
        ring:"silencing_ring::metapulse_poron_0_5",keycap:"keycap::mx",
        stab2uAssembly:"assembly2u::metakeebs",
        h2:"stabilizer_housing_2u::metapulse",sl2:"stabilizer_slider_2u::metapulse",
        ring2u:"silencing_ring::metapulse_poron_0_5",sb:"spacebar_stabilizer::metapulse"
      }
    };
    const kitResults = brandKits.map(preset => {
      api.applyKeyboardPreset(preset);
      E("renderBuild()");
      const expected = kitExpected[preset.id];
      const assessment = api.assessBuild();
      return {
        id: preset.id,
        dome: api.build.dome,
        exact:Object.entries(expected).every(([slot, part]) => api.build[slot] === part),
        complete:["dome","slider","h1","spring","ring","keycap",
          "stab2uAssembly","h2","sl2","ring2u","sb"]
          .every(slot => api.build[slot] !== null),
        domeText:d.querySelector('[data-slot-row="dome"]').textContent,
        conflictCount: assessment.counts.bad,
        unverifiedCount:assessment.counts.unverified,
        partFindings:assessment.partFindings.map(finding => ({
          part:finding.part,state:finding.state,label:finding.label
        })),
        relationCount: assessment.relations.length,
        relationNames:assessment.relations.flatMap(relation => [relation.a,relation.b]),
        ringGeometry:api.ringGeometryNote(),
        stabilizerRingGeometry:api.stabilizerRingGeometryNote(),
        statusTitle:d.getElementById("statusTitle").textContent,
        badRows:[...d.querySelectorAll('[data-slot-row]')]
          .filter(row => row.querySelector('.component-status .badge')
            && row.querySelector('.component-status .badge').textContent === "Does not work")
          .map(row => row.dataset.slotRow),
        detailNames:[...d.querySelectorAll('#compatDetails .compat-item b')]
          .map(node => node.textContent),
        sliderText:d.querySelector('[data-slot-row="slider"]').textContent,
        stabilizerSliderText:d.querySelector('[data-slot-row="sl2"]').textContent
      };
    });
    check("manufacturer kits load exact owner-confirmed parts and an intentional no-dome",
      kitResults.every(row => row.dome === "none::dome" && row.exact && row.complete
        && /intentional/i.test(row.domeText) && !/Not selected/.test(row.domeText)
        && row.relationCount > 0
        && row.relationNames.every(name => !/no dome/i.test(name))),
      {kitResults});
    const deskeysKitResult = kitResults.find(row => row.id === "kit::deskeys");
    check("Deskeys spring failure is shown once and does not blame the other kit parts",
      !!deskeysKitResult
      && deskeysKitResult.conflictCount === 1
      && JSON.stringify(deskeysKitResult.partFindings) === JSON.stringify([{
        part:"Deskeys Conical Springs",state:"bad",label:"Does not work"
      }])
      && JSON.stringify(deskeysKitResult.badRows) === JSON.stringify(["spring"])
      && deskeysKitResult.statusTitle === "1 incompatible part"
      && JSON.stringify(deskeysKitResult.detailNames) === JSON.stringify(["Deskeys Conical Springs"])
      && !deskeysKitResult.relationNames.includes("Deskeys Conical Springs"),
      {deskeysKitResult});
    check("Deskeys 0.7 mm rings match the corrected 0.5 + 0.2 mm seats",
      !!deskeysKitResult
      && /seats flush/.test(deskeysKitResult.ringGeometry || "")
      && /0\.70 mm total ring seat \(0\.50 mm slider seat \+ 0\.20 mm housing seat\) versus 0\.70 mm ring thickness/.test(
        deskeysKitResult.ringGeometry || "")
      && /seats flush/.test(deskeysKitResult.stabilizerRingGeometry || "")
      && /0\.70 mm total ring seat \(0\.50 mm slider seat \+ 0\.20 mm housing seat\) versus 0\.70 mm ring thickness/.test(
        deskeysKitResult.stabilizerRingGeometry || "")
      && deskeysKitResult.statusTitle !== "Ring fit needs review",
      {deskeysKitResult});

    const klcKitResult = kitResults.find(row => row.id === "kit::klc");
    check("KLC spring failure is likewise one culprit-only finding",
      !!klcKitResult
      && klcKitResult.conflictCount === 1
      && klcKitResult.partFindings.length === 1
      && klcKitResult.partFindings[0].part === "KLC Conical Springs"
      && klcKitResult.partFindings[0].state === "bad"
      && JSON.stringify(klcKitResult.badRows) === JSON.stringify(["spring"])
      && klcKitResult.statusTitle === "1 incompatible part"
      && !klcKitResult.relationNames.includes("KLC Conical Springs"),
      {klcKitResult});

    const metakeebsKitResult = kitResults.find(row => row.id === "kit::metakeebs");
    check("unresolved MetaPulse spring reliability is attributed once without a hard failure",
      !!metakeebsKitResult
      && metakeebsKitResult.conflictCount === 0
      && metakeebsKitResult.unverifiedCount === 1
      && metakeebsKitResult.partFindings.length === 1
      && metakeebsKitResult.partFindings[0].part === "MetaPulse Conical Springs"
      && metakeebsKitResult.partFindings[0].state === "unverified"
      && metakeebsKitResult.badRows.length === 0
      && metakeebsKitResult.statusTitle === "1 part not verified"
      && !metakeebsKitResult.relationNames.includes("MetaPulse Conical Springs"),
      {metakeebsKitResult});

    const dynacapsKitResult = kitResults.find(row => row.id === "kit::dynacaps");
    check("DynaCaps defaults use the recommended 0.5 mm Silicone rings without a fit warning",
      !!dynacapsKitResult
      && /0\.25 mm intentional pre-compression \(manufacturer recommended\)/.test(
        dynacapsKitResult.ringGeometry || "")
      && /0\.25 mm intentional pre-compression \(manufacturer recommended\)/.test(
        dynacapsKitResult.stabilizerRingGeometry || "")
      && dynacapsKitResult.statusTitle !== "Ring fit needs review"
      && dynacapsKitResult.unverifiedCount === 0
      && !/4 mm nominal travel/.test(dynacapsKitResult.sliderText)
      && !/4 mm nominal travel/.test(dynacapsKitResult.stabilizerSliderText),
      {dynacapsKitResult});

    const dynacapsPreset = brandKits.find(preset => preset.id === "kit::dynacaps");
    api.applyKeyboardPreset(dynacapsPreset);
    api.build.ring = "silencing_ring::dynacaps_silicone_0_3";
    api.build.ring2u = "silencing_ring::dynacaps_silicone_0_3";
    E("renderBuild()");
    const dynacapsSupported = {
      one:api.ringGeometryNote(),two:api.stabilizerRingGeometryNote(),
      assessments:api.ringGeometryAssessments(),
      statusTitle:d.getElementById("statusTitle").textContent
    };
    check("DynaCaps 0.3 mm rings report supported 0.05 mm pre-compression without warning",
      /0\.05 mm intentional pre-compression \(manufacturer supported\)/.test(
        dynacapsSupported.one || "")
      && /0\.05 mm intentional pre-compression \(manufacturer supported\)/.test(
        dynacapsSupported.two || "")
      && dynacapsSupported.assessments.every(row => row.warning === false)
      && dynacapsSupported.statusTitle !== "Ring fit needs review",
      {dynacapsSupported});

    api.build.ring = "ring::none";
    api.build.ring2u = "ring::none";
    E("renderBuild()");
    const dynacapsNoRing = {
      one:api.ringGeometryNote(),two:api.stabilizerRingGeometryNote(),
      assessments:api.ringGeometryAssessments(),
      statusTitle:d.getElementById("statusTitle").textContent
    };
    check("DynaCaps no-ring clearance keeps its 1u and 2u chatter warnings",
      /0\.25 mm top-out clearance \(chatter risk\)/.test(dynacapsNoRing.one || "")
      && /0\.25 mm top-out clearance \(chatter risk\)/.test(dynacapsNoRing.two || "")
      && dynacapsNoRing.assessments.length === 2
      && dynacapsNoRing.assessments.every(row => row.warning === true)
      && dynacapsNoRing.statusTitle === "Ring fit needs review",
      {dynacapsNoRing});

    api.build.ring = "silencing_ring::des_poron_0_5";
    api.build.ring2u = "silencing_ring::dynacaps_silicone_0_5";
    E("renderBuild()");
    const dynacapsForeignRing = {
      text:api.ringGeometryNote(),warning:api.ringGeometryAssessments()[0],
      statusTitle:d.getElementById("statusTitle").textContent
    };
    check("the DynaCaps exception does not suppress an equal compression from another ring system",
      /0\.25 mm compression/.test(dynacapsForeignRing.text || "")
      && !/intentional/.test(dynacapsForeignRing.text || "")
      && dynacapsForeignRing.warning && dynacapsForeignRing.warning.warning === true
      && dynacapsForeignRing.statusTitle === "Ring fit needs review",
      {dynacapsForeignRing});

    api.build.ring = "silencing_ring::dynacaps_silicone_0_5";
    api.build.h1 = "housings::topre";
    E("renderBuild()");
    const dynacapsMixedHousing = {
      text:api.ringGeometryNote(),warning:api.ringGeometryAssessments()[0]
    };
    check("the DynaCaps exception requires the matching DynaCaps housing",
      /0\.25 mm compression/.test(dynacapsMixedHousing.text || "")
      && !/intentional/.test(dynacapsMixedHousing.text || "")
      && dynacapsMixedHousing.warning && dynacapsMixedHousing.warning.warning === true,
      {dynacapsMixedHousing});

    const deskeysPreset = brandKits.find(preset => preset.id === "kit::deskeys");
    api.applyKeyboardPreset(deskeysPreset);
    api.build.ring = "silencing_ring::des_poron_0_5";
    const deskeysChatter = api.ringGeometryNote();
    api.build.ring = "silencing_ring::des_poron_1_0";
    const deskeysCompression = api.ringGeometryNote();
    check("fit-delta signs map positive to chatter and negative to compression",
      /0\.20 mm top-out clearance \(chatter risk\)/.test(deskeysChatter || "")
      && /0\.30 mm compression/.test(deskeysCompression || ""),
      {deskeysChatter, deskeysCompression});

    E("resetBuildState();renderBuild()");
    const sliderOpener = click('[data-choose="slider"]');
    check("component row opens one contextual chooser",
      d.getElementById("buildView").hidden
      && !d.getElementById("chooseView").hidden
      && d.getElementById("chooseTitle").textContent === "Choose main slider"
      && d.activeElement === d.getElementById("backToBuild")
      && [...d.querySelectorAll("[data-candidate]")].every(card =>
        api.CATALOG.sliders.some(part => part.id === card.dataset.candidate)));
    const search = d.getElementById("partSearch");
    search.focus();
    search.value = "dynacaps";
    search.dispatchEvent(new w.Event("input", {bubbles: true}));
    check("contextual search preserves focus and filters in place",
      d.activeElement === search && d.getElementById("partSearch") === search
      && d.querySelectorAll("[data-candidate]").length === 1
      && !!d.querySelector('[data-candidate="slider::dynacaps"]'));
    click('[data-candidate="slider::dynacaps"] [data-select]');
    await wait(20);
    check("selection returns to the build and restores row focus",
      api.build.slider === "slider::dynacaps"
      && !d.getElementById("buildView").hidden && d.getElementById("chooseView").hidden
      && d.activeElement && d.activeElement.dataset.choose === "slider"
      && d.querySelector('[data-slot-row="slider"]').textContent.includes("DynaCaps Slider"),
      {originalOpenerStillConnected: sliderOpener.isConnected});
    click('[data-choose="slider"]');
    check("current chooser selection is disabled and labeled Selected",
      d.querySelector('[data-candidate="slider::dynacaps"] button[disabled]').textContent === "Selected");
    click("#backToBuild");

    // The shell context has a known MetaPulse spacebar conflict. It must be
    // hidden by default, counted, and revealed only by the explicit filter.
    api.applyKeyboardPreset(starter);
    E("renderBuild()");
    click('[data-choose="sb"]');
    check("known incompatible options are hidden and counted by default",
      !d.querySelector('[data-candidate="spacebar_stabilizer::metapulse"]')
      && /known incompatible hidden/.test(d.getElementById("resultCount").textContent)
      && !d.getElementById("showIncompatible").checked);
    click("#showIncompatible");
    check("customer can reveal a known incompatible option",
      !!d.querySelector('[data-candidate="spacebar_stabilizer::metapulse"]')
      && d.querySelector('[data-candidate="spacebar_stabilizer::metapulse"]').textContent.includes("Does not work"));
    click('[data-candidate="spacebar_stabilizer::metapulse"] [data-select]');
    click('[data-choose="sb"]');
    check("a selected incompatible option remains visible for correction",
      !!d.querySelector('[data-candidate="spacebar_stabilizer::metapulse"] button[disabled]')
      && d.querySelector('[data-candidate="spacebar_stabilizer::metapulse"] button[disabled]').textContent === "Selected");
    click("#backToBuild");
    await wait(20);

    const consumerLabels = E(`[
      consumerRelation({st:"compatible"},"A","B").label,
      consumerRelation({st:"conditional",rsn:"condition"},"A","B").label,
      consumerRelation({st:"incompatible",rsn:"conflict"},"A","B").label,
      consumerRelation({st:"unknown",rsn:"gap"},"A","B").label
    ]`);
    check("compatibility maps to exactly four consumer labels",
      JSON.stringify(consumerLabels) === JSON.stringify([
        "Works", "Works with conditions", "Does not work", "Not verified"
      ]), {consumerLabels});
    check("pending and unknown both remain visibly unverified while same-slot noise is omitted",
      E('consumerRelation({st:"pending"},"A","B").label==="Not verified"')
      && E('consumerRelation({st:"not_applicable"},"A","B")===null'));
    const manufacturerFallback = E(`(function(){
      const api=window.__EC_BUILDER__;
      const dynaSlider=PARTIDX["slider::dynacaps"];
      const dynaHousing=PARTIDX["housings::dynacaps"];
      const dynaSpring=PARTIDX["conical_springs::dynacaps"];
      const topreHousing=PARTIDX["housings::topre"];
      const deskeysSlider=PARTIDX["slider::deskeys"];
      const deskeysSpring=PARTIDX["conical_springs::deskeys_conical"];
      const unknownKey=[ridOf(dynaSlider),ridOf(dynaHousing)].sort().join("||");
      const original=COMPAT_EVIDENCE[unknownKey];
      COMPAT_EVIDENCE[unknownKey]={
        st:"conditional",src:"test",nid:null,q:null,
        adj:"owner_confirmed",rsn:"A recorded condition still applies."
      };
      const explicitConditional=api.relationFor(dynaSlider,dynaHousing);
      if(original===undefined)delete COMPAT_EVIDENCE[unknownKey];
      else COMPAT_EVIDENCE[unknownKey]=original;
      return {
        sameKey:api.sameManufacturerKey(dynaSlider),
        housingKey:api.sameManufacturerKey(dynaHousing),
        sameUnknown:api.relationFor(dynaSlider,dynaHousing),
        sameOwnerPending:api.relationFor(dynaSlider,dynaSpring),
        deskeysPartFinding:api.partScopedFinding(deskeysSpring),
        absorbedSpringEdge:api.relationFor(deskeysSlider,deskeysSpring),
        mixedUnknown:api.relationFor(dynaSlider,topreHousing),
        explicitConditional
      };
    })()`);
    check("same-manufacturer fallback removes only unverified results and preserves explicit evidence",
      !!manufacturerFallback.sameKey
      && manufacturerFallback.sameKey === manufacturerFallback.housingKey
      && manufacturerFallback.sameUnknown.state === "works"
      && manufacturerFallback.sameUnknown.label === "Manufacturer matched"
      && manufacturerFallback.sameUnknown.basis === "same_manufacturer"
      && manufacturerFallback.sameOwnerPending.state === "works"
      && manufacturerFallback.sameOwnerPending.basis === "same_manufacturer"
      && manufacturerFallback.deskeysPartFinding.state === "bad"
      && manufacturerFallback.deskeysPartFinding.label === "Does not work"
      && manufacturerFallback.deskeysPartFinding.part === "Deskeys Conical Springs"
      && manufacturerFallback.absorbedSpringEdge === null
      && manufacturerFallback.explicitConditional.state === "conditional"
      && manufacturerFallback.explicitConditional.label === "Works with conditions"
      && manufacturerFallback.mixedUnknown.state === "unverified"
      && manufacturerFallback.mixedUnknown.label === "Not verified",
      {manufacturerFallback});

    E(`resetBuildState();
      build.spring="conical_springs::deskeys_conical";
      renderBuild()`);
    const deskeysSpringOnly = api.assessBuild();
    check("an incompatible spring owns one part-level finding even when selected alone",
      deskeysSpringOnly.counts.bad === 1
      && deskeysSpringOnly.partFindings.length === 1
      && deskeysSpringOnly.partFindings[0].part === "Deskeys Conical Springs"
      && deskeysSpringOnly.relations.length === 0
      && d.getElementById("statusTitle").textContent === "1 incompatible part"
      && d.querySelector('[data-slot-row="spring"] .badge').textContent === "Does not work"
      && [...d.querySelectorAll("#compatDetails .compat-item b")].map(x => x.textContent)
        .join("|") === "Deskeys Conical Springs"
      && !d.getElementById("compatDetails").textContent.includes("Deskeys Conical Springs +"),
      {deskeysSpringOnly});
    click('[data-choose="slider"]');
    check("the selected bad spring does not blame or hide replacement sliders",
      d.querySelectorAll('[data-candidate^="slider::"]').length === 8
      && !/known incompatible hidden/.test(d.getElementById("resultCount").textContent)
      && [...d.querySelectorAll('[data-candidate^="slider::"] .badge')]
        .every(badge => badge.textContent !== "Does not work"));
    click("#backToBuild");

    E("resetBuildState();renderBuild()");
    click('[data-choose="spring"]');
    check("the spring chooser hides only intrinsically incompatible springs by default",
      !d.querySelector('[data-candidate="conical_springs::deskeys_conical"]')
      && !d.querySelector('[data-candidate="conical_springs::klc_playground"]')
      && !!d.querySelector('[data-candidate="conical_springs::metapulse"]')
      && d.querySelector('[data-candidate="conical_springs::metapulse"] .badge').textContent === "Not verified"
      && /2 known incompatible hidden/.test(d.getElementById("resultCount").textContent));
    click("#showIncompatible");
    check("revealed spring failures are attributed only to their own candidates",
      d.querySelector('[data-candidate="conical_springs::deskeys_conical"] .badge').textContent === "Does not work"
      && d.querySelector('[data-candidate="conical_springs::klc_playground"] .badge').textContent === "Does not work"
      && d.querySelector('[data-candidate="conical_springs::metapulse"] .badge').textContent === "Not verified");
    click("#backToBuild");

    E('resetBuildState();build.spring="conical_springs::metapulse";renderBuild()');
    const metaSpringOnly = api.assessBuild();
    check("a standalone unverified spring governs the whole-build headline",
      metaSpringOnly.counts.unverified === 1
      && metaSpringOnly.partFindings.length === 1
      && metaSpringOnly.relations.length === 0
      && d.getElementById("statusTitle").textContent === "1 part not verified"
      && d.querySelector('[data-slot-row="spring"] .badge').textContent === "Not verified"
      && [...d.querySelectorAll("#compatDetails .compat-item b")]
        .map(node => node.textContent).join("|") === "MetaPulse Conical Springs",
      {metaSpringOnly});

    E(`resetBuildState();
      build.shell="shell::hhkb";
      build.h1="shell::hhkb";
      build.spring="conical_springs::deskeys_conical";
      build.sb="spacebar_stabilizer::metapulse";
      renderBuild()`);
    const combinedCulpritAndPair = api.assessBuild();
    check("a true pair conflict survives alongside a part-scoped spring failure",
      combinedCulpritAndPair.counts.bad === 2
      && combinedCulpritAndPair.partFindings.length === 1
      && combinedCulpritAndPair.relations.filter(relation => relation.state === "bad").length === 1
      && combinedCulpritAndPair.relations.some(relation =>
        [relation.a,relation.b].includes("HHKB Shell")
        && [relation.a,relation.b].includes("MetaPulse Spacebar Stabilizer"))
      && d.getElementById("statusTitle").textContent === "2 compatibility issues"
      && d.querySelector('[data-slot-row="spring"] .badge').textContent === "Does not work"
      && d.querySelector('[data-slot-row="sb"] .badge').textContent === "Does not work",
      {combinedCulpritAndPair});

    E(`resetBuildState();
      build.slider="slider::dynacaps";
      build.h1="housings::dynacaps";
      build.spring="conical_springs::dynacaps";
      renderBuild()`);
    check("a same-manufacturer component stack renders no Not verified checks",
      api.assessBuild().relations.length === 3
      && api.assessBuild().relations.every(relation => relation.state === "works")
      && ![...d.querySelectorAll(".component-status .badge")]
        .some(badge => badge.textContent === "Not verified")
      && d.getElementById("statusTitle").textContent === "No compatibility issues found");
    E('resetBuildState();build.slider="slider::topre";renderBuild()');
    click('[data-choose="spring"]');
    check("owner-pending DynaCaps spring claims remain Not verified",
      d.querySelector('[data-candidate="conical_springs::dynacaps"] .badge').textContent === "Not verified"
      && !d.querySelector('[data-candidate="conical_springs::dynacaps"]').textContent.includes("Works with conditions"));
    const ownerPendingCopy = E(`(function(){const a=PARTIDX["conical_springs::dynacaps"],b=PARTIDX["slider::topre"];
      return consumerRelation(evEdge(a,b),a.name,b.name).text;})()`);
    const scratchCopy = E(`(function(){const a=PARTIDX["housings::dynacaps"],b=PARTIDX["slider::hhkb_type_s"];
      return consumerRelation(evEdge(a,b),a.name,b.name).text;})()`);
    const metaCopy = E(`(function(){const a=PARTIDX["spacebar_stabilizer::metapulse"],b=PARTIDX["shell::hhkb"];
      return consumerRelation(evEdge(a,b),a.name,b.name).text;})()`);
    check("compatibility explanations contain clean consumer prose",
      !/[|*]|Omitted from product page|owner adjudication|\.\s*;|\. scratchy/.test(ownerPendingCopy+scratchCopy+metaCopy)
      && scratchCopy.includes("Reported behavior: scratchy."),
      {ownerPendingCopy,scratchCopy,metaCopy});
    click("#backToBuild");
    E('resetBuildState();build.slider="slider::hhkb_type_s";build.ring="silencing_ring::topre_poron_0_5";renderBuild()');
    click('[data-choose="h1"]');
    check("an unverified pairing governs a mixed conditional candidate",
      d.querySelector('[data-candidate="housings::dynacaps"] .badge').textContent === "Not verified");
    click("#backToBuild");
    E('resetBuildState();build.keycap="keycap::mx";build.ring="silencing_ring::topre_poron_0_5";renderBuild()');
    check("non-interacting keycap and ring do not create a false evidence gap",
      api.assessBuild().relations.length === 0
      && d.getElementById("statusTitle").textContent === "Choose another part to check compatibility");

    E("resetBuildState();renderBuild()");
    click('[data-choose="dome"]');
    check("dome candidates are explicitly outside compatibility evaluation",
      d.getElementById("domeNote").hidden === false
      && d.getElementById("resultGroups").textContent.includes("Not evaluated")
      && [...d.querySelectorAll(".candidate .badge")].every(badge => badge.textContent === "Not evaluated"));
    const brown63 = projected.find(measurement =>
      measurement.specimen_id === "dome::deskeys_v3_brown_63g");
    const requestedDomeSummary = "Weight Index 79.1 · Tactility Index 67.2 · Force-Wall 3.85 mm";
    check("dome metric formatter uses the requested order, labels, and display rounding",
      !!brown63
      && brown63.force_wall_mm === bench.find(record =>
        record.tested_part === brown63.specimen_id).travel_mm
      && api.forceWallText([brown63]) === "3.85 mm"
      && api.domeMetricSummary([brown63]) === requestedDomeSummary,
      {brown63, summary:brown63 && api.domeMetricSummary([brown63])});
    click('[data-candidate="dm-des-v3-63g"] [data-select]');
    await wait(20);
    const brownRowMeta = d.querySelector('[data-slot-row="dome"] .selection-meta').textContent;
    check("measured dome row shows exactly Weight Index, Tactility Index, and Force-Wall",
      brownRowMeta === requestedDomeSummary,
      {row:brownRowMeta});
    check("a dome-only build asks for another part instead of appearing blank",
      d.getElementById("statusTitle").textContent === "Choose another part to check compatibility"
      && d.getElementById("statusCopy").textContent.includes("Dome fit is not evaluated"));

    click('[data-choose="dome"]');
    const brownDetailButton = click('[data-candidate="dm-des-v3-63g"] [data-details]');
    const brownDetailRows = Object.fromEntries([...d.querySelectorAll("#detailBody .detail-cell")]
      .map(cell => [cell.querySelector("dt").textContent, cell.querySelector("dd").textContent]));
    check("measured dome Details includes the two indices and canonical Force-Wall",
      brownDetailRows["Weight Index"] === "79.1"
      && brownDetailRows["Tactility Index"] === "67.2"
      && brownDetailRows["Force-Wall"] === "3.85 mm",
      {rows:brownDetailRows});
    click("#closeDetails");
    await wait(20);
    check("closing measured dome Details restores its opener", d.activeElement === brownDetailButton);
    click("#backToBuild");

    api.applyKeyboardPreset(dynacapsPreset);
    E(`build.dome=${JSON.stringify(brown63 && brown63.catalog_id)};build.domeSpec=null;renderBuild()`);
    const geometryLimited = api.mainSwitchDimensions();
    check("DynaCaps ring compression limits Travel before the measured dome wall",
      geometryLimited.compressionMm === 0.25
      && geometryLimited.geometricTravelMm === 3.75
      && geometryLimited.forceWallMm === brown63.force_wall_mm
      && geometryLimited.travelMm === 3.75
      && geometryLimited.travelSource === "geometry"
      && d.getElementById("dimensionTravel").textContent === "3.75 mm"
      && d.getElementById("dimensionCompression").textContent === "0.25 mm",
      {geometryLimited});

    E(`build.slider="slider::topre";build.h1="housings::topre";build.ring="ring::none";renderBuild()`);
    const wallLimited = api.mainSwitchDimensions();
    check("a shorter measured force wall limits Travel below geometric slider travel",
      wallLimited.compressionMm === 0
      && wallLimited.geometricTravelMm === 4
      && wallLimited.forceWallMm === brown63.force_wall_mm
      && wallLimited.travelMm === brown63.force_wall_mm
      && wallLimited.travelSource === "force-wall"
      && d.getElementById("dimensionTravel").textContent === brown63.force_wall_mm.toFixed(2)+" mm"
      && d.getElementById("dimensionCompression").textContent === "0.00 mm",
      {wallLimited});

    const nullWallResult = E(`(function(){
      const part=CATALOG.domes.find(row=>(row.measurements||[]).some(
        measurement=>measurement.specimen_id==="dome::deskeys_v3_brown_63g"));
      const measurement=part.measurements.find(row=>
        row.specimen_id==="dome::deskeys_v3_brown_63g");
      const original=measurement.force_wall_mm;
      measurement.force_wall_mm=null;
      renderBuild();
      const dimensions=window.__EC_BUILDER__.mainSwitchDimensions();
      const summary=document.querySelector('[data-slot-row="dome"] .selection-meta').textContent;
      const travel=document.getElementById("dimensionTravel").textContent;
      const compression=document.getElementById("dimensionCompression").textContent;
      const nullText=window.__EC_BUILDER__.forceWallText([measurement]);
      measurement.force_wall_mm=original;
      renderBuild();
      return {dimensions,summary,travel,compression,nullText};
    })()`);
    check("an undetected dome wall stays null and geometric Travel remains available",
      nullWallResult.dimensions.forceWallMm === null
      && nullWallResult.dimensions.geometricTravelMm === 4
      && nullWallResult.dimensions.travelMm === 4
      && nullWallResult.dimensions.travelSource === "geometry"
      && nullWallResult.summary === "Weight Index 79.1 · Tactility Index 67.2 · Force-Wall Not detected"
      && nullWallResult.nullText === "Not detected"
      && nullWallResult.travel === "4.00 mm"
      && nullWallResult.compression === "0.00 mm"
      && !/0\.00 mm|NaN|undefined/.test(nullWallResult.summary),
      {nullWallResult});

    const familyNoCap = E(`(function(){
      const family=CATALOG.domes.find(row=>(row.measurements||[]).length>1);
      build.dome=family.id;build.domeSpec=null;
      build.slider="slider::dynacaps";build.h1="housings::dynacaps";
      build.ring="silencing_ring::dynacaps_silicone_0_5";renderBuild();
      return {id:family.id,count:family.measurements.length,
        dimensions:window.__EC_BUILDER__.mainSwitchDimensions()};
    })()`);
    check("a multi-specimen family selection does not invent one force-wall cap",
      familyNoCap.count > 1
      && familyNoCap.dimensions.forceWallMm === null
      && familyNoCap.dimensions.travelMm === 3.75
      && familyNoCap.dimensions.travelSource === "geometry",
      {familyNoCap});

    E("resetBuildState();renderBuild()");
    click('[data-choose="dome"]');
    const gray02 = projected.find(measurement =>
      measurement.specimen_id === "dome::sony_bke_gray_02");
    const grayCandidate = E(`([...currentCandidates.values()].find(candidate =>
      candidate.measurement && candidate.measurement.specimen_id === ${JSON.stringify(gray02 && gray02.specimen_id)}))`);
    api.selectCandidate(grayCandidate);
    await wait(20);
    const domeRowMeta = d.querySelector('[data-slot-row="dome"] .selection-meta').textContent;
    const graySummary = "Weight Index "+gray02.weight_index.toFixed(1)
      +" · Tactility Index "+gray02.tactility_index.toFixed(1)
      +" · Force-Wall "+gray02.force_wall_mm.toFixed(2)+" mm";
    check("exact grouped-dome specimen selection uses the same concise metric summary",
      !!gray02 && api.build.domeSpec === gray02.specimen_id
      && domeRowMeta === graySummary,
      {specimen: gray02 && gray02.specimen_id, row: domeRowMeta});
    click('[data-choose="dome"]');
    check("exact selected dome specimen is visibly marked Selected",
      d.querySelector('[data-candidate$="dome::sony_bke_gray_02"] button[disabled]').textContent === "Selected");
    click("#backToBuild");

    click('[data-choose="slider"]');
    const dynacapsChooserText = d.querySelector('[data-candidate="slider::dynacaps"]').textContent;
    const detailButton = d.querySelector('[data-candidate="slider::dynacaps"] [data-details]');
    detailButton.click();
    const dynacapsDetailText = d.getElementById("detailBody").textContent;
    check("DynaCaps slider omits the nominal-travel note in chooser and details",
      !/4 mm nominal travel/.test(dynacapsChooserText)
      && !/Nominal travel/.test(dynacapsDetailText),
      {dynacapsChooserText,dynacapsDetailText});
    check("details dialog receives focus",
      d.getElementById("detailDialog").open
      && d.activeElement === d.getElementById("closeDetails"));
    click("#closeDetails");
    await wait(20);
    check("closing details restores its opener", d.activeElement === detailButton);
    w.dispatchEvent(new w.KeyboardEvent("keydown", {
      key: "Escape", bubbles: true, cancelable: true,
    }));
    await wait(20);
    check("Escape returns from chooser and restores the component-row control",
      d.getElementById("chooseView").hidden && !d.getElementById("buildView").hidden
      && d.activeElement && d.activeElement.dataset.choose === "slider");

    click('[data-choose="sl2"]');
    const dynacaps2uChooserText = d.querySelector(
      '[data-candidate="stabilizer_slider_2u::dynacaps"]').textContent;
    const dynacaps2uDetailButton = d.querySelector(
      '[data-candidate="stabilizer_slider_2u::dynacaps"] [data-details]');
    dynacaps2uDetailButton.click();
    const dynacaps2uDetailText = d.getElementById("detailBody").textContent;
    check("DynaCaps 2u slider also omits the nominal-travel note in chooser and details",
      !/4 mm nominal travel/.test(dynacaps2uChooserText)
      && !/Nominal travel/.test(dynacaps2uDetailText),
      {dynacaps2uChooserText,dynacaps2uDetailText});
    click("#closeDetails");
    click("#backToBuild");

    const pb = E("PICKER_BUILD");
    check("generated build identity is rendered and coherent",
      pb.library_build === expectedBuild
      && pb.release_eligible === expectedEligible
      && typeof pb.repo_commit === "string"
      && !["records","sets","retained_run_bindings","unique_acquisitions",
        "metrics","perception","data_epoch","authority_split","bench_build"].some(key => key in pb)
      && d.getElementById("buildBadge").textContent === pb.library_build,
      {build: pb.library_build, badge: d.getElementById("buildBadge").textContent});
    check("parts-library source identity remains explicit",
      /^[0-9a-f]{64}$/.test(String(pb.parts_library_source_identity)));
    check("tool leaves browser history and URL untouched",
      w.__historyWrites.length === 0 && w.location.href === initialUrl,
      {writes: w.__historyWrites, url: w.location.href});
    const extPattern = /(?:<script[^>]+src|<img[^>]+src|@import\s+url|url\()\s*=?\s*["'(]?\s*(https?:)?\/\//gi;
    const extHits = [...html.matchAll(extPattern)].map(match => html.slice(match.index, match.index + 80));
    check("zero automatic external resource references", extHits.length === 0, {extHits});
  } catch (error) {
    check("battery executed without harness errors", false,
      {error: String(error && error.stack || error)});
  }

  const failed = checks.filter(item => !item.pass).length;
  console.log(JSON.stringify({checks, total: checks.length, failed}, null, 1));
  process.exit(failed ? 1 : 0);
})();
