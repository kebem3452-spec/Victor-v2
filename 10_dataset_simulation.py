"""
VICTOR V2 — Étape 10 : Génération du Dataset de Simulation
============================================================
Ce script rejoue Victor sur les 300 jours passés et enregistre
pour chaque course :
- Ce que Victor a prédit (confiance, ordre des chevaux)
- Ce qui s'est vraiment passé (résultat réel)
- Le contexte complet (météo, hippodrome, discipline, cotes)

C'est la "mémoire" qui va servir à entraîner le Superviseur.

Usage :
    python 10_dataset_simulation.py

Sortie :
    data/simulation.csv
"""

import pandas as pd
import numpy as np
import joblib
import json
import os
from datetime import date

DOSSIER_DATA   = "data"
DOSSIER_MODELS = "models"
FICHIER_SORTIE = os.path.join(DOSSIER_DATA, "simulation.csv")

DISCIPLINE_MAP_INV = {
    0: "CROSS", 1: "OBSTACLE", 2: "PLAT",
    3: "TROT_ATTELE", 4: "TROT_MONTE"
}

# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

def charger_tout():
    # Modèle global
    chemin_model = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")
    chemin_meta  = os.path.join(DOSSIER_MODELS, "features.json")

    model = joblib.load(chemin_model)
    with open(chemin_meta) as f:
        meta = json.load(f)
    features = [f for f in meta["features"]
                if f not in ("temperature","precipitation","vent_kmh","terrain_lourd")]

    # Dataset final avec toutes les features
    df = pd.read_csv(os.path.join(DOSSIER_DATA, "dataset_final.csv"),
                     encoding="utf-8-sig")

    # Dataset brut pour récupérer les noms et résultats réels
    df_raw = pd.read_csv(os.path.join(DOSSIER_DATA, "raw_courses.csv"),
                         encoding="utf-8-sig")

    features_dispo = [f for f in features if f in df.columns]
    df = df.dropna(subset=features_dispo + ["succes", "place", "cote"])
    df["cote"] = pd.to_numeric(df["cote"], errors="coerce").fillna(20.0)
    df = df[(df["cote"] >= 1.1) & (df["cote"] <= 80.0)].copy()

    print(f"📥 Dataset : {len(df)} lignes | Features : {len(features_dispo)}")
    return model, features_dispo, df, df_raw


# ─────────────────────────────────────────────
# IDENTIFICATION DES COURSES
# ─────────────────────────────────────────────

def identifier_courses(df):
    df = df.sort_index().reset_index(drop=True)
    df["course_id"] = (
        (df["nb_partants"] != df["nb_partants"].shift()) |
        (df["distance"]    != df["distance"].shift())    |
        (df["taux_hippo"]  != df["taux_hippo"].shift())
    ).cumsum()
    return df


# ─────────────────────────────────────────────
# GÉNÉRATION DES LIGNES DE SIMULATION
# ─────────────────────────────────────────────

def generer_simulation(model, features, df):
    """
    Pour chaque course, rejoue Victor et enregistre :
    - Sa confiance sur chaque cheval
    - L'erreur commise (écart entre rang prédit et rang réel)
    - Le contexte complet
    """
    print("⚙️  Génération du dataset de simulation...")

    df["proba"] = model.predict_proba(df[features])[:, 1]

    lignes = []

    for course_id, groupe in df.groupby("course_id"):
        if len(groupe) < 4:
            continue

        g = groupe.copy()

        # Rang prédit par Victor (1 = cheval qu'il aime le plus)
        g["rang_victor"] = g["proba"].rank(ascending=False, method="min").astype(int)

        # Rang réel à l'arrivée (place réelle)
        g["rang_reel"]   = pd.to_numeric(g["place"], errors="coerce").fillna(99)

        # Le cheval N°1 selon Victor
        top1_victor = g.loc[g["rang_victor"] == 1].iloc[0]

        # Est-ce que le top1 Victor était dans le vrai top5 ?
        top1_dans_top5 = int(top1_victor["rang_reel"] <= 5)

        # Est-ce que le vrai top1 était dans le top3 Victor ?
        vrai_gagnant_rang_victor = g.loc[
            g["rang_reel"] == 1, "rang_victor"].values
        gagnant_rang_chez_victor = int(vrai_gagnant_rang_victor[0]) if len(
            vrai_gagnant_rang_victor) > 0 else 99

        # Top5 prédit par Victor (numéros ou indices)
        top5_victor = set(g.nsmallest(5, "rang_victor").index)
        top5_reel   = set(g[g["rang_reel"] <= 5].index)
        intersection= len(top5_victor & top5_reel)

        # Score de précision Quinté (0 à 5)
        precision_quinte = intersection

        # Contexte de la course
        discipline_code = int(top1_victor.get("discipline_code", 2))
        discipline      = DISCIPLINE_MAP_INV.get(discipline_code, "PLAT")

        meteo_lourd   = int(top1_victor.get("terrain_lourd", 0))
        temperature   = float(top1_victor.get("temperature", 15.0))
        precipitation = float(top1_victor.get("precipitation", 0.0))
        vent_kmh      = float(top1_victor.get("vent_kmh", 10.0))

        nb_partants   = int(top1_victor.get("nb_partants", len(g)))
        distance      = int(top1_victor.get("distance", 1800))
        allocation    = int(top1_victor.get("allocation", 0))
        taux_hippo    = float(top1_victor.get("taux_hippo", 0.2))

        # Confiance de Victor sur son top1
        confiance_top1 = float(top1_victor["proba"] * 100)

        # Dispersion des confiances (course ouverte ou dominée)
        probas_top5    = g.nsmallest(5, "rang_victor")["proba"].tolist()
        ecart_top2     = float(probas_top5[0] - probas_top5[1]) * 100 if len(probas_top5) >= 2 else 0
        std_probas     = float(np.std([p * 100 for p in probas_top5]))

        # Cote du top1 Victor
        cote_top1 = float(top1_victor.get("cote", 20.0))

        # Erreur principale : rang réel du cheval que Victor aimait le plus
        erreur_top1 = int(top1_victor["rang_reel"])

        lignes.append({
            # Identifiants
            "course_id"              : course_id,
            "discipline"             : discipline,
            "distance"               : distance,
            "nb_partants"            : nb_partants,
            "allocation"             : allocation,
            "taux_hippo"             : round(taux_hippo, 4),

            # Prédiction Victor
            "confiance_top1"         : round(confiance_top1, 2),
            "cote_top1"              : cote_top1,
            "ecart_top2"             : round(ecart_top2, 2),
            "std_probas"             : round(std_probas, 2),

            # Météo
            "temperature"            : temperature,
            "precipitation"          : precipitation,
            "vent_kmh"               : vent_kmh,
            "terrain_lourd"          : meteo_lourd,

            # Résultats réels
            "erreur_top1"            : erreur_top1,
            "top1_dans_top5"         : top1_dans_top5,
            "gagnant_rang_chez_victor": gagnant_rang_chez_victor,
            "precision_quinte"       : precision_quinte,

            # Cible du Superviseur (1 = Victor a bien fait, 0 = il s'est trompé)
            "victor_correct"         : top1_dans_top5,
        })

    df_sim = pd.DataFrame(lignes)
    print(f"  ✅ {len(df_sim)} courses simulées")
    return df_sim


# ─────────────────────────────────────────────
# STATISTIQUES D'ANALYSE
# ─────────────────────────────────────────────

def analyser_patterns(df_sim):
    print("\n" + "="*58)
    print("📊 ANALYSE DES PATTERNS D'ERREURS DE VICTOR")
    print("="*58)

    total     = len(df_sim)
    correctes = df_sim["victor_correct"].sum()
    print(f"\n  Courses analysées : {total}")
    print(f"  Victor correct    : {correctes} ({correctes/total*100:.1f}%)")
    print(f"  Victor incorrect  : {total-correctes} ({(total-correctes)/total*100:.1f}%)")

    print(f"\n  Précision Quinté moyenne : "
          f"{df_sim['precision_quinte'].mean():.2f}/5 chevaux corrects")

    print("\n── Par discipline ──")
    disc_stats = df_sim.groupby("discipline")["victor_correct"].agg(["mean","count"])
    for disc, row in disc_stats.iterrows():
        emoji = "✅" if row["mean"] > 0.35 else "⚠️"
        print(f"  {emoji} {disc:<15} : {row['mean']*100:.1f}% correct "
              f"({int(row['count'])} courses)")

    print("\n── Par terrain ──")
    terrain_stats = df_sim.groupby("terrain_lourd")["victor_correct"].agg(["mean","count"])
    for terrain, row in terrain_stats.iterrows():
        label = "Lourd" if terrain else "Sec"
        emoji = "✅" if row["mean"] > 0.35 else "⚠️"
        print(f"  {emoji} Terrain {label:<6} : {row['mean']*100:.1f}% correct "
              f"({int(row['count'])} courses)")

    print("\n── Confiance Victor vs Réalité ──")
    df_sim["tranche_conf"] = pd.cut(
        df_sim["confiance_top1"],
        bins=[0, 30, 45, 55, 65, 100],
        labels=["<30%","30-45%","45-55%","55-65%",">65%"]
    )
    conf_stats = df_sim.groupby("tranche_conf", observed=True)["victor_correct"].agg(
        ["mean","count"])
    for tranche, row in conf_stats.iterrows():
        emoji = "✅" if row["mean"] > 0.40 else "⚠️"
        print(f"  {emoji} Confiance {str(tranche):<8} : {row['mean']*100:.1f}% correct "
              f"({int(row['count'])} courses)")

    print("\n── Par distance ──")
    df_sim["tranche_dist"] = pd.cut(
        df_sim["distance"],
        bins=[0,1400,1800,2200,9999],
        labels=["Sprint","Moyen","Long","Fond"]
    )
    dist_stats = df_sim.groupby("tranche_dist", observed=True)["victor_correct"].agg(
        ["mean","count"])
    for dist, row in dist_stats.iterrows():
        emoji = "✅" if row["mean"] > 0.35 else "⚠️"
        print(f"  {emoji} Distance {str(dist):<8} : {row['mean']*100:.1f}% correct "
              f"({int(row['count'])} courses)")

    print("="*58)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("🔬 VICTOR V2 — GÉNÉRATION DATASET DE SIMULATION")
    print("="*58)

    model, features, df, df_raw = charger_tout()
    df     = identifier_courses(df)
    df_sim = generer_simulation(model, features, df)

    # Analyse des patterns
    analyser_patterns(df_sim)

    # Sauvegarde
    df_sim.to_csv(FICHIER_SORTIE, index=False, encoding="utf-8-sig")
    print(f"\n💾 Sauvegardé : {FICHIER_SORTIE}")
    print(f"   {len(df_sim)} courses · {len(df_sim.columns)} colonnes")
    print("\n✅ Lance maintenant :")
    print("   python 11_superviseur.py")

if __name__ == "__main__":
    main()