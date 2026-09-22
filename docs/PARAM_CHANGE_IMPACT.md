# Parameter-change impact analysis
<!-- DOC VERSION: v1.1 | LAST UPDATED: 2026-09-03 | OWNER: principal -->

Quantifies the farmer-visible effect of the changes in SPEC v1.25–v1.26
(DECISIONS D-010, D-011, D-013, D-014 and the Phase 2 stage-adjusted-MAD fix).

## Method and its limitation

**This is a sensitivity sweep, not a live pipeline run.** No live weather was
available when this was produced (`api.open-meteo.com`, `archive-api.open-meteo.com`
and `api.weather.gov` are all unreachable from the analysis environment).

Rather than sample a handful of counties on one date, this sweeps the entire
decision space: every crop × every growth stage × depletion 0.00–0.95 in 0.01
steps, comparing pre-change and post-change parameters through the **real code
paths** (`kc_for_gdd_frac`, `adjusted_mad`, `build_narrative`) — not a
reimplementation.

That bounds the change rather than sampling it, which is stronger for
"how much does this alter advice". It does NOT substitute for a live run,
because it cannot confirm the pipeline ingests, persists and serves these values
correctly end to end. **A networked `alembic upgrade head && python -m app.nightly`
is still required before release.**

Fixed inputs: ET0 = 0.20 in/day (realistic NY mid-summer), AWC = 0.18 in/in
(NY state default), rain-free (worst case for irrigation timing).

---

## 1. Phase 2 — advisor now applies stage-adjusted MAD

The advisor previously used the raw `crops.mad_fraction`; the dashboard already
applied the stage adjustment. This was a live SPEC §4 v1.11 violation and the
last known advisor/dashboard divergence. Corn only, per D-009.

| stage | gdd_frac | MAD raw | MAD adjusted | depletion band where advice differs | transitions |
|---|---|---|---|---|---|
| seedling | 0.05 | 0.50 | 0.50 | — | none |
| vegetative | 0.30 | 0.50 | 0.50 | — | none |
| **pollination** | 0.56 | 0.50 | **0.30** | **0.20–0.49** (width 0.29) | HOLD→SCHEDULE, HOLD→IRRIGATE, SCHEDULE→IRRIGATE |
| **grain fill** | 0.76 | 0.50 | **0.40** | **0.31–0.49** (width 0.18) | HOLD→SCHEDULE, SCHEDULE→IRRIGATE |
| maturity | 0.95 | 0.50 | 0.50 | — | none |

**Magnitude at pollination:** MAD 0.50 → 0.30 is 1.30 in of soil water on a
36 in root zone at AWC 0.18. At ETc = 1.15 × 0.20 = 0.230 in/day, irrigation
now triggers **~5.6 days earlier** in a rain-free spell.

Every change is in the *more protective* direction, and only inside the two
yield-critical stages — which is what SPEC §4 v1.11 intends.

---

## 2. ETc change from the Kc corrections (D-010, D-013)

Percentage change in modelled crop water use, by crop and stage:

| crop | seedling | vegetative | pollination | grain fill | maturity |
|---|---|---|---|---|---|
| corn | — | — | — | **−14.6%** | **−33.3%** |
| soy | — | — | — | **−15.8%** | **−37.5%** |
| alfalfa | — | — | — | +2.6% | +5.9% |
| cover | — | — | — | — | — |
| potatoes | **+11.1%** | +3.1% | — | — | — |
| sunflower | — | — | — | **−12.1%** | **−36.4%** |
| cabbage | — | — | — | — | — |
| onions | — | — | — | — | — |
| sweet corn | — | — | — | +7.3% | **+16.7%** |

Notes:
- Corn/soy/sunflower **fall** late-season because their old `kc_end` values
  overstated a senescing canopy's water use.
- Sweet corn **rises** because it is cut green for fresh consumption, so its
  canopy is still transpiring at harvest (FAO-56 `Kc_end` 1.05).
- Seedling/vegetative/pollination were almost entirely unchanged **at the time
  this table was produced**, because those bands depend on `kc_initial` and
  `kc_mid` and no `kc_mid` had yet been changed. **D-014 has since corrected
  `kc_mid`** (corn 1.15 → 1.20, soy 1.10 → 1.15, alfalfa 1.05 → 0.95), which
  moves the curve everywhere above gdd_frac 0.10 — see §5.

---

## 3. Decision-flip bands from the crop-parameter corrections (D-013)

**10 of 45 crop-stage combinations can change advice.** All 10 belong to the
two crops whose depletion fraction `p` was corrected — the Kc changes alone
shifted no decisions at these inputs, because they act late-season where
depletion is usually already resolved.

| crop | stage | MAD old | MAD new | depletion band | transitions |
|---|---|---|---|---|---|
| potatoes | seedling | 0.450 | 0.350 | 0.25–0.44 | HOLD→SCHEDULE, SCHEDULE→IRRIGATE |
| potatoes | vegetative | 0.450 | 0.350 | 0.25–0.44 | HOLD→SCHEDULE, SCHEDULE→IRRIGATE |
| potatoes | pollination | 0.270 | 0.210 | 0.11–0.26 | HOLD→SCHEDULE, SCHEDULE→IRRIGATE |
| potatoes | grain fill | 0.360 | 0.280 | 0.19–0.35 | HOLD→SCHEDULE, SCHEDULE→IRRIGATE |
| potatoes | maturity | 0.450 | 0.350 | 0.25–0.44 | HOLD→SCHEDULE, SCHEDULE→IRRIGATE |
| onions | seedling | 0.500 | 0.300 | 0.20–0.49 | HOLD→SCHEDULE, HOLD→IRRIGATE, SCHEDULE→IRRIGATE |
| onions | vegetative | 0.500 | 0.300 | 0.20–0.49 | HOLD→SCHEDULE, HOLD→IRRIGATE, SCHEDULE→IRRIGATE |
| onions | pollination | 0.300 | 0.180 | 0.08–0.29 | HOLD→SCHEDULE, HOLD→IRRIGATE, SCHEDULE→IRRIGATE |
| onions | grain fill | 0.400 | 0.240 | 0.14–0.39 | HOLD→SCHEDULE, HOLD→IRRIGATE, SCHEDULE→IRRIGATE |
| onions | maturity | 0.500 | 0.300 | 0.20–0.49 | HOLD→SCHEDULE, HOLD→IRRIGATE, SCHEDULE→IRRIGATE |

Every transition moves toward irrigating **sooner**, for the two crops FAO-56
Table 22 identifies as least tolerant of depletion. Potatoes also gained a
smaller root zone (30 → 24 in, capped at FAO-56's maximum Zr), which reduces AW
and independently raises computed depletion.

**No decision changes** for corn, soy, alfalfa, sunflower, cabbage, sweet corn
or cover from D-013 — their `p` values were either already FAO-exact or left
deliberately more conservative.

---

## 4. What this analysis does NOT establish

1. **That the pipeline works end to end.** Requires a networked
   `alembic upgrade head && python -m app.nightly`, then before/after
   `today.etc` and `today.action` for real counties across stages.
2. **How often real counties sit inside the flip bands.** The bands are
   narrow (0.18–0.29 wide); whether NY counties actually land in them during a
   season is an empirical question this cannot answer.
3. **That the deliberate deviations are right for NY.** Root depths below
   FAO-56's Zr range (corn, alfalfa, sweet corn, cabbage) and corn/alfalfa `p`
   at 0.50 vs 0.55 were kept as conservative choices — reasoned, not measured.
4. **Anything about `cover`.** It has no FAO-56 reference; its parameters are
   unsourced (D-013).
5. **The effect of the D-014 `kc_mid` correction on decision flips.** §5 gives
   its ETc effect; the decision-flip sweep in §3 predates it and has not been
   re-run.

---

## 5. The D-014 `kc_mid` correction (added v1.1)

`kc_mid` was the last knowingly-wrong value in the math. Corrected against
FAO-56 Table 12: corn 1.15 → **1.20** (its old value was *sweet* corn's),
soy 1.10 → **1.15**, alfalfa 1.05 → **0.95**. Sunflower's 1.10 sits inside
Table 12's printed 1.0–1.15 range, so it was not touched.

Unlike `kc_end`, `kc_mid` is load-bearing across most of the season: it
terminates the vegetative ramp (gdd_frac 0.10–0.50), *is* the pollination
plateau (0.50–0.62) and originates the grain-fill ramp (0.62–0.90). So ETc
moves everywhere above gdd_frac 0.10.

Percentage change in modelled crop water use, by crop and stage:

| crop | seedling | vegetative (0.30) | pollination | grain fill (0.76) | maturity |
|---|---|---|---|---|---|
| corn | — | **+3.4%** | **+4.3%** | **+2.9%** | — |
| soy | — | **+3.3%** | **+4.5%** | **+3.1%** | — |
| alfalfa | — | **−6.9%** | **−9.5%** | **−5.1%** | — |

Computed through `kc_for_gdd_frac` against the pre-change coefficients, not
estimated. The ramp-stage percentages are smaller than the plateau's because
each ramp starts from an unchanged `kc_initial`, so only part of a ramped value
moves.

Seedling (`kc_initial`) and maturity (`kc_end`) are unchanged by construction.

**Direction matters more than magnitude here.** Corn's +4.3% at pollination is
small in percentage terms but it is an *under*-estimate being removed, at the
stage carrying STAGE_WEIGHTS 1.5 and a stage-adjusted MAD factor of 0.60 — the
one place in the season where being wrong low costs yield. Alfalfa moves the
other way: it had been over-stated, so the model will now advise irrigation
slightly later for it.

**Effect on the SPEC §4 authoritative example:** irrigation triggers on the
same day (day 3), but depletion reaches 0.540 instead of 0.533 and the refill
rises 3.12 → 3.168 in. No decision-flip sweep was re-run for this change —
see §4.5.

## Changelog
- v1.1 (2026-09-03): Added §5 (D-014 `kc_mid` correction); corrected §2's
  now-false claim that no `kc_mid` had been changed.
- v1.0 (2026-09-03): Initial analysis covering SPEC v1.25–v1.26.
