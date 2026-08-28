// Offline viewer battery: network fully rejected -> select one stable canonical
// record without special reference metadata -> the offline fallback must render
// its chart/readout from EMBEDDED (press+return) with generated canonical scalars.
const {JSDOM}=require('jsdom');const fs=require('fs');
const [viewer]=process.argv.slice(2);
if(!viewer){console.error('usage: viewer_offline_battery.js <viewer.html>');process.exit(2);}
const viewerSource=fs.readFileSync(viewer,'utf8');
const forbiddenConsumerText=/80 is not twice 40|index scale note|wall delta|vs\s+Topre/i;
let paints=0;
const pageErrors=[];
const STAT_KEYS=['Fpeak','xpeak','Fval','xval','travel','E','Epc','snap','dropF','dropX','dropRate','ndr','steep','ramp'];
function sameNullable(a,b){
 if(a==null||b==null)return a===b;
 return Number.isFinite(a)&&Number.isFinite(b)&&Math.abs(a-b)<1e-9;
}
function sameStats(actual,expected){
 return !!(actual&&expected)&&STAT_KEYS.every(k=>sameNullable(actual[k],expected[k]));
}
const dom=new JSDOM(viewerSource,{runScripts:'dangerously',url:'https://x.test/',
 beforeParse(w){w.requestAnimationFrame=cb=>setTimeout(cb,16);w.cancelAnimationFrame=clearTimeout;
  w.fetch=()=>Promise.reject(new Error('offline'));
  w.addEventListener('error',e=>pageErrors.push(String((e.error&&e.error.message)||e.message)));
  w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:(t,k)=>{
    if(k==='canvas')return {width:900,height:500};
    return (...a)=>{paints++;return {width:10};};},set:()=>true});}});
setTimeout(()=>{const w=dom.window;
 const build=w.eval('VIEWER_BUILD');
 const rows=w.eval('VTESTS');
 const primary=rows.find(t=>t.set==='Topre_R1_45g'&&t.id==='bt_0075'&&t.k==='dome_baseline');
 if(!primary){console.error('stable canonical test record missing');process.exit(2);}
 const setKey=primary.set;
 const testId=primary.id;
 const s=w.eval(`sets.get(${JSON.stringify(setKey)})`);
 if(!s||!s.btn){console.error('set button missing for',setKey);process.exit(2);}
 s.btn.click();
 setTimeout(()=>{
   const d=w.eval(`sets.get(${JSON.stringify(setKey)}).data`);
   const matches=rows.filter(t=>t.set===setKey&&t.id===testId);
   const canonical=w.eval('canonStats')(setKey,testId);
   // One selected record uses the compact measurement card. Exercise the
   // comparison table's explicit "More columns" path for full identity.
   const other=w.eval('VTESTS').find(t=>t.set!==setKey&&t.k==='dome_baseline');
   const os=w.eval(`sets.get(${JSON.stringify(other.set)})`);
   os.record_id=other.id;os.data={stats:w.eval('canonStats')(other.set,other.id),snapshot:true};
   w.eval('selected').push(other.set);w.eval('renderReadout()');
   w.document.getElementById('roMore').click();
   const expandedReadout=w.document.getElementById('readout').textContent;
   const noReferenceMetadata=!Object.keys(build).some(key=>key.startsWith('force_wall_reference'));
   const noDeltaOrScaleNote=!/forceWallDelta|wallDelta|force_wall_reference|80 is not twice 40|Index scale note|INDEX_SCALE_NOTE/.test(viewerSource)&&
     !forbiddenConsumerText.test(expandedReadout);
   const out={primarySet:setKey,primaryTestId:testId,primaryIdentityUnique:matches.length===1,
     snapshot:!!(d&&d.snapshot),
     statsMatchCanonical:sameStats(d&&d.stats,canonical),
     pressPts:d&&d.avgPress?d.avgPress.x.length:0,
     returnPts:d&&d.avgRet?d.avgRet.x.length:0,
     painted:paints>50,
     expandedReadoutShowsRecordIdentity:expandedReadout.includes('RECORD ID')&&expandedReadout.includes(testId),
     noReferenceMetadata,noDeltaOrScaleNote,
     pageErrors};
   console.log(JSON.stringify(out));
   process.exit(out.primaryIdentityUnique&&out.snapshot&&out.statsMatchCanonical&&out.pressPts>100&&out.returnPts>100&&out.painted&&out.expandedReadoutShowsRecordIdentity&&out.noReferenceMetadata&&out.noDeltaOrScaleNote&&out.pageErrors.length===0?0:1);
 },1500);
},1700);
