"""
VICTOR V2 — superviseur_utils.py
==================================
Fonctions d'intégration du Superviseur dans l'interface.
Appelé depuis 5_interface_web.py pour enrichir chaque pronostic
avec l'avis du Superviseur.
"""

import joblib
import json
import numpy as np
import os

DOSSIER_MODELS = "models"

# Cache global du Superviseur
_superviseur_model = None
_superviseur_meta  = None


def charger_superviseur():
    """Charge le Superviseur depuis le disque (une seule fois)."""
    global _superviseur_model, _superviseur_meta

    chemin_model = os.path.join(DOSSIER_MODELS, "superviseur.pkl")
    chemin_meta  = os.path.join(DOSSIER_MODELS, "superviseur_meta.json")

    if not os.path.exists(chemin_model):
        return None, None

    if _superviseur_model is None:
        _superviseur_model = joblib.load(chemin_model)
        with open(chemin_meta) as f:
            _superviseur_meta = json.load(f)

    return _superviseur_model, _superviseur_meta


def evaluer_course(
    confiance_top1: float,
    cote_top1: float,
    ecart_top2: float,
    std_probas: float,
    discipline: str,
    distance: int,
    nb_partants: int,
    taux_hippo: float,
    temperature: float = 15.0,
    precipitation: float = 0.0,
    vent_kmh: float = 10.0,
    terrain_lourd: int = 0,
) -> dict:
    """
    Demande l'avis du Superviseur sur une course.

    Retourne un dict avec :
    - score        : probabilité que Victor soit correct (0 à 1)
    - niveau       : "confiant", "prudent" ou "danger"
    - conseil      : texte à afficher à l'abonné
    - multiplicateur_kelly : ajustement de mise recommandé
    - emoji        : indicateur visuel
    """
    model, meta = charger_superviseur()

    # Si le Superviseur n'est pas encore entraîné → avis neutre
    if model is None:
        return {
            "score"                : 0.5,
            "niveau"               : "neutre",
            "conseil"              : "",
            "multiplicateur_kelly" : 1.0,
            "emoji"                : "⚪",
            "disponible"           : False,
        }

    disc_map = {
        "CROSS":0,"OBSTACLE":1,"PLAT":2,
        "TROT_ATTELE":3,"TROT_MONTE":4
    }
    disc_code = disc_map.get(discipline.upper(), 2)

    features = meta["features"]
    valeurs  = {
        "confiance_top1"  : confiance_top1,
        "cote_top1"       : cote_top1,
        "ecart_top2"      : ecart_top2,
        "std_probas"      : std_probas,
        "discipline_code" : disc_code,
        "distance"        : distance,
        "nb_partants"     : nb_partants,
        "taux_hippo"      : taux_hippo,
        "temperature"     : temperature,
        "precipitation"   : precipitation,
        "vent_kmh"        : vent_kmh,
        "terrain_lourd"   : terrain_lourd,
    }

    import pandas as pd
    X = pd.DataFrame([[valeurs.get(f, 0.0) for f in features]], columns=features)

    score = float(model.predict_proba(X)[0, 1])

    seuil_confiance = meta.get("seuil_confiance", 0.40)
    seuil_danger    = meta.get("seuil_danger", 0.30)

    if score >= seuil_confiance:
        return {
            "score"                : score,
            "niveau"               : "confiant",
            "conseil"              : f"✅ Superviseur confiant ({score*100:.0f}%) — mise normale",
            "multiplicateur_kelly" : 1.0,
            "emoji"                : "🟢",
            "disponible"           : True,
        }
    elif score >= seuil_danger:
        return {
            "score"                : score,
            "niveau"               : "prudent",
            "conseil"              : f"⚠️ Superviseur prudent ({score*100:.0f}%) — réduire la mise de moitié",
            "multiplicateur_kelly" : 0.5,
            "emoji"                : "🟡",
            "disponible"           : True,
        }
    else:
        return {
            "score"                : score,
            "niveau"               : "danger",
            "conseil"              : f"🔴 Superviseur en alerte ({score*100:.0f}%) — éviter ou mise minimale",
            "multiplicateur_kelly" : 0.25,
            "emoji"                : "🔴",
            "disponible"           : True,
        }


def avis_superviseur_depuis_analyse(snap: dict, discipline: str) -> dict:
    """
    Version simplifiée — prend directement un dict d'analyse
    (tel que produit par l'interface) et retourne l'avis du Superviseur.
    """
    df_tri   = snap["df_tri"]
    meteo    = snap.get("meteo", {})
    course   = snap["course"]

    confs    = df_tri["confiance"].tolist()
    cotes    = df_tri["cote"].tolist()

    conf_top = confs[0] if confs else 30.0
    cote_top = cotes[0] if cotes else 10.0
    ecart    = (confs[0] - confs[1]) if len(confs) >= 2 else 0.0
    std_p    = float(np.std(confs[:5])) if len(confs) >= 5 else 3.0

    return evaluer_course(
        confiance_top1 = conf_top,
        cote_top1      = cote_top,
        ecart_top2     = ecart,
        std_probas     = std_p,
        discipline     = discipline,
        distance       = course["course_raw"].get("distance", 1800),
        nb_partants    = course.get("nb_partants", len(df_tri)),
        taux_hippo     = float(df_tri["cote"].mean()),
        temperature    = meteo.get("temperature", 15.0) or 15.0,
        precipitation  = meteo.get("precipitation", 0.0) or 0.0,
        vent_kmh       = meteo.get("vent_kmh", 10.0) or 10.0,
        terrain_lourd  = meteo.get("terrain_lourd", 0) or 0,
    )