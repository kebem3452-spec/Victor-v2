"""
VICTOR V2 — Étape 1 : Collecteur de données PMU
================================================
Correction v2 : cotes lues depuis dernierRapportDirect['rapport']
"""

import requests
import pandas as pd
import time
import os
from datetime import date, timedelta
import datetime

BASE_URL  = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS   = {
    "User-Agent"     : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept"         : "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer"        : "https://www.pmu.fr/",
    "Origin"         : "https://www.pmu.fr",
}
PARAMS  = {"specialisation": "OFFLINE"}
JOURS   = 800
PAUSE   = 2.0
DOSSIER = "data"
os.makedirs(DOSSIER, exist_ok=True)


def formater_date(d):
    return d.strftime("%d%m%Y")


def extraire_cote(p: dict) -> float:
    """
    ✅ CORRECTION v2 : lit la cote depuis dernierRapportDirect['rapport']
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


def get_programme(d):
    url = f"{BASE_URL}/{formater_date(d)}"
    try:
        r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  ⚠️  Erreur programme {d}: {e}")
    return None


def get_participants(d, num_reunion, num_course):
    url = f"{BASE_URL}/{formater_date(d)}/R{num_reunion}/C{num_course}/participants"
    try:
        r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code == 200:
            return r.json().get("participants", [])
    except Exception as e:
        print(f"  ⚠️  Erreur participants R{num_reunion}C{num_course}: {e}")
    return []


def get_arrivee(d, num_reunion, num_course):
    url = f"{BASE_URL}/{formater_date(d)}/R{num_reunion}/C{num_course}"
    try:
        r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code == 200:
            data    = r.json()
            arrivee = data.get("ordreArrivee")
            if not arrivee:
                arrivee = data.get("course", {}).get("ordreArrivee", [])
            return arrivee or []
    except Exception:
        pass
    return []


def extraire_lignes(d, reunion):
    lignes = []
    num_r      = reunion.get("numOfficiel") or reunion.get("numReunion") or reunion.get("numOrdre")
    hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")

    for course in reunion.get("courses", []):
        num_c    = course.get("numOrdre")

        valeur_heure = course.get("heureDepart", "")
        if isinstance(valeur_heure, int):
            heure = datetime.datetime.fromtimestamp(valeur_heure / 1000).strftime('%H:%M')
        else:
            heure = str(valeur_heure)[:5]

        libelle     = course.get("libelle", "")
        distance    = course.get("distance", 0)
        discipline  = course.get("discipline", "")
        nb_partants = course.get("nombreDeclaresPartants", 0)
        allocation  = course.get("montantPrix", 0)

        participants = get_participants(d, num_r, num_c)
        time.sleep(0.5)
        arrivee = get_arrivee(d, num_r, num_c)
        time.sleep(0.5)

        for p in participants:
            num_cheval = p.get("numPmu") or p.get("numero")
            nom_cheval = p.get("nom", "?")

            info_jockey = p.get("driver") or p.get("jockey")
            if isinstance(info_jockey, dict):
                nom_jockey = info_jockey.get("nom", "?")
            elif isinstance(info_jockey, str):
                nom_jockey = info_jockey
            else:
                nom_jockey = "?"

            # ✅ CORRECTION : utilise extraire_cote()
            cote_finale = extraire_cote(p)

            place = 99
            for index, element in enumerate(arrivee):
                if isinstance(element, list):
                    if num_cheval in element:
                        place = index + 1
                        break
                elif isinstance(element, (int, str)):
                    if str(num_cheval) == str(element):
                        place = index + 1
                        break

            lignes.append({
                "date"                : str(d),
                "hippodrome"          : hippodrome,
                "num_reunion"         : num_r,
                "num_course"          : num_c,
                "heure"               : heure,
                "libelle_course"      : libelle,
                "discipline"          : discipline,
                "distance"            : distance,
                "nb_partants"         : nb_partants,
                "allocation"          : allocation,
                "num_cheval"          : num_cheval,
                "nom_cheval"          : nom_cheval,
                "nom_jockey"          : nom_jockey,
                "cote"                : cote_finale,
                "age"                 : p.get("age", 0),
                "sexe"                : p.get("sexe", "?"),
                "poids"               : p.get("handicapPoids", p.get("poidsConditionMonte", 0)),
                "deferre"             : p.get("deferre", ""),
                "musique"             : p.get("musique", ""),
                "nb_victoires_saison" : p.get("nombreVictoiresSaison", 0),
                "nb_courses_saison"   : p.get("nombreCoursesSaison",   0),
                "place"               : place,
            })

    return lignes


def main():
    today = date.today()

    chemin = os.path.join(DOSSIER, "raw_courses.csv")
    dates_deja_collectees = set()
    if os.path.exists(chemin):
        df_existant = pd.read_csv(chemin, usecols=["date"], encoding="utf-8-sig")
        dates_deja_collectees = set(df_existant["date"].unique())
        print(f"📂 Données existantes : {len(dates_deja_collectees)} jours déjà collectés")

    toutes = []
    jours_sautes    = 0
    jours_collectes = 0

    for i in range(1, JOURS + 1):
        d        = today - timedelta(days=i)
        date_str = str(d)

        if date_str in dates_deja_collectees:
            jours_sautes += 1
            continue

        print(f"\n📅 {d} ...", end=" ", flush=True)
        prog = get_programme(d)
        if not prog:
            print("(aucun programme)")
            time.sleep(PAUSE)
            continue

        reunions = prog.get("programme", {}).get("reunions", [])
        print(f"{len(reunions)} réunion(s)")

        for reunion in reunions:
            lignes = extraire_lignes(d, reunion)
            toutes.extend(lignes)
            print(f"  ✅ {reunion.get('hippodrome',{}).get('libelleCourt','?')} → {len(lignes)} partants")
            time.sleep(PAUSE)

        jours_collectes += 1

    print(f"\n📊 Résumé : {jours_sautes} jours ignorés, {jours_collectes} nouveaux collectés")

    if not toutes:
        print("✅ Rien de nouveau à ajouter.")
        return

    df_nouveau = pd.DataFrame(toutes)
    if os.path.exists(chemin):
        df_ancien = pd.read_csv(chemin, encoding="utf-8-sig")
        df_final  = pd.concat([df_ancien, df_nouveau], ignore_index=True)
        df_final  = df_final.drop_duplicates(
            subset=["date", "hippodrome", "num_course", "num_cheval"], keep="last")
    else:
        df_final = df_nouveau

    df_final.to_csv(chemin, index=False, encoding="utf-8-sig")
    print(f"\n💾 Enregistré : {chemin} ({len(df_final)} lignes)")


if __name__ == "__main__":
    main()