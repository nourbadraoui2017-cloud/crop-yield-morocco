"""
pull_weather_nasa_power.py -- Ajoute des features meteo (pluie, temperature)
depuis l'API NASA POWER, en complement du NDVI, pour les 6 saisons
d'entrainement.

Pourquoi maintenant : le NDVI capture "a quel point la culture est verte",
mais pas directement "combien il a plu". Deux saisons peuvent avoir un
NDVI similaire pour des raisons differentes. La pluviometrie cumulee
pendant la periode de croissance est un des predicteurs les plus
classiques du rendement agricole, et elle avait ete mise de cote deux
fois dans ce projet faute de temps (voir PROGRESS.md).

API utilisee : NASA POWER (power.larc.nasa.gov), gratuite, SANS cle
d'API, communaute "AG" (agriculture). Parametres :
- PRECTOTCORR : precipitations quotidiennes corrigees (mm/jour)
- T2M : temperature moyenne a 2m (degres C)

Point utilise : le centre de la meme boite englobante que pour le NDVI
(ee.Geometry.Rectangle([-7.0, 33.5, -5.5, 34.9]) dans pull_ndvi.py),
soit environ (34.2 N, -6.25 E). NASA POWER a une resolution assez
large (~50km) donc un seul point suffit pour toute la region.

WHERE TO RUN : localement, meme venv que les autres scripts. Necessite
internet reel, mais PAS de compte/cle API (contrairement a Earth
Engine) -- devrait marcher du premier coup.

Usage: python src/pull_weather_nasa_power.py
"""

import time

import pandas as pd
import requests

LATITUDE = 34.2
LONGITUDE = -6.25
SEASONS = [2014, 2015, 2016, 2017, 2018, 2021]  # memes saisons que le NDVI d'entrainement

API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
OUTPUT_PATH = "data/processed/weather_features.csv"


def fetch_season_weather(start_year: int) -> pd.DataFrame:
    start = f"{start_year}1101"
    end = f"{start_year + 1}0630"

    params = {
        "parameters": "PRECTOTCORR,T2M",
        "community": "AG",
        "longitude": LONGITUDE,
        "latitude": LATITUDE,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    response = requests.get(API_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()["properties"]["parameter"]

    dates = list(data["PRECTOTCORR"].keys())
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(dates, format="%Y%m%d"),
            "precip_mm": [data["PRECTOTCORR"][d] for d in dates],
            "temp_c": [data["T2M"][d] for d in dates],
        }
    )
    # NASA POWER utilise -999 comme valeur manquante
    df["precip_mm"] = df["precip_mm"].replace(-999, pd.NA)
    df["temp_c"] = df["temp_c"].replace(-999, pd.NA)
    df["season"] = start_year
    return df


def summarize_season(df: pd.DataFrame, season: int) -> dict:
    growth_stage = df[df["date"].dt.month.isin([2, 3, 4])]
    establishment = df[df["date"].dt.month.isin([11, 12])]

    return {
        "season": season,
        "rain_total_mm": df["precip_mm"].sum(),
        "rain_growth_stage_mm": growth_stage["precip_mm"].sum(),
        "rain_establishment_mm": establishment["precip_mm"].sum(),
        "temp_mean_c": df["temp_c"].mean(),
        "temp_growth_stage_mean_c": growth_stage["temp_c"].mean(),
    }


if __name__ == "__main__":
    summaries = []
    for season in SEASONS:
        print(f"Saison {season}-{season + 1}...")
        raw = fetch_season_weather(season)
        summaries.append(summarize_season(raw, season))
        time.sleep(1)  # eviter de trop solliciter l'API d'un coup

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUTPUT_PATH, index=False)
    print("\n=== Features meteo par saison ===")
    print(summary_df.to_string(index=False))
    print(f"\nSauvegarde dans {OUTPUT_PATH}")
