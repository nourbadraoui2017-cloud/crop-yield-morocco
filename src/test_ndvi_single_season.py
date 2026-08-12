"""
Quick test: confirm the region boundary looks right and pull ONE season
of NDVI data before committing to the full multi-year pull in
pull_ndvi.py. Run this first.

Usage: python src/test_ndvi_single_season.py
"""

import ee

ee.Initialize(project="crop-yield-morocco")

# Same fallback bounding box as pull_ndvi.py
region = ee.Geometry.Rectangle([-7.0, 33.5, -5.5, 34.9])

print("Region bounding box area (approx, km^2):",
      region.area().divide(1e6).getInfo())


def mask_s2_clouds(image):
    qa = image.select("QA60")
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000)


def add_ndvi(image):
    ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
    return image.addBands(ndvi)


# One recent season: Nov 2023 - Jun 2024
start, end = "2023-11-01", "2024-06-30"

collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterDate(start, end)
    .filterBounds(region)
    .map(mask_s2_clouds)
    .map(add_ndvi)
    .select("NDVI")
)

count = collection.size().getInfo()
print(f"Number of Sentinel-2 images found for {start} to {end}: {count}")

if count == 0:
    print("WARNING: no images found -- check region/date range before going further.")
else:
    mean_ndvi = collection.mean().reduceRegion(
        reducer=ee.Reducer.mean(), geometry=region, scale=100, maxPixels=1e9
    ).get("NDVI").getInfo()
    print(f"Mean NDVI over the whole season: {mean_ndvi:.4f}")
    print("If this is roughly between 0.2 and 0.6, that's a sane value for cropland/mixed land.")
