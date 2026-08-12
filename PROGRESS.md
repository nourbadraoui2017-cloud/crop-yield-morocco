# Progress Log

Track work here. One entry per session — date, what got done, what's next, any blockers.

## Build order (from README)

- [ ] 0. Check historical yield data availability (region/crop/years) — determines real timeline
- [ ] 1. Pull and visualize NDVI data for the test region via GEE
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
