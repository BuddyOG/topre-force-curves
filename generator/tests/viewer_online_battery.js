// Online viewer battery: raw fetches SERVED from the pinned cache. The staged
// viewer must select one stable canonical record without special reference
// metadata, fetch only that record's CANONICAL_RUNS, and display generated canonical
// scalars (no competing in-browser calculation/filter).
const {JSDOM}=require('jsdom');const fs=require('fs');const path=require('path');
const [viewer,cache]=process.argv.slice(2);
if(!viewer||!cache){console.error('usage: viewer_online_battery.js <viewer.html> <raw-cache>');process.exit(2);}
const viewerSource=fs.readFileSync(viewer,'utf8');
const forbiddenConsumerText=/80 is not twice 40|index scale note|wall delta|vs\s+Topre/i;
const cacheRoot=path.resolve(cache);
const rawFetches=[];const unexpectedFetches=[];const pageErrors=[];
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
  w.fetch=(u)=>{u=String(u);
    if(u.includes('api.github.com'))return Promise.reject(new Error('no api'));
    const m=u.match(/raw\.githubusercontent\.com\/[^/]+\/[^/]+\/([^/]+)\/(.+)$/);
    if(m){const rel=decodeURIComponent(m[2]);const p=path.resolve(cacheRoot,rel);
      rawFetches.push({commit:m[1],path:rel});
      if(p!==cacheRoot&&!p.startsWith(cacheRoot+path.sep)){
        unexpectedFetches.push(u);return Promise.reject(new Error('cache escape '+rel));}
      if(fs.existsSync(p))return Promise.resolve({ok:true,text:()=>Promise.resolve(fs.readFileSync(p,'utf8'))});
      return Promise.resolve({ok:false,status:404});}
    unexpectedFetches.push(u);
    return Promise.reject(new Error('unexpected '+u));};
  w.addEventListener('error',e=>pageErrors.push(String((e.error&&e.error.message)||e.message)));
  w.HTMLCanvasElement.prototype.getContext=()=>new Proxy({},{get:()=>(...a)=>({width:10}),set:()=>true});}});
setTimeout(()=>{const w=dom.window;
 const build=w.eval('VIEWER_BUILD');
 const rows=w.eval('VTESTS');
 const primary=rows.find(t=>t.set==='Topre_R1_45g'&&t.id==='bt_0075'&&t.k==='dome_baseline');
 if(!primary){console.error('stable canonical test record missing');process.exit(2);}
 const setKey=primary.set;
 const testId=primary.id;
 const canonicalRuns=w.eval('CANONICAL_RUNS')[setKey];
 if(!Array.isArray(canonicalRuns)){console.error('CANONICAL_RUNS missing for',setKey);process.exit(2);}
 const s=w.eval(`sets.get(${JSON.stringify(setKey)})`);
 if(!s||!s.btn){console.error('set button missing');process.exit(2);}
 s.btn.click();
 setTimeout(()=>{
   const d=w.eval(`sets.get(${JSON.stringify(setKey)}).data`);
   const matches=rows.filter(t=>t.set===setKey&&t.id===testId);
   const canonical=w.eval('canonStats')(setKey,testId);
   const expectedPaths=canonicalRuns.map(name=>`${setKey}/${name}`).sort();
   const fetchedPaths=rawFetches.map(item=>item.path).sort();
   const fetchedExactMembership=JSON.stringify(fetchedPaths)===JSON.stringify(expectedPaths);
   const fetchedPinnedCommit=rawFetches.length===expectedPaths.length&&rawFetches.every(item=>item.commit===build.repo_commit);
   // Add a generated snapshot-only peer without another fetch, then verify
   // that "More columns" restores the exact record identity.
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
     online:!!(d&&d.snapshot!==true&&Array.isArray(d.runs)),
     runs:d&&d.runs?d.runs.length:-1,
     expectRuns:canonicalRuns.length,
     statsAreCanonical:sameStats(d&&d.stats,canonical),
     fetchedExactMembership,fetchedPinnedCommit,
     expandedReadoutShowsRecordIdentity:expandedReadout.includes('RECORD ID')&&expandedReadout.includes(testId),
     noReferenceMetadata,noDeltaOrScaleNote,
     rawFetches,unexpectedFetches,pageErrors};
   console.log(JSON.stringify(out));
   process.exit(out.primaryIdentityUnique&&out.online&&out.runs===out.expectRuns&&out.statsAreCanonical&&out.fetchedExactMembership&&out.fetchedPinnedCommit&&out.expandedReadoutShowsRecordIdentity&&out.noReferenceMetadata&&out.noDeltaOrScaleNote&&out.unexpectedFetches.length===0&&out.pageErrors.length===0?0:1);
 },1800);
},1700);
