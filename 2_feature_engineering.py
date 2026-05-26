"""
VICTOR V2 — Étape 2 : Feature Engineering v6
=============================================
Entrée  : data/raw_courses.csv
Sortie  : data/dataset_final.csv

Nouveautés v6 :
- 3 nouvelles features terrain : jours_repos, changement_jockey, ecart_distance_opt
- Mapping discipline FIGÉ
- 4 targets : succes, succes_trio, succes_couple, top1
- Météo via merge rapide
"""

import pandas as pd
import numpy as np
import os
from utils import decoder_musique

DOSSIER = "data"

# Mapping discipline FIGÉ — ne jamais changer
DISCIPLINE_MAP = {
    "ATTELE"      : 0,
    "CROSS"       : 1,
    "HAIE"        : 2,
    "MONTE"       : 3,
    "PLAT"        : 4,
    "STEEPLECHASE": 5,
}

# ─────────────────────────────────────────────
# 1. CHARGEMENT
# ─────────────────────────────────────────────

def charger():
    chemin = os.path.join(DOSSIER, "raw_courses.csv")
    df = pd.read_csv(chemin, encoding="utf-8-sig")
    print(f"📥 Chargé : {len(df)} lignes brutes")
    return df

# ─────────────────────────────────────────────
# 2. NETTOYAGE
# ─────────────────────────────────────────────

def nettoyer(df):
    avant = len(df)
    df = df[df["nom_cheval"].notna()]
    df = df[df["nom_cheval"].str.len() > 1]
    df = df[~df["nom_cheval"].str.contains(
        "Bonus|Genybet|PMU|ticket|>", case=False, na=False)]
    df["place"] = pd.to_numeric(df["place"], errors="coerce")
    df = df[df["place"].notna()]
    df["place"] = df["place"].astype(int)
    df = df[(df["place"] <= 30) | (df["place"] == 99)]
    df["cote"] = pd.to_numeric(df["cote"], errors="coerce")\
                   .fillna(20.0).clip(lower=1.01, upper=200.0)
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce").fillna(0)
    df = df.drop_duplicates(
        subset=["date", "num_reunion", "num_course", "nom_cheval"])
    print(f"🧹 Après nettoyage : {len(df)} lignes (supprimé {avant - len(df)})")
    return df.reset_index(drop=True)

# ─────────────────────────────────────────────
# 3. TARGETS — 4 types de paris
# ─────────────────────────────────────────────

def creer_target(df):
    df["succes"]        = (df["place"] <= 5).astype(int)  # Quinté  → Top 5
    df["succes_trio"]   = (df["place"] <= 3).astype(int)  # Trio    → Top 3
    df["succes_couple"] = (df["place"] <= 2).astype(int)  # Couplé  → Top 2
    df["top1"]          = (df["place"] == 1).astype(int)  # Gagnant → 1er
    return df

# ─────────────────────────────────────────────
# 4. FEATURES MUSIQUE
# ─────────────────────────────────────────────

def extraire_stats_musique(musique):
    defaut = {"forme_recente": 5.0, "forme_10": 5.0,
              "meilleure_place": 10, "regularite": 3.0, "momentum": 0.0}
    if not isinstance(musique, str) or musique == "":
        return defaut

    places = []
    i = 0
    while i < len(musique):
        c = musique[i]
        if c.isdigit():
            num = c
            if i + 1 < len(musique) and musique[i + 1].isdigit():
                num += musique[i + 1]
                i += 1
            place = int(num)
            places.append(place if place != 0 else 15)
        i += 1

    if not places:
        return defaut

    penalite      = 3.0 if places.count(15) >= 2 else 0.0
    recent5       = places[-5:]
    poids5        = list(range(1, len(recent5) + 1))
    forme_recente = round(
        sum(p * w for p, w in zip(recent5, poids5)) / sum(poids5) + penalite, 2)
    recent10      = places[-10:]
    poids10       = list(range(1, len(recent10) + 1))
    forme_10      = round(
        sum(p * w for p, w in zip(recent10, poids10)) / sum(poids10) + penalite, 2)
    meilleure_place = int(min(places))
    regularite    = round(
        float(np.std(places[-10:])) if len(places) >= 2 else 3.0, 2)
    momentum      = round(
        float(np.mean(places[-6:-3]) - np.mean(places[-3:])), 2
    ) if len(places) >= 6 else 0.0

    return {"forme_recente": forme_recente, "forme_10": forme_10,
            "meilleure_place": meilleure_place, "regularite": regularite,
            "momentum": momentum}


def ajouter_forme(df):
    stats    = df["musique"].apply(extraire_stats_musique)
    stats_df = pd.DataFrame(list(stats))
    df       = pd.concat([df, stats_df], axis=1)
    print("✅ Features musique ajoutées")
    return df

# ─────────────────────────────────────────────
# 5. STATS HISTORIQUES
# ─────────────────────────────────────────────

def ajouter_stats_historiques(df):
    df = df.sort_values("date").reset_index(drop=True)

    cheval_vic, cheval_crs, taux_cheval = {}, {}, []
    for _, row in df.iterrows():
        nom = row["nom_cheval"]
        vic, crs = cheval_vic.get(nom, 0), cheval_crs.get(nom, 0)
        taux_cheval.append(round(vic / crs, 4) if crs >= 3 else 0.20)
        cheval_crs[nom] = crs + 1
        if row["succes"] == 1:
            cheval_vic[nom] = vic + 1
    df["taux_victoire_cheval"] = taux_cheval

    jockey_vic, jockey_crs, taux_jockey = {}, {}, []
    for _, row in df.iterrows():
        nom = row["nom_jockey"]
        vic, crs = jockey_vic.get(nom, 0), jockey_crs.get(nom, 0)
        taux_jockey.append(round(vic / crs, 4) if crs >= 5 else 0.18)
        jockey_crs[nom] = crs + 1
        if row["succes"] == 1:
            jockey_vic[nom] = vic + 1
    df["taux_victoire_jockey"] = taux_jockey

    hc_vic, hc_crs, taux_hc = {}, {}, []
    for _, row in df.iterrows():
        cle = (row["nom_cheval"], row["hippodrome"])
        vic, crs = hc_vic.get(cle, 0), hc_crs.get(cle, 0)
        taux_hc.append(round(vic / crs, 4) if crs >= 2 else 0.20)
        hc_crs[cle] = crs + 1
        if row["succes"] == 1:
            hc_vic[cle] = vic + 1
    df["taux_hippo_cheval"] = taux_hc

    dc_vic, dc_crs, taux_dc = {}, {}, []
    for _, row in df.iterrows():
        tranche = int(row["distance"] // 400) * 400
        cle = (row["nom_cheval"], tranche)
        vic, crs = dc_vic.get(cle, 0), dc_crs.get(cle, 0)
        taux_dc.append(round(vic / crs, 4) if crs >= 2 else 0.20)
        dc_crs[cle] = crs + 1
        if row["succes"] == 1:
            dc_vic[cle] = vic + 1
    df["taux_distance"] = taux_dc

    print("✅ Stats historiques ajoutées")
    return df

# ─────────────────────────────────────────────
# 5b. NOUVELLES FEATURES TERRAIN
# ─────────────────────────────────────────────

def ajouter_features_terrain(df):
    """
    3 nouvelles features basées sur l'historique du cheval :

    jours_repos        : nb de jours depuis la dernière course
                         Fenêtre optimale = 14 à 28 jours
                         Trop peu (< 7j) = cheval fatigué
                         Trop long (> 60j) = cheval rouillé

    changement_jockey  : 1 si le jockey est différent de la dernière course
                         Signal fort — un meilleur jockey = amélioration attendue

    ecart_distance_opt : écart relatif entre la distance d'aujourd'hui
                         et la distance où le cheval gagne le plus souvent
                         Plus c'est proche de 0, mieux c'est
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["nom_cheval", "date"]).reset_index(drop=True)

    # ── Jours de repos ──
    df["date_precedente"]  = df.groupby("nom_cheval")["date"].shift(1)
    df["jours_repos"]      = (df["date"] - df["date_precedente"]).dt.days.fillna(30)
    df["jours_repos"]      = df["jours_repos"].clip(1, 120)

    # ── Changement de jockey ──
    df["jockey_precedent"] = df.groupby("nom_cheval")["nom_jockey"].shift(1)
    df["changement_jockey"] = (
        (df["nom_jockey"] != df["jockey_precedent"]) &
        df["jockey_precedent"].notna()
    ).astype(int)

    # ── Distance vs distance optimale ──
    # Distance optimale = médiane des distances où le cheval a fini Top5
    dist_opt = (
        df[df["succes"] == 1]
        .groupby("nom_cheval")["distance"]
        .median()
        .rename("distance_optimale")
    )
    df = df.merge(dist_opt, on="nom_cheval", how="left")
    df["distance_optimale"]  = df["distance_optimale"].fillna(df["distance"])
    df["ecart_distance_opt"] = (
        (df["distance"] - df["distance_optimale"]).abs()
        / df["distance_optimale"].clip(lower=1)
    ).round(4)

    # Nettoyage colonnes temporaires
    df = df.drop(columns=["date_precedente", "jockey_precedent",
                           "distance_optimale"], errors="ignore")

    print("✅ Features terrain ajoutées (jours_repos, changement_jockey, ecart_distance_opt)")
    return df

# ─────────────────────────────────────────────
# 6. FEATURES CONTEXTUELLES
# ─────────────────────────────────────────────

def ajouter_features_course(df):
    df["rang_cote"]   = df.groupby(
        ["date", "num_reunion", "num_course"])["cote"].rank(method="min")
    df["est_favori"]  = (df["rang_cote"] == 1).astype(int)
    df["log_cote"]    = np.log1p(df["cote"])
    df["nb_partants"] = df.groupby(
        ["date", "num_reunion", "num_course"])["nom_cheval"].transform("count")
    df["taux_saison"] = (
        df["nb_victoires_saison"] / (df["nb_courses_saison"] + 1)).round(4)
    df["discipline_code"] = df["discipline"].map(DISCIPLINE_MAP).fillna(0).astype(int)
    print("✅ Features contextuelles ajoutées")
    return df

# ─────────────────────────────────────────────
# 7. TARGET ENCODING HIPPODROME
# ─────────────────────────────────────────────

def encoder_categoriques(df):
    hip_stats        = df.groupby("hippodrome")["succes"].mean().rename("taux_hippo")
    df               = df.merge(hip_stats, on="hippodrome", how="left")
    df["taux_hippo"] = df["taux_hippo"].fillna(df["succes"].mean())
    print("✅ Encodage hippodrome fait")
    return df

# ─────────────────────────────────────────────
# 8. MÉTÉO — VERSION RAPIDE AVEC MERGE
# ─────────────────────────────────────────────

def ajouter_meteo(df):
    if "date" not in df.columns or "hippodrome" not in df.columns:
        return df

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("meteo_mod", "8_meteo.py")
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        if "heure" not in df.columns:
            df["heure"] = "14:00"

        cache = mod.charger_cache()
        print(f"🌤️  Cache météo : {len(cache)} entrées existantes")

        combos_dataset = df[["date", "hippodrome", "heure"]].drop_duplicates()
        combos_dataset["date_str"]  = combos_dataset["date"].astype(str)
        combos_dataset["hippo_str"] = combos_dataset["hippodrome"].astype(str)

        if len(cache) > 0:
            cache["date_str"]  = cache["date"].astype(str)
            cache["hippo_str"] = cache["hippodrome"].astype(str)
            cache_set = set(zip(cache["date_str"], cache["hippo_str"]))
        else:
            cache_set = set()

        manquantes = combos_dataset[
            ~combos_dataset.apply(
                lambda r: (r["date_str"], r["hippo_str"]) in cache_set,
                axis=1
            )
        ]

        print(f"   Combinaisons dans le dataset : {len(combos_dataset)}")
        print(f"   Déjà en cache               : {len(combos_dataset) - len(manquantes)}")
        print(f"   À télécharger               : {len(manquantes)}")

        if len(manquantes) > 0:
            import time
            nouvelles_lignes = []
            for _, row in manquantes.iterrows():
                meteo = mod.get_meteo(
                    row["hippodrome"],
                    row["date_str"],
                    row["heure"],
                    utiliser_cache=False
                )
                nouvelles_lignes.append({
                    "date"         : row["date_str"],
                    "hippodrome"   : row["hippo_str"],
                    "temperature"  : meteo["temperature"],
                    "precipitation": meteo["precipitation"],
                    "vent_kmh"     : meteo["vent_kmh"],
                    "terrain_lourd": meteo["terrain_lourd"],
                })
                time.sleep(0.3)

            df_nouvelles = pd.DataFrame(nouvelles_lignes)
            cache_maj    = pd.concat([cache, df_nouvelles], ignore_index=True)\
                             .drop_duplicates(subset=["date", "hippodrome"], keep="last")
            mod.sauvegarder_cache(cache_maj)
            print(f"   ✅ {len(nouvelles_lignes)} nouvelles météos sauvegardées")
            cache = cache_maj

        cache_clean = cache[["date", "hippodrome",
                              "temperature", "precipitation",
                              "vent_kmh", "terrain_lourd"]].copy()
        cache_clean["date"]       = cache_clean["date"].astype(str)
        cache_clean["hippodrome"] = cache_clean["hippodrome"].astype(str)
        cache_clean = cache_clean.drop_duplicates(
            subset=["date", "hippodrome"], keep="last")

        df["date_merge"]  = df["date"].astype(str)
        df["hippo_merge"] = df["hippodrome"].astype(str)

        df = df.merge(
            cache_clean.rename(columns={
                "date"      : "date_merge",
                "hippodrome": "hippo_merge"
            }),
            on=["date_merge", "hippo_merge"],
            how="left"
        )

        df["temperature"]   = df["temperature"].fillna(15.0)
        df["precipitation"] = df["precipitation"].fillna(0.0)
        df["vent_kmh"]      = df["vent_kmh"].fillna(10.0)
        df["terrain_lourd"] = df["terrain_lourd"].fillna(0).astype(int)
        df = df.drop(columns=["date_merge", "hippo_merge"], errors="ignore")

        print("✅ Météo ajoutée via merge rapide")

    except Exception as e:
        print(f"⚠️  Météo ignorée ({e})")
        df["temperature"]   = 15.0
        df["precipitation"] = 0.0
        df["vent_kmh"]      = 10.0
        df["terrain_lourd"] = 0

    return df

# ─────────────────────────────────────────────
# 9. FEATURES FINALES
# ─────────────────────────────────────────────

FEATURES_FINALES = [
    # Features de base
    "cote", "log_cote", "rang_cote", "est_favori",
    "nb_partants", "distance", "discipline_code", "allocation",
    # Forme
    "forme_recente", "forme_10", "meilleure_place", "regularite", "momentum",
    # Stats historiques
    "taux_victoire_cheval", "taux_victoire_jockey",
    "taux_hippo_cheval", "taux_distance",
    "taux_saison", "nb_victoires_saison", "nb_courses_saison",
    # Cheval
    "age", "poids", "taux_hippo",
    # Météo
    "temperature", "precipitation", "vent_kmh", "terrain_lourd",
    # NOUVELLES features terrain
    "jours_repos", "changement_jockey", "ecart_distance_opt",
    # Targets et labels
    "succes", "succes_trio", "succes_couple", "top1", "place",
    "date", "num_reunion", "num_course",
]

def selectionner_features(df):
    colonnes = [c for c in FEATURES_FINALES if c in df.columns]
    df_final = df[colonnes].copy()
    feats    = [c for c in colonnes if c not in
                ("succes", "succes_trio", "succes_couple", "top1", "place")]
    print(f"✅ {len(feats)} features retenues")
    return df_final

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    df = charger()
    df = nettoyer(df)
    df = creer_target(df)
    df = ajouter_forme(df)
    df = ajouter_stats_historiques(df)
    df = ajouter_features_terrain(df)
    df = ajouter_features_course(df)
    df = encoder_categoriques(df)
    df = ajouter_meteo(df)
    df_final = selectionner_features(df)

    chemin = os.path.join(DOSSIER, "dataset_final.csv")
    df_final.to_csv(chemin, index=False, encoding="utf-8-sig")

    print(f"\n💾 Dataset final : {chemin}")
    print(f"   Lignes        : {len(df_final)}")
    print(f"   Features      : {len([c for c in df_final.columns if c not in ('succes','succes_trio','succes_couple','top1','place')])}")
    print(f"   Quinté (<=5)  : {df_final['succes'].sum()} ({df_final['succes'].mean()*100:.1f}%)")
    print(f"   Trio   (<=3)  : {df_final['succes_trio'].sum()} ({df_final['succes_trio'].mean()*100:.1f}%)")
    print(f"   Couplé (<=2)  : {df_final['succes_couple'].sum()} ({df_final['succes_couple'].mean()*100:.1f}%)")
    print(f"   Gagnant (=1)  : {df_final['top1'].sum()} ({df_final['top1'].mean()*100:.1f}%)")
    print(f"\n✅ Lance maintenant : python 3_entrainer_modele.py")

if __name__ == "__main__":
    main()
