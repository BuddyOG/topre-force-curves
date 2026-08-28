// Runtime acceptance for the fc-3.4 review viewer. Network is rejected so the
// exact generated embedded candidate is exercised without mutable inputs.
const {JSDOM,VirtualConsole}=require("jsdom");
const fs=require("fs");
const viewer=process.argv[2];
const viewerSource=fs.readFileSync(viewer,"utf8");
const mode=process.argv[3]||"missing";
const errors=[];
const nonFiniteCanvasCalls=[];
const paintedText=[];
const forbiddenPaintedText=[];
const FORBIDDEN_CONSUMER_TEXT=/80 is not twice 40|index scale note|wall delta|vs\s+Topre/i;
let pngExports=0;
const vc=new VirtualConsole();
vc.on("jsdomError",e=>errors.push(String(e&&e.message||e)));
const fetched=[];

function finiteArgs(method,args){
  for(const value of args){
    if(typeof value==="number"&&!Number.isFinite(value))
      nonFiniteCanvasCalls.push(`${String(method)}(${args.map(String).join(",")})`);
  }
}
function canvasContext(canvas){
  const target={
    canvas,
    measureText(text){return {width:String(text).length*6};},
    fillText(text,...args){
      const value=String(text);paintedText.push(value);
      if(FORBIDDEN_CONSUMER_TEXT.test(value))forbiddenPaintedText.push(value);
      finiteArgs("fillText",args);
    },
    createLinearGradient(){return {addColorStop(){}};},
    createRadialGradient(){return {addColorStop(){}};},
    createPattern(){return {};},
  };
  return new Proxy(target,{
    get(object,key){
      if(key in object)return object[key];
      return (...args)=>{finiteArgs(key,args);return undefined;};
    },
    set(object,key,value){
      if(typeof value==="number"&&!Number.isFinite(value))
        nonFiniteCanvasCalls.push(`set ${String(key)}=${String(value)}`);
      object[key]=value;return true;
    }
  });
}

const dom=new JSDOM(viewerSource,{
  runScripts:"dangerously",url:"https://review.invalid/",virtualConsole:vc,
  beforeParse(w){
    w.requestAnimationFrame=cb=>setTimeout(cb,0);w.cancelAnimationFrame=clearTimeout;
    w.fetch=url=>{
      fetched.push(String(url));
      if(mode==="malformed200")return Promise.resolve({ok:true,status:200,text:()=>Promise.resolve("garbage")});
      return Promise.reject(new Error("missing pinned review file"));
    };
    Object.defineProperty(w.HTMLCanvasElement.prototype,"clientWidth",{
      configurable:true,get(){return 1000;}
    });
    Object.defineProperty(w.HTMLCanvasElement.prototype,"clientHeight",{
      configurable:true,get(){return 625;}
    });
    w.HTMLCanvasElement.prototype.getContext=function(){
      if(!this.__reviewContext)this.__reviewContext=canvasContext(this);
      return this.__reviewContext;
    };
    w.HTMLCanvasElement.prototype.toBlob=function(callback){
      pngExports++;callback(new w.Blob(["png"],{type:"image/png"}));
    };
    w.HTMLCanvasElement.prototype.toDataURL=()=>"data:image/png;base64,";
    w.URL.createObjectURL=()=>"blob:review";w.URL.revokeObjectURL=()=>{};
    w.HTMLAnchorElement.prototype.click=()=>{};
  }
});

const delay=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  await delay(100);
  const w=dom.window;
  const build=w.eval("VIEWER_BUILD");
  const model=w.eval("PERCEPTION_MODEL");
  const rows=w.eval("VTESTS");
  // A record id is a presentation identity, not permission to hide conflicting
  // scalar authority on another record bound to the same source set.
  const duplicateDivergenceClosed=w.eval(`(()=>{
    const first=VTESTS.find(t=>t.k==="dome_baseline");
    if(!first)return false;
    const second={...first,id:"synthetic-divergent-duplicate",k:"part_assembly"};
    VTESTS.push(second);
    try{
      second.cg=first.cg+0.125;
      try{canonStats(first.set,first.id);return false;}
      catch(e){return String(e&&e.message||e).includes("divergent generated record scalars");}
    }finally{VTESTS.pop();}
  })()`);
  const primary=rows.find(t=>t.set==="Topre_R1_45g"&&t.id==="bt_0075"&&t.k==="dome_baseline");
  const primarySet=primary&&primary.set;
  const other=rows.find(t=>t.set!==primarySet&&t.k==="dome_baseline"&&
    Number.isFinite(t.wi)&&Number.isFinite(t.ti)&&Object.values(t.pp).every(Number.isFinite));
  const parts=rows.filter(t=>t.k==="part_assembly").slice(0,2);
  const part=parts[0];
  await w.eval(`toggleSet(${JSON.stringify(primarySet)},${JSON.stringify(primary.id)})`);
  const s=w.eval(`sets.get(${JSON.stringify(primarySet)})`);
  const canonical=s&&s.data&&s.data.snapshot&&s.data.stats&&s.data.stats.record_ids[0]===primary.id;
  const originalStats={...s.data.stats,percentiles:{...s.data.stats.percentiles}};
  const visibleBody=w.document.body.cloneNode(true);
  visibleBody.querySelectorAll("script,style").forEach(node=>node.remove());
  const watermarkAbsentFromLiveDom=!visibleBody.textContent.includes("UNREAL KEYBOARDS");
  paintedText.length=0;
  w.eval('chartMode="curves";render();');
  const watermarkAbsentFromLiveCanvas=!paintedText.includes("UNREAL KEYBOARDS");
  paintedText.length=0;
  w.eval('exportPNG();');
  const exportWatermarkDrawn=paintedText.includes("UNREAL KEYBOARDS");
  const expectedMetricOrder=[
    "Weight Index","Tactility Index","Collapse force","Ramp","Pre-collapse work",
    "Drop","Steepest 0.10 mm drop","Drop rate","Snap %","Detected force-wall onset"
  ];
  const normalLines=w.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const visibleStatOrder=JSON.stringify(normalLines.slice(0,expectedMetricOrder.length).map(row=>row[0]))===
    JSON.stringify(expectedMetricOrder);
  const retiredLabels=["Press work to force-wall","Norm. drop rate","Collapse-to-valley distance",
    "Collapse point","Valley"];
  const lowAssociationStatsRemoved=!normalLines.some(row=>retiredLabels.includes(row[0]));
  const indicesVisible=normalLines.some(row=>row[0]==="Weight Index"&&/\/ 100$/.test(row[1]))&&
    normalLines.some(row=>row[0]==="Tactility Index"&&/\/ 100$/.test(row[1]));
  const normalWallValueOnly=normalLines.some(row=>row[0]==="Detected force-wall onset"&&
    row[1]===`${originalStats.travel.toFixed(2)} mm`);

  const partStats=w.eval("canonStats")(part.set,part.id);
  w.__partProbe={key:part.set,record_id:part.id,data:{stats:partStats}};
  const partLines=w.eval("statLines(__partProbe)");
  const partIndicesNotCalibrated=partLines.some(row=>row[0]==="Weight Index"&&row[1]==="Not calibrated")&&
    partLines.some(row=>row[0]==="Tactility Index"&&row[1]==="Not calibrated");
  const partWallValueOnly=partLines.some(row=>row[0]==="Detected force-wall onset"&&row[1]===
    (Number.isFinite(partStats.travel)?`${partStats.travel.toFixed(2)} mm`:"Not detected"));

  const commitPinned=fetched.length>0&&fetched.every(u=>u.includes(build.repo_commit)&&!u.includes("/main/"));
  const turnaround=w.eval(`recordedTurnaround(sets.get(${JSON.stringify(primarySet)}))`);
  const noWallReferenceMetadata=!Object.keys(build).some(key=>key.startsWith("force_wall_reference"));
  const noDeltaOrScaleNoteSource=!/forceWallDelta|wallDelta|force_wall_reference|80 is not twice 40|Index scale note|INDEX_SCALE_NOTE/.test(viewerSource);
  const simplePercentileCopy=viewerSource.includes(
    "Weight Index</b> is this dome’s weight percentile compared with the other domes tested."
  )&&viewerSource.includes(
    "Tactility Index</b> is this dome’s tactility percentile compared with the other domes tested."
  );

  await w.eval(`toggleSet(${JSON.stringify(other.set)},${JSON.stringify(other.id)})`);
  w.eval('chartMode="curves";render();');
  w.document.getElementById("roMore").click();
  const expandedReadout=w.document.getElementById("readout").textContent;
  const readoutHasWallWithoutDelta=expandedReadout.includes("WALL (MM)")&&
    !FORBIDDEN_CONSUMER_TEXT.test(expandedReadout);
  w.eval('chartMode="profileWeight";render();exportPNG();');
  const weightPoints=w.eval("PROFILE_PTS.map(point=>({...point}))");
  w.eval('chartMode="profileTactility";render();exportPNG();');
  const tactilityPoints=w.eval("PROFILE_PTS.map(point=>({...point}))");
  const finitePoint=point=>Number.isFinite(point.x)&&Number.isFinite(point.y)&&
    !/NaN|Infinity/.test(point.tip);
  const weightProfile=weightPoints.length===6&&weightPoints.every(finitePoint);
  const tactilityProfile=tactilityPoints.length===8&&tactilityPoints.every(finitePoint);

  // The new index comparison is a true two-dimensional 0–100 plot: Weight
  // Index is x and Tactility Index is y.  Every calibrated selected
  // dome contributes exactly one point, with no aggregation or substitution.
  paintedText.length=0;
  w.eval('chartMode="indexScatter";render();exportPNG();');
  const scatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
  const margins=w.eval("({...M})");
  const selectedDomeStats=new Map([primarySet,other.set].map(key=>[
    key,w.eval(`sets.get(${JSON.stringify(key)}).data.stats`)
  ]));
  const scatterCoordinates=scatterPoints.length===2&&scatterPoints.every(point=>{
    const st=selectedDomeStats.get(point.key);
    if(!st||!Number.isFinite(st.weightIndex)||!Number.isFinite(st.tactilityIndex))return false;
    const legendBand=Math.min(380,Math.max(280,(1000-margins.l-margins.r)*.38));
    const left=margins.l+8,right=1000-margins.r-8-legendBand,top=margins.t+80,bottom=625-margins.b;
    const expectedX=left+(st.weightIndex/100)*(right-left);
    const expectedY=bottom-(st.tactilityIndex/100)*(bottom-top);
    return finitePoint(point)&&Math.abs(point.x-expectedX)<1e-9&&Math.abs(point.y-expectedY)<1e-9&&
      point.recordId&&point.tip.includes(`Weight Index ${st.weightIndex.toFixed(1)}`)&&
      point.tip.includes(`Tactility Index ${st.tactilityIndex.toFixed(1)}`)&&
      !/force-wall/i.test(point.tip)&&!/NaN|Infinity/.test(point.tip);
  });
  const scatterLabelsAndAxes=["Weight Index (0–100)","Tactility Index (0–100)",
    ...scatterPoints.map(point=>point.name)].every(label=>paintedText.includes(label));
  const scatterKeepsWallSeparate=!paintedText.some(text=>/force-wall/i.test(text))&&
    normalLines.some(row=>row[0]==="Detected force-wall onset");
  const hoverPoint=scatterPoints[0];
  const canvas=w.document.getElementById("chart");
  const pointerMove=new w.MouseEvent("pointermove",{
    clientX:hoverPoint.x,clientY:hoverPoint.y,bubbles:true
  });
  Object.defineProperty(pointerMove,"pointerType",{value:"mouse"});
  canvas.dispatchEvent(pointerMove);
  await delay(0);
  const hoverStats=selectedDomeStats.get(hoverPoint.key);
  const scatterTooltip=w.document.getElementById("tooltip").textContent;
  const scatterHoverLinked=w.eval("hoverKey")===hoverPoint.key&&
    !!w.document.querySelector(`#readout tr[data-key="${hoverPoint.key}"]`)?.classList.contains("hl")&&
    scatterTooltip.includes(hoverPoint.name)&&
    scatterTooltip.includes(`Weight Index ${hoverStats.weightIndex.toFixed(1)}`)&&
    scatterTooltip.includes(`Tactility Index ${hoverStats.tactilityIndex.toFixed(1)}`)&&
    !/force-wall/i.test(scatterTooltip);

  // The responsive height follows the actual chart width, not the viewport.
  // This covers desktop layouts where the sidebar makes the canvas compact.
  Object.defineProperty(w.HTMLCanvasElement.prototype,"clientWidth",{
    configurable:true,get(){return 700;}
  });
  Object.defineProperty(w.HTMLCanvasElement.prototype,"clientHeight",{
    configurable:true,get(){return 560;}
  });
  w.eval('render();');
  const compactHeightFollowsCanvas=w.document.body.classList.contains("tall-chart")&&
    w.document.body.style.getPropertyValue("--tall-chart-height")==="560px";

  // The phone layout reserves a real plot plus an out-of-plot, three-line
  // legend instead of squeezing both into the old 16:10 canvas.
  paintedText.length=0;
  w.eval('hoverKey=null;drawIndexScatter(ctx,390,592,CANVAS_THEME[theme],theme);');
  const mobileScatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
  const mobileTop=margins.t+95;
  const mobileBottom=592-margins.b-(62+mobileScatterPoints.length*34);
  const mobileLeft=margins.l+8,mobileRight=390-margins.r-8;
  const mobileScatterReadable=mobileBottom-mobileTop>=200&&mobileScatterPoints.length===2&&
    mobileScatterPoints.every(point=>{
      const st=selectedDomeStats.get(point.key);
      const expectedX=mobileLeft+(st.weightIndex/100)*(mobileRight-mobileLeft);
      const expectedY=mobileBottom-(st.tactilityIndex/100)*(mobileBottom-mobileTop);
      return Math.abs(point.x-expectedX)<1e-9&&Math.abs(point.y-expectedY)<1e-9;
    })&&paintedText.includes("Weight vs Tactility Indices")&&
    paintedText.includes("Weight Index (0–100)")&&
    paintedText.includes("Tactility Index (0–100)");
  Object.defineProperty(w.HTMLCanvasElement.prototype,"clientWidth",{
    configurable:true,get(){return 1000;}
  });
  Object.defineProperty(w.HTMLCanvasElement.prototype,"clientHeight",{
    configurable:true,get(){return 625;}
  });
  w.eval('render();');

  // Return to one test and verify every displayed measurement is rendered into
  // the PNG, whether the stats card fits in-chart or is laid out below it.
  await w.eval(`toggleSet(${JSON.stringify(other.set)},${JSON.stringify(other.id)})`);
  paintedText.length=0;
  w.eval('chartMode="curves";render();exportPNG();');
  const singlePngHasAllStats=expectedMetricOrder.every(label=>paintedText.includes(label))&&
    paintedText.includes("Detected force-wall onset");
  const singlePngHasNoDeltaOrScaleNote=!paintedText.some(text=>FORBIDDEN_CONSUMER_TEXT.test(text));

  // Force-wall absence remains a detected-event null and is independent of the
  // two perception indices.
  s.data.stats={...originalStats,travel:null};
  w.eval('chartMode="curves";render();exportPNG();');
  const wallNullLines=w.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const wallNullSafe=wallNullLines.some(row=>row[0]==="Detected force-wall onset"&&row[1]==="Not detected")&&
    wallNullLines.some(row=>row[0]==="Weight Index"&&/\/ 100$/.test(row[1]))&&
    wallNullLines.some(row=>row[0]==="Tactility Index"&&/\/ 100$/.test(row[1]));

  // Missing primary metrics/indices are ordinary unavailable values, never a
  // force-wall-style "Not detected" state and never imputed.
  s.data.stats={...originalStats,Fpeak:null,dropF:null,weightIndex:null,tactilityIndex:null,
    percentiles:{...originalStats.percentiles,cg:null,dg:null}};
  w.eval('render();exportPNG();');
  const primaryNullLines=w.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const primaryNullUnavailable=primaryNullLines.some(row=>row[0]==="Weight Index"&&row[1]==="Not available")&&
    primaryNullLines.some(row=>row[0]==="Tactility Index"&&row[1]==="Not available")&&
    !primaryNullLines.some(row=>/Index$/.test(row[0])&&row[1]==="Not detected");

  // A missing index excludes only that record.  A part assembly is separately
  // reported as not calibrated; neither condition creates a point at zero or
  // borrows a value from any mechanical measurement.
  await w.eval(`toggleSet(${JSON.stringify(other.set)},${JSON.stringify(other.id)})`);
  paintedText.length=0;
  w.eval('chartMode="indexScatter";render();exportPNG();');
  const nullScatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
  const primaryName=w.eval(`selectedName(sets.get(${JSON.stringify(primarySet)}))`);
  const nullScatterExcluded=nullScatterPoints.length===1&&nullScatterPoints[0].key===other.set&&
    paintedText.some(text=>/^Not available:/.test(text)&&text.includes(primaryName));
  const activeSelection=w.eval("selected");
  activeSelection.splice(0,activeSelection.length,...parts.map(row=>row.set));
  for(const row of parts){
    const set=w.eval(`sets.get(${JSON.stringify(row.set)})`);
    set.record_id=row.id;
    set.data={runs:[],avgPress:{x:[],F:[]},avgRet:{x:[],F:[]},
      stats:w.eval("canonStats")(row.set,row.id),snapshot:true};
  }
  paintedText.length=0;
  w.eval('chartMode="indexScatter";render();exportPNG();');
  const partScatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
  const partNames=parts.map(row=>w.eval(`selectedName(sets.get(${JSON.stringify(row.set)}))`));
  const partScatterExcluded=partScatterPoints.length===0&&
    paintedText.some(text=>/^Not calibrated:/.test(text)&&partNames.every(name=>text.includes(name)))&&
    paintedText.some(text=>/not calibrated or available for this selection/i.test(text));

  const releasedWalls=rows.map(row=>row.tv).filter(Number.isFinite);
  const furthestWall=Math.max(4.0,...releasedWalls);
  const expectedAxis=furthestWall<=4.0+1e-9?4.0:Math.ceil(furthestWall*2-1e-9)/2;
  const noRetiredCanvasValues=!paintedText.some(text=>/PRESS WORK|NORM\. DROP|COLLAPSE-TO-VALLEY|^VALLEY$|gf\s*@\s*\d/i.test(text));
  const out={
    reviewBanner:build.mode==="review"&&build.bench_build==="fc-3.4-review.2"&&
      dom.window.document.getElementById("reviewBanner").textContent.includes("complete frozen retest fleet")&&
      dom.window.document.getElementById("reviewBanner").textContent.includes("not deployed"),
    identitiesVisible:dom.window.document.getElementById("identityGrid").textContent.includes(build.data_identity),
    generatedAxis:build.axis_data_floor_mm===4.0&&expectedAxis===4.5&&
      w.eval("XMAX")===4.5&&w.eval("XMAX")===w.eval("generatedAxisMax()")&&
      releasedWalls.every(wall=>wall<=w.eval("XMAX")),
    pinnedFetch:commitPinned,
    canonicalRecord:canonical&&primary.id==="bt_0075",
    perceptionModel:model.version===build.perception_score_version&&model.reference_count===68,
    duplicateDivergenceClosed,
    noWallReferenceMetadata,
    noDeltaOrScaleNoteSource,
    simplePercentileCopy,
    watermarkAbsentFromLiveDom,
    watermarkAbsentFromLiveCanvas,
    exportWatermarkDrawn,
    separateTestLimit:turnaround&&Number.isFinite(turnaround.min)&&Number.isFinite(turnaround.max)&&turnaround.min<=turnaround.max,
    visibleStatOrder,
    lowAssociationStatsRemoved,
    indicesVisible,
    partIndicesNotCalibrated,
    normalWallValueOnly,
    partWallValueOnly,
    readoutHasWallWithoutDelta,
    weightProfile,
    tactilityProfile,
    scatterCoordinates,
    scatterLabelsAndAxes,
    scatterKeepsWallSeparate,
    scatterHoverLinked,
    compactHeightFollowsCanvas,
    mobileScatterReadable,
    nullScatterExcluded,
    partScatterExcluded,
    singlePngHasAllStats,
    singlePngHasNoDeltaOrScaleNote,
    wallNullSafe,
    primaryNullUnavailable,
    noRetiredCanvasValues,
    noForbiddenCanvasText:forbiddenPaintedText.length===0,
    finiteCanvasAndPng:nonFiniteCanvasCalls.length===0&&pngExports>=7,
    noPageErrors:errors.length===0
  };
  if(errors.length)console.error(JSON.stringify({pageErrors:errors}));
  console.log(JSON.stringify(out));
  process.exit(Object.values(out).every(Boolean)?0:1);
})().catch(e=>{console.error(e&&e.stack||e);process.exit(2);});
