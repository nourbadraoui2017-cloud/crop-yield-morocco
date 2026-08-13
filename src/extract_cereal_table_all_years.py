"""
Generalized version of extract_cereal_table.py: loops over every
available HCP regional annuaire (Annuaire Statistique Regional) for
Rabat-Sale-Kenitra, finds the cereal area/production table in EACH one
(page number varies by year, so it's located dynamically by searching
for the table title), and builds one combined multi-year dataset of
wheat area, production, and computed yield per province.

URLs below were found manually by browsing
https://www.hcp.ma/region-rabat/Publications_r3.html -- there's no
code that "discovers" these; a human (well, an AI) looked at that page
and copied the links. Some years may be missing from HCP's own site
(gaps in the list below reflect that, not an oversight here).

Each annuaire is titled by publication year but reports on the
PREVIOUS growing season (e.g. the "2023" annuaire covers the
2021-2022 campaign) -- this script reads the actual campaign label
from the table title text itself rather than assuming it matches the
file's nominal year.

Usage: python src/extract_cereal_table_all_years.py
"""

import os
import re
import requests
import pdfplumber
import pandas as pd

ANNUAIRE_URLS = {
    2023: "https://www.hcp.ma/region-rabat/docs/ASR/ANNUAIRE%20STATISTIQUE%20REGIONAL%202023%20%281%29.pdf",
    2020: "https://www.hcp.ma/region-rabat/docs/ASR/Annuaire%20Regional%202020.pdf",
    2019: "https://www.hcp.ma/region-rabat/docs/ASR/ASR%202019.pdf",
    2018: "https://www.hcp.ma/region-rabat/docs/ASR2018/ASR2018.pdf",
    2017: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2017.pdf",
    2016: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2016.pdf",
    2015: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2015.pdf",
    2013: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2013.pdf",
    2012: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2012.pdf",
    2011: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2011.pdf",
    2010: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2010.pdf",
    2009: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2009.pdf",
    2008: "https://www.hcp.ma/region-rabat/docs/ASR/ASR2008.pdf",
}

ARABIC_RE = re.compile(r"[؀-ۿ]")
NUMERIC_RE = re.compile(r"^-$|^\d")
GAP_THRESHOLD = 10
CAMPAIGN_RE = re.compile(r"(19|20)\d{2}-(19|20)?\d{2}")


def download_if_needed(url: str, out_path: str):
    if os.path.exists(out_path):
        print(f"  (already downloaded: {out_path})")
        return
    print(f"  Downloading {url} ...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
    print(f"  Saved ({len(resp.content) / 1024:.1f} KB)")


def find_cereal_table_page(pdf):
    """Search every page for the cereal area table title. Returns the
    page index (0-based) or None if not found.

    The table's title also appears on the "LISTE DES TABLEAUX" (table of
    contents) page -- that page must be excluded, or we'd extract 0 rows
    from a page that's just a list of titles, not actual data. Requiring
    BOTH the area and production titles together, and excluding the TOC
    page explicitly, reliably picks the real data page.
    """
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").upper()
        if "LISTE DES TABLEAUX" in text:
            continue
        if "SUPERFICIE DES CULTURES DES CEREALES" in text and "PRODUCTION DES CULTURES DES CEREALES" in text:
            return i
    return None


def group_words_into_rows(words, tolerance=3):
    rows = {}
    for w in words:
        matched_key = None
        for key in rows:
            if abs(key - w["top"]) < tolerance:
                matched_key = key
                break
        if matched_key is None:
            rows[w["top"]] = [w]
        else:
            rows[matched_key].append(w)
    return dict(sorted(rows.items()))


def parse_data_row(row_words):
    row_words = sorted(row_words, key=lambda w: w["x0"])
    while row_words and ARABIC_RE.search(row_words[-1]["text"]):
        row_words.pop()
    if not row_words:
        return None

    label_words = []
    i = 0
    while i < len(row_words) and not NUMERIC_RE.match(row_words[i]["text"]):
        label_words.append(row_words[i]["text"])
        i += 1
    label = " ".join(label_words)
    data_words = row_words[i:]
    if not label or len(data_words) == 0:
        return None

    columns = []
    current_group = [data_words[0]]
    for prev, curr in zip(data_words, data_words[1:]):
        gap = curr["x0"] - prev["x1"]
        if gap < GAP_THRESHOLD:
            current_group.append(curr)
        else:
            columns.append(current_group)
            current_group = [curr]
    columns.append(current_group)

    if len(columns) != 6:
        return None

    values = []
    for group in columns:
        text = "".join(w["text"] for w in group)
        try:
            values.append(0.0 if text == "-" else float(text.replace(",", ".")))
        except ValueError:
            return None  # malformed number -- skip this row rather than crash

    return label, values


def extract_table(words, top_min, top_max):
    relevant_words = [w for w in words if top_min <= w["top"] < top_max]
    rows = group_words_into_rows(relevant_words)
    results = []
    for row_words in rows.values():
        parsed = parse_data_row(row_words)
        if parsed:
            label, values = parsed
            results.append({
                "province": label,
                "ble_dur": values[0], "ble_tendre": values[1], "orge": values[2],
                "mais": values[3], "riz": values[4], "total": values[5],
            })
    return results


def process_one_annuaire(nominal_year: int, url: str) -> pd.DataFrame:
    pdf_path = f"data/raw/hcp_annuaire_rsk_{nominal_year}.pdf"
    try:
        download_if_needed(url, pdf_path)
    except Exception as e:
        print(f"  FAILED to download: {e}")
        return pd.DataFrame()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_idx = find_cereal_table_page(pdf)
            if page_idx is None:
                print("  Could not find cereal area table in this document -- skipping")
                return pd.DataFrame()

            page = pdf.pages[page_idx]
            page_text = page.extract_text() or ""
            campaign_match = CAMPAIGN_RE.search(page_text)
            campaign = campaign_match.group(0) if campaign_match else f"unknown (annuaire {nominal_year})"

            words = page.extract_words()
            prod_title_words = [w for w in words if w["text"] == "PRODUCTION"]
            if not prod_title_words:
                print("  Found area table but not production table title -- skipping")
                return pd.DataFrame()
            split_top = prod_title_words[0]["top"]

            area_rows = extract_table(words, top_min=0, top_max=split_top)
            production_rows = extract_table(words, top_min=split_top, top_max=page.height)
    except Exception as e:
        print(f"  FAILED to parse: {e}")
        return pd.DataFrame()

    area_by_province = {r["province"]: r for r in area_rows}
    output_rows = []
    for prod in production_rows:
        province = prod["province"]
        area = area_by_province.get(province)
        if not area:
            continue
        for crop in ["ble_dur", "ble_tendre"]:
            if area[crop] > 0:
                output_rows.append({
                    "annuaire_year": nominal_year,
                    "campaign": campaign,
                    "province": province,
                    "crop": crop,
                    "area_ha": area[crop],
                    "production_t": prod[crop],
                    "yield_t_ha": prod[crop] / area[crop],
                })

    print(f"  Extracted {len(output_rows)} province x crop rows (page {page_idx + 1}, campaign {campaign})")
    return pd.DataFrame(output_rows)


if __name__ == "__main__":
    all_results = []
    for year, url in sorted(ANNUAIRE_URLS.items(), reverse=True):
        print(f"\n=== Annuaire {year} ===")
        df = process_one_annuaire(year, url)
        if not df.empty:
            all_results.append(df)

    if not all_results:
        print("\nNo data extracted from any year -- something's fundamentally broken.")
    else:
        combined = pd.concat(all_results, ignore_index=True)
        combined.to_csv("data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv", index=False)
        print(f"\n=== Saved {len(combined)} rows to data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv ===")
        print(f"Distinct campaigns found: {sorted(combined['campaign'].unique())}")
