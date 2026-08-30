#!/usr/bin/env node
/* Real-browser acceptance for the lib-6 EC Parts Builder.
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
const expectedBuild = args[3] || "lib-6.0-review.1";
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
  ck(`${tag}: lib-6 page boots without obsolete product navigation`,
    await J(`!!window.__EC_BUILDER__ && !!document.getElementById("buildView")
      && !document.querySelector("nav,.tab,#view-home,#view-library,#view-workshop,#themeToggle")`));
  ck(`${tag}: expected build identity is rendered`,
    await J(`PICKER_BUILD.library_build===${JSON.stringify(expectedBuild)}
      && document.getElementById("buildBadge").textContent===PICKER_BUILD.library_build`));
  ck(`${tag}: blank boot has no inferred component`, await J(`
    Object.values(window.__EC_BUILDER__.build).every(value=>value===null)
    && !document.getElementById("buildView").hidden
    && document.getElementById("chooseView").hidden
    && document.getElementById("statusTitle").textContent==="Choose parts to begin"`));
  ck(`${tag}: exactly 13 qualified keyboard starters`,
    await J("window.__EC_BUILDER__.qualifiedKeyboardPresets().length===13"));
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
    && document.getElementById("chooseTitle").textContent==="Choose a keyboard"`));
  ck(`${tag}: keyboard chooser exposes only qualified starters`, await J(`
    document.querySelectorAll("[data-candidate]").length===13
    && [...document.querySelectorAll("[data-candidate]")].every(card=>
      window.__EC_BUILDER__.qualifiedKeyboardPresets().some(p=>p.id===card.dataset.candidate))`));
  await clickCandidate("kbd::hhkb_hybrid_type_s");
  ck(`${tag}: keyboard starter fills exactly its sourced parts and no inferred empties`, await J(`(b=>
    b.kbd==="kbd::hhkb_hybrid_type_s"&&b.shell==="shell::hhkb"
    &&b.h1==="shell::hhkb"&&b.h2==="shell::hhkb"
    &&b.dome==="dm-topre-45g"&&b.domeSpec===null
    &&b.slider==="slider::hhkb_type_s"&&b.sl2==="stabilizer_slider_2u::hhkb_type_s"
    &&b.ring===null&&b.spring===null&&b.keycap===null&&b.sb===null
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
  ck(`${tag}: owner-pending DynaCaps spring claim is Not verified`, await J(`(function(){
    const card=document.querySelector('[data-candidate="conical_springs::dynacaps"]');
    return !!card&&card.querySelector('.badge').textContent==="Not verified"
      &&!card.textContent.includes("Works with conditions");
  })()`));
  await click("#backToBuild");

  await click("#clearBuild");
  await click('[data-choose="dome"]');
  ck(`${tag}: dome choices are labeled Not evaluated`, await J(`
    !document.getElementById("domeNote").hidden
    &&[...document.querySelectorAll(".candidate .badge")].every(x=>x.textContent==="Not evaluated")`));
  ck(`${tag}: exact Sony Gray 02 specimen row is selectable`,
    await clickDomeSpecimen("dome::sony_bke_gray_02"));
  ck(`${tag}: exact dome specimen projects collapse and both index metrics`, await J(`(function(){
    const api=window.__EC_BUILDER__,m=api.DOME_MEASUREMENTS.find(x=>x.specimen_id==="dome::sony_bke_gray_02");
    const text=document.querySelector('[data-slot-row="dome"]').textContent;
    return !!m&&api.build.domeSpec===m.specimen_id
      &&text.includes(m.label.replace(/_/g," "))
      &&text.includes(m.collapse_force_gf.toFixed(1)+" gf measured")
      &&text.includes("1 measured specimen")
      &&text.includes("Weight Index "+m.weight_index.toFixed(1))
      &&text.includes("Tactility Index "+m.tactility_index.toFixed(1));
  })()`));
  ck(`${tag}: dome-only build asks for another part`, await J(`
    document.getElementById("statusTitle").textContent==="Choose another part to check compatibility"
    &&document.getElementById("statusCopy").textContent.includes("Dome fit is not evaluated")`));

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
