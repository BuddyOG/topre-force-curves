#!/usr/bin/env node
/* Runtime security battery for the Shopify parent/child bridge. */
"use strict";

const fs = require("fs");
const {JSDOM, VirtualConsole} = require("jsdom");

const pickerPath = process.argv[2];
if (!pickerPath) {
  console.error("usage: shopify_embed_runtime_battery.js <picker.html>");
  process.exit(2);
}
const html = fs.readFileSync(pickerPath, "utf8");
const checks = [];
const errors = [];
const check = (name, pass, detail = null) => checks.push({name, pass: !!pass, detail});
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

const virtualConsole = new VirtualConsole();
virtualConsole.on("jsdomError", error => errors.push(String(error && error.message || error)));
virtualConsole.on("error", error => errors.push(String(error)));

(async function run() {
  try {
    // An untrusted parent URL keeps the initial trust state empty. Synthetic
    // MessageEvents then exercise the same source/origin gate as production.
    const parentDom = new JSDOM("<!doctype html><iframe id=child></iframe><iframe id=sibling></iframe>", {
      runScripts: "dangerously",
      url: "https://embed-battery.invalid/",
      pretendToBeVisual: true,
      virtualConsole,
    });
    const parentWindow = parentDom.window;
    const child = parentWindow.document.getElementById("child").contentWindow;
    const sibling = parentWindow.document.getElementById("sibling").contentWindow;
    const sent = [];
    parentWindow.postMessage = (data, targetOrigin) => sent.push({data, targetOrigin});
    child.requestAnimationFrame = callback => setTimeout(() => callback(Date.now()), 0);
    child.cancelAnimationFrame = clearTimeout;
    child.fetch = () => Promise.reject(new Error("bridge battery is offline"));
    child.document.open();
    child.document.write(html);
    child.document.close();
    await wait(80);

    const C = expression => child.eval(expression);
    const dispatch = (data, origin, source = parentWindow) => {
      child.dispatchEvent(new child.MessageEvent("message", {data, origin, source}));
    };
    check("framed page starts without trusting an unlisted referrer",
      C("embedOrigin") === null && sent.length === 0,
      {origin: C("embedOrigin"), sent});
    check("production parent allowlist is exact",
      JSON.stringify(C("[...EMBED_ORIGINS].sort()")) === JSON.stringify([
        "https://unreal-keyboards.myshopify.com",
        "https://unrealkeyboards.com",
        "https://www.unrealkeyboards.com",
      ]));
    check("viewport validator accepts numbers only",
      C("validViewportNumber(900,100,5000)")
      && !C('validViewportNumber("900",100,5000)')
      && !C("validViewportNumber(NaN,100,5000)")
      && !C("validViewportNumber(Infinity,100,5000)"));

    const invalidCases = [
      {data: {type: "ukdl-viewport", viewH: "900", visibleTop: 0}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: 900, visibleTop: "0"}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: NaN, visibleTop: 0}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: Infinity, visibleTop: 0}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: 99, visibleTop: 0}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: 5001, visibleTop: 0}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: 900, visibleTop: -1}, origin: "https://unrealkeyboards.com"},
      {data: {type: "ukdl-viewport", viewH: 900, visibleTop: 0}, origin: "https://evil.invalid"},
      {data: {type: "not-ukdl", viewH: 900, visibleTop: 0}, origin: "https://unrealkeyboards.com"},
    ];
    for (const item of invalidCases) dispatch(item.data, item.origin);
    dispatch({type: "ukdl-viewport", viewH: 900, visibleTop: 0},
      "https://unrealkeyboards.com", sibling);
    await wait(30);
    check("invalid payloads, wrong origin, and sibling source cannot establish trust",
      C("embedOrigin") === null && sent.length === 0,
      {origin: C("embedOrigin"), sent});

    dispatch({type: "ukdl-viewport", viewH: 900, visibleTop: 10},
      "https://unrealkeyboards.com");
    await wait(30);
    check("first valid viewport message establishes trust and reports height",
      C("embedOrigin") === "https://unrealkeyboards.com"
      && sent.length === 1
      && sent[0].data.type === "ukdl-height"
      && sent[0].data.h === 400
      && sent[0].targetOrigin === "https://unrealkeyboards.com",
      {origin: C("embedOrigin"), sent});

    const afterFirst = sent.length;
    dispatch({type: "ukdl-viewport", viewH: 900, visibleTop: 20},
      "https://www.unrealkeyboards.com");
    await wait(30);
    check("trusted parent origin cannot be replaced by another allowlisted origin",
      C("embedOrigin") === "https://unrealkeyboards.com" && sent.length === afterFirst,
      {origin: C("embedOrigin"), sent: sent.length});

    dispatch({type: "ukdl-viewport", viewH: 1000, visibleTop: 20},
      "https://unrealkeyboards.com");
    await wait(30);
    check("later messages from the locked parent remain accepted",
      sent.length === afterFirst + 1
      && sent.at(-1).targetOrigin === "https://unrealkeyboards.com");

    Object.defineProperty(child.document.body, "scrollHeight", {
      configurable: true, get: () => 50000,
    });
    Object.defineProperty(child.document.documentElement, "scrollHeight", {
      configurable: true, get: () => 50000,
    });
    C("sendHeight()");
    check("child height is clamped to the documented maximum",
      sent.at(-1).data.h === 20000, sent.at(-1));
    Object.defineProperty(child.document.body, "scrollHeight", {
      configurable: true, get: () => 0,
    });
    Object.defineProperty(child.document.documentElement, "scrollHeight", {
      configurable: true, get: () => 0,
    });
    C("sendHeight()");
    check("child height is clamped to the documented minimum",
      sent.at(-1).data.h === 400, sent.at(-1));
    check("every child message uses the locked exact target origin, never wildcard",
      sent.length > 0 && sent.every(message =>
        message.targetOrigin === "https://unrealkeyboards.com"
        && message.targetOrigin !== "*"), sent);

    const standaloneErrors = [];
    const standaloneConsole = new VirtualConsole();
    standaloneConsole.on("jsdomError", error => standaloneErrors.push(String(error && error.message || error)));
    const standalone = new JSDOM(html, {
      runScripts: "dangerously",
      url: "https://buddyog.github.io/topre-force-curves/dome-lab-parts.html",
      pretendToBeVisual: true,
      virtualConsole: standaloneConsole,
      beforeParse(w) {
        w.requestAnimationFrame = callback => setTimeout(() => callback(Date.now()), 0);
        w.cancelAnimationFrame = clearTimeout;
      },
    });
    await wait(40);
    check("standalone GitHub Pages mode remains error-free and untrusted",
      standaloneErrors.length === 0 && standalone.window.eval("embedOrigin") === null,
      {standaloneErrors});
    standalone.window.close();
    parentDom.window.close();
    check("bridge battery records zero runtime errors", errors.length === 0, {errors});
  } catch (error) {
    check("bridge battery executed without harness errors", false,
      {error: String(error && error.stack || error), errors});
  }

  const failed = checks.filter(item => !item.pass).length;
  console.log(JSON.stringify({checks, total: checks.length, failed}, null, 2));
  process.exit(failed ? 1 : 0);
})();
