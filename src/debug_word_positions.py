"""
Diagnostic: print each word on the Khemisset production row along with
its x-position, so we can see the actual gap pattern between numbers
that belong to the same column vs numbers that are different columns.

Usage: python src/debug_word_positions.py
"""

import pdfplumber

PDF_PATH = "data/raw/hcp_annuaire_rsk_2023.pdf"
PAGE_NUMBER = 39

with pdfplumber.open(PDF_PATH) as pdf:
    page = pdf.pages[PAGE_NUMBER - 1]
    words = page.extract_words()

    # Find words on the same horizontal line as "Khémisset" (production row)
    # by locating it, then filtering for words with a similar 'top' value.
    khemisset_words = [w for w in words if w["text"].strip() == "Khémisset"]
    print(f"Found {len(khemisset_words)} 'Khémisset' word(s) on this page")

    for kw in khemisset_words:
        row_top = kw["top"]
        print(f"\n--- Row at top={row_top:.1f} ---")
        row_words = [w for w in words if abs(w["top"] - row_top) < 3]
        row_words.sort(key=lambda w: w["x0"])
        prev_x1 = None
        for w in row_words:
            gap = (w["x0"] - prev_x1) if prev_x1 is not None else 0
            print(f"  text={w['text']!r:20s} x0={w['x0']:.1f}  x1={w['x1']:.1f}  gap_from_prev={gap:.1f}")
            prev_x1 = w["x1"]
