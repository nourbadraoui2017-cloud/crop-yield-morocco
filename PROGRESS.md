# Progress Log

Track work here. One entry per session — date, what got done, what's next, any blockers.

## Build order (from README)

- [x] 0. Check historical yield data availability (region/crop/years) — determines real timeline
- [x] 1. Pull and visualize NDVI data for the test region via GEE
- [ ] 2. Merge NDVI with historical rainfall/temperature + yield data
- [ ] 3. Train and validate baseline regression model (test on unseen years)
- [ ] 4. Wrap in a simple Streamlit dashboard

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
