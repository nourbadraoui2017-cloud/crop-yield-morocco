"""
Print full text + detected tables for a specific range of pages from
the already-downloaded HCP regional annuaire.

Usage: python src/print_pages.py 34 40
(prints pages 34 through 40, 1-indexed, inclusive)
"""

import sys
import pdfplumber

PDF_PATH = "data/raw/hcp_annuaire_rsk_2023.pdf"

start_page = int(sys.argv[1]) if len(sys.argv) > 1 else 34
end_page = int(sys.argv[2]) if len(sys.argv) > 2 else 40

with pdfplumber.open(PDF_PATH) as pdf:
    for p in range(start_page, end_page + 1):
        if p - 1 >= len(pdf.pages):
            break
        page = pdf.pages[p - 1]
        print(f"\n{'=' * 20} PAGE {p} {'=' * 20}")
        print(page.extract_text())
        tables = page.extract_tables()
        if tables:
            print(f"\n--- {len(tables)} table(s) detected ---")
            for t in tables:
                for row in t:
                    print(row)
