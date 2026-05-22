"""
VICTOR V2 — Interface Web v12 (Mobile Native + Navigation Opti)
===============================================================
- Menu latéral mobile réactivé (🍔 hamburger menu).
- Navigation par Réunions (R1, R2...) via des onglets.
- Courses (C1, C2...) dans des cartes déroulantes (Expanders).
- HTML sécurisé sans indentation.
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

# CSS mis à jour : j'ai supprimé la règle qui cachait le menu sur mobile
st.markdown("""<style>
/* --- DESIGN HEADER DE COURSE --- */
.course-header-mobile {
    background-color: #1a1c23;
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
    text-align: center;
    border: 1px solid #2d3139;
}
.ch-title { font-size: 16px; font-weight: 800; color: #ffffff; text-transform: uppercase; margin-bottom: 4px; }
.ch-subtitle { font-size: 13px; color: #a0a5b1; font-weight: 600; }
.ch-stats { font-size: 12px; color: #6b7280; margin-top: 4px; }
.ch-time { font-size: 15px; font-weight: 700; color: #1D9E75; margin-top: 8px; }

/* --- DESIGN LISTE VERTICALE (LE TEMPLATE) --- */
.horse-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 10px;
}
.horse-row {
    display: flex;
    align-items: center;
    background-color: #21252d;
    border-radius: 8px;
    padding: 10px 12px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}
.h-num {
    width: 44px;
    height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 900;
    border-radius: 6px;
    margin-right: 14px;
    color: white;
    flex-shrink: 0;
}
/* Couleurs selon le template */
.rank-0 { background-color: #1D9E75; } /* 1er: Vert */
.rank-1, .rank-2 { background-color: #EF9F27; } /* 2e et 3e: Orange */
.rank-other { background-color: #4a4d55; } /* Autres: Gris */

.h-info {
    flex-grow: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    overflow: hidden;
}
.h-name { 
    font-size: 15px; 
    font-weight: 800; 
    color: #ffffff; 
    white-space: nowrap; 
    overflow: hidden; 
    text-overflow: ellipsis;
}
.h-cote { 
    font-size: 13px; 
    color: #a0a5b1; 
    margin-top: 2px;
    font-weight: 500;
}

.h-stats {
    text-align: right;
    display: flex;
    flex-direction: column;
    justify-content: center;
    flex-shrink: 0;
    margin-left: 10px;
}
.h-pct { font-size: 18px; font-weight: 900; color: #1D9E75; }
.h-kelly { font-size: 11px; color: #888; margin-top: 2px; }

/* Badges Superviseur */
.badge-vert   { background:#0f3d2e; color:#1D9E75; padding:4px 12px; border-radius:99px; font-size:12px; font-weight:700; }
.badge-orange { background:#3d2a0f; color:#EF9F27; padding:4px 12px; border-radius:99px; font-size:12px; font-weight:700; }
.badge-rouge  { background:#3d0f0f; color:#E24B4A; padding:4px 12px; border-radius:99px; font-size:12px; font-weight:700; }
.badge-neutre { background:#2d3139; color:#a0a5b1; padding:4px 12px; border-radius:99px; font-size:12px; font-weight:700; }
</style>""", unsafe_allow_html=True)

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
        return {"temperature": None, "precipitation": 0, "vent_kmh": 0, "terrain_lourd": 0}

# ─────────────────────────────────────────────
# PROGRAMME PMU
# ─────────────────────────────────────────────

@st.cache_data(ttl=7200)
def get_programme(date_cible):
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
                    participants = (r_p.json().get("participants", []) if r_p.status_code == 200 else [])
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

def calculer_analyses(courses, modeles, stats_cheval, stats_jockey, stats_hippo, date_cible):
    cle_session = f"analyses_{date_cible.isoformat()}"
    nb_session  = f"nb_partants_{date_cible.isoformat()}"
    nb_actuels = {c["code_pmu"]: c["nb_partants"] for c in courses}

    if (cle_session in st.session_state and
            nb_session in st.session_state and
            st.session_state[nb_session] == nb_actuels):
        return st.session_state[cle_session], False

    recalcul = cle_session in st.session_state
    analyses = []

    for c in courses:
        disc_str = c["course_raw"].get("discipline", "PLAT")
        disc_num = {"PLAT":2,"TROT_ATTELE":3,"TROT_MONTE":4, "OBSTACLE":1,"CROSS":0}.get(disc_str, 2)
        model, feats, nom_mod = choisir_modele(modeles, disc_num)

        df = construire_features(c["participants"], c["course_raw"], c["hippodrome"], stats_cheval, stats_jockey, stats_hippo)
        for col in feats:
            if col not in df.columns: df[col] = 0.0
        feats_ok = [f for f in feats if f in df.columns]
        probas   = model.predict_proba(df[feats_ok])[:, 1] * 100

        if df["cote"].min() < 2.0: continue

        df_tri = pd.DataFrame({
            "num"      : df["num"].tolist(),
            "cheval"   : df["nom_cheval"].tolist(),
            "cote"     : df["cote"].tolist(),
            "confiance": probas.tolist(),
        }).sort_values("confiance", ascending=False).reset_index(drop=True)

        score_val = float(df_tri.iloc[0]["confiance"]) / (np.log1p(float(df_tri.iloc[0]["cote"])) + 1)
        meteo = get_meteo_course(c["hippodrome"], date_cible.strftime("%Y-%m-%d"), c["heure"])
        
        sup_avis = {"niveau":"neutre","emoji":"⚪","conseil":"","multiplicateur_kelly":1.0,"disponible":False}
        if SUPERVISEUR_DISPO:
            try:
                snap_tmp = {"df_tri": df_tri, "meteo": meteo or {}, "course": c}
                sup_avis = avis_superviseur_depuis_analyse(snap_tmp, disc_str)
            except Exception: pass

        commentaires = []
        confs = df_tri["confiance"].tolist()
        ecart = confs[0] - confs[1] if len(confs) >= 2 else 0
        if ecart < 3: commentaires.append("⚠️ Course très ouverte")
        elif ecart >= 10: commentaires.append("✅ Leader identifié")
        
        analyses.append({
            "course": c, "df_tri": df_tri, "nom_mod": nom_mod, "disc_str": disc_str,
            "conf_top": float(df_tri.iloc[0]["confiance"]), "cote_top": float(df_tri.iloc[0]["cote"]),
            "score_val": score_val, "meteo": meteo, "sup_avis": sup_avis,
            "commentaires": commentaires[:2], "cotes_ont_valeur": any(ct != 20.0 for ct in df_tri["cote"].tolist()[:5])
        })

    st.session_state[cle_session] = analyses
    st.session_state[nb_session]  = nb_actuels
    return analyses, recalcul

def badge_sup(niveau):
    if niveau == "confiant": return '<span class="badge-vert">🟢 Confiant</span>'
    if niveau == "prudent": return '<span class="badge-orange">🟡 Prudent</span>'
    if niveau == "danger": return '<span class="badge-rouge">🔴 Danger</span>'
    return '<span class="badge-neutre">⚪ Neutre</span>'


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

if "model_version" not in st.session_state: st.session_state.model_version = 0

if AUTOREFRESH_DISPO: st_autorefresh(interval=2 * 60 * 60 * 1000, key="ar_victor")

with st.sidebar:
    st.markdown(f"### 👋 {nom_abonne}")
    plan_emoji = {"essentiel":"🥉","pro":"🥇","vip":"💎"}.get(plan,"🎫")
    st.caption(f"{plan_emoji} Plan **{plan.upper()}** · {jours_restants}j restants")
    
    st.markdown("---")
    bankroll = st.number_input("Montant (FCFA/€) :", min_value=100, max_value=10000000, value=10000, step=500)
    methode_kelly = st.selectbox("Méthode Kelly :", ["quarter (conservateur)", "half (modéré)", "full (agressif)"], index=0)
    methode_k = methode_kelly.split(" ")[0]

    st.markdown("---")
    mode_affichage = st.radio("Catalogue :", ["Tout le programme", "Sélection Afrique"])
    if mode_affichage == "Sélection Afrique":
        codes_saisis = st.text_input("Codes :", "R1C5, R1C6, R1C7")
        codes_actifs = [c.strip().upper() for c in codes_saisis.split(",") if c.strip()]

    st.markdown("---")
    choix_jour = st.radio("Journée :", ["Hier","Aujourd'hui","Demain"], index=1, horizontal=True)
    d0 = date.today()
    if choix_jour == "Hier": date_cible = d0 - datetime.timedelta(days=1)
    elif choix_jour == "Aujourd'hui": date_cible = d0
    else: date_cible = d0 + datetime.timedelta(days=1)

    st.markdown("---")
    if st.button("🚪 Déconnexion"):
        deconnecter(st.session_state.get("telephone",""))
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

modeles, features_global, auc = charger_modeles(st.session_state.model_version)
stats_cheval, stats_jockey, stats_hippo = charger_stats(st.session_state.model_version)

if modeles is None:
    st.error("❌ Modèle introuvable.")
    st.stop()

# ─────────────────────────────────────────────
# TITRE ET DONNÉES
# ─────────────────────────────────────────────

col_titre, col_refresh = st.columns([4, 1])
with col_titre:
    st.title("🏇 Victor V2")
with col_refresh:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Actualiser"):
        st.cache_data.clear()
        for k in list(st.session_state.keys()):
            if k.startswith("analyses_") or k.startswith("nb_partants_"): del st.session_state[k]
        st.rerun()

st.markdown("---")

with st.spinner("Chargement des courses..."):
    courses = get_programme(date_cible)

if mode_affichage == "Sélection Afrique":
    courses = [c for c in courses if c["code_pmu"] in codes_actifs]

if not courses:
    st.warning("⚠️ Aucune course disponible.")
    st.stop()

analyses, non_partant_detecte = calculer_analyses(courses, modeles, stats_cheval, stats_jockey, stats_hippo, date_cible)

if not analyses:
    st.info("Aucune course ne répond aux critères.")
    st.stop()

onglet_pronos, onglet_historique = st.tabs(["🎯 Pronostics", "📅 Historique"])

# ══════════════════════════════════════════════
# ONGLET 1 : ORGANISATION PAR RÉUNION (R1, R2...)
# ══════════════════════════════════════════════

with onglet_pronos:
    
    # 1. Regrouper les analyses par Réunion (R1, R2, etc.)
    reunions_dict = {}
    for snap in analyses:
        num_reunion = f"R{snap['course']['num_r']}"
        nom_hippo = snap['course']['hippodrome']
        key_reunion = f"{num_reunion} - {nom_hippo}"
        
        if key_reunion not in reunions_dict:
            reunions_dict[key_reunion] = []
        reunions_dict[key_reunion].append(snap)
        
    # 2. Trier les réunions (R1 avant R2, etc.)
    reunions_triees = sorted(list(reunions_dict.keys()))
    
    # 3. Créer des onglets pour chaque Réunion
    tabs_reunions = st.tabs(reunions_triees)
    
    for idx, nom_reunion in enumerate(reunions_triees):
        with tabs_reunions[idx]:
            # Trier les courses chronologiquement dans la réunion
            courses_de_reunion = sorted(reunions_dict[nom_reunion], key=lambda x: x['course']['heure'])
            
            for snap in courses_de_reunion:
                c_info = snap["course"]
                df_t   = snap["df_tri"]
                sup    = snap["sup_avis"]
                mult   = sup.get("multiplicateur_kelly", 1.0)
                
                num_c = f"C{c_info['num_c']}"
                titre_carte = f"🏁 {num_c} - {c_info['heure']} - {c_info['libelle']}"
                
                # 4. Afficher la Course dans un Expander (Carte déroulante fermée par défaut)
                with st.expander(titre_carte, expanded=False):
                    
                    # HTML de l'entête collé à gauche pour éviter le bug Markdown
                    st.markdown(f"""<div class="course-header-mobile">
<div class="ch-title">🏆 {c_info['libelle']}</div>
<div class="ch-subtitle">{c_info['hippodrome']} - {c_info['code_pmu']} - {snap['disc_str']}</div>
<div class="ch-stats">{c_info['nb_partants']} partants · {c_info['course_raw'].get('distance',0)}m</div>
<div class="ch-time">Départ à {c_info['heure']}</div>
<div style="margin-top:10px;">{badge_sup(sup["niveau"])}</div>
</div>""", unsafe_allow_html=True)

                    if not snap["cotes_ont_valeur"]:
                        st.warning("ℹ️ Cotes non disponibles. Basé sur statistiques.")

                    # DEBUT DE LA LISTE VERTICALE
                    html_list = "<div class='horse-list'>"
                    
                    for i, row in df_t.head(8).iterrows():
                        if i == 0: rank_class = "rank-0"
                        elif i in [1, 2]: rank_class = "rank-1"
                        else: rank_class = "rank-other"

                        cheval_nom = row['cheval']
                        cote_val = row['cote']
                        confiance = row['confiance']
                        mise_k = calculer_mise(bankroll, confiance/100, cote_val, methode_k)['montant_mise'] * mult

                        html_list += f"""<div class='horse-row'>
<div class='h-num {rank_class}'>{int(row['num'])}</div>
<div class='h-info'>
<div class='h-name'>{cheval_nom}</div>
<div class='h-cote'>Cote: {cote_val}</div>
</div>
<div class='h-stats'>
<div class='h-pct'>{confiance:.1f}%</div>
<div class='h-kelly'>Mise {mise_k:,.0f}</div>
</div>
</div>"""
                        
                        if i == 4 and len(df_t) > 5:
                            html_list += """<div style="text-align:center; font-size:12px; color:#1D9E75; margin: 8px 0; font-weight:bold; letter-spacing:1px;">
--- CHEVAUX SUIVANTS ---
</div>"""
                    
                    html_list += "</div>"
                    
                    st.markdown(html_list, unsafe_allow_html=True)


# ══════════════════════════════════════════════
# ONGLET 2 : HISTORIQUE
# ══════════════════════════════════════════════

with onglet_historique:
    st.subheader("📅 Historique des courses")
    chemin = os.path.join(DOSSIER_DATA, "raw_courses.csv")
    if os.path.exists(chemin):
        df_h = pd.read_csv(chemin, encoding="utf-8-sig")
        df_h["date"] = pd.to_datetime(df_h["date"])
        d_debut = st.date_input("Du :", value=date.today()-datetime.timedelta(days=7))
        d_fin = st.date_input("Au :", value=date.today())
        
        mask = ((df_h["date"].dt.date >= d_debut) & (df_h["date"].dt.date <= d_fin))
        df_f = df_h[mask]
        
        if not df_f.empty:
            hippos_h = ["Tous"] + sorted(df_f["hippodrome"].unique().tolist())
            fh = st.selectbox("Hippodrome :", hippos_h, key="hist_h")
            if fh != "Tous": df_f = df_f[df_f["hippodrome"] == fh]
            
            cols = ["date","hippodrome","num_course","num_cheval","cote","place"]
            cols_ok = [c for c in cols if c in df_f.columns]
            st.dataframe(df_f[cols_ok].sort_values(["date","num_course"]).head(200), use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée sur cette période.")
    else:
        st.info("Pas encore de données historiques.")