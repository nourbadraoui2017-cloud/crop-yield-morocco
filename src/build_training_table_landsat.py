"""
Final training table using LANDSAT NDVI features consistently across
all 6 seasons with real yield data (avoids the Sentinel-2/Landsat
sensor bias issue -- see PROGRESS.md). Sentinel-2 remains the sensor of
choice for live/future season prediction (better resolution, more
frequent revisit) once the model is actually deployed -- this table is
specifically for TRAINING, where consistency across years matters more
than resolution.

Usage: python src/build_training_table_landsat.py
"""

import pandas as pd

NDVI_LANDSAT_PATH = "data/processed/ndvi_features_landsat.csv"
YIELD_PATH = "data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv"
OUT_PATH = "data/processed/training_table_landsat.csv"


def build_yield_target(yield_df: pd.DataFrame) -> pd.DataFrame:
    region_total = yield_df[yield_df["province"] == "Total"]
    rows = []
    for campaign, group in region_total.groupby("campaign"):
        total_area = group["area_ha"].sum()
        total_production = group["production_t"].sum()
        if total_area == 0:
            continue
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
    ndvi_features = pd.read_csv(NDVI_LANDSAT_PATH)
    yield_df = pd.read_csv(YIELD_PATH)
    yield_target = build_yield_target(yield_df)

    merged = ndvi_features.merge(yield_target, on="season", how="inner")
    merged = merged.sort_values("season")

    print("=== FINAL TRAINING TABLE (Landsat NDVI, all seasons matched) ===")
    print(merged.to_string(index=False))
    print(f"\n{len(merged)} of {len(yield_target)} yield seasons matched with NDVI.")

    merged.to_csv(OUT_PATH, index=False)
    print(f"Saved to {OUT_PATH}")
