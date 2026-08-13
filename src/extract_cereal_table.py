"""
Parse the "SUPERFICIE DES CULTURES DES CEREALES" (area) and "PRODUCTION
DES CULTURES DES CEREALES" (production) tables out of the HCP regional
annuaire for Rabat-Sale-Kenitra, and compute wheat yield (tonnes/ha) per
province.

V2: uses word POSITIONS (x-coordinates), not just the text, to correctly
tell columns apart. A pure text/regex approach (V1) failed silently on
several rows because two adjacent column values that both happen to be
clean multiples of 3 digits (e.g. "20 000" then "117 300") are
indistinguishable from a single big number using text alone. Measured
directly from the PDF: fragments of the SAME number are ~1.6pt apart;
different columns are always 35pt+ apart -- a huge, reliable gap to
threshold on.

Usage: python src/extract_cereal_table.py
(currently hardcoded to the 2023 annuaire / 2021-2022 campaign, page 39,
 as a first working version -- generalize to loop over years next)
"""

import re
import pdfplumber

PDF_PATH = "data/raw/hcp_annuaire_rsk_2023.pdf"
PAGE_NUMBER = 39  # 1-indexed

ARABIC_RE = re.compile(r"[؀-ۿ]")
NUMERIC_RE = re.compile(r"^-$|^\d")
GAP_THRESHOLD = 10  # points; same-number gaps are ~1.6, different-column gaps are 35+


def group_words_into_rows(words, tolerance=3):
    """Cluster words by similar 'top' (y-position) into physical rows."""
    rows = {}
    for w in words:
        # find an existing row bucket within tolerance, or start a new one
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
    """Given all words on one physical line (sorted by x0), split into
    (province_label, [6 numeric column values]) using position-based
    gap clustering. Returns None if this doesn't look like a data row."""
    row_words = sorted(row_words, key=lambda w: w["x0"])

    # Strip trailing Arabic word(s)
    while row_words and ARABIC_RE.search(row_words[-1]["text"]):
        row_words.pop()

    if not row_words:
        return None

    # Leading non-numeric words = the province label (may be multiple
    # words, e.g. "Sidi Kacem")
    label_words = []
    i = 0
    while i < len(row_words) and not NUMERIC_RE.match(row_words[i]["text"]):
        label_words.append(row_words[i]["text"])
        i += 1
    label = " ".join(label_words)
    data_words = row_words[i:]

    if not label or len(data_words) == 0:
        return None

    # Group remaining words into columns using the x-gap threshold
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
        return None  # not the row shape we expect -- skip rather than guess

    values = []
    for group in columns:
        text = "".join(w["text"] for w in group)
        values.append(0.0 if text == "-" else float(text.replace(",", ".")))

    return label, values


def extract_table(words, top_min, top_max):
    """Extract all data rows whose vertical position falls in [top_min, top_max)."""
    relevant_words = [w for w in words if top_min <= w["top"] < top_max]
    rows = group_words_into_rows(relevant_words)

    results = []
    for row_words in rows.values():
        parsed = parse_data_row(row_words)
        if parsed:
            label, values = parsed
            results.append({
                "province": label,
                "ble_dur": values[0],
                "ble_tendre": values[1],
                "orge": values[2],
                "mais": values[3],
                "riz": values[4],
                "total": values[5],
            })
    return results


if __name__ == "__main__":
    with pdfplumber.open(PDF_PATH) as pdf:
        page = pdf.pages[PAGE_NUMBER - 1]
        words = page.extract_words()

    # Find the vertical split point between the area table and the
    # production table by locating the "PRODUCTION" title's position.
    prod_title_words = [w for w in words if w["text"] == "PRODUCTION"]
    if not prod_title_words:
        raise RuntimeError("Could not find 'PRODUCTION' title on this page")
    split_top = prod_title_words[0]["top"]

    area_rows = extract_table(words, top_min=0, top_max=split_top)
    production_rows = extract_table(words, top_min=split_top, top_max=page.height)

    print("=== AREA (hectares) ===")
    for r in area_rows:
        print(r)

    print("\n=== PRODUCTION (tonnes) ===")
    for r in production_rows:
        print(r)

    print("\n=== COMPUTED WHEAT YIELD (tonnes/ha), 2021-2022 campaign ===")
    area_by_province = {r["province"]: r for r in area_rows}
    for prod in production_rows:
        province = prod["province"]
        area = area_by_province.get(province)
        if not area:
            print(f"  (no matching area row for '{province}')")
            continue
        for crop in ["ble_dur", "ble_tendre"]:
            if area[crop] > 0:
                yield_t_ha = prod[crop] / area[crop]
                print(f"  {province:20s} {crop:12s} area={area[crop]:>10.1f} ha  "
                      f"production={prod[crop]:>10.1f} t  yield={yield_t_ha:.3f} t/ha")
