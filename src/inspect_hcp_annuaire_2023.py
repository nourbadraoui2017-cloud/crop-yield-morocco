"""
Download and scan HCP's full regional statistical yearbook (Annuaire
Statistique Regional) 2023 for Rabat-Sale-Kenitra -- looking specifically
for the agriculture/cereals/yield tables.

Usage: python src/inspect_hcp_annuaire_2023.py
"""

import requests
import pdfplumber

URL = (
    "https://www.hcp.ma/region-rabat/docs/ASR/"
    "ANNUAIRE%20STATISTIQUE%20REGIONAL%202023%20%281%29.pdf"
)
OUT_PATH = "data/raw/hcp_annuaire_rsk_2023.pdf"

print(f"Downloading {URL} ...")
resp = requests.get(URL, timeout=60)
resp.raise_for_status()
with open(OUT_PATH, "wb") as f:
    f.write(resp.content)
print(f"Saved to {OUT_PATH} ({len(resp.content) / 1024:.1f} KB)")

KEYWORDS = ["blé", "céréale", "rendement", "quintal", "qx/ha", "superficie", "production"]

with pdfplumber.open(OUT_PATH) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")

    for kw in KEYWORDS:
        pages_with_kw = []
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").lower()
            if kw.lower() in text:
                pages_with_kw.append(i + 1)
        print(f"'{kw}': found on pages {pages_with_kw}")

    # Find the page with the most cereal/yield-related hits
    best_page, best_count = None, 0
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        count = sum(text.count(k.lower()) for k in ["blé", "rendement", "céréale", "quintal"])
        if count > best_count:
            best_count, best_page = count, i

    if best_page is not None:
        print(f"\n=== Most relevant page: {best_page + 1} ({best_count} hits) ===")
        print(pdf.pages[best_page].extract_text())
        print("\n--- Tables detected on that page ---")
        for t in pdf.pages[best_page].extract_tables():
            for row in t:
                print(row)
    else:
        print("\nNo page mentions wheat/cereal/yield terms at all.")
