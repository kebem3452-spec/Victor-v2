"""
VICTOR V2 — Module 12 : Collecteur des Résultats du Soir
=========================================================
Lancé par GitHub Actions chaque soir à 20h UTC.
Récupère les arrivées officielles des courses terminées
et les sauvegarde dans raw_courses.csv ET Supabase.

Usage :
    python 12_collecteur_resultats.py
"""

import requests
import pandas as pd
import os
import datetime
from datetime import date

from auth.supabase_client import get_client

BASE_URL = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS  = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
PARAMS   = {"specialisation": "OFFLINE"}
DOSSIER  = "data"
FICHIER  = os.path.join(DOSSIER, "raw_courses.csv")


def get_arrivee_officielle(date_str: str, num_r: int, num_c: int) -> list:
    """Récupère l'ordre d'arrivée officiel d'une course terminée."""
    url = f"{BASE_URL}/{date_str}/R{num_r}/C{num_c}"
    try:
        r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
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
    """Extrait la place réelle d'un cheval depuis l'ordre d'arrivée."""
    for idx, element in enumerate(arrivee):
        if isinstance(element, list):
            if num_cheval in element:
                return idx + 1
        elif str(num_cheval) == str(element):
            return idx + 1
    return 99


def collecter_resultats_jour(d: date = None) -> dict:
    """
    Collecte les résultats réels de la journée.
    Fonctionne même si les courses du jour ne sont pas encore dans le CSV
    — il va les chercher directement dans l'API PMU.
    """
    if d is None:
        d = date.today()

    date_str = d.strftime("%d%m%Y")
    print(f"\n🏁 Collecte des résultats du {d.strftime('%d/%m/%Y')}...")

    if not os.path.exists(FICHIER):
        print("❌ raw_courses.csv introuvable.")
        return {}

    df = pd.read_csv(FICHIER, encoding="utf-8-sig")
    df_jour = df[df["date"] == str(d)].copy()

    # ✅ CORRECTION : on continue même si le CSV ne contient pas encore ce jour
    if df_jour.empty:
        print(f"   ℹ️  Pas encore de données dans le CSV pour le {d}.")
        print(f"   → Récupération directe depuis l'API PMU...")
    else:
        print(f"   {len(df_jour)} partants trouvés dans le CSV pour aujourd'hui")

    # Récupérer le programme du jour depuis l'API
    url_prog = f"{BASE_URL}/{date_str}"
    try:
        r = requests.get(url_prog, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code != 200:
            print(f"   ❌ Programme indisponible (status {r.status_code})")
            return {}
        reunions = r.json().get("programme", {}).get("reunions", [])
    except Exception as e:
        print(f"   ❌ Erreur réseau : {e}")
        return {}

    resultats           = {}
    courses_mises_a_jour = 0

    for reunion in reunions:
        num_r      = reunion.get("numOfficiel") or reunion.get("numOrdre")
        hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")

        for course in reunion.get("courses", []):
            num_c   = course.get("numOrdre")
            statut  = course.get("statut", "")
            libelle = course.get("libelle", "")

            # Ne traiter que les courses officiellement terminées
            if statut not in ("OFFICIEL", "ARRIVE", "ARRIVEE_DEFINITIVE_COMPLETE", "FIN_COURSE"):
                continue

            arrivee = get_arrivee_officielle(date_str, num_r, num_c)
            if not arrivee:
                continue

            # Mettre à jour les places dans le DataFrame si les lignes existent
            masque = (
                (df["date"] == str(d)) &
                (df["num_reunion"] == num_r) &
                (df["num_course"] == num_c)
            )
            idx_lignes = df[masque].index

            for idx in idx_lignes:
                num_cheval     = df.at[idx, "num_cheval"]
                place          = extraire_place(num_cheval, arrivee)
                df.at[idx, "place"] = place

            top5 = []
            for x in arrivee[:5]:
                 if isinstance(x, list) and len(x) > 0:
                     top5.append(str(x[0]))
                 elif not isinstance(x, list):
                     top5.append(str(x))
            resultats[f"R{num_r}C{num_c}"] = {
                "hippodrome": hippodrome,
                "libelle"   : libelle,
                "top5"      : top5,
                "statut"    : "OFFICIEL"
            }
            courses_mises_a_jour += 1
            print(f"   ✅ {hippodrome} R{num_r}C{num_c} — Top5 : {' · '.join(top5[:5])}")

            # Sauvegarder dans Supabase si disponible
            client = get_client()
            if client:
                try:
                    client.table("historique_courses").upsert({
                        "date"            : str(d),
                        "code_course"     : f"R{num_r}C{num_c}",
                        "hippodrome"      : hippodrome,
                        "resultat_reel"   : " · ".join(top5[:5]),
                        "pronostic_victor": "",
                        "succes"          : None,
                    }, on_conflict="date,code_course").execute()
                except Exception:
                    pass

    # Sauvegarder le CSV mis à jour (seulement si on a trouvé des résultats)
    if courses_mises_a_jour > 0:
        df.to_csv(FICHIER, index=False, encoding="utf-8-sig")
        print(f"\n💾 {FICHIER} mis à jour — {courses_mises_a_jour} courses avec résultats officiels")
    else:
        print("   ℹ️  Aucune course officielle disponible pour l'instant.")
        print("   (normal si les courses n'ont pas encore commencé)")

    return resultats


if __name__ == "__main__":
    print("🏁 VICTOR V2 — COLLECTEUR DE RÉSULTATS")
    print("=" * 50)
    resultats = collecter_resultats_jour()
    print(f"\n{'='*50}")
    print(f"✅ {len(resultats)} course(s) avec résultats officiels")
    if resultats:
        for code, info in resultats.items():
            print(f"   {code} {info['hippodrome']} → {' · '.join(info['top5'][:5])}")
    print("=" * 50)