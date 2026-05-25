"""
VICTOR V2 — Interface Web v13.2
"""
import streamlit as st
import requests
import pandas as pd
import numpy as np
import joblib
import json
import os
import datetime
from datetime import date, timezone

from utils import construire_features, charger_stats_historiques
from kelly import calculer_mise
from auth.supabase_client import verifier_session, deconnecter

# Configuration de la page
st.set_page_config(
    page_title="Victor V2 - Pronostics PMU",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# ROUTING UNIQUE & SIMPLE
# ─────────────────────────────────────────────

# 1. Vérification Admin
if st.query_params.get("page") == "admin":
    from pages.admin import afficher_admin
    afficher_admin()
    st.stop()

# 2. Gestion de l'accès libre et redirection forcée
ACCES_LIBRE = False 

if not ACCES_LIBRE:
    if not st.session_state.get("connecte"):
        # Redirection directe vers la page officielle dans /pages
        st.switch_page("pages/login.py")
    
    # Vérifier si la session est toujours valide
    if not verifier_session(
        st.session_state.get("telephone", ""),
        st.session_state.get("session_token", "")
    ):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("pages/login.py")

# Si on est ici, c'est qu'on est connecté
nom_abonne     = st.session_state.get("nom", "Visiteur")
jours_restants = st.session_state.get("jours_restants", 999)
plan           = st.session_state.get("plan", "pro")

# [ICI : RESTE DE TON CODE (Modeles, Programme, etc.) NE PAS CHANGER]
# ... (Gardez tout ton code existant à partir d'ici jusqu'à la fin du fichier) ...

# ─────────────────────────────────────────────
# MODÈLES & STATS
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


@st.cache_data(ttl=300)
def get_resultats_jour(date_str):
    try:
        from auth.supabase_client import get_client
        supabase = get_client()
        if not supabase:
            return {}
        res = supabase.table("historique_courses")\
                      .select("code_course, resultat_reel")\
                      .eq("date", date_str).execute()
        if res.data:
            return {
                row["code_course"]: row["resultat_reel"]
                for row in res.data
                if row.get("resultat_reel")
            }
    except Exception:
        pass
    return {}


@st.cache_data(ttl=600)
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
                heure = (datetime.datetime.fromtimestamp(valeur_heure / 1000).strftime("%H:%M")
                         if isinstance(valeur_heure, int) else str(valeur_heure)[:5])
                url_p = f"{BASE_URL}/{date_str}/R{num_r}/C{num_c}/participants"
                try:
                    r_p          = requests.get(url_p, headers=HEADERS, timeout=5)
                    participants = r_p.json().get("participants", []) if r_p.status_code == 200 else []
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


@st.cache_data(ttl=86400)
def calculer_analyses(_courses, _modeles, _stats_cheval, _stats_jockey,
                       _stats_hippo, date_cible, periode_cache):
    analyses = []
    for c in _courses:
        disc_str = c["course_raw"].get("discipline", "PLAT")
        disc_num = {"PLAT":2,"TROT_ATTELE":3,"TROT_MONTE":4,
                    "OBSTACLE":1,"CROSS":0}.get(disc_str, 2)
        model, feats, nom_mod = choisir_modele(_modeles, disc_num)
        df = construire_features(c["participants"], c["course_raw"], c["hippodrome"],
                                  _stats_cheval, _stats_jockey, _stats_hippo)
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
        if df_tri.empty: continue
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
        commentaires = []
        confs = df_tri["confiance"].tolist()
        ecart = confs[0] - confs[1] if len(confs) >= 2 else 0
        if ecart < 3:  commentaires.append("⚠️ Course très ouverte")
        elif ecart >= 10: commentaires.append("✅ Leader identifié")
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
            "cotes_ont_valeur": any(ct != 20.0 for ct in df_tri["cote"].tolist()[:5]),
            "nums_figes"      : set(int(n) for n in df_tri["num"].tolist()),
        })
    return analyses, False


def badge_sup(niveau):
    if niveau == "confiant": return '<span class="badge-vert">🟢 Confiant</span>'
    if niveau == "prudent":  return '<span class="badge-orange">🟡 Prudent</span>'
    if niveau == "danger":   return '<span class="badge-rouge">🔴 Danger</span>'
    return '<span class="badge-neutre">⚪ Neutre</span>'


# ─────────────────────────────────────────────
# SIDEBAR — bouton forcer recalcul RETIRÉ
# ─────────────────────────────────────────────

if "model_version" not in st.session_state:
    st.session_state.model_version = 0
if AUTOREFRESH_DISPO:
    st_autorefresh(interval=2 * 60 * 60 * 1000, key="ar_victor")

with st.sidebar:
    st.markdown(f"### 👋 {nom_abonne}")
    plan_emoji = {"essentiel":"🥉","pro":"🥇","vip":"💎"}.get(plan.lower(),"🎫")
    st.caption(f"{plan_emoji} Plan **{plan.upper()}** · {jours_restants}j restants")

    st.markdown("---")
    bankroll      = st.number_input("Montant (FCFA/€) :", min_value=100,
                                     max_value=10000000, value=10000, step=500)
    methode_kelly = st.selectbox("Méthode Kelly :",
                                  ["quarter (conservateur)","half (modéré)","full (agressif)"],
                                  index=0)
    methode_k     = methode_kelly.split(" ")[0]

    st.markdown("---")
    mode_affichage = st.radio("Catalogue :", ["Tout le programme","Sélection Afrique"])
    if mode_affichage == "Sélection Afrique":
        codes_saisis = st.text_input("Codes :", "R1C5, R1C6, R1C7")
        codes_actifs = [c.strip().upper() for c in codes_saisis.split(",") if c.strip()]

    st.markdown("---")
    choix_jour = st.radio("Journée :", ["Hier","Aujourd'hui","Demain"],
                           index=1, horizontal=True)
    d0 = date.today()
    if choix_jour   == "Hier":   date_cible = d0 - datetime.timedelta(days=1)
    elif choix_jour == "Demain": date_cible = d0 + datetime.timedelta(days=1)
    else:                         date_cible = d0

    st.markdown("---")
    if not ACCES_LIBRE:
        if st.button("🚪 Déconnexion"):
            deconnecter(st.session_state.get("telephone",""))
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.query_params.clear()
            st.rerun()

# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

modeles, features_global, auc = charger_modeles(st.session_state.model_version)
stats_cheval, stats_jockey, stats_hippo = charger_stats(st.session_state.model_version)

if modeles is None:
    st.error("❌ Modèle introuvable.")
    st.stop()

col_titre, _ = st.columns([4, 1])
with col_titre:
    st.title("🏇 Victor V2")

st.markdown("---")

with st.spinner("Chargement des courses..."):
    courses            = get_programme(date_cible)
    dict_fresh_courses = {c["code_pmu"]: c for c in courses}

if mode_affichage == "Sélection Afrique":
    courses = [c for c in courses if c["code_pmu"] in codes_actifs]

if not courses:
    st.warning("⚠️ Aucune course disponible pour cette date.")
    st.stop()

# ─────────────────────────────────────────────
# GEL INTELLIGENT
# ─────────────────────────────────────────────

heure_actuelle = datetime.datetime.now(timezone.utc).hour

if date_cible < d0:
    periode_cache = "fige_definitif"
elif date_cible == d0:
    if heure_actuelle < 9:
        periode_cache = f"maturation_{heure_actuelle}h"
        st.warning("🕒 **PHASE DE MATURATION DES COTES**\n\nEntre minuit et 09h00, les cotes PMU ne sont pas stables. **Pour une précision maximale, attendez 09h00.**")
    else:
        periode_cache = "fige_definitif"
        st.success("🔒 **PRONOSTICS DÉFINITIFS** — Verrouillés à 09h00. Seuls les non-partants modifient le classement.")
else:
    periode_cache = f"demain_maturation_{heure_actuelle}h"
    st.info("📅 **COURSES DE DEMAIN** — Pronostics définitifs disponibles demain à 09h00.")

analyses, _  = calculer_analyses(courses, modeles, stats_cheval, stats_jockey,
                                   stats_hippo, date_cible, periode_cache)
resultats_db = get_resultats_jour(date_cible.strftime("%Y-%m-%d"))

if not analyses:
    st.info("Aucune course ne répond aux critères d'analyse.")
    st.stop()

# ─────────────────────────────────────────────
# ONGLETS
# ─────────────────────────────────────────────

onglet_pronos, onglet_historique = st.tabs(["🎯 Pronostics", "📅 Historique"])

with onglet_pronos:

    reunions_dict = {}
    for snap in analyses:
        key_reunion = f"R{snap['course']['num_r']} - {snap['course']['hippodrome']}"
        if key_reunion not in reunions_dict:
            reunions_dict[key_reunion] = []
        reunions_dict[key_reunion].append(snap)

    reunions_triees = sorted(list(reunions_dict.keys()))
    tabs_reunions   = st.tabs(reunions_triees)

    for idx, nom_reunion in enumerate(reunions_triees):
        with tabs_reunions[idx]:
            courses_de_reunion = sorted(reunions_dict[nom_reunion],
                                        key=lambda x: x['course']['heure'])

            for snap in courses_de_reunion:
                code_pmu     = snap['course']['code_pmu']
                fresh_course = dict_fresh_courses.get(code_pmu, snap["course"])
                c_info       = fresh_course
                df_t         = snap["df_tri"]
                sup          = snap["sup_avis"]
                mult         = sup.get("multiplicateur_kelly", 1.0)
                titre_carte  = f"🏁 C{c_info['num_c']} - {c_info['heure']} - {c_info['libelle']}"

                with st.expander(titre_carte, expanded=False):

                    # Détection non-partants (3 méthodes)
                    np_pmu  = fresh_course.get('course_raw', {}).get('chevauxNonPartants', [])
                    np_flag = [
                        p.get('numPmu', p.get('num'))
                        for p in fresh_course.get('participants', [])
                        if p.get('estNonPartant') is True
                    ]
                    nums_frais = set(
                        int(p.get('numPmu', p.get('num', 0)))
                        for p in fresh_course.get('participants', [])
                        if p.get('numPmu', p.get('num', 0))
                    )
                    nums_figes   = snap.get("nums_figes", set())
                    np_disparus  = list(nums_figes - nums_frais) if nums_frais else []
                    non_partants = list(set(
                        [int(x) for x in np_pmu if x] +
                        [int(x) for x in np_flag if x] +
                        np_disparus
                    ))

                    if non_partants:
                        np_str = ", ".join([f"N°{n}" for n in sorted(non_partants)])
                        st.error(f"⚠️ NON-PARTANT(S) : {np_str} — retirés du classement")

                    st.markdown(f"""<div class="course-header-mobile">
<div class="ch-title">🏆 {c_info['libelle']}</div>
<div class="ch-subtitle">{c_info['hippodrome']} - {code_pmu} - {snap['disc_str']}</div>
<div class="ch-stats">{c_info['nb_partants']} partants · {c_info['course_raw'].get('distance',0)}m</div>
<div class="ch-time">Départ à {c_info['heure']}</div>
<div style="margin-top:10px;">{badge_sup(sup["niveau"])}</div>
</div>""", unsafe_allow_html=True)

                    if not snap["cotes_ont_valeur"]:
                        st.warning("ℹ️ Cotes non disponibles lors du calcul initial.")

                    np_ints     = [int(x) for x in non_partants]
                    df_t_actifs = df_t[~df_t['num'].astype(int).isin(np_ints)]

                    html_list = "<div class='horse-list'>"
                    for i, row in df_t_actifs.head(8).reset_index(drop=True).iterrows():
                        confiance = row['confiance']
                        cote_val  = row['cote']
                        mise_k    = calculer_mise(bankroll, confiance/100,
                                                   cote_val, methode_k)['montant_mise'] * mult
                        is_locked = (confiance > 65.0) and (plan.lower() not in ['pro','vip'])
                        if is_locked:
                            rank_class = "rank-lock"
                            cheval_nom = "🔒 ANALYSE RÉSERVÉE"
                            cote_txt   = "Passe au plan PRO"
                            conf_txt   = "<span class='h-pct-lock'>PRO</span>"
                            mise_txt   = "🔒"
                        else:
                            rank_class = "rank-0" if i == 0 else ("rank-1" if i in [1,2] else "rank-other")
                            cheval_nom = row['cheval']
                            cote_txt   = f"Cote matin: {cote_val}"
                            conf_txt   = f"<span class='h-pct'>{confiance:.1f}%</span>"
                            mise_txt   = f"Mise {mise_k:,.0f}"
                        html_list += f"""<div class='horse-row'>
<div class='h-num {rank_class}'>{int(row['num'])}</div>
<div class='h-info'><div class='h-name'>{cheval_nom}</div>
<div class='h-cote'>{cote_txt}</div></div>
<div class='h-stats'><div>{conf_txt}</div>
<div class='h-kelly'>{mise_txt}</div></div></div>"""
                        if i == 4 and len(df_t_actifs) > 5:
                            html_list += """<div style="text-align:center;font-size:12px;
color:#1D9E75;margin:8px 0;font-weight:bold;letter-spacing:1px;">--- CHEVAUX SUIVANTS ---</div>"""
                    html_list += "</div>"
                    st.markdown(html_list, unsafe_allow_html=True)

                    st.markdown("""<div class="cta-box">
<a href="https://chat.whatsapp.com/C94vxJ9VGudDX6UNAva0M1?s=cl&p=a&mlu=4" target="_blank">
📲 Rejoindre le groupe VIP (+221 76 264 17 51)</a></div>""", unsafe_allow_html=True)

                    if (code_pmu in resultats_db and
                            resultats_db[code_pmu] and
                            resultats_db[code_pmu] != 'None'):
                        st.markdown(f"""<div class="result-box">
<div class="result-title">🏁 Arrivée Officielle</div>
<div class="result-val">{resultats_db[code_pmu]}</div>
</div>""", unsafe_allow_html=True)

with onglet_historique:
    st.subheader("📅 Historique des courses")
    chemin = os.path.join(DOSSIER_DATA, "raw_courses.csv")
    if os.path.exists(chemin):
        df_h = pd.read_csv(chemin, encoding="utf-8-sig")
        df_h["date"] = pd.to_datetime(df_h["date"])
        d_debut = st.date_input("Du :", value=date.today()-datetime.timedelta(days=7))
        d_fin   = st.date_input("Au :", value=date.today())
        mask    = ((df_h["date"].dt.date >= d_debut) & (df_h["date"].dt.date <= d_fin))
        df_f    = df_h[mask]
        if not df_f.empty:
            hippos_h = ["Tous"] + sorted(df_f["hippodrome"].unique().tolist())
            fh       = st.selectbox("Hippodrome :", hippos_h, key="hist_h")
            if fh != "Tous":
                df_f = df_f[df_f["hippodrome"] == fh]
            cols    = ["date","hippodrome","num_course","num_cheval","cote","place"]
            cols_ok = [c for c in cols if c in df_f.columns]
            st.dataframe(df_f[cols_ok].sort_values(["date","num_course"]).head(200),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée sur cette période.")
    else:
        st.info("Pas encore de données historiques.")
