"""
train_baseline_model.py — Etape 3 : entrainer et valider un modele de regression
de base pour predire le rendement du ble (t/ha) a partir des features NDVI.

Avec seulement 6 saisons de donnees, on reste volontairement simple :
- Regression lineaire (et Ridge, une version regularisee) plutot qu'un modele
  complexe (un XGBoost/Random Forest apprendrait par coeur ces 6 points au
  lieu de generaliser).
- Validation "leave-one-season-out" (LOSO) : on entraine sur 5 saisons, on
  predit la 6e, on repete 6 fois (une fois par saison), puis on moyenne
  l'erreur. Avec une seule ligne par saison dans nos donnees, ca revient
  exactement a une validation "leave-one-out" (LOO) classique de sklearn.
  On n'utilise PAS un simple split train/test aleatoire : avec 6 points,
  un split aleatoire donnerait un resultat qui depend enormement du hasard
  du split, et on ne teste jamais sur toutes les saisons.

On compare plusieurs jeux de features : chaque feature NDVI seule, une
combinaison a 2 features (les deux meilleures individuellement), puis les
4 ensemble (avec Ridge pour limiter le risque de sur-ajustement quand on a
plus de features que de "degres de liberte"). A la fin, le meilleur modele
(le plus bas MAE en validation leave-one-out) est ré-entraine sur les 6
saisons completes et sauvegarde dans models/ pour etre reutilise (dashboard,
predictions futures) sans avoir a refaire cette comparaison a chaque fois.
"""

import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import LeaveOneOut
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

DATA_PATH = "data/processed/training_table_landsat.csv"
OUTPUT_PATH = "data/processed/baseline_model_comparison.csv"
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "baseline_model.joblib")
MODEL_INFO_PATH = os.path.join(MODEL_DIR, "baseline_model_info.json")

FEATURE_SETS = {
    "growth_stage_only": ["ndvi_growth_stage_mean"],
    "peak_only": ["ndvi_peak"],
    "mean_only": ["ndvi_mean"],
    "establishment_only": ["ndvi_establishment_mean"],
    "peak_and_growth_stage": ["ndvi_peak", "ndvi_growth_stage_mean"],
    "all_4_features": [
        "ndvi_peak",
        "ndvi_mean",
        "ndvi_growth_stage_mean",
        "ndvi_establishment_mean",
    ],
}

TARGET = "wheat_yield_t_ha"


def evaluate_model(model_name, model, features, X, y, seasons):
    """
    Fait une validation leave-one-out : pour chaque ligne (saison), on
    entraine le modele sur les 5 autres lignes et on predit celle qu'on a
    laissee de cote. A la fin on a une prediction "honnete" (jamais vue a
    l'entrainement) pour chacune des 6 saisons.
    """
    loo = LeaveOneOut()
    predictions = np.zeros(len(y))

    for train_idx, test_idx in loo.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train = y.iloc[train_idx]

        model.fit(X_train, y_train)
        predictions[test_idx] = model.predict(X_test)

    mae = mean_absolute_error(y, predictions)
    rmse = np.sqrt(mean_squared_error(y, predictions))
    r2 = r2_score(y, predictions)

    print(f"\n--- {model_name} ---")
    print(f"{'Saison':<12}{'Reel':>8}{'Predit':>10}{'Erreur':>10}")
    for season, actual, pred in zip(seasons, y, predictions):
        print(f"{season:<12}{actual:>8.2f}{pred:>10.2f}{abs(actual - pred):>10.2f}")
    print(f"MAE  = {mae:.3f} t/ha")
    print(f"RMSE = {rmse:.3f} t/ha")
    print(f"R2   = {r2:.3f}  (peut etre negatif avec si peu de points, c'est normal)")

    return {"model": model_name, "mae": mae, "rmse": rmse, "r2": r2, "features": features}


def main():
    df = pd.read_csv(DATA_PATH)
    y = df[TARGET]
    seasons = df["campaign"]

    results = []

    single_feature_names = {"growth_stage_only", "peak_only", "mean_only", "establishment_only"}

    print("=" * 60)
    print("MODELES LINEAIRES SIMPLES (une feature a la fois)")
    print("=" * 60)
    for name in single_feature_names:
        features = FEATURE_SETS[name]
        X = df[features]
        model = LinearRegression()
        results.append(
            evaluate_model(f"LinearRegression [{name}]", model, features, X, y, seasons)
        )

    print("\n" + "=" * 60)
    print("REGRESSION LINEAIRE (2 features : peak + growth_stage)")
    print("=" * 60)
    combo_features = FEATURE_SETS["peak_and_growth_stage"]
    X_combo = df[combo_features]
    results.append(
        evaluate_model(
            "LinearRegression [peak_and_growth_stage]",
            LinearRegression(),
            combo_features,
            X_combo,
            y,
            seasons,
        )
    )

    print("\n" + "=" * 60)
    print("REGRESSION LINEAIRE (4 features ensemble, sans regularisation)")
    print("=" * 60)
    all4_features = FEATURE_SETS["all_4_features"]
    X_all = df[all4_features]
    results.append(
        evaluate_model(
            "LinearRegression [all_4_features]", LinearRegression(), all4_features, X_all, y, seasons
        )
    )

    print("\n" + "=" * 60)
    print("RIDGE (regression regularisee, 4 features)")
    print("=" * 60)
    for alpha in [0.1, 1.0, 10.0]:
        model = Ridge(alpha=alpha)
        results.append(
            evaluate_model(
                f"Ridge (alpha={alpha}) [all_4_features]", model, all4_features, X_all, y, seasons
            )
        )

    print("\n" + "=" * 60)
    print("RESUME - classe du meilleur au moins bon (MAE le plus bas)")
    print("=" * 60)
    results_df = pd.DataFrame(results).sort_values("mae")
    print(results_df.drop(columns="features").to_string(index=False))

    results_df.drop(columns="features").to_csv(OUTPUT_PATH, index=False)
    print(f"\nResultats sauvegardes dans {OUTPUT_PATH}")

    # --- Finalisation : on reprend le meilleur modele (MAE le plus bas en LOO)
    # et on le ré-entraine sur les 6 saisons completes (plus de "trou" laisse
    # de cote), pour avoir le modele final pret a servir pour de vraies
    # predictions futures. Note : LOO nous dit quel MODELE / quelles FEATURES
    # generalisent le mieux, mais le modele final sauvegarde ici a vu les 6
    # saisons pendant son entrainement — normal, c'est la meilleure version
    # possible pour un usage reel, ce n'est plus une evaluation.
    best = results_df.iloc[0]
    best_name = best["model"]
    best_features = best["features"]

    if "Ridge" in best_name:
        alpha = float(best_name.split("alpha=")[1].split(")")[0])
        final_model = Ridge(alpha=alpha)
    else:
        final_model = LinearRegression()

    final_model.fit(df[best_features], y)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(final_model, MODEL_PATH)

    model_info = {
        "model_name": best_name,
        "features": best_features,
        "loo_mae": float(best["mae"]),
        "loo_rmse": float(best["rmse"]),
        "loo_r2": float(best["r2"]),
        "coefficients": dict(zip(best_features, final_model.coef_.tolist())),
        "intercept": float(final_model.intercept_),
        "trained_on_n_seasons": len(y),
    }
    with open(MODEL_INFO_PATH, "w") as f:
        json.dump(model_info, f, indent=2)

    print("\n" + "=" * 60)
    print(f"MODELE FINAL RETENU : {best_name}")
    print("=" * 60)
    print(f"Features   : {best_features}")
    print(f"MAE (LOO)  : {best['mae']:.3f} t/ha")
    print(f"R2  (LOO)  : {best['r2']:.3f}")
    print(f"Sauvegarde : {MODEL_PATH}")
    print(f"Infos      : {MODEL_INFO_PATH}")


if __name__ == "__main__":
    main()
