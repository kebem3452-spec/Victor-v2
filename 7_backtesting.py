"""
VICTOR V2 — Étape 7 : Backtesting ROI (corrigé v3)
====================================================
Corrections :
- Cotes forcées en numérique avant filtrage
- Filtre 1.1 → 80.0 pour retirer les aberrations
- Plafond 30.0 sur les gains pour éviter les ROI fictifs
"""

import pandas as pd
import numpy as np
import joblib
import json
import os

DOSSIER_DATA   = "data"
DOSSIER_MODELS = "models"

# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

def charger_tout():
    chemin_model = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")
    chemin_meta  = os.path.join(DOSSIER_MODELS, "features.json")

    if not os.path.exists(chemin_model):
        print("❌ Modèle introuvable. Lance d'abord python 3_entrainer_modele.py")
        exit()

    model = joblib.load(chemin_model)
    with open(chemin_meta) as f:
        meta = json.load(f)
    features = meta["features"]

    chemin_csv = os.path.join(DOSSIER_DATA, "dataset_final.csv")
    df = pd.read_csv(chemin_csv, encoding="utf-8-sig")

    features_dispo = [f for f in features if f in df.columns]
    df = df.dropna(subset=features_dispo + ["succes", "place"])

    # ✅ Forcer le type numérique avant de filtrer
    df["cote"] = pd.to_numeric(df["cote"], errors="coerce")
    df = df[df["cote"].notna()].copy()

    # ✅ Filtrer les cotes aberrantes (99.0 = donnée manquante dans l'API)
    avant = len(df)
    df = df[(df["cote"] >= 1.1) & (df["cote"] <= 80.0)].copy()
    print(f"🧹 Cotes filtrées : {avant - len(df)} lignes retirées sur {avant}")

    if len(df) == 0:
        print("❌ ERREUR : toutes les lignes ont été filtrées.")
        df_check = pd.read_csv(chemin_csv, encoding="utf-8-sig")
        print(f"   Exemples de cotes brutes : {df_check['cote'].head(10).tolist()}")
        exit()

    n       = len(df)
    seuil   = int(n * 0.80)
    df_test = df.iloc[seuil:].copy()

    print(f"📊 Backtesting sur {len(df_test)} lignes (20% les plus récentes)")
    return model, features_dispo, df_test

# ─────────────────────────────────────────────
# CALCUL DES PROBABILITÉS
# ─────────────────────────────────────────────

def calculer_probas(model, features, df_test):
    df_test = df_test.copy()
    df_test["proba"] = model.predict_proba(df_test[features])[:, 1]
    return df_test

# ─────────────────────────────────────────────
# IDENTIFICATION DES COURSES
# ─────────────────────────────────────────────

def identifier_courses(df_test):
    df_test = df_test.sort_index().reset_index(drop=True)
    df_test["course_id"] = (
        (df_test["nb_partants"] != df_test["nb_partants"].shift()) |
        (df_test["distance"]    != df_test["distance"].shift())    |
        (df_test["taux_hippo"]  != df_test["taux_hippo"].shift())
    ).cumsum()
    return df_test

# ─────────────────────────────────────────────
# SIMULATION DES PARIS
# ─────────────────────────────────────────────

def simuler_paris(df_test):
    mise = 1.0

    stats = {
        "gagnant": {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
        "valeur" : {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
        "top2"   : {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
    }

    nb_courses = 0

    for _, groupe in df_test.groupby("course_id"):
        if len(groupe) < 3:
            continue

        nb_courses += 1
        g = groupe.sort_values("proba", ascending=False).reset_index(drop=True)

        top1       = g.iloc[0]
        cote_top1  = min(float(top1["cote"]), 30.0)
        gagne_top1 = int(top1["top1"]) if "top1" in g.columns else int(top1["succes"])
        proba_top1 = float(top1["proba"])

        # ── Stratégie GAGNANT simple ──
        stats["gagnant"]["paris"]       += 1
        stats["gagnant"]["mise_totale"] += mise
        if gagne_top1:
            stats["gagnant"]["gagnes"]       += 1
            stats["gagnant"]["gains_totaux"] += mise * cote_top1

        # ── Stratégie VALEUR ──
        # Confiance > 30% ET cote entre 2.5 et 15.0
        if proba_top1 > 0.30 and 2.5 < cote_top1 < 15.0:
            stats["valeur"]["paris"]       += 1
            stats["valeur"]["mise_totale"] += mise
            if gagne_top1:
                stats["valeur"]["gagnes"]       += 1
                stats["valeur"]["gains_totaux"] += mise * cote_top1

        # ── Stratégie TOP2 ──
        if len(g) > 1:
            top2_succes = int(g.iloc[0]["succes"]) + int(g.iloc[1]["succes"])
            cote2       = min(float(g.iloc[1]["cote"]), 30.0)
            cote_moy    = (cote_top1 + cote2) / 2
        else:
            top2_succes = int(g.iloc[0]["succes"])
            cote_moy    = cote_top1

        stats["top2"]["paris"]       += 1
        stats["top2"]["mise_totale"] += mise
        if top2_succes >= 1:
            stats["top2"]["gagnes"]       += 1
            stats["top2"]["gains_totaux"] += mise * max(1.5, cote_moy * 0.4)

    return stats, nb_courses

# ─────────────────────────────────────────────
# AFFICHAGE
# ─────────────────────────────────────────────

def afficher_resultats(stats, nb_courses):
    print("\n" + "="*58)
    print("💰 RÉSULTATS DU BACKTESTING — VICTOR V2")
    print("="*58)
    print(f"  Courses analysées : {nb_courses}")
    print(f"  (cotes filtrées : 1.1 → 30.0 max)")
    print()

    for nom, s in stats.items():
        if s["paris"] == 0:
            continue

        roi    = ((s["gains_totaux"] - s["mise_totale"]) / s["mise_totale"]) * 100
        taux   = (s["gagnes"] / s["paris"]) * 100
        profit = s["gains_totaux"] - s["mise_totale"]

        emoji = "✅" if roi > 0 else "❌"
        print(f"  {'─'*50}")
        print(f"  🎯 Stratégie : {nom.upper()}")
        print(f"     Paris joués    : {s['paris']}")
        print(f"     Paris gagnés   : {s['gagnes']} ({taux:.1f}%)")
        print(f"     Mise totale    : {s['mise_totale']:.0f} unités")
        print(f"     Gains totaux   : {s['gains_totaux']:.1f} unités")
        print(f"     Profit net     : {profit:+.1f} unités")
        print(f"     ROI            : {emoji} {roi:+.1f}%")

    print(f"\n  {'─'*50}")
    print("  📌 Note : ROI calculé sur données jamais vues")
    print("  pendant l'entraînement. Cotes plafonnées à 30.")
    print("="*58)

    roi_gagnant = ((stats["gagnant"]["gains_totaux"] - stats["gagnant"]["mise_totale"])
                   / max(stats["gagnant"]["mise_totale"], 1)) * 100

    print("\n🧠 INTERPRÉTATION :")
    if roi_gagnant > 10:
        print("  🟢 Excellent — système rentable.")
        print("     Tu peux tester avec de petites mises réelles.")
    elif roi_gagnant > 0:
        print("  🟡 Positif mais fragile — rentable sur le passé.")
        print("     Continue à alimenter avec des données fraîches.")
    elif roi_gagnant > -15:
        print("  🟠 Légèrement négatif — normal à ce stade.")
        print("     Lance Optuna pour optimiser le modèle.")
    else:
        print("  🔴 Négatif — ne mise pas d'argent réel.")
        print("     Relance 9_optimiser_optuna.py et collecte plus de données.")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("🏇 VICTOR V2 — BACKTESTING ROI (v3 corrigé)")
    print("="*58)

    model, features, df_test = charger_tout()
    df_test = calculer_probas(model, features, df_test)
    df_test = identifier_courses(df_test)
    stats, nb_courses = simuler_paris(df_test)
    afficher_resultats(stats, nb_courses)

if __name__ == "__main__":
    main()