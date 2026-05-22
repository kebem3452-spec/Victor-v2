"""
VICTOR V2 — utils.py : Boîte à outils commune v3
=================================================
SOURCE UNIQUE DE VÉRITÉ — Ne jamais dupliquer ces fonctions.
"""

import numpy as np
import pandas as pd
import os

BASE_URL = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS  = {
    "User-Agent"     : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept"         : "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer"        : "https://www.pmu.fr/",
    "Origin"         : "https://www.pmu.fr",
}
PARAMS = {"specialisation": "OFFLINE"}

# 23 features v3
FEATURES = [
    "cote", "log_cote", "rang_cote", "est_favori",
    "nb_partants", "distance", "discipline_code", "allocation",
    "forme_recente", "forme_10", "meilleure_place", "regularite", "momentum",
    "taux_victoire_cheval", "taux_victoire_jockey",
    "taux_hippo_cheval", "taux_distance",
    "taux_saison", "nb_victoires_saison", "nb_courses_saison",
    "age", "poids", "taux_hippo",
]

DISCIPLINE_MAP = {
    "PLAT": 2, "TROT_ATTELE": 3, "TROT_MONTE": 4, "OBSTACLE": 1, "CROSS": 0
}

# ---------------------------------------------
# EXTRACTION DE LA COTE DEPUIS L'API PMU
# ---------------------------------------------

def extraire_cote_api(p: dict) -> float:
    """
    Lit la vraie cote depuis dernierRapportDirect['rapport'].
    Les champs coteDirect et cote sont toujours None dans l'API actuelle.
    """
    rdf = p.get("dernierRapportDirect")
    if isinstance(rdf, dict):
        rapport = rdf.get("rapport")
        if rapport and float(rapport) > 1.0:
            return round(float(rapport), 1)

    rref = p.get("dernierRapportReference")
    if isinstance(rref, dict):
        rapport = rref.get("rapport")
        if rapport and float(rapport) > 1.0:
            return round(float(rapport), 1)

    for champ in ["coteDirect", "cote"]:
        val = p.get(champ)
        if val and float(val) > 1.0:
            return round(float(val), 1)

    return 20.0


# ---------------------------------------------
# DECODAGE MUSIQUE
# ---------------------------------------------

def decoder_musique(musique: str) -> float:
    if not isinstance(musique, str) or musique == "":
        return 5.0

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
        return 5.0

    penalite = 3.0 if places.count(15) >= 2 else 0.0
    recent   = places[-5:]
    poids    = list(range(1, len(recent) + 1))
    score    = sum(p * w for p, w in zip(recent, poids)) / sum(poids)
    return round(score + penalite, 2)


def extraire_stats_musique(musique: str) -> dict:
    """Version enrichie : retourne 5 features depuis la musique."""
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

    penalite = 3.0 if places.count(15) >= 2 else 0.0

    recent5 = places[-5:]
    poids5  = list(range(1, len(recent5) + 1))
    forme_recente = round(sum(p * w for p, w in zip(recent5, poids5)) / sum(poids5) + penalite, 2)

    recent10 = places[-10:]
    poids10  = list(range(1, len(recent10) + 1))
    forme_10 = round(sum(p * w for p, w in zip(recent10, poids10)) / sum(poids10) + penalite, 2)

    meilleure_place = int(min(places))
    regularite      = round(float(np.std(places[-10:])) if len(places) >= 2 else 3.0, 2)
    momentum        = round(float(np.mean(places[-6:-3]) - np.mean(places[-3:])), 2) if len(places) >= 6 else 0.0

    return {
        "forme_recente"  : forme_recente,
        "forme_10"       : forme_10,
        "meilleure_place": meilleure_place,
        "regularite"     : regularite,
        "momentum"       : momentum,
    }

# ---------------------------------------------
# CONSTRUCTION DES FEATURES
# ---------------------------------------------

def construire_features(participants, course, hippodrome,
                         stats_cheval, stats_jockey, stats_hippo):
    lignes       = []
    nb_partants  = len(participants) or course.get("nombreDeclaresPartants", 10)
    distance     = course.get("distance", 1800)
    discipline   = course.get("discipline", "PLAT")
    allocation   = course.get("montantPrix", 0)
    taux_hippo   = stats_hippo.get(hippodrome, 0.20)
    disc_code    = DISCIPLINE_MAP.get(discipline, 2)
    tranche_dist = int(distance // 400) * 400

    # ✅ CORRECTION : lire les cotes depuis dernierRapportDirect
    cotes = []
    for p in participants:
        cotes.append(extraire_cote_api(p))

    cotes_sorted = sorted(cotes)

    for i, p in enumerate(participants):
        nom_cheval  = p.get("nom", f"Cheval_{i}")
        info_jockey = p.get("driver") or p.get("jockey")
        if isinstance(info_jockey, dict):
            nom_jockey = info_jockey.get("nom", "Inconnu")
        elif isinstance(info_jockey, str):
            nom_jockey = info_jockey
        else:
            nom_jockey = "Inconnu"

        musique   = p.get("musique", "")
        cote      = cotes[i]
        rang_cote = cotes_sorted.index(cote) + 1 if cote in cotes_sorted else nb_partants

        sc = stats_cheval.get(nom_cheval, {})
        taux_cheval = sc.get("taux", 0.18) if sc.get("courses", 0) >= 3 else 0.18

        sj = stats_jockey.get(nom_jockey, {})
        taux_jockey = sj.get("taux", 0.18) if sj.get("courses", 0) >= 5 else 0.18

        cle_hippo = f"{nom_cheval}||{hippodrome}"
        sh        = stats_cheval.get(cle_hippo, {})
        taux_hc   = sh.get("taux", 0.20) if sh.get("courses", 0) >= 2 else 0.20

        cle_dist  = f"{nom_cheval}||dist{tranche_dist}"
        sd        = stats_cheval.get(cle_dist, {})
        taux_dist = sd.get("taux", 0.20) if sd.get("courses", 0) >= 2 else 0.20

        nb_vic_s  = p.get("nombreVictoiresSaison", 0)
        nb_crs_s  = p.get("nombreCoursesSaison", 1)

        stats_mus = extraire_stats_musique(musique)

        lignes.append({
            "num"                  : p.get("numPmu", i + 1),
            "nom_cheval"           : nom_cheval,
            "nom_jockey"           : nom_jockey,
            "cote"                 : cote,
            "log_cote"             : np.log1p(cote),
            "rang_cote"            : rang_cote,
            "est_favori"           : int(rang_cote == 1),
            "nb_partants"          : nb_partants,
            "distance"             : distance,
            "discipline_code"      : disc_code,
            "allocation"           : allocation,
            "forme_recente"        : stats_mus["forme_recente"],
            "forme_10"             : stats_mus["forme_10"],
            "meilleure_place"      : stats_mus["meilleure_place"],
            "regularite"           : stats_mus["regularite"],
            "momentum"             : stats_mus["momentum"],
            "taux_victoire_cheval" : taux_cheval,
            "taux_victoire_jockey" : taux_jockey,
            "taux_hippo_cheval"    : taux_hc,
            "taux_distance"        : taux_dist,
            "taux_saison"          : nb_vic_s / (nb_crs_s + 1),
            "nb_victoires_saison"  : nb_vic_s,
            "nb_courses_saison"    : nb_crs_s,
            "age"                  : p.get("age", 5),
            "poids"                : p.get("poidsConditionMonte", 60),
            "taux_hippo"           : taux_hippo,
        })

    return pd.DataFrame(lignes)

# ---------------------------------------------
# STATS HISTORIQUES
# ---------------------------------------------

def charger_stats_historiques(chemin_csv: str):
    if not os.path.exists(chemin_csv):
        return {}, {}, {}

    df = pd.read_csv(chemin_csv, encoding="utf-8-sig")
    df["place"]  = pd.to_numeric(df["place"], errors="coerce").fillna(99)
    df["succes"] = (df["place"] <= 5).astype(int)

    sc = df.groupby("nom_cheval")["succes"].agg(["sum", "count"]).rename(
        columns={"sum": "victoires", "count": "courses"})
    sc["taux"] = (sc["victoires"] / sc["courses"]).round(4)

    sj = df.groupby("nom_jockey")["succes"].agg(["sum", "count"]).rename(
        columns={"sum": "victoires", "count": "courses"})
    sj["taux"] = (sj["victoires"] / sj["courses"]).round(4)

    stats_cheval = sc.to_dict("index")
    stats_jockey = sj.to_dict("index")

    if "hippodrome" in df.columns:
        df["cle_hippo"] = df["nom_cheval"] + "||" + df["hippodrome"]
        sh = df.groupby("cle_hippo")["succes"].agg(["sum", "count"]).rename(
            columns={"sum": "victoires", "count": "courses"})
        sh["taux"] = (sh["victoires"] / sh["courses"]).round(4)
        stats_cheval.update(sh.to_dict("index"))

    if "distance" in df.columns:
        df["tranche"]  = (df["distance"] // 400 * 400).astype(int)
        df["cle_dist"] = df["nom_cheval"] + "||dist" + df["tranche"].astype(str)
        sd = df.groupby("cle_dist")["succes"].agg(["sum", "count"]).rename(
            columns={"sum": "victoires", "count": "courses"})
        sd["taux"] = (sd["victoires"] / sd["courses"]).round(4)
        stats_cheval.update(sd.to_dict("index"))

    stats_hippo = df.groupby("hippodrome")["succes"].mean().to_dict() if "hippodrome" in df.columns else {}

    return stats_cheval, stats_jockey, stats_hippo