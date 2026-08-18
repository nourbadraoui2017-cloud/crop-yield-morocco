# Progress Log

Track work here. One entry per session — date, what got done, what's next, any blockers.

## Build order (from README)

- [x] 0. Check historical yield data availability (region/crop/years) — determines real timeline
- [x] 1. Pull and visualize NDVI data for the test region via GEE
- [x] 2. Merge NDVI with historical rainfall/temperature + yield data (NDVI+yield done; weather still pending)
- [x] 3. Train and validate baseline regression model (test on unseen years)
- [x] 4. Wrap in a simple Streamlit dashboard

---

## Log

### 2026-08-12
- Set up project repo structure (README, folders, git init). Pushed to GitHub:
  github.com/nourbadraoui2017-cloud/crop-yield-morocco
- Researched historical wheat yield data availability (step 0):
  - National-level data (1961-present) confirmed available via Ministry of
    Agriculture / World Bank — good enough to sanity-check any model.
  - Regional-level data: HCP publishes "Annuaires statistiques régionaux" and
    "Chiffres clés régionaux" (confirmed these categories exist on hcp.ma),
    and the Ministry publishes "Agricultures en Chiffres" annually. Actual
    PDFs weren't parseable via plain web fetch (likely scanned/complex
    layout) — need to download + parse programmatically to know exactly
    how many years of region-level yield data exist. This is real work,
    not just a lookup — treating it as part of Week 1-2 build, not a
    pre-check that blocks starting.
- Decision: don't let step 0 fully block step 1. Running two tracks in
  parallel — NDVI pull (step 1) can start immediately since it doesn't
  depend on resolving yield data first.
- Blocker: need target region confirmed, and a Google Earth Engine account
  (personal Google login — can't be done by Claude).
- Next: user picks region + sets up GEE account. Claude writes (a) the GEE
  NDVI pull script and (b) a script to download/parse the HCP + Ministry
  PDFs for actual regional yield data.
- Region confirmed: **Rabat-Salé-Kénitra**.
- Wrote src/pull_ndvi.py (GEE + geemap, Sentinel-2 NDVI, 10-day composites
  per growing season Nov-Jun) and src/parse_yield_pdfs.py (downloads +
  scans HCP/Ministry PDFs for region+crop+yield keyword matches, extracts
  candidate tables). Also added requirements.txt.
  NEITHER SCRIPT HAS BEEN RUN YET — the sandbox this was written in has
  no general internet access and no GEE credentials, so both are
  untested. Run them in Colab (real internet + your GEE login) and log
  what actually happens.
- Important caveat baked into pull_ndvi.py: Sentinel-2 harmonized SR
  only reliably covers ~2017 onward, so NDVI history caps out around
  8-9 growing seasons regardless of how far back yield data goes. That
  ceiling — not the yield data — may end up being the real limit on
  training set size. Worth knowing before step 2 (merging datasets).
- Blocker: still waiting on GEE account creation (user in progress).
- Next: user finishes GEE signup, then run pull_ndvi.py and
  parse_yield_pdfs.py in Colab, fix whatever breaks, log real results
  here (especially: how many years of matched NDVI+yield data end up
  usable — that's the number that determines if the modeling approach
  needs to change).

### 2026-08-13 (approx, session continued)
- GEE account created (non-commercial registration, project ID:
  `crop-yield-morocco`). Switched dev environment from Colab to local
  VS Code + venv per user preference — works fine since Earth Engine
  computes server-side; used `auth_mode='localhost'` for local auth,
  smoother than Colab's popup flow.
- **STEP 1 DONE.** src/pull_ndvi.py successfully pulled NDVI for all 8
  growing seasons (2017/18 through 2024/25), 192 rows total, saved to
  data/raw/ndvi_rabat_sale_kenitra.csv + chart at
  data/processed/ndvi_by_season.png. No gaps in the final run.
  - Bug fixed along the way: chaining a second `.filterDate()` call onto
    an already-filtered ImageCollection was silently returning 0 images
    for every window, even for seasons independently confirmed to have
    hundreds of images. Fixed by rebuilding each 10-day window's
    ImageCollection query from scratch instead of narrowing a
    pre-filtered one. Root cause not fully confirmed, but the rebuild
    is more robust regardless.
  - Region is still the rough bounding box fallback (not a precise
    admin boundary) — fine for this stage, worth refining later.
  - Visual sanity check: 2020/21 and 2023/24 show strong sustained
    greenness (peaks >0.45-0.5); 2021/22 and 2022/23 stay low and
    erratic (rarely >0.35) — consistent with known drought years.
    NDVI signal looks real, not noise.
- Next: run src/parse_yield_pdfs.py the same way (locally, in this
  same venv) to resolve step 0 for real, then move to step 2 (merge
  NDVI + weather + yield into one training table).

### 2026-08-13 (continued)
- src/parse_yield_pdfs.py (national Ministry PDF): 0 useful matches.
  That document turned out to be a glossy national highlights brochure
  (charts, not tables) with no regional breakdown and no per-hectare
  yield figures ("rendement"/"quintal"/"qx/ha" essentially absent).
  Not the right source -- abandoned in favor of HCP's regional annuaire.
- Found the real source: HCP's Annuaire Statistique Régional (ASR) for
  Rabat-Salé-Kénitra, published yearly, listed back to 2008 at
  https://www.hcp.ma/region-rabat/Publications_r3.html . Downloaded
  ASR 2023 (covers the 2021-2022 growing campaign): page 39 has clean
  tables -- area (Ha) and production (tonnes) of cereals, PER PROVINCE
  (Salé, Skhirate-Témara, Khémisset, Kénitra, Sidi Kacem, Sidi Slimane),
  broken out by crop (Blé Dur, Blé Tendre, Orge, Mais, Riz). No literal
  "rendement" column, but yield = production / area, which is exactly
  the standard definition anyway.
- **STEP 0 largely resolved for at least one year.** Wrote
  src/extract_cereal_table.py to parse this table programmatically.
  V1 (pure regex on extracted text) silently dropped several provinces:
  French thousand-separator formatting ("20 000") is text-ambiguous
  when two adjacent column values both happen to be clean 3-digit
  groups (e.g. "20 000 117 300" reads identically to one number as to
  two) -- no way to disambiguate from text alone.
  V2 (current): uses word x-coordinates instead of text. Verified
  empirically: gaps between fragments of the same number are ~1.6pt;
  gaps between different columns are always 35pt+ -- a reliable
  threshold (used 10pt) to correctly cluster words into columns
  regardless of digit-grouping coincidences. Now correctly extracts
  all 7 rows (6 provinces + Total) from both tables. Computed yields
  for 2021-2022 range 0.5-2.7 t/ha across provinces/wheat types --
  consistent with known national ranges (0.4-2.4 t/ha) and with 2021/22
  being a known drought year. Numbers look real.
- Next: generalize extract_cereal_table.py to loop over every available
  ASR year (2008-2023, URLs already listed on the HCP regional
  publications page) instead of just the hardcoded 2023 one. Table
  page number and exact layout may shift by year -- need to locate the
  table dynamically per PDF (e.g. by searching for the
  "SUPERFICIE DES CULTURES DES CEREALES" title) rather than assuming
  page 39 always. This will give the real answer to "how many years of
  matched NDVI (2017+) and yield data overlap" -- the number that
  determines the final training set size and whether the modeling
  approach needs to change.

### 2026-08-13 (continued further)
- Generalizing to all years hit a second structural surprise: the table
  layout itself changed over time, not just page numbers.
  - 2023 format (already working): provinces as ROWS, crops as
    COLUMNS, area+production tables on the SAME page.
  - ~2016-2020 format (older): crops as ROWS (". Blé Dur", ". Blé
    Tendre"), provinces as COLUMNS (with Rabat+Salé+Skhirate-Témara
    merged into ONE combined column instead of 3 separate), and
    area+production tables often on DIFFERENT (adjacent) pages.
  - Wrote src/extract_cereal_table_old_format.py for the second format,
    reusing the same x-coordinate gap-clustering technique (GAP_THRESHOLD
    still works -- it's about physical spacing, not table orientation).
  - Wrote src/build_full_yield_dataset.py to try both parsers per year
    and combine whatever works. Also fixed a cosmetic bug: campaign
    year labels sometimes extracted reversed ("2015-2014" instead of
    "2014-2015") due to bidi text extraction next to Arabic -- fixed
    by detecting and swapping when year1 > year2.
- **RESULT: 74 rows across 6 real growing seasons**: 2014-2015,
  2015-2016, 2016-2017, 2017-2018, 2018-2019, and 2021-2022 (wheat
  area, production, computed yield, per province, for Blé Dur and Blé
  Tendre separately). Saved to
  data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv
- 2008-2015 annuaires use yet a THIRD format/page structure that
  neither parser handles -- diminishing returns, decided not to chase
  further for now (see note below on why 6 seasons is enough to start).
  2008 specifically also has a corrupted PDF (decompression error).
- **Key number for the model**: cross-referencing against NDVI coverage
  (2017/18 through 2024/25, from src/pull_ndvi.py), only 3 seasons have
  BOTH real NDVI and real yield data so far: 2017-2018, 2018-2019, and
  2021-2022. The 2014-2017 yield-only seasons predate reliable
  Sentinel-2 SR coverage for this region, so they can't be used for
  NDVI-based training directly (though useful as historical/trend
  context). 3 overlapping seasons is a very small training set --
  worth remembering when picking the model in step 3 (favors a very
  simple baseline, strict regularization, leave-one-season-out
  validation; not enough data yet for tree ensembles to add value).
- STEP 0: DONE (multi-year regional data resolved).
- Next: build the actual merge (step 2) -- join
  data/raw/ndvi_rabat_sale_kenitra.csv with
  data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv on
  matching season/campaign, producing one training-ready table. Only
  the 3 overlapping seasons will have a usable label, but all 8 NDVI
  seasons are worth keeping in the merged file for context/plotting.

### 2026-08-13 (continued further still)
- Found and fixed a real bug in extract_cereal_table_old_format.py:
  for 3 of the 5 old-format years (2016/2017/2018 annuaires -> campaigns
  2014-15/2015-16/2016-17), the area AND production tables happen to sit
  on the SAME page. The code was searching the whole page for both,
  so it read the identical rows twice -- yield came out as exactly
  1.000 for all three (production == area), which was the tell that
  something was wrong. Fixed by splitting the page vertically at the
  "PRODUCTIONS" title's y-position when both tables share a page (same
  technique already used for the 2023 format). Re-ran the full
  pipeline: those 3 years now show real, distinct yields (2.64, 1.28,
  2.89 t/ha) -- sensible range, no longer suspicious.
- **STEP 2 DONE.** Wrote src/build_training_table.py: collapses the 192
  raw NDVI rows into per-season summary features (peak NDVI, mean NDVI,
  NDVI during the drought-sensitive growth stage Feb-Apr, NDVI during
  establishment Nov-Dec), collapses yield data to one region-level
  number per season (using the "Total" province row, Ble Dur + Ble
  Tendre combined), and merges both on season. Saved to
  data/processed/training_table.csv.
- Real signal check on the only 3 seasons with both NDVI and yield
  (2017-18, 2018-19, 2021-22): 2021-22 has both the lowest NDVI (peak
  and growth-stage) AND the lowest yield of the three -- consistent
  with it being a known drought year. Small sample, but the direction
  of the relationship is exactly what the model needs to learn. Good
  sign, not proof.
- Weather data (NASA POWER, rainfall/temperature) NOT yet pulled --
  still a to-do, would add real predictive signal beyond NDVI alone.
- Next: either (a) look for 1-2 more HCP annuaire editions to fill the
  2019-20/2020-21 campaign gap (would raise the usable training set
  from 3 to potentially 5 seasons -- meaningfully better for step 3),
  or (b) proceed to step 3 (baseline model) with just 3 seasons,
  accepting it's more a proof-of-concept than a real trained model at
  this sample size.

### 2026-08-13 (continued, final push of the day)
- Checked HCP directly: no annuaire edition exists for 2021 or 2022
  (list jumps straight from 2020 to 2023) -- likely a COVID-era gap.
  So 2019-20/2020-21 campaigns are permanently unavailable from this
  source; 3 overlapping seasons was a hard ceiling with Sentinel-2 alone.
- Instead extended NDVI coverage BACKWARD using Landsat 8 (available
  since 2013, vs Sentinel-2's ~2017 start). Wrote
  src/pull_ndvi_landsat.py -- per-image NDVI (not 10-day windows, since
  Landsat's 16-day revisit is too sparse for that), same summary
  features as the Sentinel-2 pipeline (peak, mean, growth-stage mean,
  establishment mean).
- **Important data-quality catch**: Landsat NDVI values run
  systematically higher than Sentinel-2's for the same seasons (e.g.
  peak ~0.68 vs ~0.45) -- different sensor, different bands/resolution.
  Mixing both sensors directly in one training set would have taught
  the model a fake "old years vs new years" pattern that's actually
  just a sensor artifact, not a real crop signal -- dangerous with only
  6 data points. Fix: recomputed Landsat NDVI for ALL 6 yield seasons
  (including 2017-18/2018-19/2021-22, which already had Sentinel-2
  data) so the whole training set uses ONE consistent sensor. Sentinel-2
  stays the plan for live/future predictions once deployed (better
  resolution + revisit); Landsat is specifically for building a
  consistent historical training set.
- **STEP 2 FULLY DONE.** Wrote src/build_training_table_landsat.py:
  merges the 6-season Landsat NDVI features with the 6-season yield
  data. Result: data/processed/training_table_landsat.csv, 6 of 6
  yield seasons matched (up from 3 of 8 with Sentinel-2 alone).
- **Strong sanity check**: ranking the 6 seasons by growth-stage NDVI
  (Feb-Apr) vs ranking by actual yield gives almost the same order --
  only 2014 and 2016 swap places. For just 6 points, that's a
  near-perfect monotonic relationship (~0.94 rank correlation) --
  strong evidence NDVI is a real, usable predictor here, not noise.
  Doesn't guarantee the model will generalize well, but it's a good sign.
- THIS is the real training table for step 3, not the earlier
  Sentinel-2-only training_table.csv (which only had 3 usable rows).
- Next: step 3 -- train and validate a baseline model (linear
  regression on the NDVI features) using leave-one-season-out
  cross-validation across these 6 seasons. Optionally pull NASA POWER
  rainfall data first to add as an extra feature (still not done).

### 2026-08-18

- **STEP 3 DONE.** Wrote src/train_baseline_model.py: compares several
  linear models (each NDVI feature alone, peak+growth_stage combined,
  all 4 features with plain LinearRegression, all 4 features with
  Ridge at alpha 0.1/1.0/10.0), all validated with leave-one-out (6
  seasons = LOO is equivalent to leave-one-season-out here).
- Decided against pulling NASA POWER weather data first -- would need
  a new pull + re-merge for uncertain benefit on only 6 points; kept
  scope to NDVI-only for this baseline. Can revisit later if the model
  needs more signal.
- **Winner: `ndvi_peak` alone.** MAE = 0.169 t/ha, RMSE = 0.175 t/ha,
  R² = 0.921 (LOO). `ndvi_growth_stage_mean` alone close second (MAE
  0.178, R² 0.872), matching the rank-correlation hint from step 2.
  The 2-feature combo (peak + growth_stage) did NOT beat peak alone
  (MAE 0.211) -- more features isn't automatically better even at n=2
  with only 6 rows.
- **Concrete overfitting example**: all-4-features LinearRegression
  collapsed (MAE 1.165, R² -5.611) -- for the 2016-2017 held-out
  season it predicted -0.70 t/ha, a physically impossible negative
  yield. With 5 training rows and 4 features per LOO fold, the model
  has almost as many parameters as data points and fits noise instead
  of signal. Ridge regularization tamed this somewhat (alpha=0.1 got
  R² back up to 0.232) but still underperformed the single-feature
  model. This is the concrete version of the "small data = simple
  model" rule discussed before starting step 3.
- Script auto-selects the best LOO model, refits it on all 6 seasons
  (full data, no held-out row -- appropriate once you're done
  evaluating and want the best real model), and saves it:
  models/baseline_model.joblib + models/baseline_model_info.json
  (features, coefficients, intercept, LOO metrics). Ready to be loaded
  directly by the Streamlit dashboard in step 4.
- Honest caveat to keep in mind: R²=0.92 on 6 points is encouraging
  but fragile -- ranking could shift with one more season of data.
  This is a proof-of-concept baseline, not a production-grade model.
- Next: step 4 -- Streamlit dashboard that loads models/baseline_model.joblib
  and shows predicted yield vs. historical average.
- **STEP 4 DONE.** Wrote dashboard/app.py: loads the saved model, a
  slider per model feature (bounded by the historical range), live
  metrics (predicted yield vs 6-season historical average), a bar
  chart (history in blue, current prediction in orange, dashed
  historical-average line), and expanders for model details (MAE/R²,
  caveat about fragility at n=6) and the raw historical table. Tested
  end to end with `streamlit run dashboard\app.py` -- works.
- Realized the dashboard slider alone is just a manual "what-if"
  simulator, not a live prediction -- flagged by Nour. Two real
  constraints found: (a) the 2026-2027 season hasn't started yet (no
  satellite imagery exists for it), so it can't be predicted today;
  (b) the model is trained on Landsat NDVI specifically, and Sentinel-2
  NDVI runs systematically lower for the same ground truth -- feeding
  Sentinel-2 values into this model directly would bias predictions
  down. A Sentinel<->Landsat calibration bridge is needed before doing
  live Sentinel-2-based predictions in-season; not built yet.
- Instead wrote src/predict_current_season.py: pulls real Landsat NDVI
  for the most recent COMPLETED season (2025-2026, harvested
  May-June 2026) by reusing get_season_ndvi_points/summarize_season
  from pull_ndvi_landsat.py, then runs it through the saved model.
  Result: ndvi_peak = 0.719 (a new high, above the 2016-2017 record of
  0.693 in training) -> predicted yield 3.187 t/ha, above every
  historical season including the best one (2017-2018, 3.02 t/ha).
  Saved to data/processed/prediction_2025_2026.csv.
- This is an extrapolation (ndvi_peak beyond the training range), so
  the LOO MAE of 0.169 doesn't strictly apply -- flagged as less
  reliable than an interpolated prediction. Sanity-checked against real
  news: 2025-2026 was confirmed (multiple sources, Aug 2026) as an
  exceptional rain-recovery season after 7 years of drought, national
  cereal harvest ~90M quintaux (more than double prior year), and
  Rabat-Salé-Kénitra production specifically up >25%. Directionally
  validates the model; the exact t/ha figure remains unverified until
  HCP eventually publishes the matching annuaire (likely 1-2 years
  out).
- **MVP (steps 0-4 from README) is now functionally complete end to
  end**: real satellite data -> real historical yield data -> trained
  validated model -> working dashboard -> one real held-out prediction
  that lines up with independent news reporting.
- **DEPLOYED.** Dashboard rewired to auto-load the latest
  data/processed/prediction_*.csv and show it in its own green panel,
  clearly separated from the orange manual NDVI simulator (real vs
  hypothetical, no longer conflated). Adjusted .gitignore
  (data/processed/* + *.csv were blocking the two small files the
  dashboard needs -- added explicit exceptions for
  training_table_landsat.csv and prediction_*.csv; raw PDFs stay
  ignored). Pushed to GitHub, deployed on Streamlit Community Cloud.
  Had to switch the repo from private to public first -- Streamlit's
  GitHub App was never installed on Nour's account (confirmed via
  github.com/settings/installations showing zero installed apps), and
  troubleshooting the App-installation flow through GitHub's UI didn't
  resolve it; going public was the pragmatic fix given there's nothing
  sensitive in the repo (no secrets committed) and it's a CV project
  anyway.
  Live at: https://crop-yield-morocco-hfxswyh57ja2zvgqztz2aj.streamlit.app
- **STEP 3bis: NASA POWER weather features added.** Wrote
  src/pull_weather_nasa_power.py -- free API, no key/account needed
  (unlike GEE), pulls daily precipitation (PRECTOTCORR) and temperature
  (T2M) for the region's bbox centroid (34.2N, -6.25E), community=AG.
  Saved to data/processed/weather_features.csv (rain + temp totals/means
  for the whole season, growth-stage Feb-Apr, and establishment Nov-Dec).
- Explored broadly first (src/train_model_with_weather.py, a scratch
  comparison script, not part of the pipeline): 5 weather features
  alone + 5 combined with ndvi_peak, 10 candidates total. Winner:
  ndvi_peak + rain_establishment_mm, MAE=0.109 (vs 0.169 for ndvi_peak
  alone) -- but flagged immediately as a multiple-comparisons risk
  (testing 10 models on 6 validation points inflates the odds that a
  "winner" is partly luck). Agronomically plausible though: early-season
  rain (germination/establishment) is complementary information to
  NDVI (overall vigor later in the season), not redundant with it.
- Folded this candidate into the OFFICIAL pipeline script
  (src/train_baseline_model.py) instead of keeping the exploration
  separate -- it now merges weather_features.csv when present, adds
  rain_establishment_only and peak_and_rain_establishment to the same
  candidate pool as all the NDVI-only models from step 3, and prints an
  explicit "multiple comparisons" warning whenever the auto-selected
  winner has more than 1 feature (so the caveat is visible every run,
  not just talked about once). Ran it: **peak_and_rain_establishment
  won again** across the full pool of 11 models (MAE=0.109, R²=0.952)
  -- replaced models/baseline_model.joblib.
- Updated src/predict_current_season.py and dashboard/app.py to match:
  the prediction script now also pulls NASA POWER weather for the
  target season (reusing fetch_season_weather/summarize_season from
  pull_weather_nasa_power.py) and builds its input from whatever
  info["features"] actually lists, so it stays correct if the model
  changes again. The dashboard's load_data() now merges
  weather_features.csv too (needed so the simulator can show a slider
  for rain_establishment_mm, not just ndvi_peak), and shows the same
  multiple-comparisons warning in the model details panel.
- Re-ran the 2025-2026 real prediction with the new model: **3.114
  t/ha** (vs 3.187 with the old ndvi_peak-only model -- close, both
  well above the historical average, reassuring agreement between the
  two). Notable: rain_establishment_mm for 2025-2026 (275.87mm) is
  ALSO slightly above the training max (273.76mm in 2014-2015), so
  this prediction extrapolates on both features now, not just one --
  reinforces rather than contradicts the existing "interpret with
  caution" caveat.
- **Sentinel-2 <-> Landsat calibration attempted.** Wrote
  src/calibrate_sentinel_landsat.py: fits a simple linear correction
  (ndvi_peak_landsat_equivalent = -0.076 + 1.619 * ndvi_peak_sentinel)
  on the 3 seasons where both sensors were computed (2017-18, 2018-19,
  2021-22), R²=0.870 on those calibration points. Saved to
  models/sentinel_to_landsat_calibration.json.
- **Validation result: works in principle, not precise enough to trust
  yet.** Compared yield predictions using real Landsat vs
  Sentinel-2-corrected NDVI for the same 3 seasons: 2021-2022 matched
  closely (0.019 t/ha apart), but 2017-2018 and 2018-2019 differed by
  0.245 and 0.264 t/ha respectively -- bigger than the yield model's
  own claimed MAE (0.109). Only 3 calibration points (2 parameters, ~1
  real degree of freedom) is genuinely too thin to trust for real
  decisions; treat this bridge as a working proof-of-concept, not
  production-ready. Would need more overlap seasons (impossible to get
  more historically since Sentinel-2 only starts ~2017 and yield data
  stops at 2021-22 -- future seasons as they happen are the only way to
  add calibration points) before relying on it for genuine in-season
  (not just post-season) predictions.
- Not done yet / open for later: precise admin boundary instead of the
  rough bounding box, automating predict_current_season.py to run on a
  schedule instead of manually, confirming whether
  peak_and_rain_establishment and the Sentinel-Landsat calibration hold
  up once more seasons of data are available (both still open
  multiple-comparisons / thin-calibration caveats), and the longer-term
  roadmap items from README (WhatsApp alerts, insurer risk scoring,
  cooperative pilot).
