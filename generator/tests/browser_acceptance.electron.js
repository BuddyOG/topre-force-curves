#!/usr/bin/env node
/* Real-browser acceptance for the lib-6.1 review EC Parts Builder.
 *
 * RUNNING (Electron is intentionally not vendored):
 *   electron --no-sandbox generator/tests/browser_acceptance.electron.js \
 *     <generated>/packs/picker.staged.html <outdir> [expectedBuild]
 *
 * The script exercises the one-tool builder at 1280, 390, and 320 CSS px.
 * It writes browser_report.json and screenshots, and exits non-zero on any
 * failure. No test mutates builder state directly; customer flows use the
 * rendered Choose, Select, Details, filter, Back, Clear, and keyboard paths.
 */
"use strict";

const {app, BrowserWindow, session} = require("electron");
const fs = require("fs");
const path = require("path");

const args = process.argv.slice(1).filter(arg => !arg.startsWith("--"));
const pickerPath = path.resolve(args[1]);
const outDir = path.resolve(args[2]);
const expectedBuild = args[3] || "lib-6.1-review.1";
if (!pickerPath || !outDir) {
  process.stderr.write("usage: electron browser_acceptance.electron.js <picker.html> <outdir> [expectedBuild]\n");
  process.exit(2);
}
fs.mkdirSync(outDir, {recursive: true});

const report = {
  picker: pickerPath,
  expectedBuild,
  started: new Date().toISOString(),
  versions: process.versions,
  checks: [],
  screenshots: [],
  requests: [],
  badRequests: [],
  console: [],
  ignoredConsole: [],
  overflow: [],
};
const ck = (name, pass, detail = null) => report.checks.push({name, pass: !!pass, detail});
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

process.on("uncaughtException", error => {
  try {
    fs.writeFileSync(path.join(outDir, "browser_report.json"), JSON.stringify({
      fatal: String(error && error.stack || error), report,
    }, null, 2));
  } catch (_) {}
  process.exit(3);
});

app.commandLine.appendSwitch("no-sandbox");
app.commandLine.appendSwitch("disable-gpu");
app.disableHardwareAcceleration();

function hookSession(ses) {
  ses.webRequest.onBeforeRequest((details, callback) => {
    report.requests.push(details.url);
    if (!/^(file|devtools|chrome-extension):/i.test(details.url)) {
      report.badRequests.push(details.url);
    }
    callback({});
  });
}

async function runCombo(width, height, tag) {
  const win = new BrowserWindow({
    width, height, useContentSize: true, show: false,
    webPreferences: {contextIsolation: false, nodeIntegration: false},
  });
  win.webContents.on("console-message", details => {
    const entry = {
      tag,
      level: details.level,
      message: details.message,
      line: details.lineNumber,
      sourceId: details.sourceId,
    };
    if (/Electron Security Warning \(Insecure Content-Security-Policy\)/.test(details.message)) {
      report.ignoredConsole.push(entry);
    } else if ((typeof details.level === "number" && details.level >= 2)
      || details.level === "warning" || details.level === "error") {
      report.console.push(entry);
    }
  });
  await win.loadFile(pickerPath);
  await sleep(180);

  const J = expression => win.webContents.executeJavaScript(expression, true);
  const click = async selector => {
    const result = await J(`(function(){
      const element=document.querySelector(${JSON.stringify(selector)});
      if(!element)return false;
      element.scrollIntoView({block:"center",inline:"nearest"});
      element.click();
      return true;
    })()`);
    await sleep(80);
    return result;
  };
  const clickCandidate = async key => {
    const result = await J(`(function(){
      const card=[...document.querySelectorAll("[data-candidate]")]
        .find(element=>element.dataset.candidate===${JSON.stringify(key)});
      const button=card&&card.querySelector("[data-select]");
      if(!button)return false;
      button.scrollIntoView({block:"center"});button.click();return true;
    })()`);
    await sleep(100);
    return result;
  };
  const clickDomeSpecimen = async specimenId => {
    const result = await J(`(function(){
      const card=[...document.querySelectorAll("[data-candidate]")].find(element=>{
        const candidate=currentCandidates.get(element.dataset.candidate);
        return candidate&&candidate.measurement
          &&candidate.measurement.specimen_id===${JSON.stringify(specimenId)};
      });
      const button=card&&card.querySelector("[data-select]");
      if(!button)return false;
      button.scrollIntoView({block:"center"});button.click();return true;
    })()`);
    await sleep(100);
    return result;
  };
  const setInput = async (selector, value) => {
    const result = await J(`(function(){
      const element=document.querySelector(${JSON.stringify(selector)});
      if(!element)return false;
      element.focus();element.value=${JSON.stringify(value)};
      element.dispatchEvent(new Event("input",{bubbles:true}));
      return document.activeElement===element;
    })()`);
    await sleep(80);
    return result;
  };
  const escape = async () => {
    win.show();
    win.focus();
    win.webContents.focus();
    win.webContents.sendInputEvent({type: "keyDown", keyCode: "ESCAPE"});
    win.webContents.sendInputEvent({type: "keyUp", keyCode: "ESCAPE"});
    await sleep(100);
  };
  const measure = async view => {
    const value = await J(`(function(){
      const root=document.documentElement;
      const visibleControls=[...document.querySelectorAll("button,input:not([type=checkbox]),select,a")]
        .filter(element=>{const style=getComputedStyle(element),r=element.getBoundingClientRect();
          return style.display!=="none"&&style.visibility!=="hidden"&&r.width>0&&r.height>0;})
        .map(element=>{const r=element.getBoundingClientRect();return {
          text:(element.textContent||element.getAttribute("aria-label")||element.id||"").trim().slice(0,60),
          left:r.left,right:r.right,width:r.width,height:r.height
        };});
      return {iw:innerWidth,ih:innerHeight,sw:root.scrollWidth,cw:root.clientWidth,
        out:visibleControls.filter(x=>x.left < -1 || x.right > innerWidth + 1),
        tiny:visibleControls.filter(x=>x.width < 24 || x.height < 24)};
    })()`);
    report.overflow.push({tag, view, ...value});
    return value;
  };
  const shot = async name => {
    win.showInactive();
    win.webContents.invalidate();
    await sleep(50);
    const file = path.join(outDir, `${tag}-${name}.png`);
    const image = await win.webContents.capturePage();
    fs.writeFileSync(file, image.toPNG());
    report.screenshots.push(file);
  };

  const originalUrl = await J("location.href");
  const originalHistory = await J("history.length");
  ck(`${tag}: viewport is exact`, await J(`innerWidth===${width}`),
    {requested: width, actual: await J("innerWidth")});
  ck(`${tag}: lib-6.1 page boots without obsolete product navigation`,
    await J(`!!window.__EC_BUILDER__ && !!document.getElementById("buildView")
      && !document.querySelector("nav,.tab,#view-home,#view-library,#view-workshop,#themeToggle")`));
  ck(`${tag}: dimension, dome-summary, and manufacturer-fallback APIs are exposed`, await J(`(api=>
    typeof api.forceWallText==="function"
    &&typeof api.domeMetricSummary==="function"
    &&typeof api.mainSwitchDimensions==="function"
    &&typeof api.relationFor==="function"
    &&typeof api.partScopedFinding==="function"
    &&typeof api.sameManufacturerKey==="function"
  )(window.__EC_BUILDER__)`));
  ck(`${tag}: expected build identity is rendered`,
    await J(`PICKER_BUILD.library_build===${JSON.stringify(expectedBuild)}
      && document.getElementById("buildBadge").textContent===PICKER_BUILD.library_build`));
  ck(`${tag}: blank boot has no inferred component`, await J(`
    Object.values(window.__EC_BUILDER__.build).every(value=>value===null)
    && !document.getElementById("buildView").hidden
    && document.getElementById("chooseView").hidden
    && document.getElementById("statusTitle").textContent==="Choose parts to begin"`));
  ck(`${tag}: exactly 28 keyboard starters and four manufacturer kits`,
    await J(`(function(){
      const rows=window.__EC_BUILDER__.qualifiedKeyboardPresets();
      return rows.length===32
        &&rows.filter(row=>row.id.startsWith("kbd::")).length===28
        &&rows.filter(row=>row.id.startsWith("kit::")).length===4;
    })()`));
  ck(`${tag}: separate 2u assembly and ring rows are rendered`, await J(`
    document.querySelectorAll("[data-slot-row]").length===11
    &&!!document.querySelector('[data-slot-row="stab2uAssembly"]')
    &&!!document.querySelector('[data-slot-row="ring2u"]')`));
  ck(`${tag}: blank build has one keyboard action and no redundant toolbar action`, await J(`
    document.querySelectorAll('[data-choose="kbd"]').length===1
    &&!document.getElementById("startKeyboard")
    &&document.getElementById("buildToolbar").hidden`));
  let layout = await measure("blank-build");
  ck(`${tag}: blank build reflows without horizontal overflow or clipped controls`,
    layout.sw <= layout.iw + 1 && layout.out.length === 0, layout);
  await shot("blank-build");

  await click('[data-choose="kbd"]');
  ck(`${tag}: keyboard chooser is contextual and receives focus`, await J(`
    document.getElementById("buildView").hidden
    && !document.getElementById("chooseView").hidden
    && document.activeElement===document.getElementById("backToBuild")
    && document.getElementById("chooseTitle").textContent==="Choose a starting point"`));
  ck(`${tag}: keyboard chooser exposes only qualified starters`, await J(`
    document.querySelectorAll("[data-candidate]").length===32
    && [...document.querySelectorAll("[data-candidate]")].every(card=>
      window.__EC_BUILDER__.qualifiedKeyboardPresets().some(p=>p.id===card.dataset.candidate))`));
  await clickCandidate("kbd::hhkb_hybrid_type_s");
  ck(`${tag}: keyboard starter fills its exact owner-confirmed parts`, await J(`(b=>
    b.kbd==="kbd::hhkb_hybrid_type_s"&&b.shell==="shell::hhkb"
    &&b.h1==="shell::hhkb"&&b.h2==="shell::hhkb"
    &&b.dome==="dm-topre-45g"&&b.domeSpec===null
    &&b.slider==="slider::hhkb_type_s"&&b.sl2==="stabilizer_slider_2u::hhkb_type_s"
    &&b.stab2uAssembly==="assembly2u::hhkb_type_s"
    &&b.ring==="silencing_ring::topre_poron_0_5"
    &&b.ring2u==="silencing_ring::topre_poron_0_5"
    &&b.spring==="conical_springs::topre"
    &&b.keycap==="keycap::topre"&&b.sb==="spacebar_stabilizer::topre"
  )(window.__EC_BUILDER__.build)`));
  ck(`${tag}: fresh keyboard starter is not marked modified`,
    await J("!document.getElementById('platformCard').textContent.includes('Modified')"));
  ck(`${tag}: integrated rows disclose the keyboard-context cascade`, await J(`(function(){
    const row=document.querySelector('[data-slot-row="h1"]');
    return row.textContent.includes("Choosing a loose part removes the keyboard starting point")
      &&row.querySelector('[data-choose="h1"]').textContent==="Use loose part"
      &&!row.querySelector('[data-remove="h1"]');
  })()`));

  await click('[data-choose="ring"]');
  await clickCandidate("ring::none");
  ck(`${tag}: changing a sourced starter marks it Modified`, await J(`
    window.__EC_BUILDER__.build.kbd==="kbd::hhkb_hybrid_type_s"
    &&window.__EC_BUILDER__.build.ring==="ring::none"
    &&document.getElementById("platformCard").textContent.includes("Modified")`));
  await click('[data-choose="kbd"]');
  ck(`${tag}: modified starter exposes an explicit reset instead of a misleading select action`, await J(`(function(){
    const button=document.querySelector('[data-candidate="kbd::hhkb_hybrid_type_s"] [data-reset-preset]');
    return !!button&&button.textContent==="Reset to recorded configuration";
  })()`));
  await click("#backToBuild");
  await click('[data-remove="kbd"]');
  ck(`${tag}: multi-part keyboard removal is recoverable`, await J(`
    window.__EC_BUILDER__.build.kbd===null&&window.__EC_BUILDER__.build.shell===null
    &&!document.getElementById("undoBar").hidden
    &&document.activeElement===document.getElementById("undoAction")`));
  layout = await measure("undo-removal");
  ck(`${tag}: persistent Undo reflows without overflow or clipped controls`,
    layout.sw <= layout.iw + 1 && layout.out.length === 0 && layout.tiny.length === 0,
    layout);
  await shot("undo-removal");
  await click("#undoAction");
  ck(`${tag}: Undo restores the modified keyboard build`, await J(`
    window.__EC_BUILDER__.build.kbd==="kbd::hhkb_hybrid_type_s"
    &&window.__EC_BUILDER__.build.shell==="shell::hhkb"
    &&window.__EC_BUILDER__.build.ring==="ring::none"`));

  await click('[data-choose="sb"]');
  ck(`${tag}: known incompatible candidates are hidden and counted by default`, await J(`
    !document.querySelector('[data-candidate="spacebar_stabilizer::metapulse"]')
    &&document.getElementById("resultCount").textContent.includes("known incompatible hidden")
    &&!document.getElementById("showIncompatible").checked`));
  await click("#showIncompatible");
  ck(`${tag}: incompatible filter reveals the candidate with consumer wording`, await J(`
    !!document.querySelector('[data-candidate="spacebar_stabilizer::metapulse"]')
    &&document.querySelector('[data-candidate="spacebar_stabilizer::metapulse"]').textContent.includes("Does not work")`));
  layout = await measure("chooser-incompatible");
  ck(`${tag}: contextual chooser reflows without horizontal overflow or clipped controls`,
    layout.sw <= layout.iw + 1 && layout.out.length === 0, layout);
  await shot("chooser-incompatible");
  await clickCandidate("spacebar_stabilizer::metapulse");
  await click('[data-choose="sb"]');
  ck(`${tag}: selected incompatible option remains visible for correction`, await J(`(function(){
    const button=document.querySelector('[data-candidate="spacebar_stabilizer::metapulse"] button[disabled]');
    return !!button&&button.textContent==="Selected";
  })()`));
  await click("#backToBuild");

  await click("#clearBuild");
  await click('[data-choose="kbd"]');
  await clickCandidate("kit::deskeys");
  ck(`${tag}: Deskeys 0.7 mm rings match both corrected 0.5 + 0.2 mm seats`, await J(`(function(){
    const api=window.__EC_BUILDER__;
    const one=api.ringGeometryNote()||"",two=api.stabilizerRingGeometryNote()||"";
    return /seats flush/.test(one)&&/seats flush/.test(two)
      &&/0\\.70 mm total ring seat \\(0\\.50 mm slider seat \\+ 0\\.20 mm housing seat\\) versus 0\\.70 mm ring thickness/.test(one)
      &&/0\\.70 mm total ring seat \\(0\\.50 mm slider seat \\+ 0\\.20 mm housing seat\\) versus 0\\.70 mm ring thickness/.test(two)
      &&document.getElementById("statusTitle").textContent!=="Ring fit needs review";
  })()`));
  ck(`${tag}: the Deskeys spring is the sole incompatible part`, await J(`(function(){
    const api=window.__EC_BUILDER__,assessment=api.assessBuild();
    const badRows=[...document.querySelectorAll('[data-slot-row]')]
      .filter(row=>row.querySelector('.component-status .badge')
        &&row.querySelector('.component-status .badge').textContent==="Does not work")
      .map(row=>row.dataset.slotRow);
    const detailNames=[...document.querySelectorAll('#compatDetails .compat-item b')]
      .map(node=>node.textContent);
    return assessment.counts.bad===1
      &&assessment.partFindings.length===1
      &&assessment.partFindings[0].part==="Deskeys Conical Springs"
      &&assessment.relations.every(relation=>
        relation.a!=="Deskeys Conical Springs"&&relation.b!=="Deskeys Conical Springs")
      &&JSON.stringify(badRows)===JSON.stringify(["spring"])
      &&JSON.stringify(detailNames)===JSON.stringify(["Deskeys Conical Springs"])
      &&document.getElementById("statusTitle").textContent==="1 incompatible part"
      &&!document.getElementById("compatDetails").textContent.includes("Deskeys Conical Springs +");
  })()`));
  // Isolate the intrinsic spring finding before checking candidate sliders.
  // The complete Deskeys kit also contains legitimate pair-specific evidence,
  // which must not be conflated with the spring-only attribution contract.
  await click("#clearBuild");
  await click('[data-choose="spring"]');
  await click("#showIncompatible");
  await clickCandidate("conical_springs::deskeys_conical");
  await click('[data-choose="slider"]');
  const innocentSliderOptions = await J(`(function(){
    const cards=[...document.querySelectorAll('[data-candidate^="slider::"]')];
    const badBadges=[...document.querySelectorAll('[data-candidate^="slider::"] .badge')]
      .filter(badge=>badge.textContent==="Does not work").map(badge=>badge.textContent);
    const hiddenText=document.getElementById("resultCount").textContent;
    return {pass:cards.length===8&&!hiddenText.includes("known incompatible hidden")
      &&badBadges.length===0,count:cards.length,hiddenText,badBadges};
  })()`);
  ck(`${tag}: a bad spring does not flag or hide innocent slider options`,
    innocentSliderOptions.pass, innocentSliderOptions);
  await click("#backToBuild");

  await click("#clearBuild");
  await click('[data-choose="kbd"]');
  await clickCandidate("kit::dynacaps");
  const dynaDefault = await J(`(function(){
    const api=window.__EC_BUILDER__,b=api.build;
    const one=api.ringGeometryNote()||"",two=api.stabilizerRingGeometryNote()||"";
    const statusTitle=document.getElementById("statusTitle").textContent;
    const sliderText=document.querySelector('[data-slot-row="slider"]').textContent;
    const stabilizerSliderText=document.querySelector('[data-slot-row="sl2"]').textContent;
    const pass=b.ring==="silencing_ring::dynacaps_silicone_0_5"
      &&b.ring2u==="silencing_ring::dynacaps_silicone_0_5"
      &&/0\\.25 mm intentional pre-compression \\(manufacturer recommended\\)/.test(one)
      &&/0\\.25 mm intentional pre-compression \\(manufacturer recommended\\)/.test(two)
      &&statusTitle!=="Ring fit needs review"
      &&sliderText.indexOf("4 mm nominal travel")<0
      &&stabilizerSliderText.indexOf("4 mm nominal travel")<0;
    return {pass,ring:b.ring,ring2u:b.ring2u,one,two,statusTitle,
      sliderHasNominalTravel:sliderText.includes("4 mm nominal travel"),
      stabilizerSliderHasNominalTravel:stabilizerSliderText.includes("4 mm nominal travel")};
  })()`);
  ck(`${tag}: DynaCaps kit loads the recommended 0.5 mm Silicone rings for 1u and 2u`,
    dynaDefault.pass, dynaDefault);
  ck(`${tag}: calculated Travel and Dome compression are visible for the DynaCaps default`, await J(`(function(){
    const dimensions=window.__EC_BUILDER__.mainSwitchDimensions();
    return dimensions.compressionMm===0.25
      &&dimensions.geometricTravelMm===3.75
      &&dimensions.forceWallMm===null
      &&dimensions.travelMm===3.75
      &&dimensions.travelSource==="geometry"
      &&document.getElementById("dimensionTravel").textContent==="3.75 mm"
      &&document.getElementById("dimensionCompression").textContent==="0.25 mm";
  })()`));
  ck(`${tag}: intentional DynaCaps compression is a sourced design note`, await J(`(function(){
    const notes=[...document.querySelectorAll("#compatDetails .compat-item")];
    return notes.filter(row=>row.querySelector("strong")&&row.querySelector("strong").textContent==="Manufacturer design note").length===2
      &&notes.filter(row=>row.querySelector('a[href="https://omnitype.com/pages/dynacap"]')).length===2;
  })()`));
  await click('[data-choose="slider"]');
  ck(`${tag}: DynaCaps 1u chooser omits nominal travel`, await J(`
    !document.querySelector('[data-candidate="slider::dynacaps"]').textContent.includes("4 mm nominal travel")`));
  await click('[data-candidate="slider::dynacaps"] [data-details]');
  ck(`${tag}: DynaCaps 1u details omit nominal travel`, await J(`
    !document.getElementById("detailBody").textContent.includes("Nominal travel")`));
  await click("#closeDetails");
  await click("#backToBuild");
  await click('[data-choose="sl2"]');
  ck(`${tag}: DynaCaps 2u chooser omits nominal travel`, await J(`
    !document.querySelector('[data-candidate="stabilizer_slider_2u::dynacaps"]').textContent.includes("4 mm nominal travel")`));
  await click('[data-candidate="stabilizer_slider_2u::dynacaps"] [data-details]');
  ck(`${tag}: DynaCaps 2u details omit nominal travel`, await J(`
    !document.getElementById("detailBody").textContent.includes("Nominal travel")`));
  await click("#closeDetails");
  await click("#backToBuild");

  await click("#clearBuild");
  await click('[data-choose="stab2uAssembly"]');
  ck(`${tag}: 2u assembly chooser exposes all ten owner-confirmed assemblies`, await J(`
    document.querySelectorAll("[data-candidate]").length===10
    &&!!document.querySelector('[data-candidate="assembly2u::topre_silenced"]')
    &&!!document.querySelector('[data-candidate="assembly2u::deskeys"]')
    &&!!document.querySelector('[data-candidate="assembly2u::dynacaps"]')
    &&!!document.querySelector('[data-candidate="assembly2u::klc"]')
    &&!!document.querySelector('[data-candidate="assembly2u::metakeebs"]')`));
  await clickCandidate("assembly2u::topre_silenced");
  ck(`${tag}: Topre Silenced assembly loads its 1.0 mm flush geometry`, await J(`(function(){
    const api=window.__EC_BUILDER__,b=api.build;
    return b.stab2uAssembly==="assembly2u::topre_silenced"
      &&b.h2==="stabilizer_housing_2u::topre_silenced"
      &&b.sl2==="stabilizer_slider_2u::topre_silenced"
      &&b.ring2u==="silencing_ring::topre_2u_poron_1_0"
      &&/seats flush/.test(api.stabilizerRingGeometryNote()||"");
  })()`));
  await click('[data-choose="ring2u"]');
  await clickCandidate("silencing_ring::topre_poron_0_5");
  ck(`${tag}: thinner 2u ring visibly reports chatter risk`, await J(`
    /0\\.50 mm top-out clearance \\(chatter risk\\)/.test(
      window.__EC_BUILDER__.stabilizerRingGeometryNote()||"")
    &&window.__EC_BUILDER__.isAssemblyModified()`));
  await click('[data-choose="ring2u"]');
  await clickCandidate("ring::none");
  ck(`${tag}: explicit no-ring still reports nonzero 2u chatter clearance`, await J(`
    /1\\.00 mm top-out clearance \\(chatter risk\\)/.test(
      window.__EC_BUILDER__.stabilizerRingGeometryNote()||"")`));

  await click("#clearBuild");
  await click('[data-choose="slider"]');
  ck(`${tag}: chooser Back control owns initial focus`,
    await J("document.activeElement===document.getElementById('backToBuild')"));
  await escape();
  ck(`${tag}: real Escape returns to build and restores row focus`, await J(`
    document.getElementById("chooseView").hidden
    &&document.activeElement&&document.activeElement.dataset.choose==="slider"`));

  await click('[data-choose="slider"]');
  ck(`${tag}: live search keeps the same focused input`, await setInput("#partSearch", "dynacaps"));
  ck(`${tag}: slider chooser filters to its exact contextual result`, await J(`
    document.querySelectorAll("[data-candidate]").length===1
    &&!!document.querySelector('[data-candidate="slider::dynacaps"]')`));
  await click('[data-candidate="slider::dynacaps"] [data-details]');
  ck(`${tag}: Details opens a modal dialog and moves focus to Close`, await J(`
    document.getElementById("detailDialog").open
    &&document.activeElement===document.getElementById("closeDetails")`));
  await escape();
  ck(`${tag}: closing Details restores its opener`, await J(`
    !document.getElementById("detailDialog").open
    &&document.activeElement&&document.activeElement.dataset.details==="slider::dynacaps"`));
  await clickCandidate("slider::dynacaps");
  ck(`${tag}: component selection returns to its build row`, await J(`
    window.__EC_BUILDER__.build.slider==="slider::dynacaps"
    &&document.activeElement&&document.activeElement.dataset.choose==="slider"`));
  await click('[data-choose="slider"]');
  ck(`${tag}: currently selected component is labeled and disabled`, await J(`(function(){
    const button=document.querySelector('[data-candidate="slider::dynacaps"] button[disabled]');
    return !!button&&button.textContent==="Selected";
  })()`));
  await click("#backToBuild");
  await click('[data-choose="spring"]');
  ck(`${tag}: same-manufacturer DynaCaps spring is not flagged Not verified`, await J(`(function(){
    const card=document.querySelector('[data-candidate="conical_springs::dynacaps"]');
    return !!card&&card.querySelector('.badge').textContent==="Manufacturer matched"
      &&!card.textContent.includes("Not verified");
  })()`));
  await clickCandidate("conical_springs::dynacaps");
  await click('[data-choose="h1"]');
  ck(`${tag}: same-manufacturer DynaCaps housing is not flagged Not verified`, await J(`(function(){
    const card=document.querySelector('[data-candidate="housings::dynacaps"]');
    return !!card&&card.querySelector('.badge').textContent==="Manufacturer matched"
      &&!card.textContent.includes("Not verified");
  })()`));
  await clickCandidate("housings::dynacaps");
  ck(`${tag}: same-manufacturer component stack has no unverified relationship`, await J(`(function(){
    const api=window.__EC_BUILDER__,assessment=api.assessBuild();
    return assessment.relations.length===3
      &&assessment.relations.every(relation=>relation.state==="works")
      &&document.getElementById("statusTitle").textContent==="No compatibility issues found"
      &&![...document.querySelectorAll(".component-status .badge")]
        .some(badge=>badge.textContent==="Not verified");
  })()`));

  await click("#clearBuild");
  await click('[data-choose="dome"]');
  ck(`${tag}: dome choices are labeled Not evaluated`, await J(`
    !document.getElementById("domeNote").hidden
    &&[...document.querySelectorAll(".candidate .badge")].every(x=>x.textContent==="Not evaluated")`));
  const brownCatalogId = await J(`window.__EC_BUILDER__.DOME_MEASUREMENTS.find(
    row=>row.specimen_id==="dome::deskeys_v3_brown_63g").catalog_id`);
  ck(`${tag}: measured Deskeys V3 Brown 63g dome is selectable`,
    await clickCandidate(brownCatalogId));
  ck(`${tag}: selected dome summary has the requested exact order and Force-Wall`, await J(`(function(){
    const api=window.__EC_BUILDER__,m=api.DOME_MEASUREMENTS.find(
      row=>row.specimen_id==="dome::deskeys_v3_brown_63g");
    const summary=document.querySelector('[data-slot-row="dome"] .selection-meta').textContent;
    return m.force_wall_mm===3.8525
      &&api.forceWallText([m])==="3.85 mm"
      &&api.domeMetricSummary([m])==="Weight Index 79.1 · Tactility Index 67.2 · Force-Wall 3.85 mm"
      &&summary==="Weight Index 79.1 · Tactility Index 67.2 · Force-Wall 3.85 mm";
  })()`));
  ck(`${tag}: dome-only build asks for another part`, await J(`
    document.getElementById("statusTitle").textContent==="Choose another part to check compatibility"
    &&document.getElementById("statusCopy").textContent.includes("Dome fit is not evaluated")`));
  await click('[data-choose="dome"]');
  await click(`[data-candidate="${brownCatalogId}"] [data-details]`);
  ck(`${tag}: measured dome Details shows Weight, Tactility, and Force-Wall values`, await J(`(function(){
    const rows=Object.fromEntries([...document.querySelectorAll("#detailBody .detail-cell")]
      .map(cell=>[cell.querySelector("dt").textContent,cell.querySelector("dd").textContent]));
    return rows["Weight Index"]==="79.1"
      &&rows["Tactility Index"]==="67.2"
      &&rows["Force-Wall"]==="3.85 mm";
  })()`));
  await click("#closeDetails");
  await click("#backToBuild");

  await click("#clearBuild");
  await click('[data-choose="kbd"]');
  await clickCandidate("kit::dynacaps");
  await click('[data-choose="dome"]');
  await clickCandidate(brownCatalogId);
  ck(`${tag}: geometric travel wins when shorter than the selected dome Force-Wall`, await J(`(function(){
    const dimensions=window.__EC_BUILDER__.mainSwitchDimensions();
    return dimensions.compressionMm===0.25
      &&dimensions.geometricTravelMm===3.75
      &&dimensions.forceWallMm===3.8525
      &&dimensions.travelMm===3.75
      &&dimensions.travelSource==="geometry"
      &&document.getElementById("dimensionTravel").textContent==="3.75 mm"
      &&document.getElementById("dimensionCompression").textContent==="0.25 mm";
  })()`));

  await click("#clearBuild");
  await click('[data-choose="kbd"]');
  await clickCandidate("kbd::realforce_r2");
  await click('[data-choose="dome"]');
  await clickCandidate(brownCatalogId);
  ck(`${tag}: measured Force-Wall wins when shorter than geometric travel`, await J(`(function(){
    const dimensions=window.__EC_BUILDER__.mainSwitchDimensions();
    return dimensions.compressionMm===0
      &&dimensions.geometricTravelMm===4
      &&dimensions.forceWallMm===3.8525
      &&dimensions.travelMm===3.8525
      &&dimensions.travelSource==="force-wall"
      &&document.getElementById("dimensionTravel").textContent==="3.85 mm"
      &&document.getElementById("dimensionCompression").textContent==="0.00 mm";
  })()`));

  ck(`${tag}: four compatibility states use only customer-facing labels`, await J(`
    JSON.stringify([
      consumerRelation({st:"compatible"},"A","B").label,
      consumerRelation({st:"conditional",rsn:"condition"},"A","B").label,
      consumerRelation({st:"incompatible",rsn:"conflict"},"A","B").label,
      consumerRelation({st:"unknown"},"A","B").label
    ])===JSON.stringify(["Works","Works with conditions","Does not work","Not verified"])`));
  layout = await measure("exact-dome-build");
  ck(`${tag}: completed flow remains within the viewport`,
    layout.sw <= layout.iw + 1 && layout.out.length === 0, layout);
  await shot("exact-dome-build");

  ck(`${tag}: tool does not mutate URL or session history`, await J(`
    location.href===${JSON.stringify(originalUrl)}&&history.length===${originalHistory}`),
    {url: await J("location.href"), history: await J("history.length")});
  ck(`${tag}: visible controls meet the 24 CSS-pixel target-size floor`,
    layout.tiny.length === 0, {tiny: layout.tiny});

  win.destroy();
}

app.on("window-all-closed", () => {});
app.whenReady().then(async () => {
  hookSession(session.defaultSession);
  const combos = [
    [1280, 900, "desktop-1280"],
    [390, 844, "phone-390"],
    [320, 800, "reflow-320"],
  ];
  for (const [width, height, tag] of combos) {
    try {
      await runCombo(width, height, tag);
    } catch (error) {
      ck(`${tag}: acceptance flow completed`, false,
        {error: String(error && error.stack || error)});
    }
  }
  ck("network: zero non-file requests across all viewports",
    report.badRequests.length === 0, {bad: report.badRequests});
  ck("console: zero error-level messages across all viewports",
    report.console.length === 0, {console: report.console});
  const overflow = report.overflow.filter(item => item.sw > item.iw + 1 || item.out.length);
  ck("layout: zero horizontal overflow or clipped controls across all recorded views",
    overflow.length === 0, {overflow});
  report.finished = new Date().toISOString();
  report.total = report.checks.length;
  report.failed = report.checks.filter(item => !item.pass).length;
  fs.writeFileSync(path.join(outDir, "browser_report.json"), JSON.stringify(report, null, 2));
  process.stdout.write(JSON.stringify({
    total: report.total, failed: report.failed,
    screenshots: report.screenshots.length, requests: report.requests.length,
  }) + "\n");
  app.exit(report.failed ? 1 : 0);
});
