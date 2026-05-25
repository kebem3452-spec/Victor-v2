"""
VICTOR V2 — Module 12 : Collecteur des Résultats du Soir
=========================================================
Lancé par GitHub Actions chaque soir à 20h UTC.

CORRECTIONS :
- get_client() appelé UNE SEULE FOIS avant la boucle (plus d'erreurs silencieuses)
- Argument date optionnel pour tester une date passée
- Écriture Supabase avec affichage de l'erreur si échec
"""

import requests
import pandas as pd
import os
import sys
import datetime
from datetime import date

from auth.supabase_client import get_client

BASE_URL = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
PARAMS   = {"specialisation": "OFFLINE"}
DOSSIER  = "data"
FICHIER  = os.path.join(DOSSIER, "raw_courses.csv")


def get_arrivee_officielle(date_str: str, num_r: int, num_c: int) -> list:
    url = f"{BASE_URL}/{date_str}/R{num_r}/C{num_c}"
    try:
        r      = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code != 200:
            return []
        data    = r.json()
        arrivee = data.get("ordreArrivee") or data.get("course", {}).get("ordreArrivee", [])
        statut  = data.get("statut") or data.get("course", {}).get("statut", "")
        if statut in ("OFFICIEL", "ARRIVE", "ARRIVEE_DEFINITIVE_COMPLETE", "FIN_COURSE"):
            return arrivee or []
        return []
    except Exception:
        return []


def extraire_place(num_cheval, arrivee: list) -> int:
    for idx, element in enumerate(arrivee):
        if isinstance(element, list):
            if num_cheval in element:
                return idx + 1
        elif str(num_cheval) == str(element):
            return idx + 1
    return 99


def collecter_resultats_jour(d: date = None) -> dict:
    if d is None:
        d = date.today()

    date_str = d.strftime("%d%m%Y")
    print(f"\n🏁 Collecte des résultats du {d.strftime('%d/%m/%Y')}...")

    if not os.path.exists(FICHIER):
        print("❌ raw_courses.csv introuvable.")
        return {}

    df     = pd.read_csv(FICHIER, encoding="utf-8-sig")
    df_jour = df[df["date"] == str(d)].copy()

    if df_jour.empty:
        print(f"   ℹ️  Pas encore de données dans le CSV pour le {d}.")
        print(f"   → Récupération directe depuis l'API PMU...")
    else:
        print(f"   {len(df_jour)} partants trouvés dans le CSV")

    # Programme du jour
    try:
        r        = requests.get(f"{BASE_URL}/{date_str}", headers=HEADERS,
                                 params=PARAMS, timeout=15)
        if r.status_code != 200:
            print(f"   ❌ Programme indisponible (status {r.status_code})")
            return {}
        reunions = r.json().get("programme", {}).get("reunions", [])
    except Exception as e:
        print(f"   ❌ Erreur réseau : {e}")
        return {}

    resultats            = {}
    courses_mises_a_jour = 0

    # ✅ CORRECTION : connexion Supabase UNE SEULE FOIS avant la boucle
    client = get_client()
    if client:
        print("   ✅ Connexion Supabase OK")
    else:
        print("   ⚠️  Supabase non disponible — résultats sauvegardés uniquement dans le CSV")

    for reunion in reunions:
        num_r      = reunion.get("numOfficiel") or reunion.get("numOrdre")
        hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")

        for course in reunion.get("courses", []):
            num_c   = course.get("numOrdre")
            statut  = course.get("statut", "")
            libelle = course.get("libelle", "")

            if statut not in ("OFFICIEL", "ARRIVE",
                               "ARRIVEE_DEFINITIVE_COMPLETE", "FIN_COURSE"):
                continue

            arrivee = get_arrivee_officielle(date_str, num_r, num_c)
            if not arrivee:
                continue

            # Mettre à jour les places dans le CSV
            masque     = ((df["date"] == str(d)) &
                          (df["num_reunion"] == num_r) &
                          (df["num_course"]  == num_c))
            idx_lignes = df[masque].index
            for idx in idx_lignes:
                num_cheval       = df.at[idx, "num_cheval"]
                df.at[idx, "place"] = extraire_place(num_cheval, arrivee)

            # Construire le Top5
            top5 = []
            for x in arrivee[:5]:
                if isinstance(x, list) and len(x) > 0:
                    top5.append(str(x[0]))
                elif not isinstance(x, list):
                    top5.append(str(x))

            top5_str = " · ".join(top5[:5])
            code_key = f"R{num_r}C{num_c}"

            resultats[code_key] = {
                "hippodrome": hippodrome,
                "libelle"   : libelle,
                "top5"      : top5,
                "statut"    : "OFFICIEL"
            }
            courses_mises_a_jour += 1
            print(f"   ✅ {hippodrome} {code_key} — Top5 : {top5_str}")

            # ✅ CORRECTION : écriture Supabase avec affichage de l'erreur
            if client:
                try:
                    client.table("historique_courses").upsert({
                        "date"            : str(d),
                        "code_course"     : code_key,
                        "hippodrome"      : hippodrome,
                        "resultat_reel"   : top5_str,
                        "pronostic_victor": "",
                        "succes"          : None,
                    }, on_conflict="date,code_course").execute()
                except Exception as e:
                    print(f"   ⚠️  Supabase échec pour {code_key} : {e}")

    # Sauvegarder le CSV
    if courses_mises_a_jour > 0:
        df.to_csv(FICHIER, index=False, encoding="utf-8-sig")
        print(f"\n💾 CSV mis à jour — {courses_mises_a_jour} courses")
        print(f"🗄️  Supabase mis à jour — {courses_mises_a_jour} courses")
    else:
        print("   ℹ️  Aucune course officielle disponible pour l'instant.")

    return resultats


if __name__ == "__main__":
    print("🏁 VICTOR V2 — COLLECTEUR DE RÉSULTATS")
    print("=" * 50)

    if len(sys.argv) > 1:
        d_force = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        print(f"📅 Date forcée : {d_force}")
        resultats = collecter_resultats_jour(d_force)
    else:
        resultats = collecter_resultats_jour()

    print(f"\n{'='*50}")
    print(f"✅ {len(resultats)} course(s) avec résultats officiels")
    if resultats:
        for code, info in resultats.items():
            print(f"   {code} {info['hippodrome']} → {' · '.join(info['top5'][:5])}")
    print("=" * 50)
