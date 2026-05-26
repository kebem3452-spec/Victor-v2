"""
VICTOR V2 — pages/inscription.py v3
Inscription avec auto-connexion via COOKIE
"""

import streamlit as st
import hashlib
import secrets
import time
from datetime import date, timedelta
from auth.supabase_client import get_client
from streamlit_cookies_controller import CookieController

COOKIE_NAME = "victor_session"
cookies = CookieController()

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


def hasher_mdp(mdp: str) -> str:
    return hashlib.sha256(mdp.encode()).hexdigest()


def render_phone_input(prefix_key, num_key, pays_key):
    col1, col2 = st.columns([1, 2])
    with col1:
        selection = st.selectbox("🌍 Pays", list(AFRICA_CODES.keys()),
                                  index=0, key=pays_key)
    with col2:
        if AFRICA_CODES[selection] == "autre":
            prefix = st.text_input("Indicatif (ex: +33)", placeholder="+xxx",
                                    key=prefix_key)
            num    = st.text_input("Numéro", placeholder="06 00 00 00 00",
                                    key=num_key)
        else:
            prefix = AFRICA_CODES[selection]
            st.text_input("Indicatif (fixe)", value=prefix, disabled=True,
                           key=prefix_key + "_auto")
            num = st.text_input("Numéro (sans indicatif)",
                                 placeholder="77 000 00 00", key=num_key)
    clean = f"{prefix.replace('+','').replace(' ','')}{num.replace(' ','')}"
    return f"+{clean}"


def afficher_inscription():
    st.markdown("""<style>
    .ins-title { font-size:2rem; font-weight:700; color:#1D9E75; text-align:center; }
    .ins-sub   { font-size:1rem; color:#888; text-align:center; margin-bottom:1.5rem; }
    </style>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="ins-title">🏇 VICTOR V2</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="ins-sub">Créer votre compte gratuit</div>',
                    unsafe_allow_html=True)

        nom       = st.text_input("👤 Prénom et Nom", key="ins_nom")
        telephone = render_phone_input("ins_prefix", "ins_num", "ins_pays")
        password  = st.text_input("🔒 Créer un mot de passe",
                                   type="password", key="ins_pwd")
        password2 = st.text_input("🔒 Confirmer le mot de passe",
                                   type="password", key="ins_pwd2")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✅ Créer mon compte", use_container_width=True,
                      type="primary"):
            if not nom.strip():
                st.error("⚠️ Entrez votre prénom et nom.")
                st.stop()
            if len(telephone) < 8 or telephone == "+":
                st.error("⚠️ Numéro de téléphone incomplet.")
                st.stop()
            if len(password) < 4:
                st.error("⚠️ Mot de passe d'au moins 4 caractères.")
                st.stop()
            if password != password2:
                st.error("⚠️ Les mots de passe ne correspondent pas.")
                st.stop()

            client = get_client()
            if not client:
                st.error("❌ Erreur de connexion au serveur.")
                st.stop()

            try:
                res = client.table("abonnes").select("telephone")\
                            .eq("telephone", telephone).execute()
                if res.data:
                    st.error("❌ Ce numéro est déjà utilisé. Connectez-vous.")
                    st.stop()

                session_token = secrets.token_hex(32)
                date_exp      = (date.today() + timedelta(days=3)).isoformat()

                client.table("abonnes").insert({
                    "telephone"      : telephone,
                    "mot_de_passe"   : hasher_mdp(password),
                    "nom"            : nom.strip(),
                    "plan"           : "essentiel",
                    "date_expiration": date_exp,
                    "actif"          : True,
                    "session_token"  : session_token,
                }).execute()

                # Session + cookie
                st.session_state["connecte"]       = True
                st.session_state["telephone"]      = telephone
                st.session_state["nom"]            = nom.strip()
                st.session_state["plan"]           = "essentiel"
                st.session_state["jours_restants"] = 3
                st.session_state["session_token"]  = session_token

                cookies.set(
                    COOKIE_NAME,
                    f"{telephone}:{session_token}",
                    max_age=60*60*24*30
                )

                st.success(f"✅ Bienvenue {nom.strip()} ! Redirection...")
                time.sleep(1)
                st.switch_page("5_interface_web.py")

            except Exception as e:
                st.error(f"❌ Erreur : {e}")

        st.markdown(
            "<div style='text-align:center;font-size:12px;color:#888;margin-top:15px'>"
            "Déjà un compte ?</div>",
            unsafe_allow_html=True
        )

        if st.button("🔑 Se connecter", use_container_width=True):
            st.switch_page("pages/login.py")


if __name__ == "__main__":
    afficher_inscription()
