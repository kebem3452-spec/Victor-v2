"""
VICTOR V2 — Étape 3 : Entraînement 4 modèles (Quinté / Trio / Couplé / Gagnant)
================================================================================
Entrée  : data/dataset_final.csv
Sortie  : models/victor_v2_GLOBAL_quinte.pkl
          models/victor_v2_GLOBAL_trio.pkl
          models/victor_v2_GLOBAL_couple.pkl
          models/victor_v2_GLOBAL_gagnant.pkl
          models/victor_v2_{DISCIPLINE}_quinte.pkl  (un par discipline)
          models/features.json
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import json
import os
from sklearn.metrics import roc_auc_score

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
    "temperature", "precipitation", "vent_kmh", "terrain_lourd",
    "jours_repos", "changement_jockey", "ecart_distance_opt",
]

# Mapping figé — NE JAMAIS CHANGER
DISC_NOMS = {
    0: "ATTELE",
    1: "CROSS",
    2: "HAIE",
    3: "MONTE",
    4: "PLAT",
    5: "STEEPLECHASE",
}

# Les 4 types de paris avec leur target et leur seuil de place
PARIS = {
    "quinte" : {"target": "succes",        "place_max": 5},
    "trio"   : {"target": "succes_trio",   "place_max": 3},
    "couple" : {"target": "succes_couple", "place_max": 2},
    "gagnant": {"target": "top1",          "place_max": 1},
}


# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

def charger():
    chemin = os.path.join(DOSSIER_DATA, "dataset_final.csv")
    df = pd.read_csv(chemin, encoding="utf-8-sig")

    features_dispo = [f for f in FEATURES if f in df.columns]
    manquantes     = [f for f in FEATURES if f not in df.columns]
    if manquantes:
        print(f"⚠️  Features absentes : {manquantes}")

    # Vérifier que les 4 targets existent
    for nom_pari, cfg in PARIS.items():
        if cfg["target"] not in df.columns:
            print(f"❌ Colonne '{cfg['target']}' manquante — "
                  f"relance d'abord python 2_feature_engineering.py")
            exit()

    df = df.dropna(subset=features_dispo)
    print(f"📥 Dataset : {len(df)} lignes | Features : {len(features_dispo)}")
    return df, features_dispo


# ─────────────────────────────────────────────
# SPLIT TEMPOREL
# ─────────────────────────────────────────────

def split_temporel(df):
    if "date" not in df.columns:
        n     = len(df)
        seuil = int(n * 0.80)
        train = df.iloc[:seuil]
        test  = df.iloc[seuil:]
        print(f"  ✂️  Train : {len(train)} | Test : {len(test)}")
        return train, test

    dates_triees  = sorted(df["date"].unique())
    seuil_idx     = int(len(dates_triees) * 0.80)
    date_coupure  = dates_triees[seuil_idx]

    train = df[df["date"] <  date_coupure].copy()
    test  = df[df["date"] >= date_coupure].copy()
    print(f"  ✂️  Train : {len(train)} lignes jusqu'au {date_coupure}")
    print(f"       Test  : {len(test)} lignes  à partir du {date_coupure}")
    return train, test


# ─────────────────────────────────────────────
# ENTRAÎNEMENT D'UN MODÈLE
# ─────────────────────────────────────────────

def entrainer(train, test, features, target, label):
    X_train = train[features]
    y_train = train[target]
    X_test  = test[features]
    y_test  = test[target]

    if len(y_train) < 100:
        print(f"  ⚠️  {label} : pas assez de données ({len(y_train)}) — ignoré")
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

    auc = roc_auc_score(y_test, model.predict_proba(X_test)[:, 1])
    print(f"  ✅ {label:<35} AUC : {auc*100:.1f}%")
    return model, auc


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    df, features = charger()
    meta = {"modeles": {}, "features_global": features, "paris": {}}

    # ── 1. Modèles GLOBAUX (toutes disciplines) ──
    print("\n" + "="*58)
    print("🌍 MODÈLES GLOBAUX")
    print("="*58)
    train_g, test_g = split_temporel(df)

    for nom_pari, cfg in PARIS.items():
        print(f"\n── Global {nom_pari.upper()} ──")
        model, auc = entrainer(
            train_g, test_g, features,
            target=cfg["target"],
            label=f"GLOBAL_{nom_pari}"
        )
        if model:
            fichier = f"victor_v2_GLOBAL_{nom_pari}.pkl"
            joblib.dump(model, os.path.join(DOSSIER_MODELS, fichier))
            meta["modeles"][f"GLOBAL_{nom_pari}"] = {
                "fichier"  : fichier,
                "auc"      : round(auc, 4),
                "features" : features,
                "pari"     : nom_pari,
                "place_max": cfg["place_max"],
            }

    # ── 2. Modèles PAR DISCIPLINE pour le Quinté ──
    print("\n" + "="*58)
    print("🎯 MODÈLES PAR DISCIPLINE (Quinté uniquement)")
    print("="*58)

    feats_disc = [f for f in features if f != "discipline_code"]

    for code, nom_disc in DISC_NOMS.items():
        df_disc = df[df["discipline_code"] == code]
        if len(df_disc) < 300:
            print(f"  ⏭️  {nom_disc} : {len(df_disc)} lignes — pas assez")
            continue

        print(f"\n── {nom_disc} ({len(df_disc)} lignes) ──")
        train_d, test_d = split_temporel(df_disc)
        model, auc = entrainer(
            train_d, test_d, feats_disc,
            target="succes",
            label=f"{nom_disc}_quinte"
        )
        if model:
            fichier = f"victor_v2_{nom_disc}_quinte.pkl"
            joblib.dump(model, os.path.join(DOSSIER_MODELS, fichier))
            meta["modeles"][f"{nom_disc}_quinte"] = {
                "fichier"  : fichier,
                "auc"      : round(auc, 4),
                "features" : feats_disc,
                "pari"     : "quinte",
                "place_max": 5,
            }

    # ── Compatibilité ancienne interface ──
    modele_global_quinte = os.path.join(DOSSIER_MODELS, "victor_v2_GLOBAL_quinte.pkl")
    compat = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")
    if os.path.exists(modele_global_quinte):
        import shutil
        shutil.copy(modele_global_quinte, compat)
        print(f"\n  📎 Copie compat : victor_v2.pkl = GLOBAL_quinte")

    # ── Sauvegarde features.json ──
    meta["features"]   = features
    meta["target"]     = "succes"
    meta["n_features"] = len(features)
    meta["auc"]        = meta["modeles"].get(
        "GLOBAL_quinte", {}).get("auc", 0.0)
    meta["disc_map"]   = DISC_NOMS

    with open(os.path.join(DOSSIER_MODELS, "features.json"), "w") as f:
        json.dump(meta, f, indent=2)

    # ── Résumé final ──
    print("\n" + "="*58)
    print("🏆 ENTRAÎNEMENT TERMINÉ")
    print("="*58)
    for nom, res in meta["modeles"].items():
        print(f"  ✅ {nom:<35} AUC : {res['auc']*100:.1f}%")
    print("="*58)
    print("\n✅ Lance maintenant : python 7_backtesting.py")


if __name__ == "__main__":
    main()
