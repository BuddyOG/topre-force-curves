# Independent test-imp 1.1.4 epoch audit

Overall result: **PASS**

This audit imports the hash-verified final `test_imp` 1.1.4 source directly. It does not reimplement intake rules and does not modify the raw cache, Git repository, generator configuration, or viewer code.

## Identity and raw evidence

- Frozen commit: `6e86ac1955a0c566c7aae521705e51371992ba8a`
- test-imp identity: `1.1.4` / `metrics-v4.2` / `intake-qc-v1.4`
- Executable SHA-256: `351607fffe30eb6da8c7612e3e1bdfad0e3a737804e8f109bbd89c8d1a64854e`
- Release ZIP SHA-256: `b1ccdaba5c4ec76b7a8516c4e8c8109c26f2cb58b0f60f49a5c5fcf9a031b284`
- Source manifest SHA-256: `0cc31a5a4ac68108377384337d1fba662ac5c22fb9c14ee37ecc75dba74d21dd` (30 checked entries)
- Release manifest SHA-256: `a4b6827de92e01bde043265f2569439fe9daa19e18a453bed956e77d6584a7b3` (5 checked entries)
- Raw semantic paths: 184
- Unique physical acquisitions: 180
- Byte-identical alias acquisitions: 4
- Full materialized Git snapshot: 189 files, tree SHA-256 `ab3ebbf03c3f5b3b7003c3442d6bce687459a0803c5eff85707a1bc359d870e1`
- Live repository stable and clean during audit: True

The four aliases are the same four Topre acquisitions under two separate semantic records (`Topre_HHKB_Pro2_45g` and `Topre_Slider_Black`). They remain separate interpretations but count as four—not eight—independent observations.

## Intake outcome

- Semantic cohorts: 76 (independent measurement cohorts: 75)
- Individually acceptable paths: 184 / 184
- Retained paths after Fc/xc rules: 184 / 184
- Omitted for individual failure: 0
- Omitted as Fc/xc outlier: 0
- Mixed-population stops: 0
- Minimum-two failures: 0
- Preferred-speed advisory paths: 0
- Hard protocol-failure paths: 0
- RAMP review paths: 0 semantic / 0 independent
- Metric-local-null paths: 0

## Predecessor-epoch Topre R2 45g retest impact

This is a descriptive epoch-to-epoch comparison, not a QC failure and not a claim about why the measurements changed.

- Predecessor: `8816ffbf80ce7fd349a1a73893ce63cd5b7ad3d2` with 3 retained runs
- Candidate: `6e86ac1955a0c566c7aae521705e51371992ba8a` with 2 retained runs
- Retained-membership delta: -1
- Retired path: Topre_R2_45g/DataLog_3.csv
- Same-path replacement blobs: 2
- Candidate RAMP values: [32.80497849259488, 33.013029351038725] gf/mm
- Formal RAMP review evaluated: False (requires 3 numeric retained runs; this two-run cohort therefore cannot emit that advisory)

| Metric | Predecessor | Candidate | Absolute delta | Relative delta |
|---|---:|---:|---:|---:|
| `collapse_force_gf` | 48.06120952380953 | 56.68564285714285 | 8.624433333333322 | 17.944686% |
| `collapse_travel_mm` | 1.2216666666666667 | 1.09 | -0.1316666666666666 | -10.777626% |
| `valley_force_gf` | 35.27088571428572 | 41.19117142857142 | 5.920285714285704 | 16.785192% |
| `valley_travel_mm` | 3.341666666666667 | 3.2 | -0.1416666666666666 | -4.239401% |
| `snap_pct` | 26.611999809157297 | 27.334006114190693 | 0.7220063050333962 | 2.713085% |
| `travel_mm` | 3.956666666666667 | 3.9575 | 0.0008333333333330195 | 0.021061% |
| `full_stroke_press_work_gf_mm` | 154.6347294166666 | 187.5858002500001 | 32.95107083333349 | 21.308972% |
| `precollapse_work_gf_mm` | 45.31721166666666 | 52.46184987500001 | 7.144638208333355 | 15.765838% |
| `drop_gf` | 12.790323809523807 | 15.49447142857143 | 2.704147619047623 | 21.142136% |
| `drop_travel_mm` | 2.12 | 2.11 | -0.010000000000000231 | -0.471698% |
| `drop_rate_gf_per_mm` | 6.032979483672862 | 7.343873664788112 | 1.3108941811152501 | 21.728802% |
| `norm_drop_rate_per_mm` | 0.125527250307629 | 0.1295519370804818 | 0.004024686772852781 | 3.206226% |
| `steepest_drop_0p10mm_gf_per_mm` | 10.299761904761908 | 12.294071428571414 | 1.9943095238095054 | 19.362676% |
| `ramp_10_90_gf_per_mm` | 39.78375411082334 | 32.909003921816804 | -6.874750189006534 | -17.280295% |

The two candidate runs agree with each other under the importer replicate rules. The table intentionally preserves the material predecessor-to-candidate shifts; those shifts do not alter the importer decision.

## Generator comparison

- Status: **pass**
- Dataset manifest: pass
- Retained-run decisions: pass
- Per-run full-precision evidence: pass
- Generated-manifest/decision/provenance bindings: pass
- Maximum scalar delta: 1.4210854715202004e-14
- Numeric tolerance: 1e-12

## Mismatch summary

- Total reported mismatches: 0

Detailed path-, hash-, decision-, metric-, cohort-, and alias-level evidence is in `test_imp_1_1_4_epoch_audit.json`; compact run and cohort tables are in the adjacent CSV files.
