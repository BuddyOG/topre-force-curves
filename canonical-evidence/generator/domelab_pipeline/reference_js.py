"""Generated JavaScript reference analyzer for cross-runtime conformance.

This is never a viewer scalar authority. It exists so edge cases in the public
curve implementation can be checked against :mod:`domelab_pipeline.core`.
"""
import json

from .core import config


def js_reference_analyzer_source():
    c = config()
    cd, valley, travel = c["collapse_detect"], c["valley"], c["travel"]
    ramp, steep = c["ramp"], c["steepest_drop"]
    cfg = {
        "k": c["smoothing"]["k"],
        "searchFraction": cd["search_fraction"],
        "halfwin": cd["local_max_halfwin_samples"],
        "lookahead": cd["drop_lookahead_samples"],
        "prominence": cd["min_prominence_gf"],
        "edge": cd["edge_margin_samples"],
        "valleyWindow": valley["seed_window_mm"],
        "passes": valley["fixed_point_max_passes"],
        "wallFloor": travel["floor_gf"],
        "wallStepFraction": travel["step_fraction"],
        "wallConsecutive": travel["consecutive_steps"],
        "steepWindow": steep["window_mm"],
        "steepTieTolerance": steep["tie_tolerance_gf_per_mm"],
        "ramp": ramp,
    }
    jcfg = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    return r'''/* Generated metrics-v4.2 reference analyzer. Canonical displayed
   scalars come from TESTS/VTESTS; this function exists only for parity tests. */
function analyze(x,F,gridConforming=true,configOverride=null){
  const C=configOverride||__CFG__;const n=x.length;
  const blank=()=>({Fpeak:null,xpeak:null,Fval:null,xval:null,snap:null,travel:null,E:null,Epc:null,
    dropF:null,dropX:null,dropRate:null,ndr:null,steep:null,ramp:null,flags:[],audit:{
      force_wall_travel_mm:null,force_wall_found:false,steepest_drop_start_mm:null,
      steepest_drop_end_mm:null,ramp_baseline_force_gf:null,ramp_x10_mm:null,ramp_x90_mm:null,
      ramp_x10_cross_count:0,ramp_x90_cross_count:0,ramp_x10_eligible_cross_count:0,
      ramp_x90_eligible_cross_count:0,ramp_band_sample_count:0,ramp_band_complete:false}});
  const out=blank(),flags=out.flags,audit=out.audit;if(n<50){flags.push("incomplete_press");return out;}
  const Fs=movAvg(F,C.k),lim=Math.floor(n*C.searchFraction);
  let pk=-1,best=-1;
  for(let i=C.edge;i<lim-C.edge;i++){
    let isMax=true;for(let j=Math.max(0,i-C.halfwin);j<Math.min(lim,i+C.halfwin);j++)
      if(Fs[j]>Fs[i]){isMax=false;break;}
    if(!isMax)continue;let fmin=Infinity;
    for(let j=i;j<Math.min(lim,i+C.lookahead);j++)if(Fs[j]<fmin)fmin=Fs[j];
    if(Fs[i]-fmin>C.prominence&&Fs[i]>best){best=Fs[i];pk=i;}
  }
  if(pk<0){for(let i=0;i<lim;i++)if(Fs[i]>best){best=Fs[i];pk=i;}
    if(pk<0){flags.push("collapse_not_found");return out;}
    flags.push("collapse_fallback_used","tactile_event_not_found");}
  const Fc=Fs[pk],xc=x[pk];let vl=-1,vmin=Infinity;
  for(let i=pk+1;i<n;i++){if(x[i]>xc+C.valleyWindow)break;if(Fs[i]<vmin){vmin=Fs[i];vl=i;}}
  if(vl<0){flags.push("valley_not_found");return out;}
  if(!gridConforming)flags.push("grid_nonconforming");
  const wallFrom=vi=>{if(!gridConforming)return null;
    for(let i=vi+1;i<n-C.wallConsecutive;i++){if(Fs[i]<C.wallFloor)continue;let ok=true;
      for(let j=i;j<i+C.wallConsecutive;j++)if(!(Fs[j+1]-Fs[j]>C.wallStepFraction*Fs[j])){ok=false;break;}
      if(ok)return i;}return null;};
  let ti=wallFrom(vl),converged=false;
  for(let pass=0;pass<C.passes;pass++){const stop=ti==null?n-1:ti;let v2=-1,m2=Infinity;
    for(let i=pk+1;i<=stop;i++)if(Fs[i]<m2){m2=Fs[i];v2=i;}
    if(v2===vl){converged=true;break;}vl=v2;ti=wallFrom(vl);}
  if(!converged)flags.push("valley_iteration_nonconverged");
  const Fv=Fs[vl],xv=x[vl];out.Fpeak=Fc;out.xpeak=xc;out.Fval=Fv;out.xval=xv;
  if(Fc>0)out.snap=(Fc-Fv)/Fc*100;else flags.push("nonpositive_collapse_force");
  if(ti==null){if(gridConforming)flags.push("bottomout_not_found");}
  else{out.travel=x[ti];audit.force_wall_travel_mm=x[ti];audit.force_wall_found=true;}
  const interp=q=>{if(q<=x[0])return F[0];if(q>=x[n-1])return F[n-1];let lo=0,hi=n-1;
    while(hi-lo>1){const mid=(lo+hi)>>1;if(x[mid]<=q)lo=mid;else hi=mid;}
    if(x[hi]===x[lo])return F[lo];const t=(q-x[lo])/(x[hi]-x[lo]);return F[lo]+t*(F[hi]-F[lo]);};
  const trapTo=endpoint=>{if(endpoint==null)return null;let W=0;
    for(let i=1;i<n;i++){if(x[i]<=endpoint)W+=(F[i]+F[i-1])/2*(x[i]-x[i-1]);
      else{const Fe=interp(endpoint);W+=(Fe+F[i-1])/2*(endpoint-x[i-1]);break;}}return W;};
  out.Epc=trapTo(xc);out.E=trapTo(out.travel);
  const dF=Fc-Fv,dX=xv-xc;out.dropF=dF;out.dropX=dX;
  if(dF<=0)flags.push("nonpositive_drop");if(dX<=0)flags.push("nonpositive_drop_travel");
  if(dF>0&&dX>0&&Fc>0){out.dropRate=dF/dX;out.ndr=dF/(Fc*dX);}
  const h=C.steepWindow;
  if(dX<h)flags.push("drop_travel_below_0p10mm");
  else if(dX>0){const cand=new Set([xc,xv-h]);for(let i=pk;i<=vl;i++){
      if(xc<=x[i]&&x[i]<=xv-h)cand.add(x[i]);if(xc<=x[i]-h&&x[i]-h<=xv-h)cand.add(x[i]-h);}
    const interpS=q=>{if(q<=x[0])return Fs[0];if(q>=x[n-1])return Fs[n-1];let lo=0,hi=n-1;
      while(hi-lo>1){const mid=(lo+hi)>>1;if(x[mid]<=q)lo=mid;else hi=mid;}
      if(x[hi]===x[lo])return Fs[lo];const t=(q-x[lo])/(x[hi]-x[lo]);return Fs[lo]+t*(Fs[hi]-Fs[lo]);};
    const slopes=[...cand].sort((a,b)=>a-b).map(q=>[q,(interpS(q)-interpS(q+h))/h]);
    const bs=Math.max(...slopes.map(v=>v[1]));
    const bq=slopes.find(v=>bs-v[1]<=C.steepTieTolerance)[0];
    out.steep=bs;audit.steepest_drop_start_mm=bq;
    audit.steepest_drop_end_mm=bq+h;}
  const r=C.ramp,tol=r.coordinate_tolerance_mm,bidx=[];
  for(let i=0;i<n;i++)if(r.reference_band_low_mm<=x[i]&&x[i]<=r.reference_band_high_mm)bidx.push(i);
  const band=bidx.map(i=>Fs[i]);audit.ramp_band_sample_count=band.length;
  audit.ramp_band_complete=!!(bidx.length&&x[0]<=r.reference_band_low_mm+tol&&
    x[n-1]>=r.reference_band_high_mm-tol);
  if(!audit.ramp_band_complete)flags.push("ramp_baseline_band_incomplete");
  else if(band.length<r.minimum_band_samples)flags.push("ramp_baseline_unavailable");
  else{const sb=[...band].sort((a,b)=>a-b),mid=sb.length>>1;
    const Fb=sb.length%2?sb[mid]:(sb[mid-1]+sb[mid])/2;audit.ramp_baseline_force_gf=Fb;
    if(xc<=r.reference_band_high_mm+tol)flags.push("ramp_reference_band_overlaps_collapse");
    else if(Fc<=Fb+r.min_rise_gf)flags.push("ramp_baseline_unavailable");
    else{const T10=Fb+r.low_fraction*(Fc-Fb),T90=Fb+r.high_fraction*(Fc-Fb);
      const crosses=T=>{const all=[],eligible=[];for(let i=1;i<=pk;i++)if(Fs[i-1]<T&&T<=Fs[i]){
        const cx=x[i-1]+(T-Fs[i-1])/(Fs[i]-Fs[i-1])*(x[i]-x[i-1]);all.push(cx);
        if(r.seating_end_mm-tol<=cx&&cx<=xc+tol)eligible.push(cx);}return [all,eligible];};
      const [a10,e10]=crosses(T10),[a90,e90]=crosses(T90);
      audit.ramp_x10_cross_count=a10.length;audit.ramp_x90_cross_count=a90.length;
      audit.ramp_x10_eligible_cross_count=e10.length;audit.ramp_x90_eligible_cross_count=e90.length;
      const x10=e10.length?e10[e10.length-1]:null,x90=e90.length?e90[e90.length-1]:null;
      audit.ramp_x10_mm=x10;audit.ramp_x90_mm=x90;
      if(x10==null||x90==null)flags.push("ramp_crossing_missing");
      else if(x10+tol>=x90)flags.push("ramp_event_order_invalid");
      else if((x90-x10)+tol<r.min_span_mm)flags.push("ramp_span_too_small");
      else out.ramp=(r.high_fraction-r.low_fraction)*(Fc-Fb)/(x90-x10);}}
  return out;
}'''.replace("__CFG__", jcfg)
