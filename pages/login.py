"""
VICTOR V2 — pages/login.py
============================
- 56 pays africains + Autre avec champ libre
- Session persistante (query_params)
- Bouton mot de passe oublié → WhatsApp +221762641751
"""

import streamlit as st
from auth.supabase_client import verifier_connexion, verifier_session

# ─────────────────────────────────────────────
# 56 PAYS AFRICAINS — commence par Mali +223
# ─────────────────────────────────────────────
AFRICA_CODES = {
    "Mali (+223)"                    : "+223",
    "Sénégal (+221)"                 : "+221",
    "Côte d'Ivoire (+225)"           : "+225",
    "Burkina Faso (+226)"            : "+226",
    "Niger (+227)"                   : "+227",
    "Togo (+228)"                    : "+228",
    "Bénin (+229)"                   : "+229",
    "Guinée (+224)"                  : "+224",
    "Mauritanie (+222)"              : "+222",
    "Gambie (+220)"                  : "+220",
    "Guinée-Bissau (+245)"           : "+245",
    "Cap-Vert (+238)"                : "+238",
    "Sierra Leone (+232)"            : "+232",
    "Libéria (+231)"                 : "+231",
    "Ghana (+233)"                   : "+233",
    "Nigeria (+234)"                 : "+234",
    "Cameroun (+237)"                : "+237",
    "Tchad (+235)"                   : "+235",
    "République Centrafricaine (+236)": "+236",
    "Gabon (+241)"                   : "+241",
    "Congo (+242)"                   : "+242",
    "RDC (+243)"                     : "+243",
    "Angola (+244)"                  : "+244",
    "Guinée Équatoriale (+240)"      : "+240",
    "Sao Tomé-et-Principe (+239)"    : "+239",
    "Rwanda (+250)"                  : "+250",
    "Burundi (+257)"                 : "+257",
    "Tanzanie (+255)"                : "+255",
    "Kenya (+254)"                   : "+254",
    "Ouganda (+256)"                 : "+256",
    "Djibouti (+253)"                : "+253",
    "Somalie (+252)"                 : "+252",
    "Éthiopie (+251)"                : "+251",
    "Érythrée (+291)"                : "+291",
    "Soudan (+249)"                  : "+249",
    "Soudan du Sud (+211)"           : "+211",
    "Égypte (+20)"                   : "+20",
    "Libye (+218)"                   : "+218",
    "Tunisie (+216)"                 : "+216",
    "Algérie (+213)"                 : "+213",
    "Maroc (+212)"                   : "+212",
    "Sahara Occidental (+212)"       : "+212",
    "Madagascar (+261)"              : "+261",
    "Maurice (+230)"                 : "+230",
    "Comores (+269)"                 : "+269",
    "Seychelles (+248)"              : "+248",
    "Réunion (+262)"                 : "+262",
    "Mayotte (+262)"                 : "+262",
    "Mozambique (+258)"              : "+258",
    "Malawi (+265)"                  : "+265",
    "Zambie (+260)"                  : "+260",
    "Zimbabwe (+263)"                : "+263",
    "Namibie (+264)"                 : "+264",
    "Botswana (+267)"                : "+267",
    "Eswatini (+268)"                : "+268",
    "Lesotho (+266)"                 : "+266",
    "Afrique du Sud (+27)"           : "+27",
    "Autre (saisir l'indicatif)"     : "autre",
}


def render_phone_input_login():
    col1, col2 = st.columns([1, 2])
    with col1:
        selection = st.selectbox(
            "🌍 Pays", list(AFRICA_CODES.keys()),
            index=0, key="login_pays"
        )
    with col2:
        if AFRICA_CODES[selection] == "autre":
            prefix = st.text_input(
                "Indicatif (ex: +33)", placeholder="+xxx",
                key="login_prefix_libre"
            )
            num = st.text_input(
                "Numéro", placeholder="06 00 00 00 00",
                key="login_num_libre"
            )
        else:
            prefix = AFRICA_CODES[selection]
            st.text_input(
                "Indicatif (fixe)", value=prefix,
                disabled=True, key="login_prefix_auto"
            )
            num = st.text_input(
                "Numéro (sans indicatif)", placeholder="77 000 00 00",
                key="login_num_auto"
            )

    clean = f"{prefix.replace('+','').replace(' ','')}{num.replace(' ','')}"
    return f"+{clean}"


def restaurer_session_depuis_url() -> bool:
    """
    ✅ SESSION PERSISTANTE
    Si l'utilisateur a déjà un token sauvegardé dans l'URL,
    on le reconnecte automatiquement sans qu'il ait à retaper son mot de passe.
    Comme un cookie — il revient sur le site et il est déjà connecté.
    """
    saved_phone = st.query_params.get("saved_phone", "")
    saved_token = st.query_params.get("saved_token", "")

    if not saved_phone or not saved_token:
        return False

    try:
        # Vérifier que le token est toujours valide dans Supabase
        valide = verifier_session(saved_phone, saved_token)
        if not valide:
            # Token expiré ou invalide — effacer les query params
            st.query_params.pop("saved_phone", None)
            st.query_params.pop("saved_token", None)
            return False

        # Récupérer les infos de l'abonné
        from auth.supabase_client import get_client
        from datetime import date
        client  = get_client()
        res     = client.table("abonnes").select(
            "nom, plan, date_expiration, session_token"
        ).eq("telephone", saved_phone).execute()

        if not res.data:
            return False

        abonne        = res.data[0]
        expiration    = date.fromisoformat(abonne["date_expiration"])
        jours_restants = (expiration - date.today()).days

        if jours_restants < 0:
            return False

        # Restaurer la session
        st.session_state["connecte"]       = True
        st.session_state["telephone"]      = saved_phone
        st.session_state["nom"]            = abonne.get("nom", "Abonné")
        st.session_state["plan"]           = abonne.get("plan", "pro")
        st.session_state["session_token"]  = saved_token
        st.session_state["jours_restants"] = jours_restants
        return True

    except Exception:
        return False


def afficher_login(prefill_phone=None):
    # ✅ Essayer de restaurer la session automatiquement
    if restaurer_session_depuis_url():
        st.rerun()
        return

    st.markdown("""
    <style>
    .login-title { font-size:2.5rem; font-weight:700; color:#1D9E75; text-align:center; }
    .login-sub   { font-size:1rem; color:#888; text-align:center; margin-bottom:2rem; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligence Artificielle PMU</div>',
                    unsafe_allow_html=True)

        if prefill_phone:
            st.info(f"Connexion pour : **{prefill_phone}**")
            telephone = prefill_phone
        else:
            telephone = render_phone_input_login()

        mot_de_passe = st.text_input(
            "🔒 Code secret", type="password", key="login_mdp"
        )

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

                    # ✅ Sauvegarder dans l'URL pour se souvenir
                    st.query_params["saved_phone"] = telephone
                    st.query_params["saved_token"] = abonne["session_token"]

                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

        st.markdown("---")

        # ✅ Mot de passe oublié → WhatsApp +221762641751
        wa_msg = "Bonjour, j'ai perdu mon mot de passe Victor V2. Mon numéro est : " + telephone
        wa_url = f"https://wa.me/221762641751?text={wa_msg.replace(' ', '%20')}"
        st.link_button(
            "🔑 Mot de passe oublié → WhatsApp",
            wa_url,
            use_container_width=True
        )

        st.markdown("---")

        # Bouton inscription
        if st.button("📝 Créer un compte gratuit", use_container_width=True):
            st.session_state["page_auth"] = "inscription"
            st.rerun()

        st.markdown(
            "<div style='text-align:center;font-size:11px;color:#888;margin-top:8px'>"
            "Support : <strong>+221 76 264 17 51</strong>"
            "</div>",
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    afficher_login()
