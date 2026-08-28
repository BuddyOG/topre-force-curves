# Conventional vs legacy median — runfilter centre comparison

runfilter-v1.1 adopts `median_conventional` (even n: average of the middle pair);
`median_upper_middle_legacy` (sorted[n//2]) is retained for this comparison only.
Centres, per-run deviations and threshold decisions are in median_comparison.json.

| Set | n | Fc centre conv / legacy (gf) | xc centre conv / legacy (mm) | membership change |
|---|---|---|---|---|

## Membership changes

Only even-run sets can differ between conventions.
