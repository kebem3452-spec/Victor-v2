"""
VICTOR V2 — Étape 6 : Mise à jour quotidienne
==============================================
Correction v2 : cotes lues depuis dernierRapportDirect['rapport']
"""

import requests
import pandas as pd
import time
import os
import datetime
from datetime import date, timedelta

BASE_URL    = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS     = {
    "User-Agent"     : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept"         : "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer"        : "https://www.pmu.fr/",
    "Origin"         : "https://www.pmu.fr",
}
PARAMS      = {"specialisation": "OFFLINE"}
PAUSE       = 2.0
TIMEOUT     = 25
MAX_RETRIES = 3
DOSSIER     = "data"
FICHIER_CSV = os.path.join(DOSSIER, "raw_courses.csv")


def formater_date(d):
    return d.strftime("%d%m%Y")


def extraire_cote(p: dict) -> float:
    """✅ CORRECTION v2 : vraie cote depuis dernierRapportDirect"""
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
    for tentative in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
        except requests.exceptions.Timeout:
            print(f"  ⏳ PMU lent... retente ({tentative+1}/{MAX_RETRIES})")
            time.sleep(PAUSE)
        except Exception as e:
            print(f"  ⚠️ Erreur : {e}")
            break
    return None


def get_participants(d, num_reunion, num_course):
    url = f"{BASE_URL}/{formater_date(d)}/R{num_reunion}/C{num_course}/participants"
    for tentative in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json().get("participants", [])
        except requests.exceptions.Timeout:
            time.sleep(PAUSE)
        except Exception:
            break
    return []


def get_arrivee(d, num_reunion, num_course):
    url = f"{BASE_URL}/{formater_date(d)}/R{num_reunion}/C{num_course}"
    for tentative in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=TIMEOUT)
            if r.status_code == 200:
                data    = r.json()
                arrivee = data.get("ordreArrivee")
                if not arrivee:
                    arrivee = data.get("course", {}).get("ordreArrivee", [])
                return arrivee or []
        except requests.exceptions.Timeout:
            time.sleep(PAUSE)
        except Exception:
            break
    return []


def extraire_lignes(d, reunion):
    lignes = []
    num_r      = reunion.get("numOfficiel") or reunion.get("numReunion") or reunion.get("numOrdre")
    hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")

    for course in reunion.get("courses", []):
        num_c    = course.get("numOrdre")

        valeur_heure = course.get("heureDepart", "")
        if isinstance(valeur_heure, int):
            heure = datetime.datetime.fromtimestamp(valeur_heure / 1000).strftime("%H:%M")
        else:
            heure = str(valeur_heure)[:5]

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
                "libelle_course"      : course.get("libelle", ""),
                "discipline"          : course.get("discipline", ""),
                "distance"            : course.get("distance", 0),
                "nb_partants"         : course.get("nombreDeclaresPartants", 0),
                "allocation"          : course.get("montantPrix", 0),
                "num_cheval"          : num_cheval,
                "nom_cheval"          : nom_cheval,
                "nom_jockey"          : nom_jockey,
                "cote"                : extraire_cote(p),  # ✅ corrigé
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


if __name__ == "__main__":
    print("=" * 52)
    print("🔄 VICTOR V2 : MISE À JOUR QUOTIDIENNE (v2)")
    print("=" * 52)

    d_hier = date.today() - timedelta(days=1)
    print(f"\n📅 Collecte des résultats de HIER ({d_hier})...", end=" ", flush=True)

    prog = get_programme(d_hier)
    if not prog:
        print("(aucun programme trouvé)")
        exit()

    reunions = prog.get("programme", {}).get("reunions", [])
    print(f"{len(reunions)} réunion(s)\n")

    lignes_nouvelles = []
    for reunion in reunions:
        nom_hippo = reunion.get("hippodrome", {}).get("libelleCourt", "?")
        print(f"📥 {nom_hippo}...")
        lignes = extraire_lignes(d_hier, reunion)
        lignes_nouvelles.extend(lignes)
        print(f"  ✅ {len(lignes)} partants")
        time.sleep(PAUSE)

    if not lignes_nouvelles:
        print("\n⚠️ Aucune donnée récupérée.")
    else:
        df_nouveau = pd.DataFrame(lignes_nouvelles)
        if os.path.exists(FICHIER_CSV):
            df_ancien       = pd.read_csv(FICHIER_CSV, encoding="utf-8-sig")
            lignes_avant    = len(df_ancien)
            df_final        = pd.concat([df_ancien, df_nouveau], ignore_index=True)
            df_final        = df_final.drop_duplicates(
                subset=["date", "hippodrome", "num_course", "num_cheval"], keep="last")
            df_final.to_csv(FICHIER_CSV, index=False, encoding="utf-8-sig")
            print(f"\n💾 {lignes_avant} → {len(df_final)} lignes (+{len(df_final)-lignes_avant})")
        else:
            df_nouveau.to_csv(FICHIER_CSV, index=False, encoding="utf-8-sig")
            print(f"\n💾 Nouveau fichier : {len(df_nouveau)} lignes")

    print("\n" + "=" * 52)
    print("✅ Mise à jour terminée ! Relance :")
    print("   python 2_feature_engineering.py")
    print("   python 3_entrainer_modele.py")
    print("=" * 52)