"""
Extends NDVI coverage backward using Landsat 8 (available from 2013,
vs Sentinel-2's ~2017 start) to cover the 2014-2015, 2015-2016, and
2016-2017 growing seasons -- the 3 years where we have real wheat
yield data (from HCP) but no Sentinel-2 NDVI.

Landsat 8 has a 16-day revisit (vs Sentinel-2's ~5 days), so instead of
forcing it into artificial 10-day windows like pull_ndvi.py did (many
would come back empty), this pulls NDVI for every individual clear
image in the season and computes the same summary features directly:
peak, mean, growth-stage mean (Feb-Apr), establishment mean (Nov-Dec).
These are the same features build_training_table.py already uses for
the Sentinel-2 seasons, so this output can be concatenated directly
with data/processed/training_table.csv.

Landsat Collection 2 Level 2 (surface reflectance) band notes:
- NIR = SR_B5, Red = SR_B4 (different band numbers than Sentinel-2!)
- Raw values need scale=0.0000275, offset=-0.2 to become real reflectance
- Cloud mask comes from the QA_PIXEL band (bits 3=cloud, 4=cloud shadow)

WHERE TO RUN: locally, same venv as pull_ndvi.py, with the GEE project
already set up. Needs real internet + earthengine-api + geemap.

Usage: python src/pull_ndvi_landsat.py
"""

import ee
import pandas as pd

ee.Initialize(project="crop-yield-morocco")

# Same fallback bounding box used in pull_ndvi.py, for consistency
GEOM = ee.Geometry.Rectangle([-7.0, 33.5, -5.5, 34.9])

SEASONS_TO_FILL = [2014, 2015, 2016, 2017, 2018, 2021]  # all 6 seasons with
    # real yield data. Deliberately includes 2017/2018/2021 too (which
    # already have Sentinel-2 NDVI) so ALL training seasons use ONE
    # consistent sensor -- mixing Landsat and Sentinel-2 NDVI directly
    # would introduce a sensor-driven bias that has nothing to do with
    # actual crop conditions, which matters a lot with only 6 data points.


def mask_landsat_clouds(image):
    qa = image.select("QA_PIXEL")
    cloud_bit = 1 << 3
    shadow_bit = 1 << 4
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(shadow_bit).eq(0))
    return image.updateMask(mask)


def scale_landsat(image):
    optical_bands = image.select("SR_B.").multiply(0.0000275).add(-0.2)
    return image.addBands(optical_bands, None, True)


def add_ndvi(image):
    ndvi = image.normalizedDifference(["SR_B5", "SR_B4"]).rename("NDVI")
    return image.addBands(ndvi)


def image_to_feature(img):
    stats = img.reduceRegion(reducer=ee.Reducer.mean(), geometry=GEOM, scale=100, maxPixels=1e9)
    return ee.Feature(None, {"date": img.date().format("YYYY-MM-dd"), "ndvi": stats.get("NDVI")})


def get_season_ndvi_points(start_year: int) -> pd.DataFrame:
    start = f"{start_year}-11-01"
    end = f"{start_year + 1}-06-30"

    collection = (
        ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")
        .filterDate(start, end)
        .filterBounds(GEOM)
        .map(mask_landsat_clouds)
        .map(scale_landsat)
        .map(add_ndvi)
        .select(["NDVI"])
    )

    n_images = collection.size().getInfo()
    print(f"  Season {start_year}/{start_year + 1}: {n_images} Landsat 8 images found")
    if n_images == 0:
        return pd.DataFrame()

    features = collection.map(image_to_feature).getInfo()["features"]
    rows = [
        {"date": f["properties"]["date"], "ndvi": f["properties"].get("ndvi")}
        for f in features
        if f["properties"].get("ndvi") is not None
    ]
    df = pd.DataFrame(rows)
    df["season"] = start_year
    print(f"    {len(df)} usable (non-cloud-masked) images")
    return df


def summarize_season(df: pd.DataFrame, season: int) -> dict:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    growth_stage = df[df["date"].dt.month.isin([2, 3, 4])]
    establishment = df[df["date"].dt.month.isin([11, 12])]

    return {
        "season": season,
        "ndvi_peak": df["ndvi"].max(),
        "ndvi_mean": df["ndvi"].mean(),
        "ndvi_growth_stage_mean": growth_stage["ndvi"].mean() if not growth_stage.empty else None,
        "ndvi_establishment_mean": establishment["ndvi"].mean() if not establishment.empty else None,
        "n_valid_periods": len(df),  # note: individual images here, not 10-day windows
    }


if __name__ == "__main__":
    all_points = []
    summaries = []

    for season in SEASONS_TO_FILL:
        df = get_season_ndvi_points(season)
        if df.empty:
            print(f"  WARNING: no usable Landsat data for season {season} -- skipping")
            continue
        all_points.append(df)
        summaries.append(summarize_season(df, season))

    if all_points:
        raw_df = pd.concat(all_points, ignore_index=True)
        raw_df.to_csv("data/raw/ndvi_landsat_rabat_sale_kenitra.csv", index=False)
        print(f"\nSaved {len(raw_df)} raw Landsat points to data/raw/ndvi_landsat_rabat_sale_kenitra.csv")

    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_df.to_csv("data/processed/ndvi_features_landsat.csv", index=False)
        print("\n=== Landsat-derived NDVI features (same format as Sentinel-2 features) ===")
        print(summary_df.to_string(index=False))
        print("\nSaved to data/processed/ndvi_features_landsat.csv")
    else:
        print("\nNo seasons produced usable data.")
