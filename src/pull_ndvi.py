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
ee.Initialize(project="crop-yield-morocco")

# ---------------------------------------------------------------------
# 2. Define the region: Rabat-Sale-Kenitra
#
#    Cherche la vraie frontiere administrative dans Earth Engine (FAO
#    GAUL) via src/region.py, avec le rectangle approximatif comme
#    filet de securite si elle n'est pas trouvee. Voir region.py pour
#    le detail et pourquoi ce changement ameliore la precision du NDVI.
# ---------------------------------------------------------------------
from region import get_region_geometry

geom = get_region_geometry()

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

    # Sanity check: full-season image count, using the exact same pattern
    # that worked in test_ndvi_single_season.py (503 images for 2023/24).
    # If this ever prints 0, the bug is upstream of the windowing below.
    full_season_check = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start, end)
        .filterBounds(geom)
    )
    print(f"  (sanity check) full-season image count: {full_season_check.size().getInfo()}")

    # 10-day composites. Some windows may have zero usable images (fully
    # clouded out, or no overpass in that narrow window) -- reduceRegion
    # on an empty composite has no "NDVI" band at all, which crashes
    # .get("NDVI") if not handled. So: check image count first, and use
    # NaN for empty windows instead of assuming every window has data.
    #
    # IMPORTANT: build each window's collection fresh from the raw
    # ImageCollection rather than further-filtering an already-filtered
    # "collection" variable -- chaining .filterDate() twice was producing
    # 0 images for every single window, including seasons independently
    # confirmed to have data. Rebuilding from scratch each time avoids
    # whatever that issue was.
    dates = pd.date_range(start, end, freq="10D")
    rows = []
    for i in range(len(dates) - 1):
        d0, d1 = dates[i], dates[i + 1]
        window = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(str(d0.date()), str(d1.date()))
            .filterBounds(geom)
            .map(mask_s2_clouds)
            .map(add_ndvi)
            .select("NDVI")
        )
        n_images = window.size().getInfo()

        if n_images == 0:
            print(f"    {d0.date()} to {d1.date()}: no images, skipping (NaN)")
            ndvi_value = float("nan")
        else:
            composite = window.mean()
            stats = composite.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=geom, scale=100, maxPixels=1e9
            )
            ndvi_value = stats.get("NDVI").getInfo()
            print(f"    {d0.date()} to {d1.date()}: {n_images} images, NDVI={ndvi_value}")

        rows.append({"date": d0, "season": start_year, "ndvi": ndvi_value})

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
    ndvi_df.to_csv("data/raw/ndvi_rabat_sale_kenitra.csv", index=False)
    print(f"Saved {len(ndvi_df)} rows to data/raw/ndvi_rabat_sale_kenitra.csv")

    # Quick visualization: one line per season
    fig, ax = plt.subplots(figsize=(10, 5))
    for season, group in ndvi_df.groupby("season"):
        ax.plot(range(len(group)), group["ndvi"], label=f"{season}/{season + 1}")
    ax.set_xlabel("10-day period since Nov 1")
    ax.set_ylabel("Mean NDVI")
    ax.set_title("NDVI by growing season - Rabat-Sale-Kenitra")
    ax.legend()
    plt.savefig("data/processed/ndvi_by_season.png", dpi=150)
    print("Saved plot to data/processed/ndvi_by_season.png")
