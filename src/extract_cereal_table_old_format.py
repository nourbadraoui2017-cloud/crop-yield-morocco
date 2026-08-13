"""
Parser for the OLDER HCP annuaire table format (used ~2015-2020, maybe
earlier), which is structurally different from the 2023 format:

  - 2023 format: provinces as ROWS, crops as COLUMNS, area+production
    on the SAME page.
  - Old format: crops as ROWS (e.g. ". Blé Dur", ". Blé Tendre"),
    provinces as COLUMNS (with Rabat+Sale+Skhirate-Temara merged into
    ONE column instead of 3 separate ones), and area+production tables
    can be on DIFFERENT pages.

Same word-position-based column detection technique as the 2023 parser
(extract_cereal_table.py) -- it still works here, just applied to
finding CROP rows instead of PROVINCE rows.

Usage: python src/extract_cereal_table_old_format.py <year>
e.g.:  python src/extract_cereal_table_old_format.py 2020
"""

import sys
import re
import pdfplumber
import pandas as pd

ARABIC_RE = re.compile(r"[؀-ۿ]")
NUMERIC_RE = re.compile(r"^-$|^\d")
GAP_THRESHOLD = 10
CAMPAIGN_RE = re.compile(r"(19|20)\d{2}-(19|20)?\d{2}")

CROP_LABELS = {"Blé Dur": "ble_dur", "Blé Tendre": "ble_tendre"}
COLUMN_NAMES = ["Rabat_Sale_SkhirateTemara", "Kenitra", "Sidi_Kacem", "Sidi_Slimane", "Khemisset", "Total"]


def find_table_page(pdf, title_fragment: str):
    """Find a page whose text contains title_fragment, skipping any
    'LISTE DES TABLEAUX' table-of-contents page."""
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").upper()
        if "LISTE DES TABLEAUX" in text:
            continue
        if title_fragment.upper() in text:
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


def parse_row_columns(row_words):
    """Split a row's words into (label_text, [numeric columns]) using
    x-position gap clustering, same technique as the 2023 parser."""
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
    if not label or not data_words:
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

    values = []
    for group in columns:
        text = "".join(w["text"] for w in group)
        try:
            values.append(0.0 if text == "-" else float(text.replace(",", ".")))
        except ValueError:
            return None

    return label, values


def find_crop_rows(page) -> dict:
    """Find the ". Blé Dur" and ". Blé Tendre" rows on this page and
    return {crop_key: [values]}."""
    words = page.extract_words()
    rows = group_words_into_rows(words)

    found = {}
    for row_words in rows.values():
        parsed = parse_row_columns(row_words)
        if not parsed:
            continue
        label, values = parsed
        cleaned_label = label.lstrip(". ").strip()
        for crop_name, crop_key in CROP_LABELS.items():
            if cleaned_label == crop_name and len(values) == 6:
                found[crop_key] = values
    return found


def process_year(nominal_year: int) -> pd.DataFrame:
    pdf_path = f"data/raw/hcp_annuaire_rsk_{nominal_year}.pdf"
    print(f"Opening {pdf_path} ...")

    with pdfplumber.open(pdf_path) as pdf:
        area_page_idx = find_table_page(pdf, "SUPERFICIE (en Ha ) DES PRINCIPALES CULTURES") \
            or find_table_page(pdf, "SUPERFICIE (en Ha) DES PRINCIPALES CULTURES")
        prod_page_idx = find_table_page(pdf, "PRODUCTIONS (en Tonnes ) DES PRINCIPALES CULTURES") \
            or find_table_page(pdf, "PRODUCTIONS (en Tonnes) DES PRINCIPALES CULTURES")

        if area_page_idx is None or prod_page_idx is None:
            print(f"  Could not find area page ({area_page_idx}) or production page ({prod_page_idx})")
            return pd.DataFrame()

        print(f"  Area table: page {area_page_idx + 1}, Production table: page {prod_page_idx + 1}")

        area_page = pdf.pages[area_page_idx]
        prod_page = pdf.pages[prod_page_idx]

        campaign_match = CAMPAIGN_RE.search(area_page.extract_text() or "")
        campaign = campaign_match.group(0) if campaign_match else f"unknown ({nominal_year})"

        area_values = find_crop_rows(area_page)
        prod_values = find_crop_rows(prod_page)

    print(f"  Area rows found: {list(area_values.keys())}")
    print(f"  Production rows found: {list(prod_values.keys())}")

    output_rows = []
    for crop_key in CROP_LABELS.values():
        if crop_key not in area_values or crop_key not in prod_values:
            continue
        for col_idx, col_name in enumerate(COLUMN_NAMES):
            area = area_values[crop_key][col_idx]
            production = prod_values[crop_key][col_idx]
            if area > 0:
                output_rows.append({
                    "annuaire_year": nominal_year,
                    "campaign": campaign,
                    "province": col_name,
                    "crop": crop_key,
                    "area_ha": area,
                    "production_t": production,
                    "yield_t_ha": production / area,
                })

    return pd.DataFrame(output_rows)


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    df = process_year(year)
    print(f"\n=== Extracted {len(df)} rows for {year} ===")
    print(df.to_string(index=False))
