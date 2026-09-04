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
const paintedCalls=[];
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
      paintedCalls.push({text:value,x:args[0],y:args[1],font:target.font||"",fillStyle:target.fillStyle||""});
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
  const display2=value=>(Math.round((Number(value)+1e-10)*100)/100).toFixed(2);
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
  const selectedBeforeFilterClear=w.eval("selected.map(key=>[key,sets.get(key).record_id])");
  const sidebarFilterToggle=w.document.querySelector("#sbFilters [data-filters-toggle]");
  const sidebarFilterBody=w.document.getElementById("sb-filter-body");
  const filtersStartCollapsed=sidebarFilterToggle.getAttribute("aria-expanded")==="false"&&sidebarFilterBody.hidden&&
    w.eval("FILTER_STATES.dome_baseline.open")===false;
  const testsToggle=w.document.getElementById("testsMenuToggle"),testsBody=w.document.getElementById("testsMenuBody");
  const testsMenuStartsOpen=testsToggle.getAttribute("aria-expanded")==="true"&&!testsBody.hidden&&
    w.document.getElementById("testsMenuCount").textContent.trim()===`${rows.filter(row=>row.k==="dome_baseline").length} tests`;
  sidebarFilterToggle.click();
  const filtersOpen=sidebarFilterToggle.getAttribute("aria-expanded")==="true"&&!sidebarFilterBody.hidden&&
    sidebarFilterBody.contains(w.document.querySelector("#sbFilters [data-query]"))&&
    sidebarFilterBody.contains(w.document.querySelector("#sbFilters [data-reset]"))&&
    sidebarFilterBody.querySelectorAll("[data-r]").length>0;
  const queryInput=w.document.querySelector("#sbFilters [data-query]");
  queryInput.value="DynaCaps";queryInput.dispatchEvent(new w.Event("input",{bubbles:true}));
  const liveNameCount=w.document.querySelector("#sbFilters [data-count]").textContent.trim()==="3 of 68";
  const collapseForceMin=w.document.querySelector('#sbFilters [data-r="cg"][data-e="0"]');
  collapseForceMin.focus();collapseForceMin.value="999";collapseForceMin.dispatchEvent(new w.Event("input",{bubbles:true}));
  const countUpdatesWithoutRerender=w.document.activeElement===collapseForceMin&&
    w.document.querySelector("#sbFilters [data-count]").textContent.trim()==="0 of 68";
  sidebarFilterToggle.click();sidebarFilterToggle.click();
  const disclosurePreservesValues=w.document.querySelector("#sbFilters [data-query]").value==="DynaCaps"&&
    w.document.querySelector('#sbFilters [data-r="cg"][data-e="0"]').value==="999"&&
    w.eval("FILTER_STATES.dome_baseline.open")===true;
  testsToggle.click();
  const testsMenuCanCollapse=testsToggle.getAttribute("aria-expanded")==="false"&&testsBody.hidden;
  queryInput.value="Topre";queryInput.dispatchEvent(new w.Event("input",{bubbles:true}));
  const activeFilterOpensTests=testsToggle.getAttribute("aria-expanded")==="true"&&!testsBody.hidden&&
    w.eval("FILTER_STATES.dome_baseline.testsOpen")===true;
  const sidebarClearButton=w.document.querySelector("#sbFilters [data-reset]");
  const sidebarClearLabel=sidebarClearButton&&sidebarClearButton.textContent.trim()==="Clear filters"&&
    sidebarClearButton.getAttribute("aria-label")==="Clear name and value filters";
  sidebarClearButton.click();
  const sidebarClearState=w.eval('FILTER_STATES.dome_baseline.q===""&&Object.keys(FILTER_STATES.dome_baseline.R).length===0')&&
    w.document.querySelector("#sbFilters [data-query]").value===""&&
    w.document.querySelector("#sbFilters [data-count]").textContent.trim()===`${rows.filter(row=>row.k==="dome_baseline").length} of ${rows.filter(row=>row.k==="dome_baseline").length}`;
  w.eval('FILTER_STATES.dome_baseline.q="still-no-match";FILTER_STATES.dome_baseline.R={tv:[9,null]};testsKind="dome_baseline";renderFilters();');
  const testsClearButton=w.document.querySelector("#filtPanel [data-reset]");
  testsClearButton.click();
  const testsClearState=w.eval('FILTER_STATES.dome_baseline.q===""&&Object.keys(FILTER_STATES.dome_baseline.R).length===0')&&
    w.document.querySelector("#filtPanel [data-query]").value==="";
  w.eval('showSub("tests")');
  const testsFilterToggle=w.document.querySelector("#filtPanel [data-filters-toggle]");
  if(testsFilterToggle.getAttribute("aria-expanded")==="true")testsFilterToggle.click();
  w.eval('showSub("comp")');
  const syncedSidebarToggle=w.document.querySelector("#sbFilters [data-filters-toggle]");
  const syncedSidebarBody=w.document.getElementById("sb-filter-body");
  const filterDisclosureSync=w.eval("FILTER_STATES.dome_baseline.open")===false&&
    syncedSidebarToggle.getAttribute("aria-expanded")==="false"&&syncedSidebarBody.hidden;
  const selectedAfterFilterClear=w.eval("selected.map(key=>[key,sets.get(key).record_id])");
  const clearFiltersContract=filtersStartCollapsed&&testsMenuStartsOpen&&filtersOpen&&liveNameCount&&
    countUpdatesWithoutRerender&&disclosurePreservesValues&&testsMenuCanCollapse&&activeFilterOpensTests&&
    sidebarClearLabel&&sidebarClearState&&testsClearState&&filterDisclosureSync&&
    JSON.stringify(selectedAfterFilterClear)===JSON.stringify(selectedBeforeFilterClear)&&
    w.document.getElementById("btnCompareClear").textContent.trim()==="Clear selection";
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
  const graphDisplayDefaults=w.eval('GRAPH_DISPLAY.style==="simplified"&&GRAPH_DISPLAY.labels&&GRAPH_DISPLAY.visuals')&&
    w.document.getElementById("graphStyleSimplified").checked&&
    !w.document.getElementById("graphStyleDetailed").checked&&
    w.document.getElementById("graphDisplaySummary").textContent.includes("Simplified")&&
    w.document.getElementById("toggleGraphLabels").checked&&
    w.document.getElementById("toggleGraphVisuals").checked;
  const simplifiedMetricOrder=["Weight Index","Collapse force","Tactility Index","Drop force","Detected force-wall onset"];
  const detailedMetricOrder=[
    "Weight Index","Collapse force","Ramp","Pre-collapse work","Tactility Index",
    "Drop force","Snap %","Steepest drop","Drop rate","Detected force-wall onset"
  ];
  const groupLabels=()=>w.eval(`statGroups(sets.get(${JSON.stringify(primarySet)})).flatMap(group=>[
    ...(group.index?[group.index[0]]:[]),...group.rows.map(row=>row[0])])`);
  const simplifiedGroups=groupLabels();
  const simplifiedStatsAllowlist=JSON.stringify(simplifiedGroups)===JSON.stringify(simplifiedMetricOrder)&&
    !/Ramp|Pre-collapse work|Snap %|Steepest drop|Drop rate|Recorded turnaround range/.test(
      w.document.getElementById("statsOut").textContent);
  const simplifiedForbidden=["RAMP","PRE-COLLAPSE WORK","DROP · SNAP %","SNAP %","STEEPEST DROP","DROP RATE",
    "Ramp","Pre-collapse work","Snap %","Steepest drop","Drop rate","Recorded turnaround range (test limit)"];
  const simplifiedRequired=["WEIGHT INDEX","TACTILITY INDEX","COLLAPSE","DROP","DETECTED FORCE-WALL ONSET"];
  paintedText.length=0;
  paintedCalls.length=0;
  w.eval('render();');
  const simplifiedScreenText=paintedText.slice();
  const simplifiedScreenCalls=paintedCalls.slice();
  const simplifiedFeatures=w.eval("[...new Set(ANNOT_HITS.map(hit=>hit.feature).filter(Boolean))]");
  const simplifiedScreenEnd=paintedText.length;
  w.eval('exportPNG();');
  const simplifiedPngText=paintedText.slice(simplifiedScreenEnd);
  const simplifiedCanvasAllowlist=[simplifiedScreenText,simplifiedPngText].every(texts=>
    simplifiedRequired.every(label=>texts.includes(label))&&
    simplifiedForbidden.every(label=>!texts.includes(label)))&&
    !simplifiedPngText.includes("Collapse force")&&!simplifiedPngText.includes("Drop force")&&
    !simplifiedPngText.includes("Detected force-wall onset")&&
    w.document.getElementById("statsOut").style.display==="none";
  const simplifiedGeometry=w.eval(`(()=>{
    const st=sets.get(${JSON.stringify(primarySet)}).data.stats,w=canvas.clientWidth,h=canvas.clientHeight;
    const plotTop=forceCurveHeaderLayout(w).plotTop,fmax=chartFmax();
    const X=value=>M.l+(value/XMAX)*(w-M.l-M.r);
    const Y=value=>h-M.b-(value/fmax)*(h-plotTop-M.b);
    return {peakX:X(st.xpeak),peakY:Y(st.Fpeak),valleyX:X(st.xval),valleyY:Y(st.Fval)};
  })()`);
  const annotationGroupCenter=(name,value)=>{
    const call=simplifiedScreenCalls.find(item=>item.text===name);
    return call?{x:call.x+(name.length*6+9+value.length*6)/2,y:call.y}:null;
  };
  const collapseValue=`${Math.round(originalStats.Fpeak)} gf`,dropValue=`${Math.round(originalStats.dropF)} gf`;
  const collapseGroup=annotationGroupCenter("COLLAPSE",collapseValue),dropGroup=annotationGroupCenter("DROP",dropValue);
  const simplifiedCenteredDimensions=!!collapseGroup&&!!dropGroup&&
    Math.abs(collapseGroup.x-simplifiedGeometry.peakX)<1e-9&&
    Math.abs(collapseGroup.y-(simplifiedGeometry.peakY-18))<1e-9&&
    Math.abs(dropGroup.x-simplifiedGeometry.valleyX)<1e-9&&
    Math.abs(dropGroup.y-((simplifiedGeometry.peakY+simplifiedGeometry.valleyY)/2+5))<1e-9;
  const simplifiedNoHiddenGeometry=simplifiedFeatures.every(feature=>
    ["weightIndex","tactilityIndex","travel","collapse","drop"].includes(feature))&&
    ["weightIndex","tactilityIndex","travel","collapse","drop"].every(feature=>simplifiedFeatures.includes(feature));
  const simplifiedPartStats=w.eval("canonStats")(part.set,part.id);
  w.__simplifiedPartProbe={key:part.set,record_id:part.id,data:{stats:simplifiedPartStats}};
  const simplifiedPartGroups=w.eval("statGroups(__simplifiedPartProbe)");
  const simplifiedPartLabels=simplifiedPartGroups.flatMap(group=>[
    ...(group.index?[group.index[0]]:[]),...group.rows.map(row=>row[0])]);
  const simplifiedPartAssemblySafe=JSON.stringify(simplifiedPartLabels)===JSON.stringify(simplifiedMetricOrder)&&
    simplifiedPartGroups[0].index[1]==="Not calibrated"&&simplifiedPartGroups[1].index[1]==="Not calibrated"&&
    simplifiedPartGroups[0].rows[0][1]!=="Not available"&&simplifiedPartGroups[1].rows[0][1]!=="Not available";
  delete w.__simplifiedPartProbe;

  const simplifiedRadio=w.document.getElementById("graphStyleSimplified");
  const detailedRadio=w.document.getElementById("graphStyleDetailed");
  detailedRadio.click();
  const detailedGroups=groupLabels();
  const detailedStyleSelected=w.eval('GRAPH_DISPLAY.style==="detailed"&&GRAPH_DISPLAY.labels&&GRAPH_DISPLAY.visuals')&&
    detailedRadio.checked&&!simplifiedRadio.checked&&
    w.document.getElementById("graphDisplaySummary").textContent.includes("Detailed")&&
    detailedMetricOrder.every(label=>detailedGroups.includes(label))&&
    detailedGroups.includes("Recorded turnaround range (test limit)");
  const detailedStatsRestored=w.document.getElementById("statsOut").style.display==="grid"&&
    /Ramp|Pre-collapse work|Snap %|Steepest drop|Drop rate|Recorded turnaround range/.test(
      w.document.getElementById("statsOut").textContent);
  const profileModes=["profileWeight","profileTactility","profileTravel","indexScatter"];
  const knownDetailLabels=new Set(["Weight Index","Collapse force","Ramp","Pre-collapse work",
    "Tactility Index","Drop force","Snap %","Steepest drop","Drop rate",
    "Travel-related measurements","Detected force-wall onset","Recorded turnaround range (test limit)"]);
  const singleProfileMeasurementsRemoved=["simplified","detailed"].every(style=>profileModes.every(mode=>{
    paintedText.length=0;paintedCalls.length=0;
    w.eval(`GRAPH_DISPLAY.style=${JSON.stringify(style)};chartMode=${JSON.stringify(mode)};render();exportPNG();`);
    const pngFooterMeasurements=paintedCalls.filter(call=>call.y>=670&&knownDetailLabels.has(call.text));
    return w.document.getElementById("statsOut").style.display==="none"&&pngFooterMeasurements.length===0;
  }));
  w.eval('GRAPH_DISPLAY.style="detailed";chartMode="curves";render();');
  simplifiedRadio.click();
  const simplifiedRoundTrip=JSON.stringify(groupLabels())===JSON.stringify(simplifiedMetricOrder)&&
    w.eval('GRAPH_DISPLAY.style==="simplified"&&GRAPH_DISPLAY.labels&&GRAPH_DISPLAY.visuals');
  detailedRadio.click();
  const styleToggleRoundTrip=simplifiedRoundTrip&&w.eval('GRAPH_DISPLAY.style==="detailed"&&GRAPH_DISPLAY.labels&&GRAPH_DISPLAY.visuals');
  const annotationLabels=["COLLAPSE","RAMP","PRE-COLLAPSE WORK","DROP · SNAP %","DROP RATE",
    "STEEPEST DROP"];

  // Labels and measurement geometry are independent presentation layers. The
  // graph identity, axes, curve, Details, and PNG provenance remain available.
  paintedText.length=0;
  w.eval('GRAPH_DISPLAY.labels=false;GRAPH_DISPLAY.visuals=true;render();exportPNG();');
  const visualOnlyFeatures=w.eval("[...new Set(ANNOT_HITS.map(hit=>hit.feature).filter(Boolean))]");
  const labelsToggleWorks=annotationLabels.every(label=>!paintedText.includes(label))&&
    paintedText.includes("DETECTED FORCE-WALL ONSET")&&paintedText.includes(`${display2(originalStats.travel)} mm`)&&
    paintedText.includes("Press displacement (mm)")&&paintedText.includes("Force (gf)")&&
    paintedText.includes("Collapse force")&&paintedText.includes("UNREAL KEYBOARDS")&&
    ["collapse","pcw","drop","dropRate","ramp","steep","travel","turnaround"].every(feature=>visualOnlyFeatures.includes(feature));

  paintedText.length=0;
  w.eval('GRAPH_DISPLAY.labels=true;GRAPH_DISPLAY.visuals=false;render();exportPNG();');
  const labelOnlyFeatures=w.eval("[...new Set(ANNOT_HITS.map(hit=>hit.feature).filter(Boolean))]");
  const visualsToggleWorks=annotationLabels.every(label=>paintedText.includes(label))&&
    ["collapse","pcw","drop","dropRate","ramp","steep","travel"].every(feature=>labelOnlyFeatures.includes(feature))&&
    !labelOnlyFeatures.includes("bottom")&&!labelOnlyFeatures.includes("turnaround");
  // Each scene now carries two wall identifiers when graph labels are on: the
  // instrument-header readout and a second label anchored to the wall marker.
  // render() plus exportPNG() therefore paint each string four times here.
  const wallMarkerLabelRestored=paintedText.filter(text=>text==="DETECTED FORCE-WALL ONSET").length>=4&&
    paintedText.filter(text=>text===`${display2(originalStats.travel)} mm`).length>=4;
  const orthogonalDropLeaderLayout=w.eval(`(()=>{
    const l=dropSnapAnnotationLayout(66,976,120,730,302,188,185);
    const compact=dropSnapAnnotationLayout(66,370,160,188,260,178,159);
    return l.side==="left"&&l.labelX+185===702&&l.labelY===258&&
      l.labelX>=66&&l.labelX+185<=976&&compact.side==="right"&&
      compact.labelX>=196&&compact.labelX+159<=370&&compact.labelY>=228&&compact.labelY<=232;
  })()`);
  const cadArrowFitContract=w.eval(`(()=>{
    const tight=verticalDimensionLayout(100,128,true),roomy=verticalDimensionLayout(100,160,true),
      labelOff=verticalDimensionLayout(100,128,false),veryTight=verticalDimensionLayout(100,118,false),
      simpleOutside=verticalDimensionLayout(100,143.99,true),simpleBoundary=verticalDimensionLayout(100,144,true),
      detailOutside=verticalDimensionLayout(100,119.99,false),detailBoundary=verticalDimensionLayout(100,120,false);
    return tight.arrowsOutside&&tight.lineTop===76&&tight.lineBottom===152&&
      tight.topBaseY===88&&tight.bottomBaseY===140&&tight.arrowHalfWidth===4.8&&
      !roomy.arrowsOutside&&roomy.lineTop===100&&roomy.lineBottom===160&&
      roomy.topBaseY===108&&roomy.bottomBaseY===152&&roomy.arrowHalfWidth===3.2&&
      !labelOff.arrowsOutside&&veryTight.arrowsOutside&&simpleOutside.arrowsOutside&&
      !simpleBoundary.arrowsOutside&&detailOutside.arrowsOutside&&!detailBoundary.arrowsOutside;
  })()`);

  paintedText.length=0;
  paintedCalls.length=0;
  w.eval('GRAPH_DISPLAY.labels=false;GRAPH_DISPLAY.visuals=false;render();exportPNG();');
  const cleanFeatures=w.eval("[...new Set(ANNOT_HITS.map(hit=>hit.feature).filter(Boolean))]");
  const headerInstrumentLayout=w.eval(`(()=>{
    const wide=forceCurveHeaderLayout(1000),compact=forceCurveHeaderLayout(390);
    const ordered=layout=>layout.blocks.every((block,index)=>block.width>0&&
      (!index||block.x>=layout.blocks[index-1].x+layout.blocks[index-1].width));
    return !wide.compact&&compact.compact&&ordered(wide)&&ordered(compact)&&
      wide.titleX+wide.titleWidth<wide.blocks[0].x&&wide.labelY<wide.valueY&&wide.titleY===wide.valueY&&
      compact.titleY<compact.labelY&&compact.labelY<compact.valueY&&
      wide.plotTop>=wide.headerBottom+16&&compact.plotTop>=compact.headerBottom+16;
  })()`);
  const headerName=w.eval(`selectedName(sets.get(${JSON.stringify(primarySet)}))`);
  const firstCall=text=>paintedCalls.find(call=>call.text===text);
  const titleCall=firstCall(headerName),weightLabelCall=firstCall("WEIGHT INDEX"),weightValueCall=firstCall("40.3"),
    tactilityLabelCall=firstCall("TACTILITY INDEX"),tactilityValueCall=firstCall("11.9"),
    wallLabelCall=firstCall("DETECTED FORCE-WALL ONSET"),wallValueCall=firstCall(`${display2(originalStats.travel)} mm`);
  const fontPx=call=>{const match=call&&call.font.match(/([\d.]+)px/);return match?+match[1]:0;};
  const headerVisualHierarchy=[titleCall,weightLabelCall,weightValueCall,tactilityLabelCall,tactilityValueCall,wallLabelCall,wallValueCall].every(Boolean)&&
    titleCall.y===weightValueCall.y&&titleCall.y===tactilityValueCall.y&&titleCall.y===wallValueCall.y&&
    weightLabelCall.y<weightValueCall.y&&tactilityLabelCall.y<tactilityValueCall.y&&wallLabelCall.y<wallValueCall.y&&
    fontPx(weightValueCall)>fontPx(weightLabelCall)&&fontPx(tactilityValueCall)>fontPx(tactilityLabelCall)&&
    fontPx(wallValueCall)>fontPx(wallLabelCall)&&weightLabelCall.x>titleCall.x+titleCall.text.length*6&&
    weightLabelCall.x<tactilityLabelCall.x&&tactilityLabelCall.x<wallLabelCall.x&&
    [weightLabelCall,tactilityLabelCall,wallLabelCall].every(call=>call.x>=0&&call.x<1000)&&
    new Set([weightLabelCall.fillStyle,tactilityLabelCall.fillStyle,wallLabelCall.fillStyle]).size===3;
  const cleanGraphKeepsIdentity=annotationLabels.every(label=>!paintedText.includes(label))&&
    cleanFeatures.every(feature=>["weightIndex","tactilityIndex","travel"].includes(feature))&&
    paintedText.includes("WEIGHT INDEX")&&paintedText.includes("40.3")&&
    paintedText.includes("TACTILITY INDEX")&&paintedText.includes("11.9")&&
    paintedText.includes("DETECTED FORCE-WALL ONSET")&&paintedText.includes(`${display2(originalStats.travel)} mm`)&&
    paintedText.includes("Press displacement (mm)")&&paintedText.includes("Collapse force")&&
    paintedText.includes("UNREAL KEYBOARDS");
  w.eval('GRAPH_DISPLAY.labels=true;GRAPH_DISPLAY.visuals=true;render();');
  const normalLines=w.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const visibleStatOrder=JSON.stringify(normalLines.slice(0,detailedMetricOrder.length).map(row=>row[0]))===
    JSON.stringify(detailedMetricOrder);
  const retiredLabels=["Press work to force-wall","Norm. drop rate","Collapse-to-valley distance",
    "Collapse point","Valley"];
  const lowAssociationStatsRemoved=!normalLines.some(row=>retiredLabels.includes(row[0]));
  const indicesVisible=normalLines.some(row=>row[0]==="Weight Index"&&/^\d+\.\dth percentile$/.test(row[1]))&&
    normalLines.some(row=>row[0]==="Tactility Index"&&/^\d+\.\dth percentile$/.test(row[1]));
  const semanticColorContract=w.eval(`(()=>{
    const expected={weight:["weightIndex","collapse","ramp","pcw"],
      tactility:["tactilityIndex","bottom","drop","dropRate","steep"],
      separate:["travel","turnaround","travelGroup"]};
    return ["dark","light"].every(th=>{
      const F=FEAT[th];
      return F.weight!==F.tactility&&F.travel!==F.weight&&F.travel!==F.tactility&&
        ![F.weight,F.tactility,F.travel,F.inactive].includes(F.curve)&&
        expected.weight.every(id=>FEATURE_FAMILY[id]==="weight"&&featureColor(F,id,CANVAS_THEME[th])===F.weight)&&
        expected.tactility.every(id=>FEATURE_FAMILY[id]==="tactility"&&featureColor(F,id,CANVAS_THEME[th])===F.tactility)&&
        expected.separate.every(id=>FEATURE_FAMILY[id]==="separate"&&featureColor(F,id,CANVAS_THEME[th])===F.travel);
    });
  })()`);
  const featureFocusContract=w.eval(`(()=>{
    try{
      setFeatureFocus("weightIndex");
      const weightActive=["weightIndex","collapse","ramp","pcw"].every(id=>featureFocusState(id)==="active")&&
        ["tactilityIndex","bottom","drop","dropRate","steep","travel"].every(id=>featureFocusState(id)==="muted")&&
        featureFillAlpha("pcw")>0&&featureFillAlpha("pcw")<=.1;
      const weightDom=[...document.querySelectorAll('#statsOut [data-family="weight"] [data-feature]')].every(node=>node.dataset.focusState==="active")&&
        [...document.querySelectorAll('#statsOut [data-family="tactility"] [data-feature]')].every(node=>node.dataset.focusState==="muted");
      setFeatureFocus("tactilityIndex");
      const tactilityActive=["tactilityIndex","bottom","drop","dropRate","steep"].every(id=>featureFocusState(id)==="active")&&
        ["weightIndex","collapse","ramp","pcw","travel"].every(id=>featureFocusState(id)==="muted");
      setFeatureFocus("ramp");
      const metricOnly=featureFocusState("ramp")==="active"&&["weightIndex","collapse","pcw","drop"].every(id=>featureFocusState(id)==="muted");
      setFeatureFocus("collapse");
      const collapseOwnsOnlyPeak=featureFocusState("collapse")==="active"&&featureFocusState("pcw")==="muted";
      setFeatureFocus("pcw");
      const pcwOwnsGuide=featureFocusState("pcw")==="active"&&featureFocusState("collapse")==="muted";
      setFeatureFocus("travel");
      const travelFamilyActive=["travel","turnaround","travelGroup"].every(id=>featureFocusState(id)==="active")&&
        ["weightIndex","tactilityIndex","collapse","drop"].every(id=>featureFocusState(id)==="muted")&&
        [...document.querySelectorAll('#statsOut [data-family="separate"] [data-feature]')].every(node=>node.dataset.focusState==="active");
      const strokeHierarchy=CURVE_STROKE_WIDTH>featureWidth("ramp",METRIC_STROKE_WIDTH)&&
        CONSTRUCTION_DASH.join(",")==="5,4";
      setFeatureFocus(null);
      const cleared=["weightIndex","collapse","ramp","pcw","tactilityIndex","drop","travel","turnaround","travelGroup"].every(id=>featureFocusState(id)==="normal");
      return weightActive&&weightDom&&tactilityActive&&metricOnly&&collapseOwnsOnlyPeak&&pcwOwnsGuide&&travelFamilyActive&&strokeHierarchy&&cleared;
    }finally{setFeatureFocus(null);}
  })()`);
  const detailFamilies=[...w.document.querySelectorAll("#statsOut [data-feature]")].every(node=>{
    const expected=w.eval(`FEATURE_FAMILY[${JSON.stringify(node.dataset.feature)}]`);
    return node.closest("[data-family]")&&node.closest("[data-family]").dataset.family===expected;
  })&&["weight","tactility","separate"].every(family=>
    w.document.querySelector(`#statsOut .so-group[data-family="${family}"]`));
  const normalWallValueOnly=normalLines.some(row=>row[0]==="Detected force-wall onset"&&
    row[1]===`${display2(originalStats.travel)} mm`);

  const partStats=w.eval("canonStats")(part.set,part.id);
  w.__partProbe={key:part.set,record_id:part.id,data:{stats:partStats}};
  const partLines=w.eval("statLines(__partProbe)");
  const partIndicesNotCalibrated=partLines.some(row=>row[0]==="Weight Index"&&row[1]==="Not calibrated")&&
    partLines.some(row=>row[0]==="Tactility Index"&&row[1]==="Not calibrated");
  const partWallValueOnly=partLines.some(row=>row[0]==="Detected force-wall onset"&&row[1]===
    (Number.isFinite(partStats.travel)?`${display2(partStats.travel)} mm`:"Not detected"));

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
  const readoutHasWallWithoutDelta=expandedReadout.includes("DETECTED FORCE-WALL ONSET (MM)")&&
    !FORBIDDEN_CONSUMER_TEXT.test(expandedReadout);
  w.eval('chartMode="profileWeight";render();exportPNG();');
  const weightPoints=w.eval("PROFILE_PTS.map(point=>({...point}))");
  w.eval('chartMode="profileTactility";render();exportPNG();');
  const tactilityPoints=w.eval("PROFILE_PTS.map(point=>({...point}))");
  const finitePoint=point=>Number.isFinite(point.x)&&Number.isFinite(point.y)&&
    !/NaN|Infinity/.test(point.tip);
  const weightProfile=weightPoints.length===6&&weightPoints.every(finitePoint);
  const tactilityProfile=tactilityPoints.length===8&&tactilityPoints.every(finitePoint)&&
    w.eval('PROFILES.profileTactility.metrics.map(metric=>metric.p).join(",")')==="dg,sn,sd,dr";

  // The travel comparison has a shareable all-domes state. Every detected
  // value keeps its exact horizontal position inside a fixed brand/version
  // row. Group summaries use one aggregate per dome dataset and a frozen
  // nine-dataset Topre production reference.
  w.eval("clearSelectionAll();");
  w.history.replaceState(null,"","/?mode=profileTravel");
  await w.eval("applySelParam()");
  await delay(0);
  const bareTravelKeys=w.eval("allDomeKeys().slice()");
  const bareTravelSelection=w.eval("selected.slice()");
  const bareTravelAutoLoads=w.eval('chartMode')==="profileTravel"&&
    bareTravelSelection.length===bareTravelKeys.length&&bareTravelKeys.every(key=>bareTravelSelection.includes(key))&&
    new URL(w.location.href).searchParams.get("sel")==="all-domes";
  const travelModeControls=w.document.body.classList.contains("comparison-chart")&&
    w.document.getElementById("compareActions").classList.contains("on")&&
    w.document.getElementById("graphDisplayMenu").classList.contains("disabled");
  w.eval("clearSelectionAll();");
  w.history.replaceState(null,"","/?mode=profileTravel&sel=all-domes");
  await w.eval("applySelParam()");
  await delay(0);
  const allDomeKeys=w.eval("allDomeKeys().slice()");
  const travelSelection=w.eval("selected.slice()");
  const travelParams=new URL(w.location.href).searchParams;
  const travelDeepLink=w.eval('chartMode')==="profileTravel"&&
    travelParams.get("mode")==="profileTravel"&&travelParams.get("sel")==="all-domes"&&
    travelSelection.length===allDomeKeys.length&&allDomeKeys.every(key=>travelSelection.includes(key))&&
    w.document.querySelector('[data-m="profileTravel"]').getAttribute("aria-pressed")==="true";
  const margins=w.eval("({...M})");
  const travelStats=new Map(w.eval("displayList().map(s=>[s.key,{travel:s.data.stats.travel,recordId:s.record_id}])"));
  let travelPoints=w.eval("TRAVEL_PTS.map(point=>({...point}))");
  const travelTestPoints=travelPoints.filter(point=>point.kind==="test");
  const travelGroupPoints=travelPoints.filter(point=>point.kind==="group");
  const travelGroups=w.eval("travelComparisonGroups(displayList()).map(group=>({id:group.id,label:group.label,count:group.members.length,detected:group.detected.length,mean:group.mean,min:group.min,max:group.max}))");
  const reference=w.eval("travelReferenceStats()");
  const referenceSets=w.eval("[...TOPRE_TRAVEL_REFERENCE_SETS]");
  const expectedReferenceSets=["Topre_HHKB_Pro2_45g","Topre_R1_30g","Topre_R1_45g","Topre_R1_55g",
    "Topre_R2_30g","Topre_R2_45g","Topre_R2_55g","Topre_RGB_45g","Topre_GX1_45g"];
  const expectedGroupCounts={"topre-production":9,"sony-bke":5,"dynacaps":3,"deskeys-v1":4,"deskeys-v2":6,
    "deskeys-v3":7,"deskeys-t1":9,"deskeys-carrot":3,"bke-redux-v1":10,"astro-domes":7,"klc-densus":3,"niz":2};
  const travelGrouping=JSON.stringify(referenceSets)===JSON.stringify(expectedReferenceSets)&&
    reference.memberCount===9&&reference.detectedCount===9&&Math.abs(reference.mean-3.940277777777778)<1e-12&&
    travelGroups.length===12&&travelGroups.reduce((sum,group)=>sum+group.count,0)===68&&
    travelGroups.every(group=>expectedGroupCounts[group.id]===group.count&&group.detected===group.count)&&
    !travelGroups.some(group=>group.id==="other-review")&&travelGroupPoints.length===travelGroups.length;
  const travelGeometry=w.eval(`travelPlotGeometry(1000,625,${travelGroups.length},false)`);
  const exactTravelPositions=travelTestPoints.length===travelStats.size&&travelTestPoints.every(point=>{
    const st=travelStats.get(point.key);
    if(!st||!Number.isFinite(st.travel)||point.recordId!==st.recordId)return false;
    const expectedX=travelGeometry.left+(st.travel/w.eval("XMAX"))*(travelGeometry.right-travelGeometry.left);
    return finitePoint(point)&&Math.abs(point.x-expectedX)<1e-9&&
      point.group&&point.tip.includes(`${point.group} · ${display2(st.travel)} mm ·`);
  });
  const minimumPointDistance=points=>{
    let distance=Infinity;
    for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++)
      if(points[i].group===points[j].group)
        distance=Math.min(distance,Math.hypot(points[i].x-points[j].x,points[i].y-points[j].y));
    return distance;
  };
  const minimumMarkerClearance=points=>{
    let clearance=Infinity;
    for(let i=0;i<points.length;i++)for(let j=i+1;j<points.length;j++)
      if(points[i].group===points[j].group)
        clearance=Math.min(clearance,Math.hypot(points[i].x-points[j].x,points[i].y-points[j].y)-
          (points[i].radius||0)-(points[j].radius||0)-
          ((points[i].strokeWidth||0)+(points[j].strokeWidth||0))/2);
    return clearance;
  };
  const wideTravelMarkerMin=minimumPointDistance(travelTestPoints);
  const wideTravelMarkerClearance=minimumMarkerClearance(travelTestPoints);
  const wideTravelMarkersSeparated=wideTravelMarkerClearance>=.25;
  const travelTableText=w.document.getElementById("readout").textContent;
  const travelTableContract=travelTableText.includes("BRAND / VERSION")&&
    travelTableText.includes("DIFFERENCE FROM TOPRE REFERENCE")&&
    travelTableText.includes("DETECTED FORCE-WALL ONSET (MM)")&&
    !travelTableText.includes("RECORDED TURNAROUND RANGE (TEST LIMIT)");
  const travelHoverPoint=travelTestPoints[Math.floor(travelTestPoints.length/2)];
  const travelCanvas=w.document.getElementById("chart");
  const travelPointer=new w.MouseEvent("pointermove",{
    clientX:travelHoverPoint.x,clientY:travelHoverPoint.y,bubbles:true
  });
  Object.defineProperty(travelPointer,"pointerType",{value:"mouse"});
  travelCanvas.dispatchEvent(travelPointer);
  await delay(0);
  const travelTooltip=w.document.getElementById("tooltip").textContent;
  const travelHoverLinked=w.eval("hoverKey")===travelHoverPoint.key&&
    !!w.document.querySelector(`#readout tr[data-key="${travelHoverPoint.key}"]`)?.classList.contains("hl")&&
    travelTooltip.includes(travelHoverPoint.name)&&travelTooltip.includes(travelHoverPoint.tip);
  w.eval("clearHover()");
  paintedText.length=0;
  const travelPngCount=pngExports;
  w.eval("exportPNG()");
  travelPoints=w.eval("TRAVEL_PTS.map(point=>({...point}))");
  const travelPng=pngExports===travelPngCount+1&&travelPoints.filter(point=>point.kind==="test").length===travelStats.size&&
    paintedText.includes("Detected Force-Wall Onset by Dome Family")&&
    paintedText.includes("Detected force-wall onset (mm)")&&
    paintedText.some(text=>text.includes("not nominal/physical switch travel"))&&
    paintedText.some(text=>text.includes("not a better/worse score"))&&
    paintedText.some(text=>text.startsWith("TOPRE PRODUCTION REFERENCE · 3.94 MM · 9 TESTS"))&&
    ["Topre production","DynaCaps","Astro Domes","Deskeys V1","Deskeys T1"].every(text=>paintedText.includes(text))&&
    !paintedText.includes("RECORDED TURNAROUND RANGE")&&
    paintedText.includes("UNREAL KEYBOARDS");
  const travelPngPainted=paintedText.slice();

  w.eval("clearSelectionAll()");
  await w.eval(`toggleSet(${JSON.stringify(primarySet)},${JSON.stringify(primary.id)})`);
  paintedText.length=0;
  w.eval('chartMode="profileTravel";render()');
  const partialToprePoints=w.eval("TRAVEL_PTS.map(point=>({...point}))");
  const partialTopreNotReference=partialToprePoints.some(point=>point.kind==="group"&&
      point.group===undefined&&point.name==="Topre production"&&
      /same at displayed precision|mm (earlier|later)/.test(point.tip))&&
    !paintedText.some(text=>/^\d+\.\d{2} mm · reference$/.test(text));
  const nearReference=rows.find(row=>row.set==="Topre_RGB_45g"&&row.k==="dome_baseline");
  w.eval("clearSelectionAll()");
  await w.eval(`toggleSet(${JSON.stringify(nearReference.set)},${JSON.stringify(nearReference.id)})`);
  paintedText.length=0;
  w.eval('drawTravelComparison(ctx,390,592,CANVAS_THEME[theme],theme)');
  const compactPartialTopreSame=paintedText.includes(`${display2(nearReference.tv)} · ≈REF`)&&
    !paintedText.some(text=>/[−-]0\.00/.test(text));
  w.eval("loadAllComparisonDomes();chartMode='profileTravel';render()");

  const nullTravelKeys=w.eval('displayList().filter(s=>travelGroupForRecord(travelRecord(s)).id==="topre-production").slice(0,2).map(s=>s.key)');
  const savedTravels=new Map(nullTravelKeys.map(key=>[key,w.eval(`sets.get(${JSON.stringify(key)}).data.stats.travel`)]));
  nullTravelKeys.forEach(key=>w.eval(`sets.get(${JSON.stringify(key)}).data.stats.travel=null`));
  paintedText.length=0;
  w.eval("render();exportPNG()");
  const nullTravelPoints=w.eval("TRAVEL_PTS.map(point=>({...point}))");
  const nullTravelPoint=nullTravelPoints.find(point=>point.kind==="test"&&point.key===nullTravelKeys[0]);
  const nullRailPoints=nullTravelPoints.filter(point=>point.kind==="test"&&nullTravelKeys.includes(point.key));
  const nullGroups=w.eval("travelComparisonGroups(displayList()).length");
  const nullGeometry=w.eval(`travelPlotGeometry(1000,625,${nullGroups},true)`);
  const nullTravelRail=!!nullTravelPoint&&nullTravelPoint.tip.includes("Detected force-wall onset not detected")&&
    Math.abs(nullTravelPoint.x-nullGeometry.ndX)<1e-9&&
    nullGeometry.valueX-nullGeometry.ndX>=10&&nullRailPoints.length===2&&
    minimumMarkerClearance(nullRailPoints)>=.25&&
    paintedText.includes("ND")&&
    nullTravelPoints.filter(point=>point.kind==="test"&&!nullTravelKeys.includes(point.key)).every(point=>{
      const st=travelStats.get(point.key);
      const expectedX=nullGeometry.left+(st.travel/w.eval("XMAX"))*(nullGeometry.right-nullGeometry.left);
      return Math.abs(point.x-expectedX)<1e-9;
    });
  for(const [key,value] of savedTravels)
    w.eval(`sets.get(${JSON.stringify(key)}).data.stats.travel=${JSON.stringify(value)}`);

  paintedText.length=0;
  w.eval('drawTravelComparison(ctx,390,592,CANVAS_THEME[theme],theme)');
  const compactTravelPoints=w.eval("TRAVEL_PTS.map(point=>({...point}))");
  const compactGeometry=w.eval(`travelPlotGeometry(390,592,${travelGroups.length},false)`);
  const compactTravelMarkerMin=minimumPointDistance(compactTravelPoints.filter(point=>point.kind==="test"));
  const compactTravelMarkerClearance=minimumMarkerClearance(compactTravelPoints.filter(point=>point.kind==="test"));
  const compactTravelReadable=compactTravelPoints.filter(point=>point.kind==="test").length===travelStats.size&&
    compactTravelPoints.every(point=>finitePoint(point)&&point.y>=compactGeometry.top&&point.y<=compactGeometry.bottom)&&
    compactTravelMarkerClearance>=.25&&
    paintedText.includes("Force-Wall Onset")&&paintedText.includes("Topre production")&&
    paintedText.includes("Proxy—not physical travel; not better/worse.")&&
    paintedText.includes("Domes: 0.00 mm precomp.; no advertised check.");

  // Restore the two-record comparison used by the remaining profile/scatter
  // checks without triggering mutable network data.
  w.eval("clearSelectionAll()");
  await w.eval(`toggleSet(${JSON.stringify(primarySet)},${JSON.stringify(primary.id)})`);
  await w.eval(`toggleSet(${JSON.stringify(other.set)},${JSON.stringify(other.id)})`);
  w.eval('chartMode="indexScatter";syncSelParam();render();');

  // The new index comparison is a true two-dimensional 0–100 plot: Weight
  // Index is x and Tactility Index is y.  Every calibrated selected
  // dome contributes exactly one point, with no aggregation or substitution.
  paintedText.length=0;
  w.eval('chartMode="indexScatter";render();exportPNG();');
  const scatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
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

  // Every comparison mode uses the same fixed chart height, independent of
  // how many tests are selected or how wide the chart becomes.
  Object.defineProperty(w.HTMLCanvasElement.prototype,"clientWidth",{
    configurable:true,get(){return 700;}
  });
  Object.defineProperty(w.HTMLCanvasElement.prototype,"clientHeight",{
    configurable:true,get(){return 560;}
  });
  w.eval('render();');
  const fixedComparisonHeight=w.document.body.classList.contains("comparison-chart")&&
    !w.document.body.classList.contains("tall-chart")&&
    w.document.body.style.getPropertyValue("--tall-chart-height")==="";

  // The phone layout reserves a real plot plus an out-of-plot, three-line
  // legend instead of squeezing both into the old 16:10 canvas.
  paintedText.length=0;
  w.eval('hoverKey=null;drawIndexScatter(ctx,390,592,CANVAS_THEME[theme],theme);');
  const mobileScatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
  const mobileTop=margins.t+95;
  const mobileBottom=592-margins.b-190;
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
  const singlePngHasAllStats=detailedMetricOrder.every(label=>paintedText.includes(label))&&
    paintedText.includes("Detected force-wall onset")&&paintedText.includes("Travel-related measurements");
  const singlePngHasNoDeltaOrScaleNote=!paintedText.some(text=>FORBIDDEN_CONSUMER_TEXT.test(text));

  // Drop force is independent of Snap %. Simplified must retain its dimension
  // and label when Snap is unavailable while keeping the duplicate strip out.
  s.data.stats={...originalStats,snap:null};
  paintedText.length=0;
  w.eval('GRAPH_DISPLAY.style="simplified";chartMode="curves";render();exportPNG();');
  const snapNullGroups=groupLabels();
  const snapNullDropRetained=paintedText.includes("DROP")&&!paintedText.includes("DROP · SNAP %")&&
    !paintedText.includes("Drop force")&&!paintedText.includes("Snap %")&&
    snapNullGroups.includes("Drop force")&&!snapNullGroups.includes("Snap %")&&
    w.eval("ANNOT_HITS.some(hit=>hit.feature==='drop')")&&
    w.document.getElementById("statsOut").style.display==="none";

  // Force-wall absence remains a detected-event null and is independent of the
  // two perception indices.
  s.data.stats={...originalStats,travel:null};
  paintedText.length=0;
  w.eval('chartMode="curves";render();exportPNG();');
  const wallNullLines=w.eval(`statLines(sets.get(${JSON.stringify(primarySet)}))`);
  const wallNullGroups=w.eval(`statGroups(sets.get(${JSON.stringify(primarySet)}))`);
  const wallNullSafe=wallNullLines.some(row=>row[0]==="Detected force-wall onset"&&row[1]==="Not detected")&&
    wallNullLines.some(row=>row[0]==="Weight Index"&&/^\d+\.\dth percentile$/.test(row[1]))&&
    wallNullLines.some(row=>row[0]==="Tactility Index"&&/^\d+\.\dth percentile$/.test(row[1]))&&
    paintedText.includes("DETECTED FORCE-WALL ONSET")&&paintedText.includes("Not detected");
  const simplifiedNullWallSafe=JSON.stringify(wallNullGroups.flatMap(group=>[
      ...(group.index?[group.index[0]]:[]),...group.rows.map(row=>row[0])]))===JSON.stringify(simplifiedMetricOrder)&&
    wallNullGroups[2].rows[0][1]==="Not detected"&&
    !paintedText.includes("Recorded turnaround range (test limit)");

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
  w.eval('chartMode="profileTravel";renderReadout();');
  const partTravelReadoutText=w.document.getElementById("readout").textContent;
  const partTravelReadout=partTravelReadoutText.includes("DETECTED FORCE-WALL ONSET (MM)")&&
    partTravelReadoutText.includes("PRECOMPRESSION (MM)")&&
    !partTravelReadoutText.includes("RECORDED TURNAROUND RANGE (TEST LIMIT)")&&
    !partTravelReadoutText.includes("DIFFERENCE FROM TOPRE REFERENCE");
  paintedText.length=0;
  w.eval('chartMode="profileTravel";render();exportPNG();');
  const partTravelCanvas=paintedText.includes("Detected Force-Wall Onset by Assembly Group")&&
    paintedText.some(text=>text.includes("Part assemblies retain recorded precompression"))&&
    paintedText.some(text=>text.includes("Topre dome reference is context only"));
  paintedText.length=0;
  w.eval('chartMode="indexScatter";render();exportPNG();');
  const partScatterPoints=w.eval("SCATTER_PTS.map(point=>({...point}))");
  const partNames=parts.map(row=>w.eval(`selectedName(sets.get(${JSON.stringify(row.set)}))`));
  const partScatterExcluded=partScatterPoints.length===0&&
    paintedText.some(text=>/^Not calibrated:/.test(text)&&partNames.every(name=>text.includes(name)))&&
    paintedText.some(text=>/not calibrated or available for this selection/i.test(text));

  w.eval('showSub("parts");clearSelectionAll();chartMode="curves";render()');
  w.document.querySelector('#modeToggle [data-m="profileTravel"]').click();
  const everyPartKey=w.eval("allPartKeys().slice()");
  const modeLoadedParts=w.eval("selected.slice()");
  const partModeAutoLoads=modeLoadedParts.length===everyPartKey.length&&
    everyPartKey.every(key=>modeLoadedParts.includes(key))&&w.eval('benchKind')==="part_assembly"&&
    w.document.getElementById("subParts").classList.contains("on")&&
    w.document.getElementById("btnCompareAll").textContent.trim()==="Load all parts";
  w.eval("clearSelectionAll()");
  w.document.getElementById("btnCompareAll").click();
  const buttonLoadedParts=w.eval("selected.slice()");
  const partLoadAllButton=buttonLoadedParts.length===everyPartKey.length&&
    everyPartKey.every(key=>buttonLoadedParts.includes(key))&&w.eval('benchKind')==="part_assembly"&&
    !buttonLoadedParts.some(key=>w.eval(`kindOf(${JSON.stringify(key)},sets.get(${JSON.stringify(key)}).record_id)`)!=="part_assembly");
  const partsComparisonLoad=partModeAutoLoads&&partLoadAllButton&&
    new URL(w.location.href).searchParams.get("sel")==="all-parts";

  const releasedWalls=rows.map(row=>row.tv).filter(Number.isFinite);
  const furthestWall=Math.max(4.0,...releasedWalls);
  const expectedAxis=furthestWall<=4.0+1e-9?4.0:Math.ceil(furthestWall*2-1e-9)/2;
  const noRetiredCanvasValues=!paintedText.some(text=>/PRESS WORK|NORM\. DROP|COLLAPSE-TO-VALLEY|^VALLEY$|gf\s*@\s*\d/i.test(text));
  const out={
    reviewBanner:build.mode==="review"&&build.bench_build==="fc-3.5-review.1"&&
      dom.window.document.getElementById("reviewBanner").textContent.includes("complete frozen retest fleet")&&
      dom.window.document.getElementById("reviewBanner").textContent.includes("not deployed"),
    identitiesVisible:dom.window.document.getElementById("identityGrid").textContent.includes(build.data_identity),
    generatedAxis:build.axis_data_floor_mm===4.0&&expectedAxis===4.5&&
      w.eval("XMAX")===4.5&&w.eval("XMAX")===w.eval("generatedAxisMax()")&&
      releasedWalls.every(wall=>wall<=w.eval("XMAX")),
    pinnedFetch:commitPinned,
    canonicalRecord:canonical&&primary.id==="bt_0075",
    clearFiltersContract,
    perceptionModel:model.version===build.perception_score_version&&model.reference_count===68,
    duplicateDivergenceClosed,
    noWallReferenceMetadata,
    noDeltaOrScaleNoteSource,
    simplePercentileCopy,
    watermarkAbsentFromLiveDom,
    watermarkAbsentFromLiveCanvas,
    exportWatermarkDrawn,
    graphDisplayDefaults,
    simplifiedStatsAllowlist,
    simplifiedCanvasAllowlist,
    simplifiedCenteredDimensions,
    simplifiedNoHiddenGeometry,
    simplifiedPartAssemblySafe,
    detailedStyleSelected,
    detailedStatsRestored,
    singleProfileMeasurementsRemoved,
    styleToggleRoundTrip,
    headerInstrumentLayout,
    headerVisualHierarchy,
    labelsToggleWorks,
    visualsToggleWorks,
    wallMarkerLabelRestored,
    orthogonalDropLeaderLayout,
    cadArrowFitContract,
    cleanGraphKeepsIdentity,
    separateTestLimit:turnaround&&Number.isFinite(turnaround.min)&&Number.isFinite(turnaround.max)&&turnaround.min<=turnaround.max,
    visibleStatOrder,
    semanticColorContract,
    featureFocusContract,
    detailFamilies,
    lowAssociationStatsRemoved,
    indicesVisible,
    partIndicesNotCalibrated,
    normalWallValueOnly,
    partWallValueOnly,
    readoutHasWallWithoutDelta,
    weightProfile,
    tactilityProfile,
    travelDeepLink,
    bareTravelAutoLoads,
    travelModeControls,
    travelGrouping,
    exactTravelPositions,
    wideTravelMarkersSeparated,
    travelTableContract,
    travelHoverLinked,
    travelPng,
    partialTopreNotReference,
    compactPartialTopreSame,
    nullTravelRail,
    compactTravelReadable,
    scatterCoordinates,
    scatterLabelsAndAxes,
    scatterKeepsWallSeparate,
    scatterHoverLinked,
    fixedComparisonHeight,
    mobileScatterReadable,
    nullScatterExcluded,
    partScatterExcluded,
    partTravelReadout,
    partTravelCanvas,
    partsComparisonLoad,
    singlePngHasAllStats,
    singlePngHasNoDeltaOrScaleNote,
    snapNullDropRetained,
    wallNullSafe,
    simplifiedNullWallSafe,
    primaryNullUnavailable,
    noRetiredCanvasValues,
    noForbiddenCanvasText:forbiddenPaintedText.length===0,
    finiteCanvasAndPng:nonFiniteCanvasCalls.length===0&&pngExports>=7,
    noPageErrors:errors.length===0
  };
  if(errors.length)console.error(JSON.stringify({pageErrors:errors}));
  if(!wideTravelMarkersSeparated||!travelPng||!nullTravelRail||!compactTravelReadable)
    console.error(JSON.stringify({wideTravelMarkerMin,compactTravelMarkerMin,wideTravelMarkerClearance,compactTravelMarkerClearance,
      travelPngPainted}));
  console.log(JSON.stringify(out));
  process.exit(Object.values(out).every(Boolean)?0:1);
})().catch(e=>{console.error(e&&e.stack||e);process.exit(2);});
