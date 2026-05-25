"""
VICTOR V2 — Module 15 : Sauvegarde des Pronostics du Jour
==========================================================
Lancé par GitHub Actions chaque matin à 09h05 UTC (10h05 Dakar).
Calcule et sauvegarde dans Supabase les pronostics définitifs de Victor
pour toutes les courses du jour.

Utilité :
- Permettre la comparaison pronostic vs résultat réel
- Tracer l'historique de performance de Victor
- Base pour analyser les mouvements de cotes plus tard

Usage :
    python 15_sauvegarder_pronostics.py
"""

import requests
import pandas as pd
import numpy as np
import joblib
import json
import os
import datetime
from datetime import date

from utils import construire_features, charger_stats_historiques, extraire_cote_api
from auth.supabase_client import get_client

BASE_URL       = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS        = {"User-Agent": "Mozilla/5.0"}
DOSSIER_MODELS = "models"
DOSSIER_DATA   = "data"
DISC_MAP_INV   = {0:"CROSS",1:"OBSTACLE",2:"PLAT",3:"TROT_ATTELE",4:"TROT_MONTE"}


def charger_modeles():
    meta_c = os.path.join(DOSSIER_MODELS, "features.json")
    if not os.path.exists(meta_c):
        print("❌ features.json introuvable")
        return None, None
    with open(meta_c) as f:
        meta = json.load(f)
    modeles = {}
    if "modeles" in meta:
        for nom, info in meta["modeles"].items():
            chemin = os.path.join(DOSSIER_MODELS, info["fichier"])
            if os.path.exists(chemin):
                modeles[nom] = {
                    "model"   : joblib.load(chemin),
                    "features": info["features"],
                }
    else:
        chemin = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")
        if os.path.exists(chemin):
            modeles["GLOBAL"] = {
                "model"   : joblib.load(chemin),
                "features": meta["features"],
            }
    return modeles, meta.get("features", [])


def choisir_modele(modeles, discipline):
    disc_map = {"PLAT":2,"TROT_ATTELE":3,"TROT_MONTE":4,"OBSTACLE":1,"CROSS":0}
    disc_code = disc_map.get(discipline, 2)
    nom = DISC_MAP_INV.get(disc_code, "PLAT")
    if nom in modeles:
        return modeles[nom]["model"], modeles[nom]["features"]
    return modeles["GLOBAL"]["model"], modeles["GLOBAL"]["features"]


def get_programme_jour(d: date) -> list:
    date_str = d.strftime("%d%m%Y")
    courses  = []
    try:
        r = requests.get(f"{BASE_URL}/{date_str}", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        for reunion in r.json().get("programme", {}).get("reunions", []):
            num_r      = reunion.get("numOfficiel") or reunion.get("numOrdre")
            hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")
            for course in reunion.get("courses", []):
                num_c = course.get("numOrdre")
                nb    = course.get("nombreDeclaresPartants", 0)
                if nb < 8:
                    continue
                vh    = course.get("heureDepart", "")
                heure = (datetime.datetime.fromtimestamp(vh/1000).strftime("%H:%M")
                         if isinstance(vh, int) else str(vh)[:5])
                url_p = f"{BASE_URL}/{date_str}/R{num_r}/C{num_c}/participants"
                try:
                    rp    = requests.get(url_p, headers=HEADERS, timeout=5)
                    parts = rp.json().get("participants", []) if rp.status_code == 200 else []
                except Exception:
                    parts = []
                if len(parts) >= 8:
                    courses.append({
                        "hippodrome"  : hippodrome,
                        "num_r"       : num_r,
                        "num_c"       : num_c,
                        "code_pmu"    : f"R{num_r}C{num_c}",
                        "heure"       : heure,
                        "libelle"     : course.get("libelle", ""),
                        "participants": parts,
                        "course_raw"  : course,
                    })
    except Exception as e:
        print(f"❌ Erreur programme : {e}")
    return courses


def calculer_prono(course, modeles, stats_cheval, stats_jockey, stats_hippo):
    disc_str = course["course_raw"].get("discipline", "PLAT")
    model, feats = choisir_modele(modeles, disc_str)

    df = construire_features(
        course["participants"], course["course_raw"],
        course["hippodrome"], stats_cheval, stats_jockey, stats_hippo
    )
    for col in feats:
        if col not in df.columns:
            df[col] = 0.0
    feats_ok = [f for f in feats if f in df.columns]
    probas   = model.predict_proba(df[feats_ok])[:, 1] * 100

    df_tri = pd.DataFrame({
        "num"      : df["num"].tolist(),
        "cote"     : df["cote"].tolist(),
        "confiance": probas.tolist(),
    }).sort_values("confiance", ascending=False).reset_index(drop=True)

    return df_tri, disc_str


def sauvegarder_pronostics_jour(d: date = None):
    if d is None:
        d = date.today()

    print(f"\n💾 SAUVEGARDE DES PRONOSTICS — {d.strftime('%d/%m/%Y')}")
    print("=" * 55)

    # Chargement modèles
    modeles, features = charger_modeles()
    if not modeles:
        print("❌ Modèles introuvables — abandon")
        return

    # Chargement stats historiques
    chemin_raw = os.path.join(DOSSIER_DATA, "raw_courses.csv")
    stats_cheval, stats_jockey, stats_hippo = charger_stats_historiques(chemin_raw)
    print(f"✅ Modèles et stats chargés")

    # Programme du jour
    courses = get_programme_jour(d)
    if not courses:
        print("❌ Aucune course disponible")
        return
    print(f"✅ {len(courses)} courses trouvées")

    # Connexion Supabase
    client = get_client()
    if not client:
        print("❌ Connexion Supabase échouée")
        return
    print("✅ Connexion Supabase OK")

    # Heure de calcul
    heure_calcul = datetime.datetime.utcnow().strftime("%H:%M UTC")

    sauvegardes   = 0
    erreurs       = 0

    for course in courses:
        try:
            df_tri, disc_str = calculer_prono(
                course, modeles, stats_cheval, stats_jockey, stats_hippo)

            if df_tri.empty:
                continue

            # Top 8 numéros, confiances et cotes
            top8         = df_tri.head(8)
            top8_nums    = ",".join([str(int(n)) for n in top8["num"].tolist()])
            top8_conf    = ",".join([f"{c:.1f}" for c in top8["confiance"].tolist()])
            top8_cotes   = ",".join([str(c) for c in top8["cote"].tolist()])

            # Score valeur du top1
            conf_top = float(df_tri.iloc[0]["confiance"])
            cote_top = float(df_tri.iloc[0]["cote"])

            client.table("pronostics_jour").upsert({
                "date"          : str(d),
                "code_course"   : course["code_pmu"],
                "hippodrome"    : course["hippodrome"],
                "heure_course"  : course["heure"],
                "discipline"    : disc_str,
                "top8_nums"     : top8_nums,
                "top8_confiances": top8_conf,
                "top8_cotes"    : top8_cotes,
                "heure_calcul"  : heure_calcul,
            }, on_conflict="date,code_course").execute()

            sauvegardes += 1
            print(f"   ✅ {course['hippodrome']} {course['code_pmu']} — "
                  f"Top1: N°{int(df_tri.iloc[0]['num'])} "
                  f"({conf_top:.0f}% | cote {cote_top})")

        except Exception as e:
            erreurs += 1
            print(f"   ❌ {course['code_pmu']} — erreur : {e}")

    print(f"\n{'='*55}")
    print(f"✅ {sauvegardes} pronostics sauvegardés dans Supabase")
    if erreurs:
        print(f"⚠️  {erreurs} erreurs")
    print(f"🕐 Calculés à {heure_calcul}")
    print("=" * 55)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        d_force = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        print(f"📅 Date forcée : {d_force}")
        sauvegarder_pronostics_jour(d_force)
    else:
        sauvegarder_pronostics_jour()
      
