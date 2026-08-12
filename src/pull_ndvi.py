"""
Pull and visualize NDVI data for the target region (Rabat-Sale-Kenitra)
via Google Earth Engine + geemap.

BUILD ORDER STEP 1 (see README.md / PROGRESS.md).

WHERE TO RUN THIS: Google Colab, per the project's tech stack. It needs
a live internet connection and an authenticated Earth Engine account,
neither of which is available in the environment this script was
written in -- it has NOT been executed or verified end-to-end. Run it,
fix whatever breaks (there will likely be something small), and log the
result in PROGRESS.md.

SETUP (one-time, in Colab):
    !pip install earthengine-api geemap -q
    import ee
    ee.Authenticate()          # opens a browser login flow
    ee.Initialize(project="YOUR-GEE-PROJECT-ID")

IMPORTANT CAVEAT TO CHECK FIRST:
Sentinel-2 (harmonized surface reflectance, COPERNICUS/S2_SR_HARMONIZED)
only has reliable coverage from ~2017 onward. That caps how many
historical growing seasons you'll have NDVI for -- roughly 2017/18
through the current season, i.e. ~8-9 seasons. Cross-check this against
however many years of *yield* data step 0 turns up (see
parse_yield_pdfs.py) -- the smaller of the two numbers is your real
training set size, and it may be small enough to change the modeling
approach (e.g. favor simpler models, pool multiple regions, or add
older sensors like Landsat 8 (2013+) or MODIS NDVI (2000+) for a longer
but coarser-resolution history).
"""

import ee
import geemap
import pandas as pd
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------
# 1. Initialize Earth Engine (run ee.Authenticate() once, separately,
#    before this if you haven't already -- see docstring above)
# ---------------------------------------------------------------------
ee.Initialize(project="YOUR-GEE-PROJECT-ID")  # <-- replace with your project ID

# ---------------------------------------------------------------------
# 2. Define the region: Rabat-Sale-Kenitra
#
#    GADM naming for Moroccan regions is inconsistent across dataset
#    versions. Rather than guessing the exact admin boundary name and
#    having it silently fail or match the wrong feature, this first
#    prints available region names so you can confirm/fix the filter
#    below before trusting the result.
# ---------------------------------------------------------------------
admin1 = ee.FeatureCollection("FAO/GAUL/2015/level1").filter(
    ee.Filter.eq("ADM0_NAME", "Morocco")
)

# Uncomment to inspect available names once, interactively:
# names = admin1.aggregate_array("ADM1_NAME").getInfo()
# print(names)

region_name_candidates = ["Rabat-Sale-Kenitra", "Rabat-Sale-Zemmour-Zaer"]
region = admin1.filter(ee.Filter.inList("ADM1_NAME", region_name_candidates))

# Fallback: if FAO/GAUL 2015 predates the 2015 Moroccan regional reform
# and doesn't have the new boundary, use a manually drawn bounding box
# instead (approximate -- refine against an actual shapefile, e.g. from
# GADM 4.1 or HCP's own geodata, before this becomes final):
FALLBACK_BBOX = ee.Geometry.Rectangle([-7.0, 33.5, -5.5, 34.9])

# geom = region.geometry()   # use once region_name_candidates is confirmed
geom = FALLBACK_BBOX  # safe default until the admin boundary is verified

# ---------------------------------------------------------------------
# 3. Cloud-masking function for Sentinel-2 SR Harmonized
# ---------------------------------------------------------------------
def mask_s2_clouds(image):
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)


def add_ndvi(image):
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return image.addBands(ndvi)


# ---------------------------------------------------------------------
# 4. Pull NDVI for one growing season (Nov 1 -> Jun 30) as a 10-day
#    composite time series, averaged over the region.
#
#    Morocco's rain-fed wheat season: planting ~Nov-Dec, harvest ~May-Jun.
# ---------------------------------------------------------------------
def get_season_ndvi(start_year: int) -> pd.DataFrame:
    """NDVI time series for the growing season starting in `start_year`
    (e.g. start_year=2022 -> Nov 2022 through Jun 2023)."""
    start = f"{start_year}-11-01"
    end = f"{start_year + 1}-06-30"

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(geom)
        .map(mask_s2_clouds)
        .map(add_ndvi)
        .select("NDVI")
    )

    # 10-day composites
    dates = pd.date_range(start, end, freq="10D")
    rows = []
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        composite = collection.filterDate(str(d0.date()), str(d1.date())).mean()
        stats = composite.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=geom, scale=100, maxPixels=1e9
        )
        rows.append({"date": d0, "season": start_year, "ndvi": stats.get("NDVI")})

    # .getInfo() triggers actual computation -- do it once at the end,
    # not per-row, to avoid excessive round trips
    results = ee.List([r["ndvi"] for r in rows]).getInfo()
    for row, val in zip(rows, results):
        row["ndvi"] = val

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# 5. Pull all available seasons and save
# ---------------------------------------------------------------------
if __name__ == "__main__":
    FIRST_SEASON_START_YEAR = 2017  # Sentinel-2 coverage realistically starts here
    LAST_SEASON_START_YEAR = 2024   # adjust to the most recently completed season

    all_seasons = []
    for year in range(FIRST_SEASON_START_YEAR, LAST_SEASON_START_YEAR + 1):
        print(f"Pulling season {year}/{year + 1}...")
        df = get_season_ndvi(year)
        all_seasons.append(df)

    ndvi_df = pd.concat(all_seasons, ignore_index=True)
    ndvi_df.to_csv("../data/raw/ndvi_rabat_sale_kenitra.csv", index=False)
    print(f"Saved {len(ndvi_df)} rows to data/raw/ndvi_rabat_sale_kenitra.csv")

    # Quick visualization: one line per season
    fig, ax = plt.subplots(figsize=(10, 5))
    for season, group in ndvi_df.groupby("season"):
        ax.plot(range(len(group)), group["ndvi"], label=f"{season}/{season + 1}")
    ax.set_xlabel("10-day period since Nov 1")
    ax.set_ylabel("Mean NDVI")
    ax.set_title("NDVI by growing season - Rabat-Sale-Kenitra")
    ax.legend()
    plt.savefig("../data/processed/ndvi_by_season.png", dpi=150)
    print("Saved plot to data/processed/ndvi_by_season.png")
