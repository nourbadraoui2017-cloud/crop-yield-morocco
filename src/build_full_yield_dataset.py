"""
Combines both table-format parsers (2023's provinces-as-rows format,
and the older crops-as-rows format used ~2015-2020) across every
downloaded annuaire year, and builds one final multi-year wheat yield
dataset for Rabat-Sale-Kenitra.

Tries the old-format parser first (covers more years), falls back to
treating the file as new-format if that finds nothing. Skips any file
that's missing or corrupted rather than crashing the whole run.

Usage: python src/build_full_yield_dataset.py
"""

import os
import pandas as pd

import extract_cereal_table_old_format as old_fmt
import extract_cereal_table_all_years as new_fmt

YEARS = [2023, 2020, 2019, 2018, 2017, 2016, 2015, 2013, 2012, 2011, 2010, 2009, 2008]


def try_old_format(year: int) -> pd.DataFrame:
    try:
        return old_fmt.process_year(year)
    except Exception as e:
        print(f"    old-format parser failed: {e}")
        return pd.DataFrame()


def try_new_format(year: int) -> pd.DataFrame:
    try:
        url = new_fmt.ANNUAIRE_URLS.get(year)
        if not url:
            return pd.DataFrame()
        return new_fmt.process_one_annuaire(year, url)
    except Exception as e:
        print(f"    new-format parser failed: {e}")
        return pd.DataFrame()


if __name__ == "__main__":
    all_dfs = []

    for year in YEARS:
        pdf_path = f"data/raw/hcp_annuaire_rsk_{year}.pdf"
        print(f"\n=== {year} ===")
        if not os.path.exists(pdf_path):
            print("  PDF not downloaded yet -- run extract_cereal_table_all_years.py first")
            continue

        df = try_old_format(year)
        if df.empty:
            print("  Old format found nothing, trying new format...")
            df = try_new_format(year)

        if df.empty:
            print("  FAILED: neither format worked for this year")
        else:
            print(f"  SUCCESS: {len(df)} rows, campaign(s): {sorted(df['campaign'].unique())}")
            all_dfs.append(df)

    if not all_dfs:
        print("\nNothing extracted from any year.")
    else:
        combined = pd.concat(all_dfs, ignore_index=True)

        # Fix campaign labels that came out reversed (e.g. "2015-2014"
        # instead of "2014-2015") -- an artifact of extracting French
        # text mixed with right-to-left Arabic on the same line.
        def fix_campaign_order(campaign: str) -> str:
            parts = campaign.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                y1, y2 = int(parts[0]), int(parts[1])
                if y1 > y2:
                    return f"{y2}-{y1}"
            return campaign

        combined["campaign"] = combined["campaign"].apply(fix_campaign_order)

        out_path = "data/processed/wheat_yield_rabat_sale_kenitra_all_years.csv"
        combined.to_csv(out_path, index=False)
        print(f"\n=== FINAL: {len(combined)} rows saved to {out_path} ===")
        print(f"Years covered (by annuaire): {sorted(combined['annuaire_year'].unique())}")
        print(f"Campaigns covered: {sorted(combined['campaign'].unique())}")
