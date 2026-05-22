"""
VICTOR V2 — Interface Web v10
==============================
Corrections v10 :
- Pronostics figés au premier calcul (ne changent plus)
- Refresh uniquement pour détecter les non-partants (toutes les 2h)
- Pourcentage affiché sous les étoiles
- 5 premiers numéros bien visibles et grands
- Suivants bien visibles
- Cotes à 20.0 expliquées pour les courses futures
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
import joblib
import json
import os
import datetime
from datetime import date

from utils import construire_features, charger_stats_historiques
from kelly import calculer_mise
from auth.supabase_client import verifier_session, deconnecter

try:
    from superviseur_utils import avis_superviseur_depuis_analyse
    SUPERVISEUR_DISPO = True
except Exception:
    SUPERVISEUR_DISPO = False

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_DISPO = True
except ImportError:
    AUTOREFRESH_DISPO = False

st.set_page_config(
    page_title="Victor V2 - Pronostics PMU",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.course-header {
    background: var(--color-background-secondary);
    border-left: 4px solid #1D9E75;
    border-radius: 0 10px 10px 0;
    padding: 10px 14px;
    margin-bottom: 10px;
}
.course-date  { font-size: 11px; color: #888; margin-bottom: 2px; }
.course-lieu  { font-size: 16px; font-weight: 700; color: var(--color-text-primary); }
.course-prix  { font-size: 13px; color: #1D9E75; font-weight: 500; margin-top: 2px; }
.course-heure { font-size: 13px; color: var(--color-text-secondary); }

.ticket-box {
    background: #0d1117;
    border: 2px solid #1D9E75;
    border-radius: 14px;
    padding: 22px 12px;
    text-align: center;
    margin: 8px 0;
}
.ticket-nums {
    color: white;
    font-size: 48px;
    font-weight: 900;
    letter-spacing: 8px;
    font-family: monospace;
    margin: 10px 0;
    line-height: 1.1;
}
.ticket-suivants {
    color: #1D9E75;
    font-size: 15px;
    font-weight: 700;
    margin-top: 10px;
    letter-spacing: 2px;
}

.cheval-card {
    text-align: center;
    padding: 8px 4px;
}
.cheval-num {
    font-size: 28px;
    font-weight: 800;
    color: var(--color-text-primary);
}
.cheval-etoiles { font-size: 14px; margin: 2px 0; }
.cheval-pct {
    font-size: 15px;
    font-weight: 700;
    color: #1D9E75;
}
.cheval-cote {
    font-size: 11px;
    color: #888;
    margin-top: 2px;
}

.badge-vert   { background:#0f3d2e; color:#1D9E75; padding:3px 10px;
                border-radius:99px; font-size:12px; font-weight:600; }
.badge-orange { background:#3d2a0f; color:#EF9F27; padding:3px 10px;
                border-radius:99px; font-size:12px; font-weight:600; }
.badge-rouge  { background:#3d0f0f; color:#E24B4A; padding:3px 10px;
                border-radius:99px; font-size:12px; font-weight:600; }
.badge-neutre { background:var(--color-background-tertiary);
                color:var(--color-text-secondary); padding:3px 10px;
                border-radius:99px; font-size:12px; }

.fige-badge {
    background: #1a2a1a;
    color: #1D9E75;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    display: inline-block;
    margin-bottom: 6px;
}

@media (max-width: 640px) {
    .ticket-nums { font-size: 32px; letter-spacing: 4px; }
    section[data-testid="stSidebar"] { display: none; }
}
</style>
""", unsafe_allow_html=True)

BASE_URL       = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS        = {"User-Agent": "Mozilla/5.0"}
DOSSIER_MODELS = "models"
DOSSIER_DATA   = "data"
DISCIPLINE_MAP_INV = {0:"CROSS",1:"OBSTACLE",2:"PLAT",3:"TROT_ATTELE",4:"TROT_MONTE"}

# ─────────────────────────────────────────────
# SESSION & ROUTING
# ─────────────────────────────────────────────

if "connecte" not in st.session_state:
    st.session_state["connecte"] = False

if st.query_params.get("page") == "admin":
    from pages.admin import afficher_admin
    afficher_admin()
    st.stop()

def verifier_acces():
    if not st.session_state.get("connecte"):
        return False
    return verifier_session(
        st.session_state.get("telephone", ""),
        st.session_state.get("session_token", "")
    )

if not verifier_acces():
    from pages.login import afficher_login
    afficher_login()
    st.stop()

nom_abonne     = st.session_state.get("nom", "Abonné")
jours_restants = st.session_state.get("jours_restants", 0)
plan           = st.session_state.get("plan", "pro")

# ─────────────────────────────────────────────
# MODÈLES ET STATS
# ─────────────────────────────────────────────

@st.cache_resource
def charger_modeles(version=0):
    meta_c = os.path.join(DOSSIER_MODELS, "features.json")
    if not os.path.exists(meta_c):
        return None, None, 0.0
    with open(meta_c) as f:
        meta = json.load(f)
    modeles = {}
    if "modeles" in meta:
        for nom, info in meta["modeles"].items():
            chemin = os.path.join(DOSSIER_MODELS, info["fichier"])
            if os.path.exists(chemin):
                modeles[nom] = {"model": joblib.load(chemin),
                                "features": info["features"],
                                "auc": info["auc"]}
    else:
        chemin = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")
        if os.path.exists(chemin):
            modeles["GLOBAL"] = {"model": joblib.load(chemin),
                                  "features": meta["features"],
                                  "auc": meta.get("auc", 0.0)}
    if not modeles:
        return None, None, 0.0
    auc = modeles.get("GLOBAL", list(modeles.values())[0])["auc"]
    return modeles, meta.get("features", []), auc


def choisir_modele(modeles, discipline_code):
    nom = DISCIPLINE_MAP_INV.get(discipline_code, "PLAT")
    if nom in modeles:
        return modeles[nom]["model"], modeles[nom]["features"], nom
    return modeles["GLOBAL"]["model"], modeles["GLOBAL"]["features"], "GLOBAL"


@st.cache_data
def charger_stats(version=0):
    return charger_stats_historiques(os.path.join(DOSSIER_DATA, "raw_courses.csv"))


@st.cache_data(ttl=3600)
def get_meteo_course(hippodrome, date_str, heure):
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("m", "8_meteo.py")
        mod  = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.get_meteo(hippodrome, date_str, heure)
    except Exception:
        return {"temperature": None, "precipitation": 0,
                "vent_kmh": 0, "terrain_lourd": 0}


# ─────────────────────────────────────────────
# PROGRAMME PMU — cache 2h pour stabilité
# ─────────────────────────────────────────────

@st.cache_data(ttl=7200)  # ✅ 2 heures — pronostics stables
def get_programme(date_cible):
    """
    Cache de 2 heures.
    Les pronostics ne changent pas toutes les 5 minutes.
    Seuls les non-partants (disparition d'un cheval) peuvent
    déclencher un recalcul via le bouton manuel.
    """
    date_str = date_cible.strftime("%d%m%Y")
    courses  = []
    try:
        r = requests.get(f"{BASE_URL}/{date_str}", headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        for reunion in r.json().get("programme", {}).get("reunions", []):
            num_r      = reunion.get("numOfficiel") or reunion.get("numOrdre")
            hippodrome = reunion.get("hippodrome", {}).get("libelleCourt", "?")
            for course in reunion.get("courses", []):
                num_c       = course.get("numOrdre")
                nb_partants = course.get("nombreDeclaresPartants", 0)
                if nb_partants < 8:
                    continue
                valeur_heure = course.get("heureDepart", "")
                heure = (datetime.datetime.fromtimestamp(
                    valeur_heure / 1000).strftime("%H:%M")
                    if isinstance(valeur_heure, int) else str(valeur_heure)[:5])
                url_p = f"{BASE_URL}/{date_str}/R{num_r}/C{num_c}/participants"
                try:
                    r_p = requests.get(url_p, headers=HEADERS, timeout=5)
                    participants = (r_p.json().get("participants", [])
                                    if r_p.status_code == 200 else [])
                except Exception:
                    participants = []
                if len(participants) >= 8:
                    courses.append({
                        "hippodrome"  : hippodrome,
                        "num_r"       : num_r,
                        "num_c"       : num_c,
                        "code_pmu"    : f"R{num_r}C{num_c}",
                        "heure"       : heure,
                        "libelle"     : course.get("libelle", ""),
                        "participants": participants,
                        "course_raw"  : course,
                        "nb_partants" : len(participants),
                    })
    except Exception as e:
        st.error(f"Erreur PMU : {e}")
    return courses


# ─────────────────────────────────────────────
# PRONOSTICS FIGÉS
# ─────────────────────────────────────────────

def calculer_analyses(courses, modeles, stats_cheval, stats_jockey,
                       stats_hippo, date_cible):
    """
    Calcule les pronostics et les fige en session.
    Ne recalcule QUE si les partants ont changé (non-partant détecté).
    """
    cle_session = f"analyses_{date_cible.isoformat()}"
    nb_session  = f"nb_partants_{date_cible.isoformat()}"

    # Compter les partants actuels pour détecter les non-partants
    nb_actuels = {c["code_pmu"]: c["nb_partants"] for c in courses}

    # Si on a déjà calculé ET les partants n'ont pas changé → retourner le cache
    if (cle_session in st.session_state and
            nb_session in st.session_state and
            st.session_state[nb_session] == nb_actuels):
        return st.session_state[cle_session], False

    # Recalcul nécessaire
    recalcul = cle_session in st.session_state  # True = non-partant détecté
    analyses = []

    for c in courses:
        disc_str = c["course_raw"].get("discipline", "PLAT")
        disc_num = {"PLAT":2,"TROT_ATTELE":3,"TROT_MONTE":4,
                    "OBSTACLE":1,"CROSS":0}.get(disc_str, 2)
        model, feats, nom_mod = choisir_modele(modeles, disc_num)

        df = construire_features(c["participants"], c["course_raw"],
                                  c["hippodrome"], stats_cheval,
                                  stats_jockey, stats_hippo)
        for col in feats:
            if col not in df.columns:
                df[col] = 0.0
        feats_ok = [f for f in feats if f in df.columns]
        probas   = model.predict_proba(df[feats_ok])[:, 1] * 100

        if df["cote"].min() < 2.0:
            continue

        df_tri = pd.DataFrame({
            "num"      : df["num"].tolist(),
            "cheval"   : df["nom_cheval"].tolist(),
            "cote"     : df["cote"].tolist(),
            "confiance": probas.tolist(),
        }).sort_values("confiance", ascending=False).reset_index(drop=True)

        score_val = float(df_tri.iloc[0]["confiance"]) / (
            np.log1p(float(df_tri.iloc[0]["cote"])) + 1)

        meteo = get_meteo_course(c["hippodrome"],
                                  date_cible.strftime("%Y-%m-%d"), c["heure"])

        sup_avis = {"niveau":"neutre","emoji":"⚪","conseil":"",
                    "multiplicateur_kelly":1.0,"disponible":False}
        if SUPERVISEUR_DISPO:
            try:
                snap_tmp = {"df_tri": df_tri, "meteo": meteo or {}, "course": c}
                sup_avis = avis_superviseur_depuis_analyse(snap_tmp, disc_str)
            except Exception:
                pass

        # Commentaires automatiques
        commentaires = []
        confs = df_tri["confiance"].tolist()
        cotes = df_tri["cote"].tolist()
        ecart = confs[0] - confs[1] if len(confs) >= 2 else 0
        if ecart < 3:
            commentaires.append("⚠️ Course très ouverte — surprise possible")
        elif ecart >= 10:
            commentaires.append("✅ Leader bien identifié")
        if cotes[0] > 8:
            commentaires.append("🎯 Outsider en tête — cote intéressante")
        if meteo and meteo.get("terrain_lourd"):
            commentaires.append("🟫 Terrain lourd — avantage aux habitués")
        if c["nb_partants"] >= 15:
            commentaires.append(f"🐴 Grande course ({c['nb_partants']} partants) — Quinté désordre conseillé")

        cotes_ont_valeur = any(ct != 20.0 for ct in cotes[:5])

        analyses.append({
            "course"          : c,
            "df_tri"          : df_tri,
            "nom_mod"         : nom_mod,
            "disc_str"        : disc_str,
            "conf_top"        : float(df_tri.iloc[0]["confiance"]),
            "cote_top"        : float(df_tri.iloc[0]["cote"]),
            "score_val"       : score_val,
            "meteo"           : meteo,
            "sup_avis"        : sup_avis,
            "commentaires"    : commentaires[:2],
            "cotes_ont_valeur": cotes_ont_valeur,
        })

    # Figer en session
    st.session_state[cle_session] = analyses
    st.session_state[nb_session]  = nb_actuels
    return analyses, recalcul


# ─────────────────────────────────────────────
# HELPERS AFFICHAGE
# ─────────────────────────────────────────────

def etoiles(c):
    if c >= 70: return "⭐⭐⭐⭐⭐"
    if c >= 55: return "⭐⭐⭐⭐"
    if c >= 40: return "⭐⭐⭐"
    if c >= 25: return "⭐⭐"
    return "⭐"


def badge_sup(niveau):
    if niveau == "confiant":
        return '<span class="badge-vert">🟢 Superviseur : Confiant</span>'
    if niveau == "prudent":
        return '<span class="badge-orange">🟡 Superviseur : Prudent</span>'
    if niveau == "danger":
        return '<span class="badge-rouge">🔴 Superviseur : Danger</span>'
    return '<span class="badge-neutre">⚪ Superviseur en attente</span>'


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

if "model_version" not in st.session_state:
    st.session_state.model_version = 0

# ✅ Auto-refresh toutes les 2h — uniquement pour détecter les non-partants
if AUTOREFRESH_DISPO:
    st_autorefresh(interval=2 * 60 * 60 * 1000, key="ar_victor")

with st.sidebar:
    st.markdown(f"### 👋 {nom_abonne}")
    plan_emoji = {"essentiel":"🥉","pro":"🥇","vip":"💎"}.get(plan,"🎫")
    st.caption(f"{plan_emoji} Plan **{plan.upper()}** · {jours_restants}j restants")
    if jours_restants <= 5:
        st.warning(f"⚠️ Expire dans {jours_restants}j\n+221 76 264 17 51")

    st.markdown("---")
    if st.button("🔄 Recharger le modèle IA"):
        st.session_state.model_version += 1
        st.cache_resource.clear()
        st.cache_data.clear()
        # Effacer aussi les pronostics figés
        for k in list(st.session_state.keys()):
            if k.startswith("analyses_") or k.startswith("nb_partants_"):
                del st.session_state[k]
        st.rerun()

    st.markdown("---")
    st.subheader("💰 Bankroll")
    bankroll      = st.number_input("Montant (FCFA/€) :",
                                     min_value=100, max_value=10000000,
                                     value=10000, step=500)
    methode_kelly = st.selectbox("Méthode Kelly :",
                                  ["quarter (conservateur)",
                                   "half (modéré)", "full (agressif)"], index=0)
    methode_k     = methode_kelly.split(" ")[0]

    st.markdown("---")
    afficher_meteo_flag = st.toggle("🌤️ Météo", value=True)
    vue_ticket          = st.toggle("🎫 Vue Ticket", value=True)

    st.markdown("---")
    st.subheader("🌍 Zone")
    mode_affichage = st.radio("Catalogue :",
                               ["Tout le programme", "Sélection Afrique"])
    if mode_affichage == "Sélection Afrique":
        codes_saisis = st.text_input("Codes :", "R1C5, R1C6, R1C7")
        codes_actifs = [c.strip().upper() for c in codes_saisis.split(",") if c.strip()]

    st.markdown("---")
    st.subheader("📆 Journée")
    choix_jour = st.radio("", ["Hier","Aujourd'hui","Demain"],
                           index=1, horizontal=True)
    d0 = date.today()
    if choix_jour == "Hier":
        date_cible = d0 - datetime.timedelta(days=1)
    elif choix_jour == "Aujourd'hui":
        date_cible = d0
    else:
        date_cible = d0 + datetime.timedelta(days=1)

    st.markdown("---")
    if st.button("🚪 Déconnexion"):
        deconnecter(st.session_state.get("telephone",""))
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

modeles, features_global, auc = charger_modeles(st.session_state.model_version)
stats_cheval, stats_jockey, stats_hippo = charger_stats(st.session_state.model_version)

if modeles is None:
    st.error("❌ Modèle introuvable.")
    st.stop()

info_m = " | ".join([f"{n} {modeles[n]['auc']*100:.0f}%" for n in modeles.keys()])
st.sidebar.info(f"🧠 {info_m}")

# Date lisible en français
jours_fr = {"Monday":"Lundi","Tuesday":"Mardi","Wednesday":"Mercredi",
            "Thursday":"Jeudi","Friday":"Vendredi","Saturday":"Samedi","Sunday":"Dimanche"}
mois_fr  = {1:"Janvier",2:"Février",3:"Mars",4:"Avril",5:"Mai",6:"Juin",
            7:"Juillet",8:"Août",9:"Septembre",10:"Octobre",11:"Novembre",12:"Décembre"}
jour_sem    = jours_fr.get(date_cible.strftime("%A"), date_cible.strftime("%A"))
date_lisible= f"{jour_sem} {date_cible.day} {mois_fr.get(date_cible.month,'')} {date_cible.year}"

# ─────────────────────────────────────────────
# TITRE
# ─────────────────────────────────────────────

col_titre, col_refresh = st.columns([4, 1])
with col_titre:
    st.title("🏇 Victor V2")
    st.markdown(f"### 📅 {date_lisible}")
with col_refresh:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.button("🔄 Actualiser\n(non-partants)", use_container_width=True):
        st.cache_data.clear()
        for k in list(st.session_state.keys()):
            if k.startswith("analyses_") or k.startswith("nb_partants_"):
                del st.session_state[k]
        st.rerun()

st.markdown("---")

# ─────────────────────────────────────────────
# PROGRAMME + ANALYSES
# ─────────────────────────────────────────────

with st.spinner(f"Chargement du {date_lisible}..."):
    courses = get_programme(date_cible)

if mode_affichage == "Sélection Afrique":
    courses = [c for c in courses if c["code_pmu"] in codes_actifs]

if not courses:
    st.warning(f"⚠️ Aucune course pour le {date_lisible}.")
    st.stop()

analyses, non_partant_detecte = calculer_analyses(
    courses, modeles, stats_cheval, stats_jockey, stats_hippo, date_cible)

if non_partant_detecte:
    st.warning("⚡ Non-partant détecté — pronostics recalculés automatiquement.")

if not analyses:
    st.info("Aucune course ne répond aux critères.")
    st.stop()

st.sidebar.success(f"📅 {len(analyses)} courses analysées")

# Heure de calcul
heure_calcul = st.session_state.get(
    f"heure_calcul_{date_cible.isoformat()}",
    datetime.datetime.now().strftime("%H:%M")
)
st.session_state[f"heure_calcul_{date_cible.isoformat()}"] = heure_calcul
st.caption(f"🔒 Pronostics calculés à **{heure_calcul}** · "
           f"Stables jusqu'au prochain non-partant · "
           f"Refresh auto toutes les 2h")

# ─────────────────────────────────────────────
# ONGLETS
# ─────────────────────────────────────────────

onglet1, onglet2, onglet3 = st.tabs([
    "🎯 Snipers & Pronostics",
    "📊 Toutes les courses",
    "📅 Historique"
])

# ══════════════════════════════════════════════
# ONGLET 1
# ══════════════════════════════════════════════

with onglet1:

    top3 = sorted(analyses, key=lambda x: x["score_val"], reverse=True)[:3]

    st.subheader(f"🎯 Top 3 Snipers — {date_lisible}")
    st.caption("Score Valeur = Confiance ÷ log(Cote)")

    s_cols = st.columns(3)
    for idx, snap in enumerate(top3):
        c_info = snap["course"]
        df_t   = snap["df_tri"]
        sup    = snap["sup_avis"]
        with s_cols[idx]:
            st.markdown(badge_sup(sup["niveau"]), unsafe_allow_html=True)
            st.markdown(f"### 🔥 Top {idx+1}")
            if afficher_meteo_flag and snap["meteo"].get("temperature"):
                m = snap["meteo"]
                st.caption(f"🌡️ {m['temperature']:.0f}°C · "
                           f"{'🟫 Lourd' if m['terrain_lourd'] else '🟩 Sec'}")
            st.markdown(f"""
<div class="course-header">
  <div class="course-date">{date_lisible}</div>
  <div class="course-lieu">📍 {c_info['hippodrome']}</div>
  <div class="course-prix">🏆 {c_info['libelle']}</div>
  <div class="course-heure">⏰ {c_info['heure']} · {c_info['code_pmu']}</div>
</div>
""", unsafe_allow_html=True)
            st.metric(label="Confiance IA",
                      value=f"{snap['conf_top']:.1f}%",
                      delta=f"Score : {snap['score_val']:.1f}")
            kelly = calculer_mise(bankroll, snap["conf_top"]/100,
                                   snap["cote_top"], methode_k)
            mult  = sup.get("multiplicateur_kelly", 1.0)
            mise  = kelly["montant_mise"] * mult
            num_top = int(df_t.iloc[0]["num"])
            st.markdown(
                f"🐴 **{num_top}** {etoiles(snap['conf_top'])}\n\n"
                f"🎫 Cote : **{snap['cote_top']}**  |  💰 Mise : **{mise:,.0f}**\n\n"
                f"🤖 *{snap['nom_mod']}*"
            )
            if sup.get("conseil"):
                st.caption(sup["conseil"])

    st.markdown("---")
    st.subheader("🎟️ Pronostics complets")

    for snap in analyses:
        c_info = snap["course"]
        df_t   = snap["df_tri"]
        sup    = snap["sup_avis"]

        with st.expander(
            f"⏰ {c_info['heure']} · 📍 {c_info['hippodrome']} · "
            f"{c_info['libelle']} ({c_info['code_pmu']})",
            expanded=(mode_affichage == "Sélection Afrique")
        ):
            # Infos course
            st.markdown(f"""
<div class="course-header">
  <div class="course-date">📅 {date_lisible}</div>
  <div class="course-lieu">📍 {c_info['hippodrome']}</div>
  <div class="course-prix">🏆 {c_info['libelle']}</div>
  <div class="course-heure">
    ⏰ {c_info['heure']} · {c_info['code_pmu']} ·
    {c_info['course_raw'].get('distance',0)}m · {c_info['nb_partants']} partants
  </div>
</div>
""", unsafe_allow_html=True)

            # Superviseur
            st.markdown(badge_sup(sup["niveau"]), unsafe_allow_html=True)
            if sup.get("conseil"):
                st.caption(sup["conseil"])

            # Commentaires
            for comm in snap["commentaires"]:
                st.caption(comm)

            # Météo
            if afficher_meteo_flag and snap["meteo"].get("temperature"):
                m = snap["meteo"]
                terrain = "🟫 Terrain lourd" if m["terrain_lourd"] else "🟩 Terrain sec"
                st.info(f"🌤️ {m['temperature']:.0f}°C · "
                        f"🌧️ {m['precipitation']:.1f}mm · "
                        f"💨 {m['vent_kmh']:.0f}km/h · {terrain}")

            # Avertissement cotes futures
            if not snap["cotes_ont_valeur"]:
                st.warning("ℹ️ Les cotes ne sont pas encore disponibles pour cette course "
                           "(normal pour demain). Les pronostics sont basés sur la forme "
                           "et les statistiques — les cotes seront disponibles le jour J.")

            st.caption(f"🤖 Modèle : **{snap['nom_mod']}**")

            top5     = df_t["num"].head(5).astype(int).tolist()
            suivants = df_t["num"].iloc[5:8].astype(int).tolist()

            if vue_ticket:
                nums_str = " · ".join([str(n) for n in top5])
                suiv_str = " - ".join([str(n) for n in suivants])

                # ✅ Ticket avec numéros grands et bien visibles
                st.markdown(f"""
<div class="ticket-box">
  <div style="color:#888;font-size:11px;letter-spacing:1px;margin-bottom:6px">
    {c_info['hippodrome']} · {c_info['code_pmu']} · {c_info['course_raw'].get('distance',0)}m
  </div>
  <div class="ticket-nums">{nums_str}</div>
  <div class="ticket-suivants">SUIVANTS : {suiv_str}</div>
</div>
""", unsafe_allow_html=True)

                # ✅ Étoiles + POURCENTAGE sous chaque numéro
                cols_e = st.columns(5)
                for i, row in df_t.head(5).iterrows():
                    with cols_e[i]:
                        st.markdown(
                            f"<div class='cheval-card'>"
                            f"<div class='cheval-num'>{int(row['num'])}</div>"
                            f"<div class='cheval-etoiles'>{etoiles(row['confiance'])}</div>"
                            f"<div class='cheval-pct'>{row['confiance']:.0f}%</div>"
                            f"<div class='cheval-cote'>Cote {row['cote']}</div>"
                            f"</div>",
                            unsafe_allow_html=True
                        )
            else:
                mult = sup.get("multiplicateur_kelly", 1.0)
                df_t["⭐"] = df_t["confiance"].apply(etoiles)
                df_t["%"]  = df_t["confiance"].apply(lambda x: f"{x:.0f}%")
                df_t["Kelly"] = df_t.apply(
                    lambda r: f"{calculer_mise(bankroll, r['confiance']/100, r['cote'], methode_k)['montant_mise']*mult:,.0f}",
                    axis=1
                )
                st.dataframe(
                    df_t[["num","cote","⭐","%","Kelly"]].rename(
                        columns={"num":"N°","cote":"Cote"}
                    ).head(8),
                    use_container_width=True, hide_index=True
                )

            # Tickets — numéros sans N°
            t1, t2, t3, t4 = st.columns(4)
            with t1:
                st.success(f"**💡 GAGNANT**\n\n**{top5[0]}**")
            with t2:
                if len(top5) >= 2:
                    st.info(f"**🟢 COUPLÉ**\n\n{top5[0]} · {top5[1]}")
            with t3:
                if len(top5) >= 3:
                    st.warning(f"**🟡 TIERCÉ**\n\n"
                               f"{top5[0]} · {top5[1]} · {top5[2]}")
            with t4:
                st.error(f"**🔴 QUINTÉ+**\n\n"
                         f"{' · '.join([str(n) for n in top5])}")

# ══════════════════════════════════════════════
# ONGLET 2
# ══════════════════════════════════════════════

with onglet2:
    st.subheader("📊 Toutes les courses analysées")
    col1, col2 = st.columns(2)
    with col1:
        hippos       = ["Tous"] + sorted({a["course"]["hippodrome"] for a in analyses})
        filtre_hippo = st.selectbox("Hippodrome :", hippos)
    with col2:
        recherche = st.text_input("Mot-clé :", "")

    analyses_f = analyses
    if filtre_hippo != "Tous":
        analyses_f = [a for a in analyses_f
                      if a["course"]["hippodrome"] == filtre_hippo]
    if recherche:
        analyses_f = [a for a in analyses_f
                      if recherche.lower() in a["course"]["libelle"].lower()]

    for snap in analyses_f:
        c_info = snap["course"]
        df_t   = snap["df_tri"]
        top5   = df_t["num"].head(5).astype(int).tolist()
        sup    = snap["sup_avis"]

        with st.expander(
            f"⏰ {c_info['heure']} · 📍 {c_info['hippodrome']} — {c_info['libelle']}"
        ):
            st.markdown(f"""
<div class="course-header">
  <div class="course-lieu">📍 {c_info['hippodrome']}</div>
  <div class="course-prix">🏆 {c_info['libelle']}</div>
  <div class="course-heure">⏰ {c_info['heure']} · {c_info['code_pmu']} · {c_info['nb_partants']} partants</div>
</div>
""", unsafe_allow_html=True)
            st.markdown(badge_sup(sup["niveau"]), unsafe_allow_html=True)
            mult = sup.get("multiplicateur_kelly", 1.0)
            df_t["⭐"] = df_t["confiance"].apply(etoiles)
            df_t["%"]  = df_t["confiance"].apply(lambda x: f"{x:.0f}%")
            df_t["Kelly"] = df_t.apply(
                lambda r: f"{calculer_mise(bankroll, r['confiance']/100, r['cote'], methode_k)['montant_mise']*mult:,.0f}",
                axis=1
            )
            st.dataframe(
                df_t[["num","cote","⭐","%","Kelly"]].rename(
                    columns={"num":"N°","cote":"Cote"}
                ).head(8),
                use_container_width=True, hide_index=True
            )
            st.markdown("**Quinté+ :** " + " · ".join([str(n) for n in top5]))

# ══════════════════════════════════════════════
# ONGLET 3
# ══════════════════════════════════════════════

with onglet3:
    st.subheader("📅 Historique des courses")
    chemin = os.path.join(DOSSIER_DATA, "raw_courses.csv")
    if os.path.exists(chemin):
        df_h = pd.read_csv(chemin, encoding="utf-8-sig")
        df_h["date"] = pd.to_datetime(df_h["date"])
        c1, c2 = st.columns(2)
        with c1:
            d_debut = st.date_input("Du :",
                                     value=date.today()-datetime.timedelta(days=7))
        with c2:
            d_fin = st.date_input("Au :", value=date.today())
        mask = ((df_h["date"].dt.date >= d_debut) &
                (df_h["date"].dt.date <= d_fin))
        df_f = df_h[mask]
        if not df_f.empty:
            hippos_h = ["Tous"] + sorted(df_f["hippodrome"].unique().tolist())
            fh = st.selectbox("Hippodrome :", hippos_h, key="hist_h")
            if fh != "Tous":
                df_f = df_f[df_f["hippodrome"] == fh]
            cols = ["date","hippodrome","num_course","num_cheval","cote","place"]
            cols_ok = [c for c in cols if c in df_f.columns]
            st.dataframe(
                df_f[cols_ok].sort_values(["date","num_course"]).head(200),
                use_container_width=True, hide_index=True
            )
            st.caption(f"{len(df_f)} partants sur la période")
        else:
            st.info("Aucune donnée sur cette période.")
    else:
        st.info("Pas encore de données historiques.")