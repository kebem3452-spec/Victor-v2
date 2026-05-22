"""
VICTOR V2 — Correction des cotes dans raw_courses.csv
======================================================
Ce script corrige la fonction d'extraction des cotes.
La cote réelle est dans dernierRapportDirect['rapport']
et non dans coteDirect ou cote (qui sont toujours None).

Usage : python fix_cote.py
"""

import requests
import pandas as pd
import time
import os
from datetime import date, timedelta
import datetime

BASE_URL = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS  = {
    "User-Agent"     : "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept"         : "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer"        : "https://www.pmu.fr/",
    "Origin"         : "https://www.pmu.fr",
}
PARAMS   = {"specialisation": "OFFLINE"}
PAUSE    = 1.5
DOSSIER  = "data"
FICHIER  = os.path.join(DOSSIER, "raw_courses.csv")


def formater_date(d):
    return d.strftime("%d%m%Y")


def extraire_cote(p: dict) -> float:
    """
    ✅ CORRECTION : lit la cote depuis dernierRapportDirect['rapport']
    Fallback sur dernierRapportReference['rapport'] si Direct absent.
    Fallback final à 20.0 si rien n'est disponible.
    """
    # Source 1 : rapport direct (cote en temps réel)
    rdf = p.get("dernierRapportDirect")
    if isinstance(rdf, dict):
        rapport = rdf.get("rapport")
        if rapport and float(rapport) > 1.0:
            return round(float(rapport), 1)

    # Source 2 : rapport de référence (cote de base)
    rref = p.get("dernierRapportReference")
    if isinstance(rref, dict):
        rapport = rref.get("rapport")
        if rapport and float(rapport) > 1.0:
            return round(float(rapport), 1)

    # Source 3 : anciens champs (au cas où)
    for champ in ["coteDirect", "cote"]:
        val = p.get(champ)
        if val and float(val) > 1.0:
            return round(float(val), 1)

    return 20.0  # valeur neutre si vraiment rien


def get_participants(d, num_r, num_c):
    url = f"{BASE_URL}/{formater_date(d)}/R{num_r}/C{num_c}/participants"
    try:
        r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code == 200:
            return r.json().get("participants", [])
    except Exception:
        pass
    return []


def get_programme(d):
    url = f"{BASE_URL}/{formater_date(d)}"
    try:
        r = requests.get(url, headers=HEADERS, params=PARAMS, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def main():
    print("🔧 CORRECTION DES COTES — Victor V2")
    print("="*52)
    print("Ce script re-collecte les vraies cotes depuis")
    print("dernierRapportDirect['rapport'] pour les 300 jours.")
    print("="*52)

    if not os.path.exists(FICHIER):
        print(f"❌ {FICHIER} introuvable.")
        return

    df = pd.read_csv(FICHIER, encoding="utf-8-sig")
    print(f"📂 Chargé : {len(df)} lignes, {df['date'].nunique()} jours")
    print(f"   Cote actuelle min/max : {df['cote'].min()} / {df['cote'].max()}")

    today = date.today()
    dates_a_corriger = sorted(df["date"].unique())
    total = len(dates_a_corriger)
    print(f"\n📅 Dates à recorriger : {total}")
    print("   (appui sur Ctrl+C pour arrêter proprement)\n")

    corrections = {}  # {(date, hippodrome, num_course, num_cheval): nouvelle_cote}
    traites = 0

    try:
        for date_str in dates_a_corriger:
            try:
                d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue

            prog = get_programme(d)
            if not prog:
                continue

            reunions = prog.get("programme", {}).get("reunions", [])
            for reunion in reunions:
                num_r      = reunion.get("numOfficiel") or reunion.get("numOrdre")
                hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")

                for course in reunion.get("courses", []):
                    num_c        = course.get("numOrdre")
                    participants = get_participants(d, num_r, num_c)
                    time.sleep(0.3)

                    for p in participants:
                        num_cheval = p.get("numPmu") or p.get("numero")
                        cote       = extraire_cote(p)
                        cle        = (date_str, hippodrome, num_c, num_cheval)
                        corrections[cle] = cote

            traites += 1
            if traites % 10 == 0:
                print(f"  ✅ {traites}/{total} jours traités — {len(corrections)} cotes récupérées")
            time.sleep(PAUSE)

    except KeyboardInterrupt:
        print("\n⚠️  Arrêt manuel. Application des corrections collectées jusqu'ici.")

    print(f"\n📊 {len(corrections)} cotes récupérées sur {total} jours")

    if not corrections:
        print("❌ Aucune correction à appliquer.")
        return

    # Appliquer les corrections
    def corriger_ligne(row):
        cle = (str(row["date"]), str(row["hippodrome"]),
               int(row["num_course"]) if pd.notna(row["num_course"]) else 0,
               int(row["num_cheval"])  if pd.notna(row["num_cheval"])  else 0)
        return corrections.get(cle, row["cote"])

    print("⚙️  Application des corrections...")
    df["cote"] = df.apply(corriger_ligne, axis=1)

    # Statistiques après correction
    cotes_corrigees = df[df["cote"] != 99.0]["cote"]
    print(f"   Cotes corrigées : {len(cotes_corrigees)} lignes")
    print(f"   Cote min : {df['cote'].min():.1f}")
    print(f"   Cote max : {df['cote'].max():.1f}")
    print(f"   Cote moyenne : {df['cote'].mean():.1f}")

    # Sauvegarde
    df.to_csv(FICHIER, index=False, encoding="utf-8-sig")
    print(f"\n💾 Sauvegardé : {FICHIER}")
    print("\n✅ Correction terminée !")
    print("   Relance maintenant :")
    print("   python 2_feature_engineering.py")
    print("   python 3_entrainer_modele.py")
    print("   python 7_backtesting.py")


if __name__ == "__main__":
    main()