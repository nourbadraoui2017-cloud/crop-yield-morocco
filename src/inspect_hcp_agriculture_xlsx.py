"""
Download and inspect HCP's regional agriculture statistics file for
Rabat-Sale-Kenitra (part of Annuaire Statistique Regional 2023).

This is a much more promising source than the Ministry PDF: it's an
actual Excel file (not a scanned/chart-heavy PDF), specifically
covering "Agriculture, forets et peche" for this exact region.

Usage: python src/inspect_hcp_agriculture_xlsx.py
"""

import requests
import pandas as pd

URL = "https://www.hcp.ma/region-rabat/docs/ASR/4-agriculture%2C%20forets%20et%20peche.xlsx"
OUT_PATH = "data/raw/hcp_rsk_agriculture_2023.xlsx"

print(f"Downloading {URL} ...")
resp = requests.get(URL, timeout=60)
resp.raise_for_status()
with open(OUT_PATH, "wb") as f:
    f.write(resp.content)
print(f"Saved to {OUT_PATH} ({len(resp.content) / 1024:.1f} KB)")

# Excel files can have multiple sheets -- list them all first
xls = pd.ExcelFile(OUT_PATH)
print(f"\nSheet names: {xls.sheet_names}")

for sheet in xls.sheet_names:
    df = pd.read_excel(OUT_PATH, sheet_name=sheet, header=None)
    print(f"\n=== Sheet '{sheet}' (shape: {df.shape}) ===")
    print(df.head(15).to_string())
