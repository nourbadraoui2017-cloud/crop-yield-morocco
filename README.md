# Satellite-Based Crop Yield Prediction

## The Problem

Over 60% of Morocco's rural population depends directly on agriculture, mostly small farmers working plots under 5 hectares, mostly rain-fed rather than irrigated. Morocco just came out of a seven-year drought, and agriculture consumes roughly 84% of the country's water — the entire system is highly exposed to rainfall variability.

The core issue: nobody in the chain has reliable early information about how the harvest will turn out.

- **Farmers** don't know until harvest whether the season is good or bad, so they can't plan — whether to sell early, hold, seek off-farm income, or adjust next season's planting.
- **Insurers** can't price fair drought insurance for small farmers because assessing risk plot-by-plot (site visits, manual surveys) is too expensive relative to small policy sizes. Today, only about **3% of small farmers in Morocco** have any climate risk insurance.
- **Cooperatives and government** only learn about a bad harvest once it's happening — too late to plan storage, imports, or aid distribution ahead of time.

Existing satellite-based crop monitoring tools (e.g. USDA, FAO systems) are built for large-scale national/continental forecasting, not packaged affordably for a local insurer or cooperative in Morocco. The gap isn't the science — it's that nobody has adapted it for this specific, smaller-scale use case.

## The Solution

Satellites (e.g. Sentinel-2) photograph farmland regularly and for free. Healthy, well-growing crops reflect light differently than stressed or sparse ones — greener, denser. By tracking this "greenness" (via a vegetation index like NDVI) throughout a growing season and comparing it to historical yield outcomes, you can predict this season's yield *before* harvest, instead of waiting until it's too late.

### How it works, step by step

1. **Continuous data collection** — pull new satellite imagery every few days for the target region, combined with rainfall/temperature data, throughout the growing season.
2. **Learning from the past** — gather several years of historical satellite data + real recorded yields (from public agricultural statistics) and train a model on the relationship between them.
3. **Live prediction during the season** — run the current season's incoming data through the trained model to produce a running forecast that gets more confident as the season progresses.
4. **Delivery, tailored per audience:**
   - **Farmers** — a simple WhatsApp alert (e.g. "expected yield below average, consider adjusting water use").
   - **Insurers** — an API/dashboard giving a risk score per region to plug into policy pricing.
   - **Cooperatives/government** — a multi-region dashboard for planning storage/imports ahead of time.

## Tech Stack

Everything is built in **Python**.

| Purpose | Tool |
|---|---|
| Satellite data access | Google Earth Engine (GEE) + `geemap` |
| Dev environment | Google Colab (free compute) |
| Data handling | `pandas`, `numpy` |
| Model training | `scikit-learn` / `xgboost` (start simple, not deep learning) |
| Weather data | NASA POWER API |
| Historical yield data | Morocco Ministry of Agriculture / HCP publications (manual gathering) |
| Visualization | `matplotlib` |
| Dashboard / delivery | Streamlit |
| Version control | GitHub |
| Dev assistant | Claude Code (for writing/debugging the pipeline incrementally) |

## MVP Scope

Start narrow: **one region, one crop** (wheat is a good choice — most historical data available).

Build order:
1. Pull and visualize NDVI data for the test region via GEE.
2. Merge with historical rainfall/temperature + yield data.
3. Train and validate a baseline regression model (test on unseen years, not just random rows).
4. Wrap the result in a simple Streamlit dashboard showing predicted yield vs. historical average.

## Timeline (realistic estimate)

| Phase | Time |
|---|---|
| Setup + first satellite pull | Week 1 |
| Historical data gathering (likely bottleneck) | Week 2 (could stretch to 3-4) |
| Model building & validation | Weeks 3-4 |
| Dashboard + polish | Weeks 5-6 |

**Total: ~4-8 weeks**, depending on time available around studies. The biggest wildcard is how easy it is to obtain historical yield data at the needed resolution — worth checking before writing any code.

## Business Model

- License the risk score/API to **insurers** for pricing parametric drought insurance.
- Sell reports/dashboards to **agricultural cooperatives** for planning storage and logistics.
- Provide forecasting to **government/ONCA** for national planning.
- Target **agri-input suppliers** (fertilizer/seed companies) who want to identify underperforming regions early.

Realistic sales path: build → validate against historical data → run one free/discounted pilot season with a willing cooperative → use real results to sell to insurers and others.

## Legal & Licensing

- **Sentinel-2 data** is free and explicitly licensed for commercial use (reproduction, distribution, modification), with only an attribution requirement ("Copernicus Sentinel data [year]").
- Selling the product commercially requires a business registration — **auto-entrepreneur status** is the simplest starting point in Morocco.
- If personal data is collected (e.g. farmer phone numbers), Morocco's data protection law (**Loi 09-08**) applies — basic consent and data handling practices needed.
- The model and software built on top of the open data are fully owned by the builder and can be sold, licensed, or offered as a subscription/API.

## Why It's a Strong CV Project

Combines three genuinely valuable, hireable skills:
- Working with satellite/geospatial data (remote sensing) — a rare, marketable skill.
- Time-series machine learning — extracting real patterns from historical data.
- Applying it to a real, high-stakes problem (Morocco's drought-exposed agriculture) rather than a toy dataset.

## Next Steps

1. Check what historical yield data is actually available (region/crop/years) — this determines the real timeline.
2. Set up Google Earth Engine account and pull first NDVI data for a test region.
3. Build the training dataset (NDVI + weather + yield).
4. Train and validate baseline model.
5. Build Streamlit dashboard.
6. Pilot with one cooperative to validate real-world accuracy.
