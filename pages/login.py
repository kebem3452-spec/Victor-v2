"""
VICTOR V2 — pages/login.py
Session persistante via query_params dans l'URL (Streamlit Cloud compatible)
Aucun JS, aucun iframe, aucun localStorage.
"""

import streamlit as st
from auth.supabase_client import verifier_connexion, verifier_session

AFRICA_CODES = {
    "Mali (+223)": "+223", "Sénégal (+221)": "+221", "Côte d'Ivoire (+225)": "+225",
    "Burkina Faso (+226)": "+226", "Niger (+227)": "+227", "Togo (+228)": "+228",
    "Bénin (+229)": "+229", "Guinée (+224)": "+224", "Mauritanie (+222)": "+222",
    "Gambie (+220)": "+220", "Guinée-Bissau (+245)": "+245", "Cap-Vert (+238)": "+238",
    "Sierra Leone (+232)": "+232", "Libéria (+231)": "+231", "Ghana (+233)": "+233",
    "Nigeria (+234)": "+234", "Cameroun (+237)": "+237", "Tchad (+235)": "+235",
    "République Centrafricaine (+236)": "+236", "Gabon (+241)": "+241", "Congo (+242)": "+242",
    "RDC (+243)": "+243", "Angola (+244)": "+244", "Guinée Équatoriale (+240)": "+240",
    "Sao Tomé-et-Principe (+239)": "+239", "Rwanda (+250)": "+250", "Burundi (+257)": "+257",
    "Tanzanie (+255)": "+255", "Kenya (+254)": "+254", "Ouganda (+256)": "+256",
    "Djibouti (+253)": "+253", "Somalie (+252)": "+252", "Éthiopie (+251)": "+251",
    "Érythrée (+291)": "+291", "Soudan (+249)": "+249", "Soudan du Sud (+211)": "+211",
    "Égypte (+20)": "+20", "Libye (+218)": "+218", "Tunisie (+216)": "+216",
    "Algérie (+213)": "+213", "Maroc (+212)": "+212", "Sahara Occidental (+212)": "+212",
    "Madagascar (+261)": "+261", "Maurice (+230)": "+230", "Comores (+269)": "+269",
    "Seychelles (+248)": "+248", "Réunion (+262)": "+262", "Mayotte (+262)": "+262",
    "Mozambique (+258)": "+258", "Malawi (+265)": "+265", "Zambie (+260)": "+260",
    "Zimbabwe (+263)": "+263", "Namibie (+264)": "+264", "Botswana (+267)": "+267",
    "Eswatini (+268)": "+268", "Lesotho (+266)": "+266", "Afrique du Sud (+27)": "+27",
    "Autre (saisir l'indicatif)": "autre",
}

def render_phone_input_login():
    col1, col2 = st.columns([1, 2])
    with col1:
        selection = st.selectbox("🌍 Pays", list(AFRICA_CODES.keys()), index=0, key="login_pays")
    with col2:
        if AFRICA_CODES[selection] == "autre":
            prefix = st.text_input("Indicatif", placeholder="+xxx", key="login_prefix_libre")
            num = st.text_input("Numéro", placeholder="06 00 00 00 00", key="login_num_libre")
        else:
            prefix = AFRICA_CODES[selection]
            st.text_input("Indicatif", value=prefix, disabled=True, key="login_prefix_auto")
            num = st.text_input("Numéro", placeholder="77 000 00 00", key="login_num_auto")
    clean = f"{prefix.replace('+','').replace(' ','')}{num.replace(' ','')}"
    return f"+{clean}"


def afficher_login():

    # ── PRIORITÉ 1 : session_state déjà active (même session navigateur) ──
    if st.session_state.get("connecte"):
        st.switch_page("5_interface_web.py")
        return

    # ── PRIORITÉ 2 : token dans l'URL → restauration automatique ──
    # L'URL ressemble à : https://...streamlit.app/?t=TOKEN&p=TELEPHONE
    # L'utilisateur met cette URL en favori après sa 1ère connexion.
    # Streamlit Cloud conserve les query_params dans l'URL → ça survit au rafraîchissement.
    url_token = st.query_params.get("t", "")
    url_phone = st.query_params.get("p", "")

    if url_token and url_phone:
        # Vérifier avec Supabase que le token est toujours valide
        if verifier_session(url_phone, url_token):
            # Récupérer les infos complètes de l'abonné
            try:
                from auth.supabase_client import get_client
                from datetime import date
                client = get_client()
                res = client.table("abonnes").select(
                    "nom, plan, date_expiration"
                ).eq("telephone", url_phone).execute()
                if res.data:
                    abonne = res.data[0]
                    expiration = date.fromisoformat(abonne["date_expiration"])
                    jours_restants = (expiration - date.today()).days
                    nom  = abonne.get("nom", "Abonné")
                    plan = abonne.get("plan", "pro")
                else:
                    jours_restants = 999
                    nom  = "Abonné"
                    plan = "pro"
            except Exception:
                jours_restants = 999
                nom  = "Abonné"
                plan = "pro"

            # Restaurer la session complète
            st.session_state["connecte"]       = True
            st.session_state["telephone"]      = url_phone
            st.session_state["session_token"]  = url_token
            st.session_state["nom"]            = nom
            st.session_state["plan"]           = plan
            st.session_state["jours_restants"] = jours_restants
            st.switch_page("5_interface_web.py")
            return
        else:
            # Token expiré ou invalide → effacer l'URL et afficher le formulaire
            st.query_params.clear()
            st.warning("⚠️ Session expirée. Veuillez vous reconnecter.")

    # ── PRIORITÉ 3 : afficher le formulaire de connexion ──
    st.markdown("""<style>
    .login-title { font-size:2.5rem; font-weight:700; color:#1D9E75; text-align:center; }
    .login-sub { font-size:1rem; color:#888; text-align:center; margin-bottom:1rem; }
    </style>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligence Artificielle PMU</div>', unsafe_allow_html=True)

        telephone    = render_phone_input_login()
        mot_de_passe = st.text_input("🔒 Code secret", type="password", key="login_mdp")

        if st.button("🚀 Se connecter", use_container_width=True, type="primary"):
            if len(telephone) < 8 or not mot_de_passe:
                st.error("⚠️ Remplissez tous les champs.")
            else:
                with st.spinner("Vérification..."):
                    result = verifier_connexion(telephone, mot_de_passe)

                if result["succes"]:
                    abonne = result["abonne"]
                    st.session_state["connecte"]       = True
                    st.session_state["telephone"]      = abonne["telephone"]
                    st.session_state["nom"]            = abonne.get("nom", "Abonné")
                    st.session_state["plan"]           = abonne.get("plan", "pro")
                    st.session_state["session_token"]  = abonne["session_token"]
                    st.session_state["jours_restants"] = abonne["jours_restants"]

                    # Sauvegarder token + téléphone dans l'URL
                    # → l'utilisateur met cette URL en favori = connexion automatique à vie
                    st.query_params["t"] = abonne["session_token"]
                    st.query_params["p"] = abonne["telephone"]

                    st.switch_page("5_interface_web.py")
                else:
                    st.error(f"❌ {result['message']}")

        if st.button("📝 Créer un compte gratuit", use_container_width=True):
            st.switch_page("pages/inscription.py")

        wa_msg = "Bonjour, j'ai perdu mon mot de passe Victor V2. Mon numéro est : " + telephone
        wa_url = f"https://wa.me/221762641751?text={wa_msg.replace(' ', '%20')}"
        st.link_button("🔑 Mot de passe oublié ?", wa_url, use_container_width=True)


if __name__ == "__main__":
    afficher_login()
