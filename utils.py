"""
VICTOR V2 — utils.py : Boîte à outils commune v4
=================================================
SOURCE UNIQUE DE VÉRITÉ — Ne jamais dupliquer ces fonctions.

NOUVEAUTÉ v4 :
- extraire_stats_musique_discipline() : filtre la musique par discipline
  Un cheval en PLAT aujourd'hui → on ignore ses résultats en TROT et vice versa
- Correction majeure de précision des pronostics
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

# Lettres de discipline dans la musique PMU
# Chaque lettre indique le type de course dans la musique
LETTRES_DISCIPLINE = {
    "PLAT"        : set(),           # Pas de lettre = Plat par défaut
    "TROT_ATTELE" : {"a"},           # a = Attelé
    "TROT_MONTE"  : {"m", "p"},      # m = Monté, p = aussi Monté (ancienne notation)
    "OBSTACLE"    : {"h", "s", "c"}, # h = Haies, s = Steeple, c = Cross-country
    "CROSS"       : {"c", "x"},      # c = Cross, x = Cross-country
}

# ─────────────────────────────────────────────
# EXTRACTION DE LA COTE DEPUIS L'API PMU
# ─────────────────────────────────────────────

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


# ─────────────────────────────────────────────
# DÉCODAGE MUSIQUE
# ─────────────────────────────────────────────

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
    """Version sans filtre discipline — utilisée pour le feature engineering historique."""
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

    return _calculer_stats_depuis_places(places)


def extraire_stats_musique_discipline(musique: str, discipline: str) -> dict:
    """
    ✅ NOUVELLE FONCTION v4 — Filtre la musique par discipline.

    Explication simple :
    La musique d'un cheval ressemble à : "1a3p2h5"
    - "1a" = 1er place en course Attelée
    - "3p" = 3ème place en course Montée
    - "2h" = 2ème place en course Haies
    - "5"  = 5ème place en Plat (pas de lettre = Plat)

    Si le cheval court en PLAT aujourd'hui, on ne garde que
    les résultats sans lettre (Plat). Les autres sont ignorés.

    C'est comme évaluer un footballeur uniquement sur ses matchs
    de foot, pas ses matchs de rugby.
    """
    defaut = {"forme_recente": 5.0, "forme_10": 5.0,
               "meilleure_place": 10, "regularite": 3.0, "momentum": 0.0}

    if not isinstance(musique, str) or musique == "":
        return defaut

    # Lettres qui correspondent à la discipline cible
    disc_upper   = discipline.upper() if discipline else "PLAT"
    lettres_cible = LETTRES_DISCIPLINE.get(disc_upper, set())

    # Toutes les lettres de discipline connues (pour savoir si c'est une autre discipline)
    toutes_lettres = set()
    for lettres in LETTRES_DISCIPLINE.values():
        toutes_lettres.update(lettres)

    places = []
    i = 0
    while i < len(musique):
        c = musique[i]
        if c.isdigit():
            # Lire le nombre (peut être sur 2 chiffres)
            num = c
            if i + 1 < len(musique) and musique[i + 1].isdigit():
                num += musique[i + 1]
                i += 1
            place = int(num)
            place = place if place != 0 else 15

            # Regarder la lettre qui suit ce nombre
            lettre_suivante = ""
            if i + 1 < len(musique) and musique[i + 1].isalpha():
                lettre_suivante = musique[i + 1].lower()

            # Décider si on garde ce résultat
            if disc_upper == "PLAT":
                # Pour le PLAT : garder seulement les résultats sans lettre
                # ou avec des lettres qui ne sont pas d'autres disciplines
                if lettre_suivante == "" or lettre_suivante not in toutes_lettres:
                    places.append(place)
            else:
                # Pour les autres disciplines : garder seulement les résultats
                # avec la lettre correspondante à cette discipline
                if lettre_suivante in lettres_cible:
                    places.append(place)

        i += 1

    # Si pas assez de résultats dans cette discipline, retourner défaut
    # (le cheval est nouveau dans cette discipline)
    if len(places) < 2:
        return defaut

    return _calculer_stats_depuis_places(places)


def _calculer_stats_depuis_places(places: list) -> dict:
    """Calcule les 5 features statistiques depuis une liste de places."""
    penalite = 3.0 if places.count(15) >= 2 else 0.0

    recent5 = places[-5:]
    poids5  = list(range(1, len(recent5) + 1))
    forme_recente = round(
        sum(p * w for p, w in zip(recent5, poids5)) / sum(poids5) + penalite, 2)

    recent10 = places[-10:]
    poids10  = list(range(1, len(recent10) + 1))
    forme_10 = round(
        sum(p * w for p, w in zip(recent10, poids10)) / sum(poids10) + penalite, 2)

    meilleure_place = int(min(places))
    regularite      = round(float(np.std(places[-10:])) if len(places) >= 2 else 3.0, 2)
    momentum        = round(
        float(np.mean(places[-6:-3]) - np.mean(places[-3:])), 2
    ) if len(places) >= 6 else 0.0

    return {
        "forme_recente"  : forme_recente,
        "forme_10"       : forme_10,
        "meilleure_place": meilleure_place,
        "regularite"     : regularite,
        "momentum"       : momentum,
    }


# ─────────────────────────────────────────────
# CONSTRUCTION DES FEATURES
# ─────────────────────────────────────────────

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

    # Lire les cotes depuis dernierRapportDirect
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

        sc          = stats_cheval.get(nom_cheval, {})
        taux_cheval = sc.get("taux", 0.18) if sc.get("courses", 0) >= 3 else 0.18

        sj          = stats_jockey.get(nom_jockey, {})
        taux_jockey = sj.get("taux", 0.18) if sj.get("courses", 0) >= 5 else 0.18

        cle_hippo = f"{nom_cheval}||{hippodrome}"
        sh        = stats_cheval.get(cle_hippo, {})
        taux_hc   = sh.get("taux", 0.20) if sh.get("courses", 0) >= 2 else 0.20

        cle_dist  = f"{nom_cheval}||dist{tranche_dist}"
        sd        = stats_cheval.get(cle_dist, {})
        taux_dist = sd.get("taux", 0.20) if sd.get("courses", 0) >= 2 else 0.20

        nb_vic_s  = p.get("nombreVictoiresSaison", 0)
        nb_crs_s  = p.get("nombreCoursesSaison", 1)

        # ✅ CORRECTION v4 : utiliser la musique filtrée par discipline
        stats_mus = extraire_stats_musique_discipline(musique, discipline)

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


# ─────────────────────────────────────────────
# STATS HISTORIQUES
# ─────────────────────────────────────────────

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

    stats_hippo = df.groupby("hippodrome")["succes"].mean().to_dict() \
        if "hippodrome" in df.columns else {}

    return stats_cheval, stats_jockey, stats_hippo
