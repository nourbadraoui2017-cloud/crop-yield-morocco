"""
dashboard/app.py — Etape 4 : dashboard Streamlit MVP.

Charge le modele entraine a l'etape 3 (models/baseline_model.joblib) et
l'utilise pour transformer une valeur de NDVI en prevision de rendement,
affichee a cote de la moyenne historique.

Lancer avec (depuis C:\\crop-yield-morocco, venv active) :
    streamlit run dashboard/app.py

Note : c'est un MVP a un seul input (la feature retenue a l'etape 3,
normalement ndvi_peak). Plus tard, cet input pourra venir directement
d'un pull NDVI en cours de saison (src/pull_ndvi.py) au lieu d'etre
saisi a la main.
"""

import glob
import json

import joblib
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

DATA_PATH = "data/processed/training_table_landsat.csv"
WEATHER_PATH = "data/processed/weather_features.csv"
MODEL_PATH = "models/baseline_model.joblib"
MODEL_INFO_PATH = "models/baseline_model_info.json"
REAL_PREDICTION_GLOB = "data/processed/prediction_*.csv"
TARGET = "wheat_yield_t_ha"

# Trois couleurs, choisies pour rester distinguables meme en cas de
# daltonisme : bleu = historique reel, orange = simulateur "et si",
# vert = vraie prediction (calculee a partir de vrai NDVI satellite).
COLOR_HISTORY = "#4C72B0"
COLOR_SIMULATOR = "#DD8452"
COLOR_REAL_PREDICTION = "#55A868"

st.set_page_config(page_title="Prevision rendement ble - Rabat-Sale-Kenitra", layout="centered")


@st.cache_data
def load_data():
    """
    Charge le NDVI + rendement, et fusionne les features meteo (etape 3bis)
    si ce fichier existe -- le modele retenu peut utiliser une feature
    meteo en plus du NDVI (ex: rain_establishment_mm), donc le dashboard
    doit pouvoir lui fournir un slider pour n'importe quelle feature
    qu'il utilise reellement, pas seulement le NDVI.
    """
    df = pd.read_csv(DATA_PATH)
    try:
        weather_df = pd.read_csv(WEATHER_PATH)
        df = df.merge(weather_df, on="season", how="left")
    except FileNotFoundError:
        pass
    return df


@st.cache_resource
def load_model():
    model = joblib.load(MODEL_PATH)
    with open(MODEL_INFO_PATH, encoding="utf-8") as f:
        info = json.load(f)
    return model, info


def load_latest_real_prediction():
    """
    Charge la prediction reelle la plus recente generee par
    src/predict_current_season.py (fichier data/processed/prediction_*.csv).
    Retourne None si le script n'a encore jamais ete lance -- le
    dashboard doit rester utilisable meme sans ca, juste avec le
    simulateur.
    """
    files = sorted(glob.glob(REAL_PREDICTION_GLOB))
    if not files:
        return None
    return pd.read_csv(files[-1]).iloc[0]


df = load_data()
model, info = load_model()
features = info["features"]
real_pred = load_latest_real_prediction()

st.title("Prevision du rendement du ble — Rabat-Sale-Kenitra")
st.caption(
    "Prototype (proof-of-concept) entraine sur seulement 6 saisons "
    "(2014-2015 a 2021-2022). A prendre comme une demonstration du "
    "pipeline, pas comme un modele pret pour la production."
)

if real_pred is not None:
    st.subheader(f"Prediction reelle — saison {real_pred['campaign']}")
    st.write(
        "Calculee a partir du vrai NDVI satellite de cette saison "
        "(`src/predict_current_season.py`), pas d'une valeur saisie a la main."
    )
    real_delta = float(real_pred["predicted_yield_t_ha"]) - float(real_pred["historical_avg_t_ha"])
    col1, col2 = st.columns(2)
    col1.metric(
        "Rendement predit (reel)",
        f"{float(real_pred['predicted_yield_t_ha']):.2f} t/ha",
        delta=f"{real_delta:+.2f} t/ha vs moyenne",
    )
    col2.metric("Moyenne historique", f"{float(real_pred['historical_avg_t_ha']):.2f} t/ha")
else:
    st.info(
        "Aucune prediction reelle trouvee pour l'instant. Lance "
        "`python src\\predict_current_season.py` dans un terminal pour en "
        "generer une a partir de vraies donnees satellite."
    )

st.divider()

st.subheader("Simulateur — tester d'autres valeurs de NDVI")
st.caption(
    "Ceci n'est PAS une prediction en direct : c'est un outil pour explorer "
    "comment le modele reagirait a une valeur de NDVI hypothetique, saisie "
    "a la main ci-dessous."
)

# Un input par feature retenue par le modele (aujourd'hui juste ndvi_peak,
# mais ecrit pour rester correct si un futur modele en retient plusieurs).
input_values = {}
for feature in features:
    historical_min = float(df[feature].min())
    historical_max = float(df[feature].max())
    historical_mean = float(df[feature].mean())
    input_values[feature] = st.slider(
        feature,
        min_value=round(historical_min - 0.05, 2),
        max_value=round(historical_max + 0.05, 2),
        value=round(historical_mean, 2),
        step=0.01,
        help=f"Plage observee historiquement : {historical_min:.2f} a {historical_max:.2f}",
    )

X_input = pd.DataFrame([input_values])[features]
simulated_prediction = float(model.predict(X_input)[0])
historical_avg = float(df[TARGET].mean())
simulated_delta = simulated_prediction - historical_avg

col1, col2 = st.columns(2)
col1.metric(
    "Rendement simule",
    f"{simulated_prediction:.2f} t/ha",
    delta=f"{simulated_delta:+.2f} t/ha vs moyenne",
)
col2.metric("Moyenne historique (6 saisons)", f"{historical_avg:.2f} t/ha")

st.subheader("Rendement historique vs prevision")

seasons = df["campaign"].tolist()
yields = df[TARGET].tolist()
colors = [COLOR_HISTORY] * len(df)

if real_pred is not None:
    seasons.append(f"{real_pred['campaign']} (reel)")
    yields.append(float(real_pred["predicted_yield_t_ha"]))
    colors.append(COLOR_REAL_PREDICTION)

seasons.append("Simulateur (saisie actuelle)")
yields.append(simulated_prediction)
colors.append(COLOR_SIMULATOR)

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.bar(seasons, yields, color=colors)
ax.axhline(
    historical_avg,
    color="#666666",
    linestyle="--",
    linewidth=1,
    label=f"Moyenne historique ({historical_avg:.2f} t/ha)",
)
ax.set_ylabel("Rendement (t/ha)")
ax.set_title("Rendement par saison")
ax.legend()
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
st.pyplot(fig)

with st.expander("Details du modele"):
    st.write(f"**Modele retenu** : {info['model_name']}")
    st.write(f"**Features** : {', '.join(features)}")
    st.write(f"**MAE (validation leave-one-out)** : {info['loo_mae']:.3f} t/ha")
    st.write(f"**RMSE (validation leave-one-out)** : {info['loo_rmse']:.3f} t/ha")
    st.write(f"**R2 (validation leave-one-out)** : {info['loo_r2']:.3f}")
    st.write(f"**Entraine sur** : {info['trained_on_n_seasons']} saisons")
    st.caption(
        "R2 calcule en leave-one-out sur seulement 6 points : encourageant "
        "mais fragile, pourrait changer avec une saison de donnees en plus."
    )
    if len(features) > 1:
        st.warning(
            "Ce modele a plus d'une feature, choisie parmi une dizaine de "
            "candidats testes sur seulement 6 points de validation. Avec si "
            "peu de donnees, une partie de l'avantage mesure peut venir du "
            "hasard plutot que d'un vrai signal -- a interpreter avec "
            "prudence (voir PROGRESS.md pour le detail)."
        )

with st.expander("Donnees historiques utilisees"):
    st.dataframe(df, width="stretch")
