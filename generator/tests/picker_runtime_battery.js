#!/usr/bin/env node
/* EC Parts Builder runtime battery -- lib-6 single-tool contract.
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
  expectedBuild = "lib-6.0-review.1", expectedEligibleRaw = "false"] = process.argv;
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
    check("lib-6 runtime API is present",
      !!api && Array.isArray(api.SLOT_DEFS) && typeof api.assessBuild === "function");
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
    check("blank build exposes one keyboard action without a redundant toolbar control",
      d.querySelectorAll('[data-choose="kbd"]').length === 1
      && !d.getElementById("startKeyboard")
      && d.getElementById("buildToolbar").hidden);

    // The public page deliberately projects only exact dome specimens and
    // their three consumer metrics. Full curves and assembly records remain
    // in the frozen evidence package, not in this tool.
    const projected = api.DOME_MEASUREMENTS;
    const domeRecords = bench.filter(record => record.kind === "dome_baseline");
    check("dome measurement projection covers every canonical dome baseline",
      projected.length === domeRecords.length
      && projected.every(measurement => domeRecords.some(record =>
        record.tested_part === measurement.specimen_id
        && record.collapse_force_gf === measurement.collapse_force_gf)),
      {projected: projected.length, domeRecords: domeRecords.length});
    check("projected dome metrics are finite fleet percentiles",
      projected.every(measurement =>
        Number.isFinite(measurement.collapse_force_gf)
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
    check("exactly 13 qualified keyboard starters are public",
      qualified.length === 13
      && qualified.every(preset => preset.id.startsWith("kbd::")
        && Object.keys(preset).every(key => ["id","label","slots","notice"].includes(key))
        && Object.keys(preset.slots || {}).length > 0
        && Object.values(preset.slots).every(selection =>
          JSON.stringify(Object.keys(selection)) === JSON.stringify(["part"]))),
      {ids: qualified.map(preset => preset.id)});
    const rc1 = qualified.find(preset => preset.id === "kbd::realforce_rc1");
    check("ambiguous RC1 dome is left blank with a visible instruction",
      !rc1.slots.dome && /30 g and 45 g variants/.test(rc1.notice));
    api.applyKeyboardPreset(rc1);
    E("renderBuild()");
    check("RC1 dome choice instruction is visible after applying the starter",
      api.build.dome === null
      && d.getElementById("platformCard").textContent.includes("Choose dome:")
      && d.getElementById("platformCard").textContent.includes("30 g and 45 g variants"));
    check("consumer keyboard copy contains no internal note identifiers",
      api.CATALOG.keyboards.every(keyboard =>
        !(keyboard.notes || []).join(" ").includes("note_hhkb_mx")));
    check("generic MX keycaps are not mislabeled as aftermarket",
      api.CATALOG.keycaps.find(part => part.id === "keycap::mx").type === "");

    const starter = qualified.find(preset => preset.id === "kbd::hhkb_hybrid_type_s");
    api.applyKeyboardPreset(starter);
    E("renderBuild()");
    check("keyboard starter fills only its exact source-backed configuration",
      api.build.kbd === "kbd::hhkb_hybrid_type_s"
      && api.build.shell === "shell::hhkb"
      && api.build.h1 === "shell::hhkb" && api.build.h2 === "shell::hhkb"
      && api.build.dome === "dm-topre-45g" && api.build.domeSpec === null
      && api.build.slider === "slider::hhkb_type_s"
      && api.build.sl2 === "stabilizer_slider_2u::hhkb_type_s"
      && api.build.ring === null && api.build.spring === null
      && api.build.keycap === null && api.build.sb === null,
      {build: JSON.parse(JSON.stringify(api.build))});
    check("source-backed starter is initially unmodified",
      E("isPresetModified()") === false
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
      && api.build.h1 === "housings::topre" && api.build.h2 === null && api.build.sb === null
      && d.getElementById("liveStatus").textContent.includes("integrated parts were removed")
      && d.activeElement === d.getElementById("undoAction"),
      {build: JSON.parse(JSON.stringify(api.build))});
    click("#undoAction");
    check("multi-part replacement offers an immediate working Undo",
      api.build.kbd === starter.id && api.build.shell === "shell::hhkb"
      && api.build.h1 === "shell::hhkb" && api.build.h2 === "shell::hhkb"
      && api.build.ring === "ring::none"
      && d.getElementById("undoBar").hidden);

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
    check("an all-unknown build is never described as conflict-free",
      d.getElementById("statusTitle").textContent === "Compatibility not verified"
      && !d.getElementById("statusPanel").textContent.includes("No known conflicts"));

    E("resetBuildState();renderBuild()");
    click('[data-choose="dome"]');
    check("dome candidates are explicitly outside compatibility evaluation",
      d.getElementById("domeNote").hidden === false
      && d.getElementById("resultGroups").textContent.includes("Not evaluated")
      && [...d.querySelectorAll(".candidate .badge")].every(badge => badge.textContent === "Not evaluated"));
    const gray02 = projected.find(measurement =>
      measurement.specimen_id === "dome::sony_bke_gray_02");
    const grayCandidate = E(`([...currentCandidates.values()].find(candidate =>
      candidate.measurement && candidate.measurement.specimen_id === ${JSON.stringify(gray02 && gray02.specimen_id)}))`);
    api.selectCandidate(grayCandidate);
    await wait(20);
    const domeRowText = d.querySelector('[data-slot-row="dome"]').textContent;
    check("exact dome specimen selection projects only its measured metrics",
      !!gray02 && api.build.domeSpec === gray02.specimen_id
      && domeRowText.includes(gray02.label.replace(/_/g, " "))
      && domeRowText.includes(gray02.collapse_force_gf.toFixed(1) + " gf measured")
      && domeRowText.includes("1 measured specimen")
      && domeRowText.includes("Weight Index " + gray02.weight_index.toFixed(1))
      && domeRowText.includes("Tactility Index " + gray02.tactility_index.toFixed(1)),
      {specimen: gray02 && gray02.specimen_id, row: domeRowText});
    check("a dome-only build asks for another part instead of appearing blank",
      d.getElementById("statusTitle").textContent === "Choose another part to check compatibility"
      && d.getElementById("statusCopy").textContent.includes("Dome fit is not evaluated"));
    click('[data-choose="dome"]');
    check("exact selected dome specimen is visibly marked Selected",
      d.querySelector('[data-candidate$="dome::sony_bke_gray_02"] button[disabled]').textContent === "Selected");
    click("#backToBuild");

    click('[data-choose="slider"]');
    const detailButton = d.querySelector('[data-candidate="slider::dynacaps"] [data-details]');
    detailButton.click();
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
