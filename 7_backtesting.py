"""
VICTOR V2 — Étape 7 : Backtesting ROI v4.1 (Corrigé)
======================================================
Simule les 4 types de paris sur les 20% de données les plus récentes.
Correction : Identification unique des courses par Date + Hippo + Numéro.
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
    chemin_meta = os.path.join(DOSSIER_MODELS, "features.json")
    with open(chemin_meta) as f:
        meta = json.load(f)

    # On utilise le modèle global quinté pour le backtesting principal
    chemin_model = os.path.join(DOSSIER_MODELS, "victor_v2_GLOBAL_quinte.pkl")
    if not os.path.exists(chemin_model):
        chemin_model = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")

    model    = joblib.load(chemin_model)
    features = meta.get("features_global", meta.get("features", []))

    chemin_csv = os.path.join(DOSSIER_DATA, "dataset_final.csv")
    df = pd.read_csv(chemin_csv, encoding="utf-8-sig")

    features_dispo = [f for f in features if f in df.columns]
    targets        = ["succes", "succes_trio", "succes_couple", "top1", "place"]
    targets_dispo  = [t for t in targets if t in df.columns]

    df = df.dropna(subset=features_dispo + ["place"])
    df["cote"] = pd.to_numeric(df["cote"], errors="coerce")
    df = df[df["cote"].notna()].copy()

    avant = len(df)
    df = df[(df["cote"] >= 1.1) & (df["cote"] <= 80.0)].copy()
    print(f"🧹 Cotes filtrées : {avant - len(df)} lignes retirées sur {avant}")

    n       = len(df)
    seuil   = int(n * 0.80)
    df_test = df.iloc[seuil:].copy()

    print(f"📊 Backtesting sur {len(df_test)} lignes (20% les plus récentes)")
    return model, features_dispo, df_test


# ─────────────────────────────────────────────
# CALCUL DES PROBABILITÉS
# ─────────────────────────────────────────────

def calculer_probas(model, features, df):
    df = df.copy()
    df["proba"] = model.predict_proba(df[features])[:, 1]
    return df


# ─────────────────────────────────────────────
# IDENTIFICATION DES COURSES (CORRIGÉ 🚀)
# ─────────────────────────────────────────────

def identifier_courses(df):
    df = df.copy()
    
    # On vérifie la présence des colonnes idéales
    colonnes_id = ["date", "hippodrome", "num_course"]
    
    if all(col in df.columns for col in colonnes_id):
        # Crée un ID unique du style "2026-05-25_VINCENNES_1"
        df["course_id"] = df["date"].astype(str) + "_" + df["hippodrome"].astype(str) + "_" + df["num_course"].astype(str)
    elif "date" in df.columns and "code_course" in df.columns:
        df["course_id"] = df["date"].astype(str) + "_" + df["code_course"].astype(str)
    else:
        # Solution de secours améliorée si les colonnes manquent
        print("⚠️ Attention : Colonnes date/hippo introuvables, utilisation du fallback.")
        df = df.sort_index().reset_index(drop=True)
        df["course_id"] = (
            (df["nb_partants"] != df["nb_partants"].shift()) |
            (df["distance"]    != df["distance"].shift())    |
            (df["taux_hippo"]  != df["taux_hippo"].shift())
        ).cumsum()
        
    return df


# ─────────────────────────────────────────────
# SIMULATION DES PARIS
# ─────────────────────────────────────────────

def simuler_paris(df_test):
    """
    Pour chaque course, simule les 4 stratégies de paris.

    Gains réalistes estimés :
    - GAGNANT  : cote réelle du cheval
    - COUPLE   : cote_1 * cote_2 * 0.65  (approximation marché PMU)
    - TRIO     : cote_1 * cote_2 * cote_3 * 0.40
    - QUINTE+  : gain fixe de 50x la mise si 5/5, 8x si 4/5
    """
    mise = 1.0

    stats = {
        "gagnant": {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
        "couple" : {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
        "trio"   : {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
        "quinte" : {"paris": 0, "gagnes": 0, "mise_totale": 0.0, "gains_totaux": 0.0},
    }

    nb_courses = 0

    for _, groupe in df_test.groupby("course_id"):
        if len(groupe) < 4:
            continue

        nb_courses += 1
        g = groupe.sort_values("proba", ascending=False).reset_index(drop=True)

        # Places réelles
        g["place_int"] = pd.to_numeric(g["place"], errors="coerce").fillna(99).astype(int)

        # Cotes des chevaux sélectionnés
        cotes = g["cote"].tolist()

        # ── GAGNANT : cheval N°1 de Victor ──
        top1_place = g.iloc[0]["place_int"]
        cote_top1  = min(float(g.iloc[0]["cote"]), 50.0)
        stats["gagnant"]["paris"]       += 1
        stats["gagnant"]["mise_totale"] += mise
        if top1_place == 1:
            stats["gagnant"]["gagnes"]       += 1
            stats["gagnant"]["gains_totaux"] += mise * cote_top1

        # ── COUPLÉ : Top2 Victor dans le vrai Top2 ──
        if len(g) >= 2:
            top2_places = set(g.iloc[:2]["place_int"].tolist())
            cote_c1     = min(float(g.iloc[0]["cote"]), 30.0)
            cote_c2     = min(float(g.iloc[1]["cote"]), 30.0)
            gain_couple = cote_c1 * cote_c2 * 0.65
            stats["couple"]["paris"]       += 1
            stats["couple"]["mise_totale"] += mise
            if top2_places <= {1, 2}:
                stats["couple"]["gagnes"]       += 1
                stats["couple"]["gains_totaux"] += mise * gain_couple

        # ── TRIO : Top3 Victor dans le vrai Top3 ──
        if len(g) >= 3:
            top3_places = set(g.iloc[:3]["place_int"].tolist())
            cote_t1     = min(float(g.iloc[0]["cote"]), 20.0)
            cote_t2     = min(float(g.iloc[1]["cote"]), 20.0)
            cote_t3     = min(float(g.iloc[2]["cote"]), 20.0)
            gain_trio   = cote_t1 * cote_t2 * cote_t3 * 0.40
            stats["trio"]["paris"]       += 1
            stats["trio"]["mise_totale"] += mise
            if top3_places <= {1, 2, 3}:
                stats["trio"]["gagnes"]       += 1
                stats["trio"]["gains_totaux"] += mise * gain_trio

        # ── QUINTÉ : Top5 Victor vs vrai Top5 ──
        if len(g) >= 5:
            top5_victor = set(g.iloc[:5]["place_int"].tolist())
            top5_reel   = {1, 2, 3, 4, 5}
            communs     = len(top5_victor & top5_reel)
            stats["quinte"]["paris"]       += 1
            stats["quinte"]["mise_totale"] += mise
            if communs >= 5:
                stats["quinte"]["gagnes"]       += 1
                stats["quinte"]["gains_totaux"] += mise * 50.0  # 5/5 ordre libre
            elif communs >= 4:
                stats["quinte"]["gagnes"]       += 1
                stats["quinte"]["gains_totaux"] += mise * 8.0   # 4/5 bonus

    return stats, nb_courses


# ─────────────────────────────────────────────
# AFFICHAGE
# ─────────────────────────────────────────────

def afficher_resultats(stats, nb_courses):
    print("\n" + "="*60)
    print("💰 RÉSULTATS DU BACKTESTING — VICTOR V2 v4.1")
    print("="*60)
    print(f"  Courses analysées : {nb_courses}")
    print()

    for nom, s in stats.items():
        if s["paris"] == 0:
            continue

        roi    = ((s["gains_totaux"] - s["mise_totale"]) / s["mise_totale"]) * 100
        taux   = (s["gagnes"] / s["paris"]) * 100
        profit = s["gains_totaux"] - s["mise_totale"]
        emoji  = "✅" if roi > 0 else "❌"

        print(f"  {'─'*55}")
        print(f"  🎯 Stratégie : {nom.upper()}")
        print(f"     Paris joués    : {s['paris']}")
        print(f"     Paris gagnés   : {s['gagnes']} ({taux:.1f}%)")
        print(f"     Mise totale    : {s['mise_totale']:.0f} unités")
        print(f"     Gains totaux   : {s['gains_totaux']:.1f} unités")
        print(f"     Profit net     : {profit:+.1f} unités")
        print(f"     ROI            : {emoji} {roi:+.1f}%")

    print(f"\n  {'─'*55}")
    print("  📌 Gains estimés sur base marché PMU réel")
    print("  📌 QUINTÉ : 50x si 5/5, 8x si 4/5")
    print("="*60)

    # Interprétation globale
    roi_gagnant = ((stats["gagnant"]["gains_totaux"] - stats["gagnant"]["mise_totale"])
                   / max(stats["gagnant"]["mise_totale"], 1)) * 100
    roi_quinte  = ((stats["quinte"]["gains_totaux"] - stats["quinte"]["mise_totale"])
                   / max(stats["quinte"]["mise_totale"], 1)) * 100

    print("\n🧠 INTERPRÉTATION :")
    print(f"  Gagnant ROI : {roi_gagnant:+.1f}%")
    print(f"  Quinté  ROI : {roi_quinte:+.1f}%")

    if roi_gagnant > 5:
        print("  🟢 Gagnant rentable — système valide pour mises réelles.")
    elif roi_gagnant > -10:
        print("  🟡 Gagnant légèrement négatif — lance Optuna pour optimiser.")
    else:
        print("  🔴 Gagnant négatif — collecte plus de données récentes.")

    if roi_quinte > 0:
        print("  🟢 Quinté rentable — bon signal pour le Quinté Afrique.")
    else:
        print("  🟡 Quinté négatif — normal, le Quinté exact est très difficile.")
        print("     Concentre-toi sur la stratégie GAGNANT ou COUPLE.")

    print("="*60)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("🏇 VICTOR V2 — BACKTESTING ROI v4.1")
    print("="*60)

    model, features, df_test = charger_tout()
    df_test = calculer_probas(model, features, df_test)
    df_test = identifier_courses(df_test)
    stats, nb_courses = simuler_paris(df_test)
    afficher_resultats(stats, nb_courses)


if __name__ == "__main__":
    main()
