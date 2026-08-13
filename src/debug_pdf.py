"""
Diagnostic v2: instead of requiring crop+yield keywords together on the
same page (too strict), just report which pages mention each keyword at
all, individually, so we can see what's actually in this document.

Usage: python src/debug_pdf.py
"""

import pdfplumber

pdf_path = "data/raw/ministry_agricultures_en_chiffres.pdf"

KEYWORDS = [
    "blé", "céréale", "rendement", "quintal", "qx/ha", "hectare",
    "production", "superficie", "campagne agricole",
]

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")

    for kw in KEYWORDS:
        pages_with_kw = []
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "").lower()
            if kw.lower() in text:
                pages_with_kw.append(i + 1)
        print(f"'{kw}': found on pages {pages_with_kw}")

    # Print full text of whichever page mentions "blé" most, if any
    print("\n--- Looking for the page most likely to have wheat data ---")
    best_page, best_count = None, 0
    for i, page in enumerate(pdf.pages):
        text = (page.extract_text() or "").lower()
        count = text.count("blé") + text.count("rendement") + text.count("céréale")
        if count > best_count:
            best_count, best_page = count, i

    if best_page is not None:
        print(f"Page {best_page + 1} looks most relevant ({best_count} keyword hits). Full text:\n")
        print(pdf.pages[best_page].extract_text())
    else:
        print("No page mentions wheat/cereal/yield terms at all.")
