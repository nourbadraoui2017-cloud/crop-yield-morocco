"""
train_model_with_weather.py -- Etape 3bis : teste si les features meteo
(NASA POWER) ajoutent un vrai signal par rapport au NDVI seul.

Fusionne data/processed/training_table_landsat.csv (NDVI + rendement)
avec data/processed/weather_features.csv (pluie/temperature) sur la
colonne "season", puis compare plusieurs jeux de features en LOO
(leave-one-out), exactement comme dans train_baseline_model.py :
- chaque feature meteo seule
- le champion actuel (ndvi_peak seul, MAE=0.169 en reference)
- ndvi_peak combine a chaque feature meteo (2 features)

Important : ce script COMPARE seulement, il ne remplace PAS
automatiquement models/baseline_model.joblib. Avec seulement 6 points,
ajouter une feature n'ameliore pas forcement les choses (on l'a deja vu
avec le combo NDVI a l'etape 3) -- on decide ensemble, a partir des
vrais chiffres, si un nouveau modele merite de remplacer l'actuel.

Usage: python src/train_model_with_weather.py
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

NDVI_PATH = "data/processed/training_table_landsat.csv"
WEATHER_PATH = "data/processed/weather_features.csv"
OUTPUT_PATH = "data/processed/model_comparison_with_weather.csv"
TARGET = "wheat_yield_t_ha"

CHAMPION_MAE = 0.169  # ndvi_peak seul, etape 3 -- reference a battre

WEATHER_FEATURES = [
    "rain_total_mm",
    "rain_growth_stage_mm",
    "rain_establishment_mm",
    "temp_mean_c",
    "temp_growth_stage_mean_c",
]


def evaluate(model_name, features, X, y, seasons):
    loo = LeaveOneOut()
    predictions = np.zeros(len(y))
    for train_idx, test_idx in loo.split(X):
        model = LinearRegression()
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        predictions[test_idx] = model.predict(X.iloc[test_idx])

    mae = mean_absolute_error(y, predictions)
    rmse = np.sqrt(mean_squared_error(y, predictions))
    r2 = r2_score(y, predictions)

    print(f"\n--- {model_name} ---")
    for season, actual, pred in zip(seasons, y, predictions):
        print(f"  {season:<12} reel={actual:.2f}  predit={pred:.2f}  erreur={abs(actual - pred):.2f}")
    print(f"  MAE={mae:.3f}  RMSE={rmse:.3f}  R2={r2:.3f}")

    return {"model": model_name, "features": ", ".join(features), "mae": mae, "rmse": rmse, "r2": r2}


def main():
    ndvi_df = pd.read_csv(NDVI_PATH)
    weather_df = pd.read_csv(WEATHER_PATH)
    df = ndvi_df.merge(weather_df, on="season", how="inner")

    if len(df) != len(ndvi_df):
        print(
            f"ATTENTION: {len(ndvi_df)} saisons NDVI mais {len(df)} apres fusion "
            f"avec la meteo -- verifie que les saisons correspondent."
        )

    y = df[TARGET]
    seasons = df["campaign"]
    results = []

    print("=" * 60)
    print("FEATURES METEO SEULES")
    print("=" * 60)
    for feature in WEATHER_FEATURES:
        results.append(evaluate(f"[{feature}]", [feature], df[[feature]], y, seasons))

    print("\n" + "=" * 60)
    print("NDVI_PEAK + UNE FEATURE METEO (2 features)")
    print("=" * 60)
    for feature in WEATHER_FEATURES:
        combo = ["ndvi_peak", feature]
        results.append(evaluate(f"[ndvi_peak + {feature}]", combo, df[combo], y, seasons))

    print("\n" + "=" * 60)
    print(f"RESUME -- champion actuel (ndvi_peak seul) : MAE = {CHAMPION_MAE:.3f} t/ha")
    print("=" * 60)
    results_df = pd.DataFrame(results).sort_values("mae")
    print(results_df.to_string(index=False))

    best = results_df.iloc[0]
    if best["mae"] < CHAMPION_MAE:
        print(
            f"\n>> '{best['model']}' bat le champion actuel "
            f"({best['mae']:.3f} < {CHAMPION_MAE:.3f}) -- pourrait valoir le coup "
            f"de remplacer le modele sauvegarde."
        )
    else:
        print(
            f"\n>> Rien ne bat le champion actuel (ndvi_peak seul, {CHAMPION_MAE:.3f}). "
            f"La meteo n'ajoute pas de signal suffisant ici pour justifier une feature "
            f"de plus sur seulement 6 points -- le modele sauvegarde ne change pas."
        )

    results_df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSauvegarde dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
