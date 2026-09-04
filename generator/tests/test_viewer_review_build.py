"""Focused contract checks for the fc-3.5 review viewer.

These tests generate in memory from the same pinned cache as the production
pipeline.  They do not promote or rewrite the shared staging tree.
"""
import json
import math
import os
import subprocess

import pytest

from domelab_pipeline.packs import (
    VIEWER_BUILD_PROFILE,
    VIEWER_BUILD_PROFILES,
    _extract_blob,
)
from domelab_pipeline.pipeline import generate
from domelab_pipeline.parity import _node_modules
from domelab_pipeline import perception


HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="module")
def review_candidate(cache, commit):
    staged, records, *_ = generate(cache, commit, "unused", write=False, run_parity=False)
    return staged, records


@pytest.fixture(scope="module")
def release_candidate(cache, commit):
    staged, records, *_ = generate(
        cache, commit, "unused", write=False, run_parity=False,
        viewer_profile="release",
    )
    return staged, records


def _blob(html, name):
    return _extract_blob(html, name)[2]


def _mask_blob(html, name):
    start, end, _ = _extract_blob(html, name)
    return html[:start] + f"<{name}>" + html[end:]


def test_release_profile_changes_only_presentation_identity(
        review_candidate, release_candidate):
    review_staged, review_records = review_candidate
    release_staged, release_records = release_candidate
    review_html = review_staged["packs/viewer.staged.html"]
    release_html = release_staged["packs/viewer.staged.html"]
    review_build = _blob(review_html, "VIEWER_BUILD")
    release_build = _blob(release_html, "VIEWER_BUILD")

    assert review_build["mode"] == "review"
    assert review_build["presentation_role"] == "review_candidate"
    assert review_build["release_eligible"] is False
    assert review_build["bench_build"] == "fc-3.5-review.1"
    assert release_build["mode"] == "release"
    assert release_build["presentation_role"] == "public_release"
    assert release_build["release_eligible"] is True
    assert release_build["bench_build"] == "fc-3.5"
    for key in VIEWER_BUILD_PROFILES["review"]:
        if key not in {"mode", "presentation_role", "release_eligible", "bench_build"}:
            assert release_build[key] == review_build[key]

    # The parts library carries the same presentation identity split in its
    # generated PICKER_BUILD blob. Only the release profile is eligible.
    review_pb = _blob(review_staged["packs/picker.staged.html"], "PICKER_BUILD")
    release_pb = _blob(release_staged["packs/picker.staged.html"], "PICKER_BUILD")
    assert review_pb["mode"] == "review" and release_pb["mode"] == "release"
    assert review_pb["presentation_role"] == "review_candidate"
    assert release_pb["presentation_role"] == "public_release"
    assert review_pb["library_build"] == "lib-6.1-review.1"
    assert release_pb["library_build"] == "lib-6.1"
    assert review_pb["release_eligible"] is False
    assert release_pb["release_eligible"] is True
    for key in review_pb:
        if key not in {"mode", "presentation_role",
                       "library_build", "release_eligible"}:
            assert release_pb[key] == review_pb[key], key

    # Profile selection cannot alter the frozen records, generated data packs,
    # scientific constants, membership, or any source outside the two
    # generated presentation-identity blobs.
    assert release_records == review_records
    assert set(release_staged) == set(review_staged)
    for path in review_staged:
        if path not in {"packs/viewer.staged.html", "packs/picker.staged.html",
                        "generated_manifest.json"}:
            assert release_staged[path] == review_staged[path], path
    review_manifest = json.loads(review_staged["generated_manifest.json"])
    release_manifest = json.loads(release_staged["generated_manifest.json"])
    for moving in ("packs/viewer.staged.html", "packs/picker.staged.html"):
        review_hash = review_manifest.pop(moving)
        release_hash = release_manifest.pop(moving)
        assert review_hash != release_hash, moving
    assert release_manifest == review_manifest
    assert _mask_blob(release_html, "VIEWER_BUILD") == _mask_blob(
        review_html, "VIEWER_BUILD"
    )
    for name in ("PERCEPTION_MODEL", "RECORD_IDS_BY_SET", "CANONICAL_RUNS",
                 "INTAKE_RAMP_REVIEWS_BY_SET", "GENERATED_EXCLUSIONS",
                 "EMBEDDED", "VTESTS"):
        assert _blob(release_html, name) == _blob(review_html, name), name


def test_viewer_records_keep_generated_precision_and_explicit_identity(review_candidate):
    staged, records = review_candidate
    html = staged["packs/viewer.staged.html"]
    rows = _blob(html, "VTESTS")
    by_id = {r["id"]: r for r in rows}
    assert len(by_id) == len(records)
    for rec in records:
        row = by_id[rec["test_id"]]
        assert row["source_set"] == rec["set"]
        assert row["cg"] == rec["collapse_force_gf"]
        assert row["cx"] == rec["collapse_travel_mm"]
        assert row["tv"] == rec["travel_mm"]
        assert row["en"] == rec["full_stroke_press_work_gf_mm"]
        assert isinstance(row["tl_min"], (int, float))
        assert isinstance(row["tl_max"], (int, float))
        assert row["tl_min"] <= row["tl_max"]
        assert row["mfr"] == rec.get("manufacturer")
        assert row["wt"] == rec.get("nominal_weight_g")
        assert row["ver"] == rec.get("variant")
        assert row["sty"] == rec.get("style")
        assert row["cohort"] == rec.get("measurement_cohort_id")
        assert row["alias_group"] == rec.get("evidence_alias_group")
        assert row["alias_role"] == rec.get("evidence_alias_role")
    # At least one value would change if the viewer pack rounded its authority.
    assert any(row["cg"] != round(row["cg"], 1) for row in rows)


def test_pilot_indices_are_record_bound_and_parts_are_not_calibrated(review_candidate):
    staged, _ = review_candidate
    html = staged["packs/viewer.staged.html"]
    rows = _blob(html, "VTESTS")
    model = _blob(html, "PERCEPTION_MODEL")

    assert model["version"] == "perception-rank-v1"
    assert model["reference_count"] == 68
    assert model["weight"]["primary_viewer_key"] == "cg"
    assert model["weight"]["score_viewer_key"] == "wi"
    assert model["tactility"]["primary_viewer_key"] == "dg"
    assert model["tactility"]["score_viewer_key"] == "ti"
    assert model["missing"] == "not_available_no_imputation"

    domes = [row for row in rows if row["k"] == "dome_baseline"]
    parts = [row for row in rows if row["k"] == "part_assembly"]
    assert len(domes) == model["reference_count"]
    assert parts
    for row in domes:
        assert row["wi"] == row["pp"]["cg"]
        assert row["ti"] == row["pp"]["dg"]
        assert 0.0 <= row["wi"] <= 100.0
        assert 0.0 <= row["ti"] <= 100.0
    for row in parts:
        assert row["wi"] is None and row["ti"] is None
        assert all(value is None for value in row["pp"].values())


def test_shared_acquisition_aliases_preserve_both_semantic_records(review_candidate):
    staged, records = review_candidate
    html = staged["packs/viewer.staged.html"]
    records_by_id = {record["test_id"]: record for record in records}
    rows = [
        row for row in _blob(html, "VTESTS")
        if row.get("alias_group") == "egrp_topre_hhkb_pro2_45g__topre_slider_black"
    ]
    assert len(rows) == 2
    assert len({r["id"] for r in rows}) == 2
    assert {r["k"] for r in rows} == {"dome_baseline", "part_assembly"}
    assert len({r["source_set"] for r in rows}) == 2
    assert len({r["cohort"] for r in rows}) == 1
    assert all(records_by_id[row["id"]]["evidence_alias_group"] for row in rows)
    assert "const KINDS_OF_SET={}" in html
    assert "const RECORD_BY_ID=new Map" in html
    assert "KIND_OF_SET[t.set]=t.k" not in html
    assert "toggleSet(key,recordId=null)" in html
    assert "function selectedName(s)" in html
    assert "recordId:t.id||null" in html
    assert "duplicate source set has divergent generated record scalars" in html


def test_viewer_is_generated_fleet_only_and_commit_pinned(review_candidate, commit):
    staged, _ = review_candidate
    html = staged["packs/viewer.staged.html"]
    build = _blob(html, "VIEWER_BUILD")
    metadata = json.loads(staged["schema_meta.staged.json"])
    assert build["mode"] == VIEWER_BUILD_PROFILE["mode"] == "review"
    assert build["presentation_role"] == "review_candidate"
    assert build["release_eligible"] is False
    assert build["bench_build"] == VIEWER_BUILD_PROFILE["bench_build"]
    assert build["metrics"] == metadata["method_config"]["metrics_version"]
    assert build["intake"] == metadata["intake_policy"]["version"]
    assert build["repo_commit"] == commit
    assert build["data_epoch"] == (
        f"{VIEWER_BUILD_PROFILE['data_epoch_prefix']}{commit[:7]}"
    )
    assert not any(key.startswith("force_wall_reference") for key in build)
    assert build["canonical_evidence_identity"] == build["data_identity"]
    assert build["data_artifact_role"] == "canonical_retention_authority"
    assert build["canonical_data_release_eligible"] is True
    assert build["semantic_run_binding_count"] == 184
    assert build["unique_acquisition_count"] == 180
    assert build["independent_measurement_cohort_count"] == 75
    assert build["shared_evidence_alias_group_count"] == 1
    assert build["bench_build"] == "fc-3.5-review.1"
    assert build["perception_score_version"] == "perception-rank-v1"
    assert len(build["data_identity"]) == 64
    assert "api.github.com/repos" not in html
    assert 'const BRANCH = "main"' not in html
    assert "/blob/main/" not in html
    assert "FALLBACK_CSVS){" in html
    assert "VIEWER_BUILD.repo_commit" in html
    assert "set is not in generated retained membership" in html
    assert "generated retained-run membership mismatch" in html


def test_shared_absolute_axis_covers_every_released_force_wall(review_candidate):
    staged, _ = review_candidate
    html = staged["packs/viewer.staged.html"]
    build = _blob(html, "VIEWER_BUILD")
    rows = _blob(html, "VTESTS")
    walls = [row["tv"] for row in rows if isinstance(row.get("tv"), (int, float))]
    assert walls
    assert build["axis_data_floor_mm"] == 4.0
    furthest_wall = max(walls)
    shared_max = (
        4.0 if furthest_wall <= 4.0 + 1e-9
        else math.ceil(furthest_wall * 2 - 1e-9) / 2
    )
    assert shared_max == 4.5
    assert all(wall <= shared_max for wall in walls)
    # Every selection uses one generated fleet-wide absolute scale. It expands
    # from the ordinary 4.0 mm base only when a released force-wall marker
    # requires more room; recorded sample/turnaround extent is not the driver.
    assert "const XMAX=generatedAxisMax();" in html
    axis_source = html.split("function generatedAxisMax(){", 1)[1].split(
        "const XMAX=generatedAxisMax();", 1
    )[0]
    assert "VIEWER_BUILD.force_wall_domain_max_mm" in axis_source
    assert "VTESTS" not in axis_source
    assert "EMBEDDED" not in axis_source
    assert "curve_domain_max_mm" not in axis_source
    assert "dynamicXmax" not in html
    assert "for(let gx=0;gx<=XMAX+1e-9;gx+=0.5)" in html
    assert 'const XMAX=4.0' not in html
    assert "per-dome" not in html.lower()


def test_public_metric_profile_and_force_wall_contract(review_candidate):
    staged, _ = review_candidate
    html = staged["packs/viewer.staged.html"]
    assert "Detected force-wall onset" in html
    assert "DETECTED FORCE-WALL ONSET" in html
    assert "operational proxy from the complete measured test assembly" in html
    assert "Recorded turnaround range (test limit)" in html
    assert "acquisition extent only and is never physical travel" in html
    assert "Not detected" in html
    assert "const wallText=isNum(wall)?`${displayFixed(wall,2)} mm`:" in html
    assert "function displayFixed(value,digits)" in html
    assert "forceWallDelta(" not in html
    assert "forceWallDeltaValue(" not in html
    assert "wallDelta" not in html
    assert "force_wall_reference" not in html
    assert 'canonStats("Topre_45g")' not in html
    assert 'canonStats("Topre_R1_45g")' not in html
    assert '"TRAVEL (MM)"' not in html
    assert ">Travel<" not in html
    assert "from 0 to Travel" not in html
    assert "Documentation:</b> public method, interpretation, provenance" in html
    assert 'href="documentation/index.html"' in html
    assert 'href="documentation/index.html#rights-and-reuse"' in html
    assert "documentation &amp; terms" in html
    assert "© 2026 Brian “BuddyOG” Gebo — Unreal Keyboards. All rights reserved." in html
    assert "unrealkeyboards.com/blogs/topre-mods/topre-dome-force-curves" not in html
    assert '<link rel="canonical" href="https://buddyog.github.io/topre-force-curves/">' in html
    assert '<meta property="og:url" content="https://buddyog.github.io/topre-force-curves/">' in html
    assert '<meta property="og:image" content="https://buddyog.github.io/topre-force-curves/assets/force-curve-bench-fc-3.5-og.png">' in html
    assert '<meta property="og:image:width" content="2968">' in html
    assert '<meta property="og:image:height" content="1928">' in html
    assert "Each index uses one full-precision input" in html
    assert "correlation coefficients and supporting descriptors are not calculation weights" in html
    assert 'href="https://doi.org/10.5281/zenodo.22295223"' in html
    assert "collapse-force percentile within the frozen 68-dome reference fleet" in html
    assert "force-Drop percentile within the frozen 68-dome reference fleet" in html
    assert "owner selects the canonical public URL" not in html
    assert '<button class="xtab subtab" id="subParts" type="button">Parts</button>' in html
    assert '<button class="xtab subtab" id="subTests" type="button">Tests</button>' in html
    assert 'href="dome-lab-parts.html"' not in html
    assert "Under runfilter-v1.1" not in html
    assert "run-to-run deviation in collapse force is under one gram" not in html
    assert "Scalar landmarks/markers are arithmetic means of per-run detections" in html
    assert "Averaged visualization traces are built separately" in html
    assert "a marker therefore need not lie on a feature of the averaged trace" in html
    assert "recordedTurnaround(s)" in html
    assert "formatTurnaroundRange(turn)" in html
    assert "if(hasWall&&isNum(st.E))" not in html
    assert "if(hasWall){const lx=" in html
    assert "isNum(s.data.stats.travel)?sampleAt" in html
    assert "Comparison overlays retain a visible wall-onset marker for every" in html
    assert "else if(showVisuals&&isNum(st.travel))" in html
    assert 'if(v==null)v=c[0]==="travel"?"Not detected"' in html
    assert 'v=cc[0]==="tv"?"Not detected":"Not available"' in html
    assert 'aria-pressed="false" data-m="profileWeight">Weight profile</button>' in html
    assert 'aria-pressed="false" data-m="profileTactility">Tactility profile</button>' in html
    assert 'aria-pressed="false" data-m="profileTravel">Force-wall onset</button>' in html
    assert 'aria-pressed="false" data-m="indexScatter">Weight vs tactility</button>' in html
    assert 'id="btnCompareClear" type="button">Clear selection</button>' in html
    assert '>Clear filters</button>' in html
    assert 'aria-label="Clear name and value filters"' in html
    assert "Reset filters" not in html
    assert 'data-filters-toggle' in html
    assert 'const bodyId=`${prefix}-filter-body`;' in html
    assert 'aria-controls="${bodyId}"' in html
    assert "Value filters" not in html
    assert 'id="testsMenuToggle"' in html
    assert 'aria-controls="testsMenuBody"' in html
    assert 'id="testsMenuBody"' in html
    assert 'function resetFilters(kind){const s=FILTER_STATES[kind];s.q="";s.R={};}' in html
    assert "const PROFILE_PTS=[]" in html
    assert "function drawProfile(" in html
    assert "const SCATTER_PTS=[]" in html
    assert "function drawIndexScatter(" in html
    assert "const TRAVEL_PTS=[]" in html
    assert "function drawTravelComparison(" in html
    assert "if(isTravelProfileMode()){drawTravelComparison(g,w,h,T,th);return;}" in html
    assert 'if(["curves","profileWeight","profileTactility","profileTravel","indexScatter"].includes(requestedMode))' in html
    assert 't.toLowerCase()==="all-domes"' in html
    assert 't.toLowerCase()==="all-parts"' in html
    assert 'if(!toks.length){if(isDerivedComparisonMode())loadAllComparisonSets(benchKind);return;}' in html
    assert 'function allKeysForKind(kind)' in html
    assert 'function loadAllComparisonSets(kind=benchKind)' in html
    assert 'function loadAllComparisonParts()' in html
    assert 'benchKind==="part_assembly"?"Load all parts":"Load all domes"' in html
    assert 'const TOPRE_TRAVEL_REFERENCE_SETS=Object.freeze([' in html
    assert '"Topre_HHKB_Pro2_45g"' in html
    assert '"Topre_GX1_45g"' in html
    assert "function travelReferenceStats()" in html
    assert "function travelGroupForRecord(rec)" in html
    assert 'label:"DynaCaps"' in html
    assert 'label:"Astro Domes"' in html
    assert 'label:`Deskeys ${rec.sty}`' in html
    assert 'label:"BKE Redux v1"' in html
    assert 'tip:`${group.label} · Detected force-wall onset not detected`' in html
    assert "const unavailable=chosen.filter" in html
    assert "function travelComparisonGroups(chosen)" in html
    assert "function travelPlotGeometry(w,h,groupCount,hasMissing)" in html
    assert "function travelRowLayout(groups,top,bottom)" in html
    assert "function packTravelMarkers(members,X,rowY,rowStep,compact)" in html
    assert "g.strokeRect(-4.5,-4.5,9,9)" in html
    assert 'const isFullReferenceGroup=group.id==="topre-production"' in html
    assert 'if(Math.abs(delta)<.005)return "same at displayed precision"' in html
    assert 'Math.abs(delta)<.005?"≈REF"' in html
    assert 'not nominal/physical switch travel; not a better/worse score' in html
    assert 'Proxy—not physical travel; not better/worse.' in html
    assert 'Domes: 0.00 mm precomp.; no advertised check.' in html
    assert 'Detected Force-Wall Onset by Assembly Group' in html
    assert 'Part assemblies retain recorded precompression; the Topre dome reference is context only.' in html
    assert "TOPRE PRODUCTION REFERENCE" in html
    assert "All dome baselines use 0.00&nbsp;mm added precompression" in html
    assert "not by itself verification of an advertised travel claim" in html
    assert 'renderSbFilters();\n      setTestsMenuOpen(FILTER_STATES[benchKind].testsOpen,benchKind);\n      applyFilter();' in html
    assert 'core=["name","travelGroup","travel","travelDelta"]' in html
    readout_columns = html.split("let core,extra;", 1)[1]
    travel_branch = readout_columns.split('if(isTravelProfileMode()){', 1)[1].split('}else if(isPart)', 1)[0]
    assert "turnaround" not in travel_branch
    assert "Weight Index (0–100)" in html
    assert "Tactility Index (0–100)" in html
    assert "Not calibrated:" in html
    assert "Not available:" in html
    assert "not calibrated or available for this selection" in html
    assert "force-wall" in html.lower()
    assert "body.comparison-chart .chartwrap" in html
    assert "height:640px" in html
    assert ".chartwrap,body.comparison-chart .chartwrap{width:100%;aspect-ratio:auto;height:560px;min-height:0}" in html
    assert ".chartwrap,body.comparison-chart .chartwrap{height:520px}" in html
    assert 'document.body.classList.toggle("comparison-chart",derivedOn)' in html
    assert 'document.body.style.removeProperty("--tall-chart-height")' in html
    assert "const plotTop=M.t+78" in html
    assert "const singleHeader=selected.length===1?forceCurveHeaderLayout(w):null" in html
    assert "const plotTop=singleHeader?singleHeader.plotTop:selected.length>1?M.t+58:M.t" in html
    assert 'x.setAttribute("aria-pressed",String(on))' in html
    assert "tooltip.offsetHeight>wrap.height-8" in html
    assert "Collapse-force Weight Index" in html
    assert "Drop-based Tactility Index" in html
    assert "Not calibrated: ${omitted.map(selectedName).join" in html
    assert "function drawExportStats(" in html
    assert "if(externalStats)drawExportStats" in html
    assert 'id="graphDisplayMenu"' in html
    assert 'id="graphDisplaySummary">Graph display · Simplified' in html
    assert 'id="graphStyleSimplified" name="graphStyle" value="simplified" type="radio" checked' in html
    assert 'id="graphStyleDetailed" name="graphStyle" value="detailed" type="radio"' in html
    assert 'id="toggleGraphLabels"' in html
    assert 'id="toggleGraphVisuals"' in html
    assert 'const GRAPH_DISPLAY={style:"simplified",labels:true,visuals:true}' in html
    assert 'function simplifiedGraphDisplay(){return chartMode==="curves"&&GRAPH_DISPLAY.style==="simplified";}' in html
    assert 'detailed=GRAPH_DISPLAY.style==="detailed"' in html
    assert 'GRAPH_DISPLAY.style=e.target.value==="detailed"?"detailed":"simplified"' in html
    assert "if(showVisuals&&hasWall)" in html
    assert "if(showVisuals&&detailed&&isNum(st.ramp)" in html
    assert "if(showLabels){" in html
    assert 'if(e.key==="Escape")' in html
    assert "ANNOT_HITS.length=0" in html
    assert 'if(kindOf(s.key,s.record_id)!=="dome_baseline"' not in html
    assert "Press Work vs Snap" not in html
    assert "Drop Rate vs Norm. Drop Rate" not in html
    normalized_html = html.replace("\\u00B7", "\u00b7").upper()
    for retired_heading in (
        "PRESS WORK TO FORCE-WALL (GF\u00b7MM)",
        "NORM. DROP RATE (/MM)",
        "COLLAPSE-TO-VALLEY DISTANCE (MM)",
        "COLLAPSE (MM)",
        "VALLEY (GF)",
        "VALLEY (MM)",
    ):
        assert retired_heading not in normalized_html
    assert "Families stay contiguous so screen readers" in html
    assert '["Weight Index",indexText(st.weightIndex)]' in html
    assert '["Tactility Index",indexText(st.tactilityIndex)]' in html
    assert 'const FEATURE_FAMILY=Object.freeze({weightIndex:"weight"' in html
    assert 'family:"weight",title:"Weight Index"' in html
    assert 'family:"tactility",title:"Tactility Index"' in html
    assert 'family:"separate",title:"Travel-related measurements",index:null,focus:"travelGroup"' in html
    assert '.statsout .so-group.family-separate{border-top-color:var(--separate)}' in html
    assert '.statsout .so-head.family-separate{color:var(--separate)}' in html
    assert '.statsout .family-separate .so-l,.statsout .family-separate .so-v{color:var(--separate)}' in html
    assert 'if(family==="separate")return F.travel' in html
    assert 'group.family==="weight"?F.weight:group.family==="tactility"?F.tactility:F.travel' in html
    assert '["Drop force",isNum(st.dropF)' in html
    assert 'rows:take(simplified?["Collapse force"]:["Collapse force","Ramp","Pre-collapse work"])' in html
    assert 'rows:take(simplified?["Drop force"]:["Drop force","Snap %","Steepest drop","Drop rate"])' in html
    assert 'rows:take(simplified?["Detected force-wall onset"]:["Detected force-wall onset","Recorded turnaround range (test limit)"])' in html
    assert 'if(interactive&&isDerivedComparisonMode())hideStatsOut()' in html
    assert 'const hasDrop=hasCollapse&&hasValley&&isNum(st.dropF)' in html
    assert 'const hasSnap=hasDrop&&isNum(st.snap)' in html
    assert 'const dropName=detailed?"DROP · SNAP %":"DROP"' in html
    assert 'annot(dropDimX,(Y(st.Fpeak)+Y(st.Fval))/2+5,dropName,val,DTXT.snap,"center","drop",true)' in html
    assert 'const placed=annot(dropLayout.labelX,dropLayout.labelY,dropName,val' in html
    assert '"STEEPEST DROP",`${st.steep.toFixed(1)} gf/mm`' in html
    assert '"Steepest 0.10 mm drop"' not in html
    assert 'const CURVE_STROKE_WIDTH=3.5' in html
    assert 'const CONSTRUCTION_DASH=Object.freeze([5,4])' in html
    assert 'drawStroke(ap,FC.curve,CURVE_STROKE_WIDTH,1)' in html
    assert 'g.setLineDash(CONSTRUCTION_DASH);g.globalAlpha=featureAlpha("ramp"' in html
    assert 'g.setLineDash([3,4]);g.globalAlpha=featureAlpha("pcw",.82)' in html
    assert 'g.strokeStyle=featureColor(FC,"pcw",T);g.lineWidth=featureWidth("pcw",1.3)' in html
    assert 'g.setLineDash([3,4]);g.globalAlpha=featureAlpha("collapse",.82)' not in html
    assert 'g.lineWidth=CURVE_STROKE_WIDTH;g.beginPath();g.moveTo(X(steepA.x)' in html
    assert 'g.globalAlpha=featureFillAlpha("pcw")' in html
    assert 'g.globalAlpha=featureHatchAlpha("pcw")' in html
    assert 'for(let hx=pcwLeft-pcwHeight;hx<=pcwRight;hx+=10)' in html
    assert 'if(showVisuals&&detailed&&ap&&ap.x&&ap.x.length&&hasCollapse)' in html
    assert 'if(showVisuals&&detailed&&turnaround)' in html
    assert 'if(showVisuals&&detailed&&hasCollapse)' in html
    assert 'if(detailed&&isNum(st.dropRate))' in html
    assert 'if(showVisuals&&detailed&&isNum(st.steep)' in html
    assert 'if(detailed&&hasCollapse&&isNum(st.Epc))' in html
    assert 'if(detailed&&turnaround)for(const limit' in html
    assert 'const valleyFeature=detailed?"bottom":"drop"' in html
    assert 'if(detailed)dropLeaderAnchor={x:dropDimX,y:py}' in html
    assert 'dropDimX=detailed?(dropSpan>=32?bx-16:px+dropSpan/2):bx' in html
    assert 'annot(detailed?collapseX-14:collapseX,collapseY,"COLLAPSE",val,DTXT.collapse,detailed?"right":"center","collapse")' in html
    assert 'dropRateDimY=Math.max(plotTop+18,py-114)' in html
    assert 'function dropSnapAnnotationLayout(left,right,top,dropDimX,peakY,dropRateY,labelWidth)' in html
    assert 'const DIMENSION_INSIDE_ARROW_LENGTH=8' in html
    assert 'const DIMENSION_INSIDE_ARROW_HALF_WIDTH=3.2' in html
    assert 'const DIMENSION_OUTSIDE_ARROW_LENGTH=12' in html
    assert 'const DIMENSION_OUTSIDE_ARROW_HALF_WIDTH=4.8' in html
    assert 'const DIMENSION_OUTSIDE_LEADER=12' in html
    assert 'function verticalDimensionLayout(y1,y2,labelInside=false)' in html
    assert 'const requiredInside=2*DIMENSION_INSIDE_ARROW_LENGTH+(labelInside?28:4)' in html
    assert 'const arrowsOutside=span<requiredInside' in html
    assert 'const arrowLength=arrowsOutside?DIMENSION_OUTSIDE_ARROW_LENGTH:DIMENSION_INSIDE_ARROW_LENGTH' in html
    assert 'const arrowHalfWidth=arrowsOutside?DIMENSION_OUTSIDE_ARROW_HALF_WIDTH:DIMENSION_INSIDE_ARROW_HALF_WIDTH' in html
    assert 'const outsideExtent=DIMENSION_OUTSIDE_ARROW_LENGTH+DIMENSION_OUTSIDE_LEADER' in html
    assert 'dropDimension=verticalDimensionLayout(py,vy,!detailed&&showLabels)' in html
    assert 'g.moveTo(dropDimX,dropDimension.lineTop);g.lineTo(dropDimX,dropDimension.lineBottom)' in html
    assert 'g.lineTo(dropDimX-dropDimension.arrowHalfWidth,dropDimension.topBaseY)' in html
    assert 'g.lineTo(dropDimX-dropDimension.arrowHalfWidth,dropDimension.bottomBaseY)' in html
    assert 'x:dropDimX-10,y:dropDimension.lineTop-4,w:20,h:dropDimension.lineBottom-dropDimension.lineTop+8' in html
    assert 'Math.max(dropRateY+50,peakY-44,top+34)' in html
    assert 'const preferredClearance=28,minimumClearance=8' in html
    assert 'elbowX=dropLeaderAnchor.x,elbowY=endY' in html
    assert 'endX=dropLayout.side==="left"?placed.x+placed.tw+7:placed.x-7' in html
    assert 'g.lineTo(elbowX,elbowY);g.lineTo(endX,endY)' in html
    assert 'g.lineTo(dropLeaderAnchor.x-3.2,dropLeaderAnchor.y-8)' in html
    assert 'g.lineTo(dropLeaderAnchor.x+3.2,dropLeaderAnchor.y-8)' in html
    assert 'if(!dropDimension.arrowsOutside)' in html
    assert 'x:elbowX-6,y:Math.min(dropLeaderAnchor.y,elbowY)' in html
    assert 'x:Math.min(elbowX,endX),y:elbowY-6' in html
    assert '"STEEPEST DROP",`${st.steep.toFixed(1)} gf/mm`,DTXT.steep,"steep",18)' in html
    assert 'wallName="DETECTED FORCE-WALL ONSET"' in html
    assert 'wallVal=hasWall?`${displayFixed(st.travel,2)} mm`:"Not detected"' in html
    assert 'wallX=hasWall?X(st.travel):w-M.r' in html
    assert 'annot(wallOnLeft?wallX-14:wallX+14,h-M.b-12,wallName,wallVal,DTXT.travel' in html
    assert 'if(!detailed)hideStatsOut()' in html
    assert 'const externalStats=hasStats&&chartMode==="curves"&&!simplifiedGraphDisplay()&&statsCardGeom(ctx,single,w,h).external' in html
    assert 'function formatPercentileRank(value){return isNum(value)?`${value.toFixed(1)}th percentile`' in html
    assert "/ 100" not in html
    assert "function forceCurveHeaderLayout(w)" in html
    assert "function drawForceCurveHeaderMetric(" in html
    assert 'titleStats.weightIndex.toFixed(1)' in html
    assert 'titleStats.tactilityIndex.toFixed(1)' in html
    assert 'drawForceCurveHeaderMetric(g,T,FEAT[th],header,0,"WEIGHT INDEX"' in html
    assert 'drawForceCurveHeaderMetric(g,T,FEAT[th],header,1,"TACTILITY INDEX"' in html
    assert 'drawForceCurveHeaderMetric(g,T,FEAT[th],header,2,"DETECTED FORCE-WALL ONSET","FORCE-WALL ONSET",wall,"travel")' in html
    assert "Percentiles in the ${domeReferenceCount()}-dome released reference fleet" not in html
    tactility_profile = html.split("profileTactility:", 1)[1].split("]}", 1)[0]
    assert tactility_profile.index('p:"dg"') < tactility_profile.index('p:"sn"')
    assert tactility_profile.index('p:"sn"') < tactility_profile.index('p:"sd"')
    assert tactility_profile.index('p:"sd"') < tactility_profile.index('p:"dr"')
    assert (
        "Weight Index</b> is this dome’s weight percentile compared with the "
        "other domes tested."
    ) in html
    assert (
        "Tactility Index</b> is this dome’s tactility percentile compared with "
        "the other domes tested."
    ) in html
    assert "80 is not twice 40" not in html
    assert "Index scale note" not in html
    assert "INDEX_SCALE_NOTE" not in html
    assert "100 × average zero-based rank / 67" not in html
    assert "Part-assembly records are shown as Not calibrated" in html
    assert "complete frozen retest fleet" in html
    assert "review-only and not deployed" in html
    assert "ec-parts-dataset.xlsx" not in html
    assert "documentation/subjective-pilot/index.html" in html
    assert "25-dome pilot" in html
    assert "do not establish independent causal contributions" in html
    assert "same measurement cohort share raw acquisitions" in html


def test_png_export_has_png_only_unreal_keyboards_watermark(review_candidate):
    staged, _ = review_candidate
    html = staged["packs/viewer.staged.html"]
    assert "function drawExportWatermark(g,w,h){" in html
    assert 'const text="UNREAL KEYBOARDS"' in html
    assert 'g.fillStyle="rgba(28,36,34,.055)"' in html
    # One definition plus one call: the watermark is an export-only layer.
    assert html.count("drawExportWatermark(") == 2
    export_source = html.split("function exportPNG(){", 1)[1].split(
        "function copyShareLink", 1
    )[0]
    white_background = (
        "g.fillStyle=CANVAS_THEME.light.exportBg;g.fillRect(0,0,w,exportH);"
    )
    assert white_background in export_source
    assert export_source.index(white_background) < export_source.index(
        "drawExportWatermark(g,w,h);"
    ) < export_source.index('drawScene(g,w,h,{export:true,theme:"light"});')


def test_internal_perception_model_preserves_full_equations():
    model = perception.MODEL
    assert model["percentile_formula"] == (
        "100 * (average_zero_based_rank) / (N - 1)"
    )
    assert model["ties"] == "average_occupied_rank"
    assert model["between_reference_values"] == "linear_interpolation"
    assert model["outside_reference_range"] == "clamp_0_100"
    assert model["missing"] == "not_available_no_imputation"
    assert model["weight"]["primary_metric"] == "collapse_force_gf"
    assert model["tactility"]["primary_metric"] == "drop_gf"

    # Behavioral examples close the gap between a prose formula and the
    # executable authority: ties use their average occupied rank, intermediate
    # values interpolate linearly, endpoints clamp, and null is not imputed.
    reference = [10.0, 20.0, 20.0, 40.0]
    assert perception._mid_percentile(10.0, reference) == 0.0
    assert perception._mid_percentile(20.0, reference) == 50.0
    assert perception._mid_percentile(15.0, reference) == 25.0
    assert perception._mid_percentile(5.0, reference) == 0.0
    assert perception._mid_percentile(45.0, reference) == 100.0
    assert perception._mid_percentile(None, reference) is None


def test_review_viewer_runtime_is_null_safe_and_identity_safe(review_candidate, tmp_path):
    viewer = tmp_path / "viewer.review.html"
    viewer.write_text(review_candidate[0]["packs/viewer.staged.html"], encoding="utf-8", newline="\n")
    js = os.path.join(HERE, "viewer_review_runtime.js")
    env = dict(os.environ)
    env["NODE_PATH"] = _node_modules()
    for mode in ("missing", "malformed200"):
        run = subprocess.run(["node", js, str(viewer), mode], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=env, timeout=30)
        assert run.returncode == 0, f"{mode}:\n{run.stdout}\n{run.stderr}"
        result = json.loads(run.stdout.strip().splitlines()[-1])
        assert all(result.values()), {"mode": mode, **result}
