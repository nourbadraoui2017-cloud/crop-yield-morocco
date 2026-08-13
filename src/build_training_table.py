"""
Step 2: merge the NDVI time series with the wheat yield data into one
training-ready table.

What this does:
1. Load the raw NDVI data (192 rows: one row per 10-day period per
   season) and collapse each season down to a handful of SUMMARY
   features (peak greenness, average greenness, greenness during the
   drought-sensitive growth stage, etc.) -- not the raw 24 points,
   which would be too many inputs for the tiny amount of yield data
   available (see README/PROGRESS for why: this is a small-data
   problem, favor few strong features over many raw ones).
2. Load the yield data and collapse it to ONE region-level number per
   season: use the "Total" province row (already a region-wide sum
   across all 6 provinces) and combine Ble Dur + Ble Tendre into one
   overall wheat figure, since NDVI can't distinguish wheat variety
   spatially anyway.
3. Join both on season, producing one row per growing season. Seasons
   without matching yield data (2019-2024) keep their NDVI features but
   get an empty yield -- still useful to keep for later exploration,
   just not usable to train on directly.

Usage: python src/build_training_table.py
"""

import pandas as pd

NDVI_PATH = "data/raw/ndvi_rabat_sale_kenitra.csv"
YIELD_PATH = "data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv"
OUT_PATH = "data/processed/training_table.csv"


def build_ndvi_features(ndvi_df: pd.DataFrame) -> pd.DataFrame:
    ndvi_df = ndvi_df.copy()
    ndvi_df["date"] = pd.to_datetime(ndvi_df["date"])

    rows = []
    for season, group in ndvi_df.groupby("season"):
        group = group.dropna(subset=["ndvi"])
        if group.empty:
            continue

        # Drought-sensitive growth stage for Moroccan rain-fed wheat is
        # roughly Feb-Apr (stem elongation through heading) -- NDVI
        # during this window is usually the strongest yield predictor.
        growth_stage = group[group["date"].dt.month.isin([2, 3, 4])]
        establishment = group[group["date"].dt.month.isin([11, 12])]

        rows.append({
            "season": season,
            "ndvi_peak": group["ndvi"].max(),
            "ndvi_mean": group["ndvi"].mean(),
            "ndvi_growth_stage_mean": growth_stage["ndvi"].mean() if not growth_stage.empty else None,
            "ndvi_establishment_mean": establishment["ndvi"].mean() if not establishment.empty else None,
            "n_valid_periods": len(group),
        })

    return pd.DataFrame(rows)


def build_yield_target(yield_df: pd.DataFrame) -> pd.DataFrame:
    # "Total" province = already summed across all 6 provinces in the
    # region -- exactly the region-level number we need.
    region_total = yield_df[yield_df["province"] == "Total"]

    rows = []
    for campaign, group in region_total.groupby("campaign"):
        total_area = group["area_ha"].sum()
        total_production = group["production_t"].sum()
        if total_area == 0:
            continue

        # campaign season start year, e.g. "2017-2018" -> 2017, to match
        # the NDVI table's "season" column (which is also the start year)
        season_start_year = int(campaign.split("-")[0])

        rows.append({
            "season": season_start_year,
            "campaign": campaign,
            "wheat_area_ha": total_area,
            "wheat_production_t": total_production,
            "wheat_yield_t_ha": total_production / total_area,
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    ndvi_df = pd.read_csv(NDVI_PATH)
    yield_df = pd.read_csv(YIELD_PATH)

    ndvi_features = build_ndvi_features(ndvi_df)
    yield_target = build_yield_target(yield_df)

    print("=== NDVI features per season ===")
    print(ndvi_features.to_string(index=False))

    print("\n=== Yield target per season ===")
    print(yield_target.to_string(index=False))

    merged = ndvi_features.merge(yield_target, on="season", how="left")
    merged = merged.sort_values("season")

    print("\n=== MERGED TRAINING TABLE ===")
    print(merged.to_string(index=False))

    n_usable = merged["wheat_yield_t_ha"].notna().sum()
    print(f"\n{n_usable} of {len(merged)} seasons have both NDVI and yield data "
          f"-- that's the real training set size for step 3.")

    merged.to_csv(OUT_PATH, index=False)
    print(f"Saved to {OUT_PATH}")
