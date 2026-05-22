"""
VICTOR V2 — Module 8 : Collecte Météo
======================================
Source : Open-Meteo (API gratuite, sans clé, historique + prévisions)
Usage  : appelé automatiquement depuis 2_feature_engineering.py
         et depuis 5_interface_web.py

Ce module ajoute 4 features météo pour chaque course :
- temperature    : température en °C au moment de la course
- precipitation  : pluie en mm (0 = sec, >5 = terrain lourd)
- vent_kmh       : vitesse du vent en km/h
- terrain_lourd  : 1 si pluie > 2mm (binaire, très utilisé en turf)

Hippodrome → coordonnées GPS (les principaux hippodromes PMU)
"""

import requests
import pandas as pd
import time
import os
from datetime import date, datetime, timedelta

# ─────────────────────────────────────────────
# COORDONNÉES DES HIPPODROMES
# ─────────────────────────────────────────────
# Format : "NOM_COURT": (latitude, longitude)
# NOM_COURT = libelleCourt retourné par l'API PMU

HIPPODROMES_GPS = {
    # 🇫🇷 Les Incontournables du Quinté+ (Plat, Trot, Obstacle)
    "VINCENNES"       : (48.848, 2.440),
    "LONGCHAMP"       : (48.857, 2.233),
    "CHANTILLY"       : (49.194, 2.467),
    "DEAUVILLE"       : (49.352, 0.074),
    "AUTEUIL"         : (48.856, 2.255),
    "ENGHIEN"         : (48.970, 2.308),
    "CAGNES"          : (43.664, 7.149),
    "CABOURG"         : (49.288, -0.116), # Très important pour les Quintés d'été
    "CLAIREFONTAINE"  : (49.340, 0.060),  # Très important l'été (Galop/Obstacle)
    "SAINT-CLOUD"     : (48.842, 2.203),
    "MAUQUENCHY"      : (49.605, 1.470),  # Fréquent pour le Trot
    "LAVAL"           : (48.061, -0.793), # Fréquent pour le Trot (Grand National)
    "COMPIEGNE"       : (49.418, 2.823),
    "FONTAINEBLEAU"   : (48.395, 2.700),
    "VICHY"           : (46.128, 3.426),
    "BORDEAUX"        : (44.869, -0.609),
    "NANTES"          : (47.218, -1.553),
    "LYON"            : (45.757, 4.832),  # Couvre Lyon-Parilly et Lyon-La Soie
    "MARSEILLE"       : (43.296, 5.381),  # Couvre Borély et Vivaux
    "TOULOUSE"        : (43.605, 1.444),
    "PAU"             : (43.300, -0.370),
    "LE CROISE"       : (50.654, 3.093),  # Croisé-Laroche
    "AMIENS"          : (49.888, 2.264),
    "CRAON"           : (47.842, -0.932),
    "PONTCHATEAU"     : (47.433, -2.087),
    "MESLAY"          : (47.954, -0.551), # Meslay-du-Maine
    
    # 🌍 Afrique (Pour tes courses locales ou tes tests)
    "DAKAR"           : (14.716, -17.467),
    "ABIDJAN"         : (5.359, -4.008),
    "BAMAKO"          : (12.650, -8.000),
    "CASABLANCA"      : (33.589, -7.604),
    "TUNIS"           : (36.819, 10.166),
    
    # 🌍 Autres Internationaux
    "BRUXELLES"       : (50.846, 4.352),
    "HAMBOURG"        : (53.550, 9.993),
    "MILAN"           : (45.464, 9.190),
}

CACHE_FILE = os.path.join("data", "meteo_cache.csv")

# ─────────────────────────────────────────────
# CACHE LOCAL
# ─────────────────────────────────────────────

def charger_cache():
    if os.path.exists(CACHE_FILE):
        return pd.read_csv(CACHE_FILE, encoding="utf-8-sig")
    return pd.DataFrame(columns=["date", "hippodrome", "temperature",
                                   "precipitation", "vent_kmh", "terrain_lourd"])

def sauvegarder_cache(df_cache):
    os.makedirs("data", exist_ok=True)
    df_cache.to_csv(CACHE_FILE, index=False, encoding="utf-8-sig")

# ─────────────────────────────────────────────
# APPEL API OPEN-METEO
# ─────────────────────────────────────────────

def get_meteo_jour(lat, lon, date_str, heure_course="14:00"):
    """
    Récupère la météo historique pour une date et un lieu donnés.
    Utilise l'API Open-Meteo Archive (gratuite, sans clé).

    Retourne dict avec temperature, precipitation, vent_kmh.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude"        : lat,
        "longitude"       : lon,
        "start_date"      : date_str,
        "end_date"        : date_str,
        "hourly"          : "temperature_2m,precipitation,windspeed_10m",
        "timezone"        : "auto",
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None

        data = r.json()
        hourly = data.get("hourly", {})

        temps  = hourly.get("temperature_2m", [])
        precip = hourly.get("precipitation", [])
        vent   = hourly.get("windspeed_10m", [])

        if not temps:
            return None

        # Heure de la course (14h par défaut si inconnue)
        try:
            heure_int = int(heure_course.split(":")[0])
        except Exception:
            heure_int = 14
        heure_int = max(0, min(heure_int, len(temps) - 1))

        return {
            "temperature"  : round(float(temps[heure_int]),   1),
            "precipitation": round(float(precip[heure_int]),  2),
            "vent_kmh"     : round(float(vent[heure_int]),    1),
        }

    except Exception:
        return None


def get_meteo_prevision(lat, lon, date_str, heure_course="14:00"):
    """
    Récupère les prévisions météo (pour aujourd'hui / demain).
    Utilise l'API Open-Meteo Forecast.
    """
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude"   : lat,
        "longitude"  : lon,
        "hourly"     : "temperature_2m,precipitation,windspeed_10m",
        "timezone"   : "auto",
        "forecast_days": 3,
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return None

        data   = r.json()
        hourly = data.get("hourly", {})
        times  = hourly.get("time", [])
        temps  = hourly.get("temperature_2m", [])
        precip = hourly.get("precipitation", [])
        vent   = hourly.get("windspeed_10m", [])

        # Trouver l'index correspondant à la date + heure
        try:
            heure_int = int(heure_course.split(":")[0])
        except Exception:
            heure_int = 14

        cible = f"{date_str}T{heure_int:02d}:00"
        if cible in times:
            idx = times.index(cible)
        else:
            # Prendre l'heure la plus proche
            idx = heure_int if heure_int < len(temps) else 14

        return {
            "temperature"  : round(float(temps[idx]),  1),
            "precipitation": round(float(precip[idx]), 2),
            "vent_kmh"     : round(float(vent[idx]),   1),
        }

    except Exception:
        return None

# ─────────────────────────────────────────────
# FONCTION PRINCIPALE : météo pour une date + hippodrome
# ─────────────────────────────────────────────

def get_meteo(hippodrome: str, date_str: str, heure: str = "14:00",
              utiliser_cache: bool = True) -> dict:
    """
    Retourne les données météo pour un hippodrome et une date.
    Cherche d'abord dans le cache local, puis appelle l'API.

    hippodrome : nom court PMU (ex: "VINCENNES", "LONGCHAMP", "DAKAR")
    date_str   : format "YYYY-MM-DD"
    heure      : format "HH:MM"
    """
    valeur_defaut = {
        "temperature"  : 15.0,
        "precipitation": 0.0,
        "vent_kmh"     : 10.0,
        "terrain_lourd": 0,
    }

    # Trouver les coordonnées GPS
    coords = None
    hippo_upper = hippodrome.upper().strip()
    for nom, gps in HIPPODROMES_GPS.items():
        if nom in hippo_upper or hippo_upper in nom:
            coords = gps
            break

    if coords is None:
        return valeur_defaut

    lat, lon = coords

    # Chercher dans le cache
    if utiliser_cache:
        cache = charger_cache()
        ligne = cache[(cache["date"] == date_str) & (cache["hippodrome"] == hippodrome)]
        if len(ligne) > 0:
            row = ligne.iloc[0]
            return {
                "temperature"  : float(row["temperature"]),
                "precipitation": float(row["precipitation"]),
                "vent_kmh"     : float(row["vent_kmh"]),
                "terrain_lourd": int(row["terrain_lourd"]),
            }

    # Appel API
    today = date.today()
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return valeur_defaut

    if date_obj < today:
        meteo = get_meteo_jour(lat, lon, date_str, heure)
    else:
        meteo = get_meteo_prevision(lat, lon, date_str, heure)

    if meteo is None:
        return valeur_defaut

    meteo["terrain_lourd"] = int(meteo["precipitation"] > 2.0)

    # Sauvegarder dans le cache
    if utiliser_cache:
        cache    = charger_cache()
        nouvelle = pd.DataFrame([{
            "date"         : date_str,
            "hippodrome"   : hippodrome,
            "temperature"  : meteo["temperature"],
            "precipitation": meteo["precipitation"],
            "vent_kmh"     : meteo["vent_kmh"],
            "terrain_lourd": meteo["terrain_lourd"],
        }])
        cache = pd.concat([cache, nouvelle], ignore_index=True).drop_duplicates(
            subset=["date", "hippodrome"], keep="last")
        sauvegarder_cache(cache)

    return meteo


# ─────────────────────────────────────────────
# ENRICHISSEMENT DU DATASET ENTIER
# ─────────────────────────────────────────────

def enrichir_dataset_meteo(df: pd.DataFrame,
                            col_date="date",
                            col_hippo="hippodrome",
                            col_heure="heure") -> pd.DataFrame:
    print("🌤️  Enrichissement météo en cours...")

    combos = df[[col_date, col_hippo, col_heure]].drop_duplicates()

    # ✅ Cache chargé UNE SEULE FOIS au début
    cache    = charger_cache()
    cache_set = set(
        zip(cache["date"].astype(str), cache["hippodrome"].astype(str))
    )

    resultats = {}
    nouveaux  = 0

    for _, row in combos.iterrows():
        date_str   = str(row[col_date])
        hippodrome = str(row[col_hippo])
        heure      = str(row[col_heure]) if col_heure in row and pd.notna(row[col_heure]) else "14:00"
        cle        = (date_str, hippodrome)

        # Vérification instantanée dans le set (pas de lecture disque)
        if cle in cache_set:
            # Lire depuis le cache déjà chargé en mémoire
            ligne = cache[
                (cache["date"].astype(str) == date_str) &
                (cache["hippodrome"].astype(str) == hippodrome)
            ]
            if len(ligne) > 0:
                row_c = ligne.iloc[0]
                resultats[cle] = {
                    "temperature"  : float(row_c["temperature"]),
                    "precipitation": float(row_c["precipitation"]),
                    "vent_kmh"     : float(row_c["vent_kmh"]),
                    "terrain_lourd": int(row_c["terrain_lourd"]),
                }
                continue

        # Pas en cache → appel API
        meteo = get_meteo(hippodrome, date_str, heure, utiliser_cache=False)
        resultats[cle] = meteo
        nouveaux += 1

        # Ajouter au cache en mémoire
        nouvelle = pd.DataFrame([{
            "date": date_str, "hippodrome": hippodrome,
            "temperature": meteo["temperature"],
            "precipitation": meteo["precipitation"],
            "vent_kmh": meteo["vent_kmh"],
            "terrain_lourd": meteo["terrain_lourd"],
        }])
        cache     = pd.concat([cache, nouvelle], ignore_index=True)
        cache_set.add(cle)
        time.sleep(0.3)

    # Sauvegarder le cache une seule fois à la fin
    if nouveaux > 0:
        sauvegarder_cache(cache.drop_duplicates(subset=["date","hippodrome"], keep="last"))

    print(f"  ✅ {len(resultats)} combinaisons ({nouveaux} nouvelles · {len(resultats)-nouveaux} depuis cache)")

    df = df.copy()
    df["temperature"]   = df.apply(lambda r: resultats.get((str(r[col_date]), str(r[col_hippo])), {}).get("temperature",   15.0), axis=1)
    df["precipitation"] = df.apply(lambda r: resultats.get((str(r[col_date]), str(r[col_hippo])), {}).get("precipitation",  0.0), axis=1)
    df["vent_kmh"]      = df.apply(lambda r: resultats.get((str(r[col_date]), str(r[col_hippo])), {}).get("vent_kmh",      10.0), axis=1)
    df["terrain_lourd"] = df.apply(lambda r: resultats.get((str(r[col_date]), str(r[col_hippo])), {}).get("terrain_lourd",   0),  axis=1)

    return df


# ─────────────────────────────────────────────
# TEST RAPIDE
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🌤️  Test météo Open-Meteo")
    print("─" * 40)

    tests = [
        ("VINCENNES", "2025-03-15", "14:30"),
        ("LONGCHAMP", "2025-04-20", "15:00"),
        ("DAKAR",     "2026-04-20", "23:00"),
    ]

    for hippo, d, h in tests:
        meteo = get_meteo(hippo, d, h)
        print(f"  {hippo:<15} {d}  {h}  →  "
              f"{meteo['temperature']:+.1f}°C  "
              f"Pluie:{meteo['precipitation']}mm  "
              f"Vent:{meteo['vent_kmh']}km/h  "
              f"Lourd:{meteo['terrain_lourd']}")

    print("\n✅ Module météo opérationnel.")