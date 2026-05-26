"""
VICTOR V2 — Interface Web v16.0 — VERSION DÉFINITIVE
=====================================================
Architecture single-page : login + interface dans un seul fichier.
Plus aucun switch_page croisé → impossible d'avoir une boucle.

Logique d'authentification :
1. session_state.connecte → afficher interface
2. Cookie présent → restaurer session puis afficher interface
3. URL t/p présent (compat) → restaurer + écrire cookie
4. Rien → afficher formulaire login DANS CETTE PAGE
"""

import streamlit as st
import requests
import pandas as pd
import numpy as np
import joblib
import json
import os
import time
import hashlib
import secrets
import datetime
from datetime import date, timedelta, timezone

from utils import construire_features, charger_stats_historiques
from kelly import calculer_mise
from auth.supabase_client import (
    verifier_connexion, deconnecter, get_client
)
from streamlit_cookies_controller import CookieController

try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_DISPO = True
except ImportError:
    AUTOREFRESH_DISPO = False

# ═════════════════════════════════════════════════════
# CONFIG GLOBAL
# ═════════════════════════════════════════════════════

st.set_page_config(
    page_title="Victor V2 - Pronostics PMU",
    page_icon="🏇",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_URL       = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme"
HEADERS        = {"User-Agent": "Mozilla/5.0"}
DOSSIER_MODELS = "models"
DOSSIER_DATA   = "data"
ACCES_LIBRE    = False
COOKIE_NAME    = "victor_session"

cookies = CookieController()

# ═════════════════════════════════════════════════════
# CSS GLOBAL
# ═════════════════════════════════════════════════════

st.markdown("""<style>
.login-card { max-width:480px; margin:40px auto; padding:32px; background:#1a1c23;
              border-radius:16px; border:1px solid #2d3139; }
.login-title { font-size:2.5rem; font-weight:900; color:#1D9E75; text-align:center; }
.login-sub   { font-size:1rem; color:#a0a5b1; text-align:center; margin-bottom:1.5rem; }

.course-header-mobile { background-color:#1a1c23; border-radius:12px; padding:16px;
                        margin-bottom:16px; text-align:center; border:1px solid #2d3139; }
.ch-title { font-size:16px; font-weight:800; color:#fff; text-transform:uppercase; margin-bottom:4px; }
.ch-sub   { font-size:13px; color:#a0a5b1; font-weight:600; }
.ch-stats { font-size:12px; color:#6b7280; margin-top:4px; }
.ch-time  { font-size:15px; font-weight:700; color:#1D9E75; margin-top:8px; }
.ch-conseil{ font-size:12px; color:#a0a5b1; margin-top:6px; }

.horse-list{ display:flex; flex-direction:column; gap:8px; margin-top:10px; }
.horse-row { display:flex; align-items:center; background-color:#21252d;
             border-radius:8px; padding:10px 12px; }
.h-num     { width:44px; height:44px; display:flex; align-items:center; justify-content:center;
             font-size:22px; font-weight:900; border-radius:6px; margin-right:14px; color:white; flex-shrink:0; }
.rank-0 { background-color:#1D9E75; }
.rank-1, .rank-2 { background-color:#EF9F27; }
.rank-other { background-color:#4a4d55; }
.rank-lock  { background-color:#2d3139; }
.h-info { flex:1; }
.h-name { font-size:14px; font-weight:700; color:#fff; }
.h-cote { font-size:12px; color:#a0a5b1; margin-top:2px; }
.h-stats{ text-align:right; }
.h-pct  { font-size:15px; font-weight:800; color:#1D9E75; }
.h-pct-lock { font-size:13px; font-weight:700; color:#6b7280; }
.h-kelly{ font-size:11px; color:#a0a5b1; margin-top:2px; }

.result-box { background:#1D9E7511; border:1px solid #1D9E7544; border-radius:10px; padding:12px; margin-top:10px; }
.result-title { font-size:12px; color:#1D9E75; font-weight:700; margin-bottom:4px; }
.result-val { font-size:16px; font-weight:800; color:#fff; }
.cta-box   { background:#1a1c23; border:1px solid #2d3139; border-radius:10px; padding:12px; margin-top:12px; text-align:center; }
.cta-box a { color:#1D9E75; text-decoration:none; font-weight:700; font-size:13px; }

.badge-or    { background:#EF9F27; color:#1a1100; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:900; }
.badge-signal{ background:#3B82F6; color:#fff; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:800; }
.badge-faible{ background:#374151; color:#9CA3AF; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:700; }

.banniere-or    { background:#EF9F27; border-radius:16px; padding:20px; margin-bottom:16px; }
.banniere-titre { font-size:22px !important; font-weight:900 !important; color:#1a1100 !important; }
.banniere-sub   { font-size:14px !important; font-weight:600 !important; color:#3d2000 !important; margin-top:4px; }

.cs-card  { background:#7a4f00; border:2px solid #EF9F27; border-radius:12px; padding:14px; height:100%; }
.cs-code  { font-size:11px !important; font-weight:800 !important; color:#FCD34D !important; }
.cs-cheval{ font-size:18px !important; font-weight:900 !important; color:#fff !important; margin:6px 0; }
.cs-stats { font-size:13px !important; font-weight:700 !important; color:#FCD34D !important; }
.cs-hippo { font-size:11px !important; color:#d4b483 !important; margin-top:4px; }

.banniere-locked{ background:#1D9E7522; border:2px solid #1D9E75; border-radius:16px; padding:20px; margin-bottom:16px; text-align:center; }
.locked-titre { font-size:20px; font-weight:900; color:#1D9E75; }
.locked-sub   { font-size:13px; color:#a0a5b1; margin-top:6px; }
.locked-cta   { font-size:14px; color:#EF9F27; font-weight:800; margin-top:10px; }
</style>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════
# ROUTING ADMIN
# ═════════════════════════════════════════════════════

if st.query_params.get("page") == "admin":
    from pages.admin import afficher_admin
    afficher_admin()
    st.stop()

# ═════════════════════════════════════════════════════
# CONSTANTES PAYS
# ═════════════════════════════════════════════════════

AFRICA_CODES = {
    "Mali (+223)": "+223", "Sénégal (+221)": "+221", "Côte d'Ivoire (+225)": "+225",
    "Burkina Faso (+226)": "+226", "Niger (+227)": "+227", "Togo (+228)": "+228",
    "Bénin (+229)": "+229", "Guinée (+224)": "+224", "Mauritanie (+222)": "+222",
    "Gambie (+220)": "+220", "Guinée-Bissau (+245)": "+245", "Cap-Vert (+238)": "+238",
    "Sierra Leone (+232)": "+232", "Libéria (+231)": "+231", "Ghana (+233)": "+233",
    "Nigeria (+234)": "+234", "Cameroun (+237)": "+237", "Tchad (+235)": "+235",
    "République Centrafricaine (+236)": "+236", "Gabon (+241)": "+241",
    "Congo (+242)": "+242", "RDC (+243)": "+243", "Angola (+244)": "+244",
    "Guinée Équatoriale (+240)": "+240", "Sao Tomé-et-Principe (+239)": "+239",
    "Rwanda (+250)": "+250", "Burundi (+257)": "+257", "Tanzanie (+255)": "+255",
    "Kenya (+254)": "+254", "Ouganda (+256)": "+256", "Djibouti (+253)": "+253",
    "Somalie (+252)": "+252", "Éthiopie (+251)": "+251", "Érythrée (+291)": "+291",
    "Soudan (+249)": "+249", "Soudan du Sud (+211)": "+211", "Égypte (+20)": "+20",
    "Libye (+218)": "+218", "Tunisie (+216)": "+216", "Algérie (+213)": "+213",
    "Maroc (+212)": "+212", "Madagascar (+261)": "+261", "Maurice (+230)": "+230",
    "Comores (+269)": "+269", "Seychelles (+248)": "+248", "Réunion (+262)": "+262",
    "Mozambique (+258)": "+258", "Malawi (+265)": "+265", "Zambie (+260)": "+260",
    "Zimbabwe (+263)": "+263", "Namibie (+264)": "+264", "Botswana (+267)": "+267",
    "Eswatini (+268)": "+268", "Lesotho (+266)": "+266", "Afrique du Sud (+27)": "+27",
    "Autre (saisir l'indicatif)": "autre",
}

# ═════════════════════════════════════════════════════
# RESTAURATION DE SESSION
# ═════════════════════════════════════════════════════

def restaurer_depuis(telephone, token):
    """Vérifie le couple (téléphone, token) dans Supabase et restaure la session."""
    try:
        client = get_client()
        if not client:
            return False
        res = client.table("abonnes").select(
            "nom, plan, date_expiration, actif, session_token"
        ).eq("telephone", telephone).execute()
        if not res.data:
            return False
        ab = res.data[0]
        if not ab.get("actif", True):
            return False
        if ab.get("session_token", "") != token:
            return False
        exp = date.fromisoformat(ab["date_expiration"])
        st.session_state["connecte"]       = True
        st.session_state["telephone"]      = telephone
        st.session_state["session_token"]  = token
        st.session_state["nom"]            = ab.get("nom", "Abonné")
        st.session_state["plan"]           = ab.get("plan", "pro")
        st.session_state["jours_restants"] = max(0, (exp - date.today()).days)
        return True
    except Exception:
        # Supabase injoignable → restauration tolérante (priorité à l'UX)
        st.session_state["connecte"]       = True
        st.session_state["telephone"]      = telephone
        st.session_state["session_token"]  = token
        st.session_state["nom"]            = "Abonné"
        st.session_state["plan"]           = "pro"
        st.session_state["jours_restants"] = 999
        return True


def tenter_restauration():
    """Tente de restaurer la session via cookie puis via URL."""
    if st.session_state.get("connecte"):
        return True

    # 1. Cookie
    try:
        cookie_val = cookies.get(COOKIE_NAME)
        if cookie_val and ":" in cookie_val:
            tel, tok = cookie_val.split(":", 1)
            if restaurer_depuis(tel, tok):
                return True
    except Exception:
        pass

    # 2. URL (ancien format favoris)
    url_tok = st.query_params.get("t", "")
    url_tel = st.query_params.get("p", "")
    if url_tok and url_tel:
        if restaurer_depuis(url_tel, url_tok):
            try:
                cookies.set(COOKIE_NAME, f"{url_tel}:{url_tok}", max_age=60*60*24*30)
            except Exception:
                pass
            st.query_params.clear()
            return True

    return False


# ═════════════════════════════════════════════════════
# FORMULAIRE LOGIN — INTÉGRÉ DANS CETTE PAGE
# ═════════════════════════════════════════════════════

def afficher_login_inline():
    """Affiche le formulaire de connexion directement dans 5_interface_web.py."""

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligence Artificielle PMU</div>', unsafe_allow_html=True)

        # Numéro
        c1, c2 = st.columns([1, 2])
        with c1:
            selection = st.selectbox("🌍 Pays", list(AFRICA_CODES.keys()),
                                      index=0, key="li_pays")
        with c2:
            if AFRICA_CODES[selection] == "autre":
                prefix = st.text_input("Indicatif", placeholder="+xxx", key="li_pfx")
                num    = st.text_input("Numéro", placeholder="06 00 00 00 00", key="li_num")
            else:
                prefix = AFRICA_CODES[selection]
                st.text_input("Indicatif", value=prefix, disabled=True, key="li_pfx_auto")
                num = st.text_input("Numéro", placeholder="77 000 00 00", key="li_num_auto")

        clean = f"{prefix.replace('+','').replace(' ','')}{num.replace(' ','')}"
        telephone = f"+{clean}"

        mot_de_passe = st.text_input("🔒 Code secret", type="password", key="li_mdp")

        if st.button("🚀 Se connecter", use_container_width=True, type="primary"):
            if len(telephone) < 8 or not mot_de_passe:
                st.error("⚠️ Remplissez tous les champs.")
            else:
                with st.spinner("Vérification..."):
                    result = verifier_connexion(telephone, mot_de_passe)
                if result["succes"]:
                    ab = result["abonne"]
                    st.session_state["connecte"]       = True
                    st.session_state["telephone"]      = ab["telephone"]
                    st.session_state["nom"]            = ab.get("nom", "Abonné")
                    st.session_state["plan"]           = ab.get("plan", "pro")
                    st.session_state["session_token"]  = ab["session_token"]
                    st.session_state["jours_restants"] = ab["jours_restants"]
                    try:
                        cookies.set(
                            COOKIE_NAME,
                            f"{ab['telephone']}:{ab['session_token']}",
                            max_age=60*60*24*30
                        )
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

        if st.button("📝 Créer un compte gratuit", use_container_width=True):
            st.session_state["__mode__"] = "inscription"
            st.rerun()

        wa_msg = "Bonjour, j'ai perdu mon mot de passe Victor V2. Mon numéro est : " + telephone
        wa_url = f"https://wa.me/221762641751?text={wa_msg.replace(' ', '%20')}"
        st.link_button("🔑 Mot de passe oublié ?", wa_url, use_container_width=True)


def afficher_inscription_inline():
    """Formulaire d'inscription inline."""

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Créer un compte gratuit (3 jours)</div>', unsafe_allow_html=True)

        nom = st.text_input("👤 Prénom et Nom", key="ii_nom")

        c1, c2 = st.columns([1, 2])
        with c1:
            selection = st.selectbox("🌍 Pays", list(AFRICA_CODES.keys()),
                                      index=0, key="ii_pays")
        with c2:
            if AFRICA_CODES[selection] == "autre":
                prefix = st.text_input("Indicatif", placeholder="+xxx", key="ii_pfx")
                num    = st.text_input("Numéro", placeholder="06 00 00 00 00", key="ii_num")
            else:
                prefix = AFRICA_CODES[selection]
                st.text_input("Indicatif", value=prefix, disabled=True, key="ii_pfx_auto")
                num = st.text_input("Numéro", placeholder="77 000 00 00", key="ii_num_auto")

        clean = f"{prefix.replace('+','').replace(' ','')}{num.replace(' ','')}"
        telephone = f"+{clean}"

        pwd  = st.text_input("🔒 Mot de passe", type="password", key="ii_pwd")
        pwd2 = st.text_input("🔒 Confirmer mot de passe", type="password", key="ii_pwd2")

        if st.button("✅ Créer mon compte", use_container_width=True, type="primary"):
            if not nom.strip():
                st.error("⚠️ Entrez votre nom.")
            elif len(telephone) < 8:
                st.error("⚠️ Numéro incomplet.")
            elif len(pwd) < 4:
                st.error("⚠️ Mot de passe trop court (4 caractères min).")
            elif pwd != pwd2:
                st.error("⚠️ Les mots de passe ne correspondent pas.")
            else:
                client = get_client()
                if not client:
                    st.error("❌ Erreur de connexion serveur.")
                else:
                    try:
                        res = client.table("abonnes").select("telephone")\
                                    .eq("telephone", telephone).execute()
                        if res.data:
                            st.error("❌ Numéro déjà utilisé. Connectez-vous.")
                        else:
                            tok      = secrets.token_hex(32)
                            date_exp = (date.today() + timedelta(days=3)).isoformat()
                            mdp_hash = hashlib.sha256(pwd.encode()).hexdigest()
                            client.table("abonnes").insert({
                                "telephone"      : telephone,
                                "mot_de_passe"   : mdp_hash,
                                "nom"            : nom.strip(),
                                "plan"           : "essentiel",
                                "date_expiration": date_exp,
                                "actif"          : True,
                                "session_token"  : tok,
                            }).execute()
                            st.session_state["connecte"]       = True
                            st.session_state["telephone"]      = telephone
                            st.session_state["nom"]            = nom.strip()
                            st.session_state["plan"]           = "essentiel"
                            st.session_state["jours_restants"] = 3
                            st.session_state["session_token"]  = tok
                            try:
                                cookies.set(COOKIE_NAME, f"{telephone}:{tok}",
                                             max_age=60*60*24*30)
                            except Exception:
                                pass
                            st.success(f"✅ Bienvenue {nom.strip()} !")
                            time.sleep(1)
                            st.session_state.pop("__mode__", None)
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")

        if st.button("🔑 J'ai déjà un compte", use_container_width=True):
            st.session_state["__mode__"] = "login"
            st.rerun()


# ═════════════════════════════════════════════════════
# GATE D'AUTHENTIFICATION
# ═════════════════════════════════════════════════════

if not ACCES_LIBRE:
    if not tenter_restauration():
        mode = st.session_state.get("__mode__", "login")
        if mode == "inscription":
            afficher_inscription_inline()
        else:
            afficher_login_inline()
        st.stop()
else:
    st.session_state["connecte"]       = True
    st.session_state["nom"]            = "Visiteur"
    st.session_state["plan"]           = "pro"
    st.session_state["jours_restants"] = 999

nom_abonne     = st.session_state.get("nom", "Visiteur")
jours_restants = st.session_state.get("jours_restants", 999)
plan           = st.session_state.get("plan", "pro")
est_pro        = plan.lower() in ["pro", "vip"]

# ═════════════════════════════════════════════════════
# CHARGEMENT MODÈLES
# ═════════════════════════════════════════════════════

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
                modeles[nom] = {
                    "model"   : joblib.load(chemin),
                    "features": info["features"],
                    "auc"     : info["auc"],
                }
    else:
        chemin = os.path.join(DOSSIER_MODELS, "victor_v2.pkl")
        if os.path.exists(chemin):
            modeles["GLOBAL"] = {
                "model"   : joblib.load(chemin),
                "features": meta["features"],
                "auc"     : meta.get("auc", 0.0),
            }
    return modeles, meta.get("features_global", meta.get("features", [])), meta.get("auc", 0.0)


@st.cache_data(ttl=3600)
def charger_stats(version=0):
    chemin = os.path.join(DOSSIER_DATA, "raw_courses.csv")
    if not os.path.exists(chemin):
        chemin = os.path.join(DOSSIER_DATA, "dataset_final.csv")
    return charger_stats_historiques(chemin)


def choisir_modele(modeles, disc_code):
    DISC_NOMS = {0:"ATTELE",1:"CROSS",2:"HAIE",3:"MONTE",4:"PLAT",5:"STEEPLECHASE"}
    nom_disc  = DISC_NOMS.get(disc_code, "PLAT")
    for cle in [f"{nom_disc}_quinte", "GLOBAL_quinte", "GLOBAL"]:
        if cle in modeles:
            return modeles[cle]["model"], modeles[cle]["features"], cle
    return None, [], "AUCUN"

# ═════════════════════════════════════════════════════
# PMU API
# ═════════════════════════════════════════════════════

@st.cache_data(ttl=300)
def get_programme(d: date):
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
                num_c       = course.get("numOrdre")
                nb_partants = course.get("nombreDeclaresPartants", 0)
                if nb_partants < 4:
                    continue
                vh    = course.get("heureDepart", "")
                heure = (datetime.datetime.fromtimestamp(vh/1000).strftime("%H:%M")
                         if isinstance(vh, int) else str(vh)[:5])
                url_p = f"{BASE_URL}/{date_str}/R{num_r}/C{num_c}/participants"
                try:
                    rp = requests.get(url_p, headers=HEADERS, timeout=5)
                    participants = rp.json().get("participants",[]) if rp.status_code==200 else []
                except Exception:
                    participants = []
                if len(participants) >= 4:
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


@st.cache_data(ttl=3600)
def get_resultats_jour(date_str):
    try:
        client = get_client()
        if not client:
            return {}
        res = client.table("historique_courses").select(
            "code_course, resultat_reel"
        ).eq("date", date_str).execute()
        return {r["code_course"]: r["resultat_reel"] for r in res.data} if res.data else {}
    except Exception:
        return {}

# ═════════════════════════════════════════════════════
# FIABILITÉ
# ═════════════════════════════════════════════════════

def calculer_fiabilite(df_tri):
    if df_tri.empty:
        return "faible"
    cote  = float(df_tri.iloc[0]["cote"])
    proba = float(df_tri.iloc[0]["confiance"]) / 100.0
    val   = proba * cote
    if 4.0 <= cote <= 12.0 and val > 1.10:
        return "coup_sur"
    elif 3.0 <= cote <= 15.0 and val > 1.0:
        return "signal"
    return "faible"


def badge_fiabilite(niveau):
    if niveau == "coup_sur":
        return '<span class="badge-or">🏆 COUP SÛR</span>'
    elif niveau == "signal":
        return '<span class="badge-signal">📡 SIGNAL</span>'
    return '<span class="badge-faible">⚠️ FAIBLE</span>'


def conseil_fiabilite(niveau):
    if niveau == "coup_sur":
        return "🏆 Victor identifie une valeur claire — mise recommandée"
    elif niveau == "signal":
        return "📡 Signal intéressant — miser prudemment"
    return "⚠️ Cours difficile à cerner — éviter ou miser au minimum"

# ═════════════════════════════════════════════════════
# ANALYSES
# ═════════════════════════════════════════════════════

@st.cache_data(ttl=86400)
def calculer_analyses(_courses, _modeles, _stats_cheval, _stats_jockey,
                       _stats_hippo, date_cible, periode_cache):
    analyses = []
    disc_map = {"PLAT":4,"ATTELE":0,"MONTE":3,"HAIE":2,
                "STEEPLECHASE":5,"CROSS":1,"TROT_ATTELE":0,"TROT_MONTE":3,"OBSTACLE":2}
    for c in _courses:
        disc_str = c["course_raw"].get("discipline", "PLAT")
        disc_num = disc_map.get(disc_str, 4)
        model, feats, nom_mod = choisir_modele(_modeles, disc_num)
        if model is None:
            continue
        try:
            df = construire_features(c["participants"], c["course_raw"], c["hippodrome"],
                                      _stats_cheval, _stats_jockey, _stats_hippo)
            for col in feats:
                if col not in df.columns:
                    df[col] = 0.0
            feats_ok = [f for f in feats if f in df.columns]
            if not feats_ok:
                continue
            probas = model.predict_proba(df[feats_ok])[:, 1] * 100
        except Exception:
            continue
        if df["cote"].min() < 1.5:
            continue
        df_tri = pd.DataFrame({
            "num"      : df["num"].tolist(),
            "cheval"   : df["nom_cheval"].tolist(),
            "cote"     : df["cote"].tolist(),
            "confiance": probas.tolist(),
        }).sort_values("confiance", ascending=False).reset_index(drop=True)
        if df_tri.empty:
            continue
        fiabilite = calculer_fiabilite(df_tri)
        analyses.append({
            "course"          : c,
            "df_tri"          : df_tri,
            "nom_mod"         : nom_mod,
            "disc_str"        : disc_str,
            "conf_top"        : float(df_tri.iloc[0]["confiance"]),
            "cote_top"        : float(df_tri.iloc[0]["cote"]),
            "fiabilite"       : fiabilite,
            "cotes_ont_valeur": any(ct != 20.0 for ct in df_tri["cote"].tolist()[:5]),
            "nums_figes"      : set(int(n) for n in df_tri["num"].tolist()),
        })
    return analyses, False

# ═════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════

if "model_version" not in st.session_state:
    st.session_state.model_version = 0
if AUTOREFRESH_DISPO:
    st_autorefresh(interval=2*60*60*1000, key="ar_victor")

with st.sidebar:
    st.markdown(f"### 👋 {nom_abonne}")
    plan_emoji = {"essentiel":"🥉","pro":"🥇","vip":"💎"}.get(plan.lower(),"🎫")
    st.caption(f"{plan_emoji} Plan **{plan.upper()}** · {jours_restants}j restants")
    st.markdown("---")

    bankroll = st.number_input("Montant (FCFA/€) :", min_value=100,
                                max_value=10000000, value=10000, step=500)
    methode_kelly = st.selectbox("Méthode Kelly :",
                                  ["quarter (conservateur)","half (modéré)","full (agressif)"],
                                  index=0)
    methode_k = methode_kelly.split(" ")[0]
    st.markdown("---")

    mode_affichage = st.radio("Catalogue :", ["Tout le programme","Sélection Afrique"])
    codes_actifs   = []
    if mode_affichage == "Sélection Afrique":
        codes_saisis = st.text_input("Codes :", "R1C5, R1C6, R1C7")
        codes_actifs = [c.strip().upper() for c in codes_saisis.split(",") if c.strip()]
    st.markdown("---")

    choix_jour = st.radio("Journée :", ["Hier","Aujourd'hui","Demain"], index=1, horizontal=True)
    d0 = date.today()
    date_cible = (d0 - datetime.timedelta(days=1) if choix_jour == "Hier"
                  else d0 + datetime.timedelta(days=1) if choix_jour == "Demain"
                  else d0)
    st.markdown("---")

    if not ACCES_LIBRE:
        if st.button("🚪 Déconnexion"):
            try:
                deconnecter(st.session_state.get("telephone", ""))
            except Exception:
                pass
            try:
                cookies.remove(COOKIE_NAME)
            except Exception:
                pass
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

# ═════════════════════════════════════════════════════
# CHARGEMENT DONNÉES
# ═════════════════════════════════════════════════════

modeles, features_global, auc = charger_modeles(st.session_state.model_version)

try:
    stats_cheval, stats_jockey, stats_hippo = charger_stats(st.session_state.model_version)
except Exception as e:
    st.warning(f"⚠️ Stats historiques indisponibles — mode dégradé. ({e})")
    stats_cheval, stats_jockey, stats_hippo = {}, {}, {}

if modeles is None:
    st.error("❌ Modèle introuvable.")
    st.stop()

st.title("🏇 Victor V2")
st.markdown("---")

with st.spinner("Chargement des courses..."):
    courses            = get_programme(date_cible)
    dict_fresh_courses = {c["code_pmu"]: c for c in courses}

if mode_affichage == "Sélection Afrique" and codes_actifs:
    courses = [c for c in courses if c["code_pmu"] in codes_actifs]

if not courses:
    st.warning("⚠️ Aucune course disponible pour cette date.")
    st.stop()

heure_utc = datetime.datetime.now(timezone.utc).hour
if date_cible < d0:
    periode_cache = "fige_definitif"
elif date_cible == d0:
    if heure_utc < 9:
        periode_cache = f"maturation_{heure_utc}h"
        st.warning("🕒 Pronostics en maturation — définitifs à 09h00.")
    else:
        periode_cache = "fige_definitif"
        st.success("🔒 Pronostics définitifs verrouillés à 09h00.")
else:
    periode_cache = f"demain_{heure_utc}h"
    st.info("📅 Courses de demain — pronostics définitifs demain à 09h00.")

analyses, _ = calculer_analyses(courses, modeles, stats_cheval, stats_jockey,
                                  stats_hippo, date_cible, periode_cache)
resultats_db = get_resultats_jour(date_cible.strftime("%Y-%m-%d"))

if not analyses:
    st.info("Aucune course analysable aujourd'hui.")
    st.stop()

# ═════════════════════════════════════════════════════
# BANNIÈRE COUPS SÛRS
# ═════════════════════════════════════════════════════

coups_surs = [a for a in analyses if a["fiabilite"] == "coup_sur"]

if coups_surs:
    if est_pro:
        cols_cs = st.columns([2, 1, 1, 1])
        with cols_cs[0]:
            st.markdown(f"""<div class="banniere-or">
<div class="banniere-titre">🏆 COUPS SÛRS DU JOUR</div>
<div class="banniere-sub">Victor a identifié {len(coups_surs)} course(s) à forte valeur</div>
</div>""", unsafe_allow_html=True)
        for i, snap in enumerate(coups_surs[:3]):
            with cols_cs[i+1]:
                top1 = snap["df_tri"].iloc[0]
                st.markdown(f"""<div class="cs-card">
<div class="cs-code">{snap['course']['code_pmu']} · {snap['course']['heure']}</div>
<div class="cs-cheval">N°{int(top1['num'])} {top1['cheval']}</div>
<div class="cs-stats">Cote {top1['cote']:.1f} · {top1['confiance']:.0f}%</div>
<div class="cs-hippo">{snap['course']['hippodrome']}</div>
</div>""", unsafe_allow_html=True)
        st.markdown("---")
    else:
        st.markdown(f"""<div class="banniere-locked">
<div class="locked-titre">🏆 {len(coups_surs)} COUP(S) SÛR(S) DISPONIBLE(S)</div>
<div class="locked-sub">Victor a repéré des courses à forte valeur. Réservé membres PRO et VIP.</div>
<div class="locked-cta">→ WhatsApp +221 76 264 17 51 pour passer PRO</div>
</div>""", unsafe_allow_html=True)
        st.markdown("---")

# ═════════════════════════════════════════════════════
# ONGLETS
# ═════════════════════════════════════════════════════

onglet_pronos, onglet_historique = st.tabs(["🎯 Pronostics", "📅 Historique"])

with onglet_pronos:
    reunions_dict = {}
    for snap in analyses:
        key = f"R{snap['course']['num_r']} - {snap['course']['hippodrome']}"
        reunions_dict.setdefault(key, []).append(snap)

    tabs_reunions = st.tabs(sorted(reunions_dict.keys()))

    for idx, nom_reunion in enumerate(sorted(reunions_dict.keys())):
        with tabs_reunions[idx]:
            for snap in sorted(reunions_dict[nom_reunion], key=lambda x: x['course']['heure']):
                code_pmu     = snap['course']['code_pmu']
                fresh_course = dict_fresh_courses.get(code_pmu, snap["course"])
                c_info       = fresh_course
                df_t         = snap["df_tri"]
                fiabilite    = snap["fiabilite"]
                titre_carte  = f"🏁 C{c_info['num_c']} - {c_info['heure']} - {c_info['libelle']}"

                with st.expander(titre_carte, expanded=(fiabilite == "coup_sur")):

                    np_flag = [
                        p.get('numPmu', p.get('num'))
                        for p in fresh_course.get('participants', [])
                        if p.get('estNonPartant') is True
                    ]
                    nums_frais  = set(
                        int(p.get('numPmu', p.get('num', 0)))
                        for p in fresh_course.get('participants', [])
                        if p.get('numPmu', p.get('num', 0))
                    )
                    np_disparus  = list(snap.get("nums_figes", set()) - nums_frais)
                    non_partants = list(set([int(x) for x in np_flag if x] + np_disparus))

                    if non_partants:
                        st.error(f"⚠️ NON-PARTANT(S) : {', '.join([f'N°{n}' for n in sorted(non_partants)])}")

                    st.markdown(f"""<div class="course-header-mobile">
<div class="ch-title">🏆 {c_info['libelle']}</div>
<div class="ch-sub">{c_info['hippodrome']} · {code_pmu} · {snap['disc_str']}</div>
<div class="ch-stats">{c_info['nb_partants']} partants · {c_info['course_raw'].get('distance',0)}m</div>
<div class="ch-time">Départ à {c_info['heure']}</div>
<div style="margin-top:10px;">{badge_fiabilite(fiabilite)}</div>
<div class="ch-conseil">{conseil_fiabilite(fiabilite)}</div>
</div>""", unsafe_allow_html=True)

                    if not snap["cotes_ont_valeur"]:
                        st.warning("ℹ️ Cotes non disponibles au moment du calcul.")

                    np_ints     = [int(x) for x in non_partants]
                    df_t_actifs = df_t[~df_t['num'].astype(int).isin(np_ints)]

                    html_list = "<div class='horse-list'>"
                    for i, row in df_t_actifs.head(8).reset_index(drop=True).iterrows():
                        conf    = row['confiance']
                        cote_v  = row['cote']
                        mise_k  = calculer_mise(bankroll, conf/100, cote_v, methode_k)['montant_mise']
                        locked  = (conf > 65.0) and (not est_pro)
                        if locked:
                            rc = "rank-lock"
                            nom_ch  = "🔒 RÉSERVÉ PRO"
                            cote_tx = "Plan PRO pour débloquer"
                            conf_tx = "<span class='h-pct-lock'>🔒</span>"
                            mise_tx = ""
                        else:
                            rc = "rank-0" if i==0 else ("rank-1" if i in [1,2] else "rank-other")
                            nom_ch  = row['cheval']
                            cote_tx = f"Cote : {cote_v:.1f}"
                            conf_tx = f"<span class='h-pct'>{conf:.1f}%</span>"
                            mise_tx = f"Mise {mise_k:,.0f}"
                        html_list += f"""<div class='horse-row'>
<div class='h-num {rc}'>{int(row['num'])}</div>
<div class='h-info'><div class='h-name'>{nom_ch}</div>
<div class='h-cote'>{cote_tx}</div></div>
<div class='h-stats'><div>{conf_tx}</div>
<div class='h-kelly'>{mise_tx}</div></div></div>"""
                        if i == 4 and len(df_t_actifs) > 5:
                            html_list += """<div style="text-align:center;font-size:12px;
color:#1D9E75;margin:8px 0;font-weight:bold;">── CHEVAUX SUIVANTS ──</div>"""
                    html_list += "</div>"
                    st.markdown(html_list, unsafe_allow_html=True)

                    st.markdown("""<div class="cta-box">
<a href="https://chat.whatsapp.com/C94vxJ9VGudDX6UNAva0M1" target="_blank">
📲 Rejoindre le groupe VIP WhatsApp</a></div>""", unsafe_allow_html=True)

                    if (code_pmu in resultats_db and
                            resultats_db[code_pmu] and
                            resultats_db[code_pmu] != 'None'):
                        st.markdown(f"""<div class="result-box">
<div class="result-title">🏁 Arrivée Officielle</div>
<div class="result-val">{resultats_db[code_pmu]}</div>
</div>""", unsafe_allow_html=True)

with onglet_historique:
    st.subheader("📅 Historique des courses")
    chemin_h = os.path.join(DOSSIER_DATA, "raw_courses.csv")
    if os.path.exists(chemin_h):
        df_h    = pd.read_csv(chemin_h, encoding="utf-8-sig")
        df_h["date"] = pd.to_datetime(df_h["date"])
        d_debut = st.date_input("Du :", value=date.today()-datetime.timedelta(days=7))
        d_fin   = st.date_input("Au :", value=date.today())
        df_f    = df_h[(df_h["date"].dt.date >= d_debut) & (df_h["date"].dt.date <= d_fin)]
        if not df_f.empty:
            hippos_h = ["Tous"] + sorted(df_f["hippodrome"].unique().tolist())
            fh = st.selectbox("Hippodrome :", hippos_h, key="hist_h")
            if fh != "Tous":
                df_f = df_f[df_f["hippodrome"] == fh]
            cols_ok = [c for c in ["date","hippodrome","num_course","num_cheval","cote","place"]
                       if c in df_f.columns]
            st.dataframe(df_f[cols_ok].sort_values(["date","num_course"]).head(200),
                         use_container_width=True, hide_index=True)
        else:
            st.info("Aucune donnée sur cette période.")
    else:
        st.info("Pas encore de données historiques.")
