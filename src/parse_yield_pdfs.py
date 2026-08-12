"""
Download and parse the HCP / Ministry of Agriculture PDFs to find out
exactly how many years of REGIONAL wheat yield data actually exist.

BUILD ORDER STEP 0 (see README.md / PROGRESS.md) -- this is the real
answer to "is the historical data actually there", not just a lookup.

WHERE TO RUN THIS: needs real internet access. The sandbox this was
written in could not reach agriculture.gov.ma or hcp.ma directly (no
general outbound network access), so this script has NOT been executed
or verified -- run it in Colab or locally, see what breaks, and log
the actual findings in PROGRESS.md. Web search only confirmed these
document *categories* exist:
  - HCP: "Annuaires statistiques régionaux" / "Chiffres clés régionaux"
    (browse https://www.hcp.ma/downloads/?tag=Annuaires+statistiques+régionaux
    to find the exact PDF for Rabat-Salé-Kénitra)
  - Ministry: "Agricultures en Chiffres" (annual), e.g.
    https://www.agriculture.gov.ma/sites/default/files/19-00145-book_agricultures_en_chiffres_def.pdf
  Actual regional wheat-yield tables inside those PDFs have not been
  confirmed to exist in a clean, extractable form yet -- that's what
  this script is for.

Install once: pip install requests pdfplumber pandas
"""

import re
import requests
import pdfplumber
import pandas as pd

# ---------------------------------------------------------------------
# 1. Candidate source PDFs to check.
#    Add more URLs here as you find them on hcp.ma / agriculture.gov.ma
#    -- the ones below are what a first pass turned up; they are
#    NOT guaranteed to contain region x year x crop yield tables.
# ---------------------------------------------------------------------
SOURCES = {
    "ministry_agricultures_en_chiffres": (
        "https://www.agriculture.gov.ma/sites/default/files/"
        "19-00145-book_agricultures_en_chiffres_def.pdf"
    ),
    # TODO: replace with the actual regional annuaire PDF URL for
    # Rabat-Sale-Kenitra once found via the hcp.ma downloads page above.
    # "hcp_annuaire_regional_rsk": "https://www.hcp.ma/downloads/....pdf",
}

REGION_NAME_VARIANTS = [
    "Rabat-Salé-Kénitra",
    "Rabat-Sale-Kenitra",
    "Rabat Salé Kénitra",
]
CROP_KEYWORDS = ["blé tendre", "blé dur", "blé", "céréales", "wheat"]
YIELD_KEYWORDS = ["rendement", "quintal", "qx/ha", "kg/ha", "yield"]

# A year looks like 19xx or 20xx, optionally as a campaign "2019/2020" or "2019-20"
YEAR_PATTERN = re.compile(r"(19|20)\d{2}([/\-](\d{2,4}))?")


def download_pdf(url: str, out_path: str) -> str:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


def find_relevant_pages(pdf_path: str) -> list[dict]:
    """Scan every page; flag ones that mention the target region AND a
    wheat/cereal keyword AND a yield keyword -- those are candidates
    for containing the table we actually need."""
    hits = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            text_lower = text.lower()

            has_region = any(r.lower() in text_lower for r in REGION_NAME_VARIANTS)
            has_crop = any(c.lower() in text_lower for c in CROP_KEYWORDS)
            has_yield = any(y.lower() in text_lower for y in YIELD_KEYWORDS)

            if has_crop and has_yield:
                # Note: has_region is tracked separately since national
                # tables (no region breakdown) are still useful context
                years_found = YEAR_PATTERN.findall(text)
                hits.append(
                    {
                        "page": i + 1,
                        "has_region_match": has_region,
                        "n_years_mentioned": len(years_found),
                        "tables_on_page": len(page.extract_tables()),
                    }
                )
    return hits


def extract_tables_from_pages(pdf_path: str, page_numbers: list[int]) -> list[pd.DataFrame]:
    """Pull actual tables from the flagged pages (1-indexed page_numbers)."""
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in page_numbers:
            page = pdf.pages[p - 1]
            for raw_table in page.extract_tables():
                if raw_table and len(raw_table) > 1:
                    df = pd.DataFrame(raw_table[1:], columns=raw_table[0])
                    df["_source_page"] = p
                    tables.append(df)
    return tables


if __name__ == "__main__":
    summary_rows = []

    for name, url in SOURCES.items():
        print(f"\n=== {name} ===")
        pdf_path = f"../data/raw/{name}.pdf"
        try:
            download_pdf(url, pdf_path)
        except Exception as e:
            print(f"  FAILED to download: {e}")
            continue

        hits = find_relevant_pages(pdf_path)
        print(f"  {len(hits)} candidate pages found (crop + yield keywords)")
        region_hits = [h for h in hits if h["has_region_match"]]
        print(f"  {len(region_hits)} of those also mention the target region")

        if region_hits:
            tables = extract_tables_from_pages(
                pdf_path, [h["page"] for h in region_hits]
            )
            for j, table in enumerate(tables):
                out_csv = f"../data/raw/{name}_table_{j}.csv"
                table.to_csv(out_csv, index=False)
                print(f"    saved candidate table -> {out_csv} (inspect manually)")

        summary_rows.append(
            {
                "source": name,
                "candidate_pages": len(hits),
                "region_specific_pages": len(region_hits),
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    print("\n=== SUMMARY (log this in PROGRESS.md) ===")
    print(summary_df.to_string(index=False))
    summary_df.to_csv("../data/processed/yield_data_availability_summary.csv", index=False)
