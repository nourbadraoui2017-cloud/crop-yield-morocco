"""
calibrate_sentinel_landsat.py -- Calibre le NDVI Sentinel-2 vers l'echelle
Landsat, pour pouvoir un jour nourrir le modele (entraine sur du NDVI
Landsat) avec des donnees Sentinel-2 en direct pendant la saison en cours
-- Sentinel-2 a une bien meilleure frequence de passage (~5 jours vs 16
pour Landsat), donc c'est le vrai plan pour des predictions EN COURS de
saison plutot qu'apres coup comme aujourd'hui avec
predict_current_season.py.

Pourquoi une correction est necessaire : vu a l'etape 2, Landsat donne un
NDVI systematiquement plus haut que Sentinel-2 pour la meme realite de
terrain (capteur, bandes spectrales et resolution differents). Nourrir
le modele avec du NDVI Sentinel-2 brut le biaiserait vers le bas.

Donnees utilisees : les 3 saisons ou on a calcule le NDVI avec LES DEUX
capteurs separement (2017-18, 2018-19, 2021-22) -- data/processed/
training_table.csv (Sentinel-2) et training_table_landsat.csv (Landsat).
On y ajuste une regression lineaire simple : landsat_peak = a + b * sentinel_peak.

ATTENTION -- encore plus fragile que le modele de rendement lui-meme :
on calibre sur seulement 3 points (2 parametres a ajuster, donc 1 seul
"degre de liberte" reel). A traiter comme une preuve de concept, pas
comme une correction fiable, tant qu'on n'a pas plus de saisons ou les
deux capteurs se chevauchent.

Validation : on applique la correction aux 3 saisons de chevauchement et
on compare "prediction avec Sentinel-2 corrige" vs "prediction avec le
vrai Landsat" vs "rendement reel" -- si les deux premieres se
ressemblent, la correction fait a peu pres son travail.

Usage: python src/calibrate_sentinel_landsat.py
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

SENTINEL_PATH = "data/processed/training_table.csv"
LANDSAT_PATH = "data/processed/training_table_landsat.csv"
WEATHER_PATH = "data/processed/weather_features.csv"
MODEL_PATH = "models/baseline_model.joblib"
MODEL_INFO_PATH = "models/baseline_model_info.json"
CALIBRATION_PATH = "models/sentinel_to_landsat_calibration.json"


def main():
    sentinel_df = pd.read_csv(SENTINEL_PATH)[["season", "ndvi_peak"]].rename(
        columns={"ndvi_peak": "ndvi_peak_sentinel"}
    )
    landsat_df = pd.read_csv(LANDSAT_PATH)[["season", "ndvi_peak", "campaign", "wheat_yield_t_ha"]].rename(
        columns={"ndvi_peak": "ndvi_peak_landsat"}
    )

    overlap = landsat_df.merge(sentinel_df, on="season", how="inner")
    print(f"Saisons avec les deux capteurs : {len(overlap)}")
    print(overlap[["campaign", "ndvi_peak_sentinel", "ndvi_peak_landsat"]].to_string(index=False))

    if len(overlap) < 3:
        print("Pas assez de saisons de chevauchement pour calibrer -- abandon.")
        return

    X = overlap[["ndvi_peak_sentinel"]]
    y = overlap["ndvi_peak_landsat"]

    calib_model = LinearRegression()
    calib_model.fit(X, y)
    predicted_landsat = calib_model.predict(X)
    r2 = r2_score(y, predicted_landsat)

    a = float(calib_model.intercept_)
    b = float(calib_model.coef_[0])

    print(f"\nCorrection ajustee : ndvi_peak_landsat_equivalent = {a:.4f} + {b:.4f} * ndvi_peak_sentinel")
    print(f"R2 sur les {len(overlap)} points de calibration : {r2:.3f}")
    print(
        f"\nATTENTION : calibre sur seulement {len(overlap)} points (2 parametres) -- "
        f"quasiment aucune marge pour verifier que ca generalise. A confirmer avec "
        f"plus de saisons de chevauchement a l'avenir."
    )

    os.makedirs("models", exist_ok=True)
    with open(CALIBRATION_PATH, "w") as f:
        json.dump(
            {
                "intercept": a,
                "coefficient": b,
                "r2_on_calibration_points": float(r2),
                "n_calibration_points": len(overlap),
                "formula": "ndvi_peak_landsat_equivalent = intercept + coefficient * ndvi_peak_sentinel",
            },
            f,
            indent=2,
        )
    print(f"Sauvegarde dans {CALIBRATION_PATH}")

    # --- Validation : la correction sert-elle vraiment a quelque chose ?
    # On refait les predictions de rendement des 3 saisons de chevauchement,
    # une fois avec le vrai Landsat, une fois avec le Sentinel-2 corrige, et
    # on compare les deux aux vrais rendements.
    print("\n" + "=" * 60)
    print("VALIDATION : predictions avec Landsat reel vs Sentinel-2 corrige")
    print("=" * 60)

    model = joblib.load(MODEL_PATH)
    with open(MODEL_INFO_PATH, encoding="utf-8") as f:
        info = json.load(f)
    features = info["features"]

    weather_df = pd.read_csv(WEATHER_PATH) if os.path.exists(WEATHER_PATH) else None
    if weather_df is not None:
        overlap = overlap.merge(weather_df, on="season", how="left")

    overlap["ndvi_peak_sentinel_corrige"] = a + b * overlap["ndvi_peak_sentinel"]

    for _, row in overlap.iterrows():
        row_landsat = {**row.to_dict(), "ndvi_peak": row["ndvi_peak_landsat"]}
        row_sentinel = {**row.to_dict(), "ndvi_peak": row["ndvi_peak_sentinel_corrige"]}

        missing = [f for f in features if f not in row_landsat or pd.isna(row_landsat[f])]
        if missing:
            print(f"{row['campaign']}: feature(s) manquante(s) {missing}, saison ignoree.")
            continue

        X_landsat = pd.DataFrame([{f: row_landsat[f] for f in features}])
        X_sentinel = pd.DataFrame([{f: row_sentinel[f] for f in features}])

        pred_landsat = float(model.predict(X_landsat)[0])
        pred_sentinel = float(model.predict(X_sentinel)[0])
        actual = row["wheat_yield_t_ha"]

        print(f"\n{row['campaign']} :")
        print(f"  Rendement reel                        : {actual:.3f} t/ha")
        print(f"  Predit avec Landsat reel               : {pred_landsat:.3f} t/ha")
        print(f"  Predit avec Sentinel-2 corrige         : {pred_sentinel:.3f} t/ha")
        print(f"  Ecart entre les deux methodes          : {abs(pred_landsat - pred_sentinel):.3f} t/ha")


if __name__ == "__main__":
    main()
