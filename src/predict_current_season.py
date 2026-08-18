"""
predict_current_season.py — Utilise le modele entraine (etape 3) pour
predire le rendement d'une saison reelle qui n'a PAS servi a l'entrainement.

Aujourd'hui (aout 2026), la saison 2026-2027 n'a pas encore commence
(plantation nov-dec 2026) -- impossible de la predire, aucune image
satellite n'existe encore pour elle. La derniere saison DEJA TERMINEE
est 2025-2026 (recolte mai-juin 2026) : c'est elle qu'on predit ici --
le test le plus honnete possible aujourd'hui, sur une saison que le
modele n'a jamais vue, ni a l'entrainement ni ailleurs.

Important -- piege du capteur : on reutilise Landsat 8 (pas Sentinel-2)
parce que le modele a ete entraine sur du NDVI Landsat uniquement.
Le NDVI Sentinel-2 est systematiquement plus bas pour la meme realite
de terrain (peak ~0.45 vs ~0.68 pour Landsat sur les memes saisons,
vu a l'etape 2). Le melanger directement biaiserait la prediction vers
le bas. Utiliser Sentinel-2 en direct (meilleure resolution/frequence,
le vrai plan a terme) demandera d'abord une correction
Sentinel<->Landsat, pas encore construite.

On reutilise directement get_season_ndvi_points() et summarize_season()
de pull_ndvi_landsat.py, et fetch_season_weather()/summarize_season() de
pull_weather_nasa_power.py -- meme logique deja testee pour les 6 saisons
d'entrainement, donc pas de code duplique, et surtout on ne touche a
aucun fichier du pipeline d'entrainement (pas de risque de corrompre
training_table_landsat.csv ou weather_features.csv).

Note (etape 3bis) : le modele retenu peut maintenant utiliser une feature
meteo (rain_establishment_mm) en plus du NDVI -- ce script pull donc les
deux, et ne construit la prediction qu'a partir de ce que
models/baseline_model_info.json indique reellement utiliser (info["features"]),
pour rester correct meme si le modele change a nouveau plus tard.

WHERE TO RUN: localement, meme venv que les autres scripts. Necessite
internet reel + earthengine-api (pour le NDVI) -- la partie meteo
n'a besoin d'aucune cle/compte.

Usage: python src/predict_current_season.py
"""

import json

import joblib
import pandas as pd

from pull_ndvi_landsat import get_season_ndvi_points, summarize_season as summarize_ndvi_season
from pull_weather_nasa_power import fetch_season_weather, summarize_season as summarize_weather_season

SEASON_TO_PREDICT = 2025  # = saison 2025-2026 (nov 2025 - juin 2026), la derniere terminee

MODEL_PATH = "models/baseline_model.joblib"
MODEL_INFO_PATH = "models/baseline_model_info.json"
TRAINING_DATA_PATH = "data/processed/training_table_landsat.csv"
OUTPUT_PATH = f"data/processed/prediction_{SEASON_TO_PREDICT}_{SEASON_TO_PREDICT + 1}.csv"


def main():
    print(f"Pull du NDVI Landsat 8 pour la saison {SEASON_TO_PREDICT}-{SEASON_TO_PREDICT + 1}...")
    raw_ndvi = get_season_ndvi_points(SEASON_TO_PREDICT)
    if raw_ndvi.empty:
        print("Aucune image Landsat trouvee pour cette saison -- impossible de predire.")
        return

    features_row = summarize_ndvi_season(raw_ndvi, SEASON_TO_PREDICT)
    print("\nFeatures NDVI calculees :")
    for k, v in features_row.items():
        print(f"  {k}: {v}")

    print(f"\nPull des donnees meteo NASA POWER pour la saison {SEASON_TO_PREDICT}-{SEASON_TO_PREDICT + 1}...")
    raw_weather = fetch_season_weather(SEASON_TO_PREDICT)
    weather_row = summarize_weather_season(raw_weather, SEASON_TO_PREDICT)
    print("Features meteo calculees :")
    for k, v in weather_row.items():
        print(f"  {k}: {v}")
    features_row.update(weather_row)

    with open(MODEL_INFO_PATH, encoding="utf-8") as f:
        info = json.load(f)
    model = joblib.load(MODEL_PATH)
    features = info["features"]

    missing = [f for f in features if features_row.get(f) is None]
    if missing:
        print(
            f"\nATTENTION: feature(s) manquante(s) {missing} (probablement pas assez "
            f"d'images claires sur la periode correspondante) -- prediction impossible."
        )
        return

    X = pd.DataFrame([{f: features_row[f] for f in features}])
    prediction = float(model.predict(X)[0])

    train_df = pd.read_csv(TRAINING_DATA_PATH)
    historical_avg = float(train_df["wheat_yield_t_ha"].mean())

    print("\n" + "=" * 60)
    print(f"PREDICTION saison {SEASON_TO_PREDICT}-{SEASON_TO_PREDICT + 1}")
    print("=" * 60)
    print(f"Rendement predit      : {prediction:.3f} t/ha")
    print(f"Moyenne historique    : {historical_avg:.3f} t/ha (6 saisons 2014-2022)")
    print(f"Ecart vs moyenne      : {prediction - historical_avg:+.3f} t/ha")
    print(
        f"\nRappel : MAE du modele en validation = {info['loo_mae']:.3f} t/ha -- "
        f"a lire comme 'incertitude typique', pas une prediction exacte."
    )

    pd.DataFrame(
        [
            {
                "season": SEASON_TO_PREDICT,
                "campaign": f"{SEASON_TO_PREDICT}-{SEASON_TO_PREDICT + 1}",
                **{f: features_row[f] for f in features},
                "predicted_yield_t_ha": prediction,
                "historical_avg_t_ha": historical_avg,
            }
        ]
    ).to_csv(OUTPUT_PATH, index=False)
    print(f"\nSauvegarde dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
