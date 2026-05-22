"""
VICTOR V2 — Étape 3 : Entraînement multi-modèles par discipline
===============================================================
Entrée  : data/dataset_final.csv
Sortie  : models/victor_v2_PLAT.pkl
          models/victor_v2_TROT.pkl
          models/victor_v2_OBSTACLE.pkl
          models/victor_v2_GLOBAL.pkl  (fallback toutes disciplines)
          models/features.json

Nouveauté v3 :
- Un modèle entraîné PAR discipline (PLAT, TROT, OBSTACLE)
- Un modèle global en fallback si la discipline est inconnue
- 23 features au lieu de 17
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import json
import os
from sklearn.metrics import roc_auc_score, classification_report

DOSSIER_DATA   = "data"
DOSSIER_MODELS = "models"
os.makedirs(DOSSIER_MODELS, exist_ok=True)

FEATURES = [
    "cote", "log_cote", "rang_cote", "est_favori",
    "nb_partants", "distance", "discipline_code", "allocation",
    "forme_recente", "forme_10", "meilleure_place", "regularite", "momentum",
    "taux_victoire_cheval", "taux_victoire_jockey",
    "taux_hippo_cheval", "taux_distance",
    "taux_saison", "nb_victoires_saison", "nb_courses_saison",
    "age", "poids", "taux_hippo",
]
TARGET = "succes"

# Mapping discipline_code → nom lisible
DISC_NOMS = {0: "CROSS", 1: "OBSTACLE", 2: "PLAT", 3: "TROT_ATTELE", 4: "TROT_MONTE"}

# ─────────────────────────────────────────────
# FONCTIONS COMMUNES
# ─────────────────────────────────────────────

def charger():
    chemin = os.path.join(DOSSIER_DATA, "dataset_final.csv")
    df = pd.read_csv(chemin, encoding="utf-8-sig")

    # Garder seulement les features disponibles
    features_dispo = [f for f in FEATURES if f in df.columns]
    manquantes = [f for f in FEATURES if f not in df.columns]
    if manquantes:
        print(f"⚠️  Features absentes du CSV (seront ignorées) : {manquantes}")

    df = df.dropna(subset=features_dispo + [TARGET])
    print(f"📥 Dataset : {len(df)} lignes | Succès : {df[TARGET].mean()*100:.1f}%")
    return df, features_dispo

def split_temporel(df):
    n     = len(df)
    seuil = int(n * 0.80)
    train = df.iloc[:seuil]
    test  = df.iloc[seuil:]
    print(f"✂️  Train : {len(train)} | Test : {len(test)}")
    return train, test

def entrainer_un_modele(train, test, features, label="GLOBAL"):
    X_train, y_train = train[features], train[TARGET]
    X_test,  y_test  = test[features],  test[TARGET]

    if len(y_train) < 100:
        print(f"  ⚠️  Pas assez de données pour {label} ({len(y_train)} lignes) — ignoré")
        return None, 0.0

    ratio = max(1.0, (y_train == 0).sum() / max((y_train == 1).sum(), 1))

    params = {
        "objective"        : "binary",
        "metric"           : "auc",
        "learning_rate"    : 0.05,
        "n_estimators"     : 1000,
        "num_leaves"       : 63,
        "max_depth"        : 7,
        "min_child_samples": 20,
        "feature_fraction" : 0.8,
        "bagging_fraction" : 0.8,
        "bagging_freq"     : 5,
        "scale_pos_weight" : ratio,
        "verbose"          : -1,
        "random_state"     : 42,
    }

    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50, verbose=False),
            lgb.log_evaluation(period=200),
        ],
    )

    y_proba = model.predict_proba(X_test)[:, 1]
    auc     = roc_auc_score(y_test, y_proba)
    print(f"  ✅ {label} — AUC : {auc*100:.1f}% ({len(train)} lignes train)")
    return model, auc

# ─────────────────────────────────────────────
# ENTRAÎNEMENT PAR DISCIPLINE
# ─────────────────────────────────────────────

def main():
    df, features = charger()

    print("\n" + "="*55)
    print("🏇 ENTRAÎNEMENT GLOBAL (toutes disciplines)")
    print("="*55)
    train_g, test_g   = split_temporel(df)
    model_g, auc_g    = entrainer_un_modele(train_g, test_g, features, "GLOBAL")

    resultats = {"GLOBAL": {"model": model_g, "auc": auc_g, "features": features}}

    print("\n" + "="*55)
    print("🎯 ENTRAÎNEMENT PAR DISCIPLINE")
    print("="*55)

    for code, nom in DISC_NOMS.items():
        df_disc = df[df["discipline_code"] == code]
        if len(df_disc) < 200:
            print(f"  ⏭️  {nom} : seulement {len(df_disc)} lignes — pas assez pour un modèle dédié")
            continue

        print(f"\n── {nom} ({len(df_disc)} lignes) ──")

        # Pour un modèle par discipline, on retire discipline_code (inutile)
        feats_disc = [f for f in features if f != "discipline_code"]
        train_d, test_d = split_temporel(df_disc)
        model_d, auc_d  = entrainer_un_modele(train_d, test_d, feats_disc, nom)

        if model_d is not None:
            resultats[nom] = {"model": model_d, "auc": auc_d, "features": feats_disc}

    # ─── Sauvegarde ───
    print("\n" + "="*55)
    print("💾 SAUVEGARDE")
    print("="*55)

    meta = {"modeles": {}, "features_global": features}

    for nom, res in resultats.items():
        if res["model"] is None:
            continue
        chemin = os.path.join(DOSSIER_MODELS, f"victor_v2_{nom}.pkl")
        joblib.dump(res["model"], chemin)
        meta["modeles"][nom] = {
            "fichier" : f"victor_v2_{nom}.pkl",
            "auc"     : round(res["auc"], 4),
            "features": res["features"],
        }
        print(f"  ✅ {chemin} (AUC {res['auc']*100:.1f}%)")

    # Compatibilité avec l'ancienne interface (victor_v2.pkl = modèle global)
    if model_g:
        joblib.dump(model_g, os.path.join(DOSSIER_MODELS, "victor_v2.pkl"))

    meta["auc"]      = round(auc_g, 4)
    meta["features"] = features
    meta["accuracy"] = 0.0
    meta["target"]   = TARGET
    meta["n_features"] = len(features)

    with open(os.path.join(DOSSIER_MODELS, "features.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n  ✅ features.json sauvegardé")
    print("\n" + "="*55)
    print("🏆 Entraînement terminé !")
    print(f"   Modèle global AUC : {auc_g*100:.1f}%")
    for nom, res in resultats.items():
        if nom != "GLOBAL" and res["model"] is not None:
            print(f"   Modèle {nom:<12} AUC : {res['auc']*100:.1f}%")
    print("="*55)

if __name__ == "__main__":
    main()