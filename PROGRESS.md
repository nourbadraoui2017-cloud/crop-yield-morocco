# Progress Log

Track work here. One entry per session — date, what got done, what's next, any blockers.

## Build order (from README)

- [ ] 0. Check historical yield data availability (region/crop/years) — determines real timeline
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
