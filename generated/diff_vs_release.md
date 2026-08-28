# Generated-output diff — staged metrics-v4.2 vs current release artifacts

Classes (generated programmatically; 'identical' tolerance 1e-09):
`release-rounding` — the staged full-precision value rounds back to the stored release
value at (or below) its stored precision. Full-fleet JS/Python parity shows the two work
implementations are exactly equal on this fleet (endpoints fall on recorded knots), so
endpoint interpolation is a forward-looking safeguard, not a cause of current changes.
`median-change` — runfilter-v1.1 conventional-median membership change (Topre_45g only).
`small legacy position delta — cause unadjudicated` — a position aggregate differs from
the stored release value by <=0.003 mm. Step 2.2 labelled this `release-history drift`,
asserting a historical cause. No historical provenance proves that cause, so the label is
now neutral: the delta is observed, its origin is not adjudicated. Per-run JS/Python parity
is exact today; staged values are the corrected candidates.

## DynaCaps Light (DynaCaps_Light_35g, bt_0005)
- collapse_force_gf: 31.2 -> 35.91386666666667  [REVIEW (|d|=4.714)]
- collapse_travel_mm: 1.185 -> 1.3016666666666667  [REVIEW (|d|=0.1167)]
- valley_force_gf: 26.8 -> 30.01795238095238  [REVIEW (|d|=3.218)]
- valley_travel_mm: 2.975 -> 3.1366666666666667  [REVIEW (|d|=0.1617)]
- snap_pct: 14.2 -> 16.416749057010595  [REVIEW (|d|=2.217)]
- travel_mm: 3.915 -> 3.9283333333333332  [REVIEW (|d|=0.01333)]
- full_stroke_press_work_gf_mm: 109.0 -> 122.16709366666662  [REVIEW (|d|=13.17)]
- precollapse_work_gf_mm: 31.0 -> 37.029116249999994  [REVIEW (|d|=6.029)]
- drop_gf: 4.4 -> 5.89591428571429  [REVIEW (|d|=1.496)]
- drop_travel_mm: 1.79 -> 1.835  [REVIEW (|d|=0.045)]
- drop_rate_gf_per_mm: 2.5 -> 3.21672408326212  [REVIEW (|d|=0.7167)]
- norm_drop_rate_per_mm: 0.079 -> 0.08957411971600898  [REVIEW (|d|=0.01057)]
- steepest_drop_0p10mm_gf_per_mm: 4.8 -> 6.078809523809501  [REVIEW (|d|=1.279)]
- ramp_10_90_gf_per_mm: 16 -> 25.06264141151885  [REVIEW (|d|=9.063)]
## Dynacaps Heavy (Dynacaps_Heavy_55g, bt_0007)
- collapse_force_gf: 53.3 -> 53.2234  [REVIEW (|d|=0.0766)]
- travel_mm: 3.915 -> 3.91  [REVIEW (|d|=0.005)]
- full_stroke_press_work_gf_mm: 174.0 -> 173.25385824999995  [REVIEW (|d|=0.7461)]
- precollapse_work_gf_mm: 52.0 -> 50.781965875000004  [REVIEW (|d|=1.218)]
- drop_rate_gf_per_mm: 6.3 -> 6.207456011272269  [REVIEW (|d|=0.09254)]
- norm_drop_rate_per_mm: 0.118 -> 0.11662967647270059  [REVIEW (|d|=0.00137)]
- ramp_10_90_gf_per_mm: 33.2 -> 33.31368484902542  [REVIEW (|d|=0.1137)]
## BKE Redux Extreme 01 (BKE_Redux_v1_Extreme_01, bt_0008)
- collapse_force_gf: 131.5 -> 132.02869523809522  [REVIEW (|d|=0.5287)]
- collapse_travel_mm: 0.94 -> 0.9466666666666667  [REVIEW (|d|=0.006667)]
- valley_force_gf: 52.3 -> 52.24304285714286  [REVIEW (|d|=0.05696)]
- snap_pct: 60.3 -> 60.42924915333297  [REVIEW (|d|=0.1292)]
- travel_mm: 3.305 -> 3.3033333333333332  [small legacy position delta — cause unadjudicated]
- full_stroke_press_work_gf_mm: 309.0 -> 309.99494216666653  [REVIEW (|d|=0.9949)]
- precollapse_work_gf_mm: 105.0 -> 106.32115941666665  [REVIEW (|d|=1.321)]
- drop_gf: 79.3 -> 79.78565238095238  [REVIEW (|d|=0.4857)]
- drop_travel_mm: 1.905 -> 1.9033333333333333  [small legacy position delta — cause unadjudicated]
- drop_rate_gf_per_mm: 41.6 -> 41.92192410797165  [REVIEW (|d|=0.3219)]
- norm_drop_rate_per_mm: 0.316 -> 0.3175083640625419  [REVIEW (|d|=0.001508)]
- steepest_drop_0p10mm_gf_per_mm: 63.4 -> 65.19223809523815  [REVIEW (|d|=1.792)]
- ramp_10_90_gf_per_mm: 75.2 -> 75.1273126296851  [REVIEW (|d|=0.07269)]
## NiZ 65g (NiZ_Black_65g, bt_0009)
- collapse_travel_mm: 1.655 -> 1.6800000000000002  [REVIEW (|d|=0.025)]
- valley_force_gf: 65.9 -> 65.77074999999999  [REVIEW (|d|=0.1293)]
- valley_travel_mm: 3.185 -> 3.1675  [REVIEW (|d|=0.0175)]
- snap_pct: 12.8 -> 13.054219584844176  [REVIEW (|d|=0.2542)]
- travel_mm: 3.925 -> 3.9074999999999998  [REVIEW (|d|=0.0175)]
- full_stroke_press_work_gf_mm: 249.0 -> 247.99782712499987  [REVIEW (|d|=1.002)]
- precollapse_work_gf_mm: 91.0 -> 92.40610137499996  [REVIEW (|d|=1.406)]
- drop_gf: 9.7 -> 9.873757142857137  [REVIEW (|d|=0.1738)]
- drop_travel_mm: 1.53 -> 1.4874999999999998  [REVIEW (|d|=0.0425)]
- drop_rate_gf_per_mm: 6.3 -> 6.630018921475871  [REVIEW (|d|=0.33)]
- norm_drop_rate_per_mm: 0.084 -> 0.08765484121196465  [REVIEW (|d|=0.003655)]
- steepest_drop_0p10mm_gf_per_mm: 12.3 -> 11.394714285714258  [REVIEW (|d|=0.9053)]
- ramp_10_90_gf_per_mm: 55.1 -> 55.672509258376124  [REVIEW (|d|=0.5725)]
## Sony BKE Gray 01 (Sony_BKE_Gray_01, bt_0010)
- collapse_force_gf: 78 -> 67.8313  [REVIEW (|d|=10.17)]
- collapse_travel_mm: 1.29 -> 1.1066666666666667  [REVIEW (|d|=0.1833)]
- valley_force_gf: 29.8 -> 28.017866666666666  [REVIEW (|d|=1.782)]
- valley_travel_mm: 3.125 -> 3.016666666666667  [REVIEW (|d|=0.1083)]
- snap_pct: 61.8 -> 58.6905912432249  [REVIEW (|d|=3.109)]
- travel_mm: 3.15 -> 3.24  [REVIEW (|d|=0.09)]
- full_stroke_press_work_gf_mm: 181.0 -> 158.03232791666667  [REVIEW (|d|=22.97)]
- precollapse_work_gf_mm: 80.0 -> 60.54712116666667  [REVIEW (|d|=19.45)]
- drop_gf: 48.2 -> 39.81343333333333  [REVIEW (|d|=8.387)]
- drop_travel_mm: 1.835 -> 1.91  [REVIEW (|d|=0.075)]
- drop_rate_gf_per_mm: 26.3 -> 20.84419672955294  [REVIEW (|d|=5.456)]
- norm_drop_rate_per_mm: 0.337 -> 0.307277587940844  [REVIEW (|d|=0.02972)]
- steepest_drop_0p10mm_gf_per_mm: 62.4 -> 34.754666666666715  [REVIEW (|d|=27.65)]
## Sony BKE Brown 02 (Sony_BKE_Brown_02, bt_0013)
- valley_travel_mm: 3.055 -> 3.0566666666666666  [small legacy position delta — cause unadjudicated]
- travel_mm: 3.495 -> 3.4933333333333336  [small legacy position delta — cause unadjudicated]
## Topre Slider (baseline) (Topre_Slider_Black, bt_0015)
- drop_travel_mm: 2.095 -> 2.09625  [small legacy position delta — cause unadjudicated]
## Topre Silent (Type-S) Slider (Topre_Slider_Type-S, bt_0016)
- drop_travel_mm: 2.005 -> 2.0033333333333334  [small legacy position delta — cause unadjudicated]
## Topre Silent (Realforce) Slider (Topre_Slider_Silenced_Purple, bt_0017)
- collapse_travel_mm: 1.245 -> 1.2425  [small legacy position delta — cause unadjudicated]
## Topre Slider + 0.3 mm Poron (Topre_Slider_Black_Silenced_0.3mm_Poron, bt_0018)
- collapse_travel_mm: 0.98 -> 1.01  [REVIEW (|d|=0.03)]
- valley_travel_mm: 2.87 -> 2.875  [REVIEW (|d|=0.005)]
- snap_pct: 25.5 -> 25.311117832224767  [REVIEW (|d|=0.1889)]
- precollapse_work_gf_mm: 54.0 -> 55.28166150000001  [REVIEW (|d|=1.282)]
- drop_gf: 15.6 -> 15.490085714285716  [REVIEW (|d|=0.1099)]
- drop_travel_mm: 1.89 -> 1.865  [REVIEW (|d|=0.025)]
- norm_drop_rate_per_mm: 0.135 -> 0.1357164495025457  [REVIEW (|d|=0.0007164)]
- steepest_drop_0p10mm_gf_per_mm: 14.8 -> 14.683214285714321  [REVIEW (|d|=0.1168)]
- ramp_10_90_gf_per_mm: 27.3 -> 27.64936823790968  [REVIEW (|d|=0.3494)]
## Topre Slider + 0.5 mm Poron (Topre_Slider_Black_Silenced_0.5mm_Poron, bt_0019)
- collapse_force_gf: 67.6 -> 67.96520714285714  [REVIEW (|d|=0.3652)]
- collapse_travel_mm: 0.79 -> 0.8174999999999999  [REVIEW (|d|=0.0275)]
- valley_force_gf: 49.4 -> 49.59655  [REVIEW (|d|=0.1966)]
- snap_pct: 26.9 -> 27.026738689059364  [REVIEW (|d|=0.1267)]
- full_stroke_press_work_gf_mm: 205.0 -> 205.590258875  [REVIEW (|d|=0.5903)]
- precollapse_work_gf_mm: 47.0 -> 49.500436750000006  [REVIEW (|d|=2.5)]
- drop_gf: 18.2 -> 18.36865714285714  [REVIEW (|d|=0.1687)]
- drop_travel_mm: 1.835 -> 1.8125  [REVIEW (|d|=0.0225)]
- drop_rate_gf_per_mm: 9.9 -> 10.134477682036696  [REVIEW (|d|=0.2345)]
- norm_drop_rate_per_mm: 0.147 -> 0.14911295713873154  [REVIEW (|d|=0.002113)]
- steepest_drop_0p10mm_gf_per_mm: 23.9 -> 24.373357142857124  [REVIEW (|d|=0.4734)]
- ramp_10_90_gf_per_mm: 30.2 -> 30.70789568143951  [REVIEW (|d|=0.5079)]
## DynaCaps Slider + 0.3 mm Poron (Dynacaps_Slider_0.3mm_Poron, bt_0020)
- collapse_force_gf: 60.4 -> 60.293299999999995  [REVIEW (|d|=0.1067)]
- valley_force_gf: 45.3 -> 45.21789047619047  [REVIEW (|d|=0.08211)]
- travel_mm: 3.985 -> 3.983333333333333  [small legacy position delta — cause unadjudicated]
- norm_drop_rate_per_mm: 0.132 -> 0.13261072794441334  [REVIEW (|d|=0.0006107)]
- ramp_10_90_gf_per_mm: 43.7 -> 43.35994355657245  [REVIEW (|d|=0.3401)]
## DynaCaps Slider + 0.5 mm Silicone (Dynacaps_Slider_0.5mm_Silicone, bt_0021)
- collapse_force_gf: 61.4 -> 61.650828571428576  [REVIEW (|d|=0.2508)]
- collapse_travel_mm: 0.88 -> 0.86  [REVIEW (|d|=0.02)]
- valley_force_gf: 45.7 -> 45.644864285714284  [REVIEW (|d|=0.05514)]
- valley_travel_mm: 2.99 -> 2.995  [REVIEW (|d|=0.005)]
- snap_pct: 25.5 -> 25.957199162593078  [REVIEW (|d|=0.4572)]
- full_stroke_press_work_gf_mm: 194.0 -> 194.62513412500005  [REVIEW (|d|=0.6251)]
- precollapse_work_gf_mm: 47.0 -> 45.603353999999996  [REVIEW (|d|=1.397)]
- drop_gf: 15.7 -> 16.00596428571429  [REVIEW (|d|=0.306)]
- drop_travel_mm: 2.11 -> 2.135  [REVIEW (|d|=0.025)]
- drop_rate_gf_per_mm: 7.4 -> 7.4969387755102055  [REVIEW (|d|=0.09694)]
- norm_drop_rate_per_mm: 0.121 -> 0.1215793871784219  [REVIEW (|d|=0.0005794)]
- steepest_drop_0p10mm_gf_per_mm: 14.8 -> 15.052285714285745  [REVIEW (|d|=0.2523)]
- ramp_10_90_gf_per_mm: 30.2 -> 29.97705178612518  [REVIEW (|d|=0.2229)]
## DynaCaps Housing + Slider + 0.5 mm Silicone (DynaCaps_Parts, bt_0022)
- collapse_travel_mm: 0.975 -> 0.974  [small legacy position delta — cause unadjudicated]
## Topre 45g Aged (Topre_HHKB_Pro2_45g, bt_0023)
- drop_travel_mm: 2.095 -> 2.09625  [small legacy position delta — cause unadjudicated]

Summary: 16 identical, 130 release-rounding, 0 median-change, 10 small legacy position delta — cause unadjudicated, 96 REVIEW.
