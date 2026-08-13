"""
Diagnostic v2: find the "Agriculture" chapter itself in the 2020
annuaire (regardless of exact table title wording), and print what's
actually on those pages.

Usage: python src/debug_old_annuaire.py
"""

import pdfplumber

PDF_PATH = "data/raw/hcp_annuaire_rsk_2020.pdf"

with pdfplumber.open(PDF_PATH) as pdf:
    print(f"Total pages: {len(pdf.pages)}\n")

    # Look for pages where "Agriculture" appears as a short chapter-title-like
    # line (not buried in a long sentence), similar to how 2023's chapter
    # started with a standalone "Agriculture" line.
    candidate_pages = []
    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.lower().startswith("agriculture") and len(stripped) < 40:
                candidate_pages.append(i + 1)
                break

    print(f"Pages where a line starts with 'Agriculture' (short line, likely a heading): {candidate_pages}")

    # Print full text of the first few candidates
    for p in candidate_pages[:4]:
        print(f"\n{'=' * 20} PAGE {p} {'=' * 20}")
        print(pdf.pages[p - 1].extract_text()[:800])
