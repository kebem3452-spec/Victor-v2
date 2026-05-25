"""
VICTOR V2 — pages/login.py
============================
Page de connexion avec lien vers inscription.
"""

import streamlit as st
from auth.supabase_client import verifier_connexion

AFRICA_CODES = {
    "Sénégal (+221)"      : "+221",
    "Mali (+223)"         : "+223",
    "Côte d'Ivoire (+225)": "+225",
    "Burkina Faso (+226)" : "+226",
    "Niger (+227)"        : "+227",
    "Togo (+228)"         : "+228",
    "Bénin (+229)"        : "+229",
    "Guinée (+224)"       : "+224",
    "Mauritanie (+222)"   : "+222",
    "Cameroun (+237)"     : "+237",
    "France (+33)"        : "+33",
    "Autre"               : "autre",
}


def render_phone_input_login():
    col1, col2 = st.columns([1, 2])
    with col1:
        selection = st.selectbox("Pays", list(AFRICA_CODES.keys()),
                                  index=0, key="login_pays")
    with col2:
        if AFRICA_CODES[selection] == "autre":
            prefix = st.text_input("Indicatif", placeholder="+xxx",
                                    key="login_indic_manuel")
            num    = st.text_input("Numéro", key="login_num_manuel")
        else:
            prefix = AFRICA_CODES[selection]
            st.text_input("Indicatif (fixe)", value=prefix,
                           disabled=True, key="login_indic_auto")
            num = st.text_input("Numéro (sans indicatif)",
                                 placeholder="77 000 00 00",
                                 key="login_num_auto")

    clean = f"{prefix.replace('+','').replace(' ','')}{num.replace(' ','')}"
    return f"+{clean}"


def afficher_login(prefill_phone=None):
    st.markdown("""
    <style>
    .login-title { font-size:2.2rem; font-weight:700; color:#1D9E75; text-align:center; }
    .login-sub   { font-size:1rem; color:#888; text-align:center; margin-bottom:1.5rem; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligence Artificielle PMU</div>',
                    unsafe_allow_html=True)

        if prefill_phone:
            st.info(f"Connexion pour : **{prefill_phone}**")
            telephone = prefill_phone
        else:
            telephone = render_phone_input_login()

        mot_de_passe = st.text_input("🔒 Code secret", type="password",
                                      key="login_mdp")

        if st.button("🚀 Se connecter", use_container_width=True, type="primary"):
            if len(telephone) < 8 or not mot_de_passe:
                st.error("Remplissez tous les champs.")
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
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

        st.markdown("---")

        # Bouton inscription
        if st.button("📝 Créer un compte gratuit", use_container_width=True):
            st.session_state["page_auth"] = "inscription"
            st.rerun()

        st.link_button(
            "❓ Mot de passe oublié",
            "https://wa.me/221762641751?text=Bonjour, j'ai perdu mon mot de passe Victor V2.",
            use_container_width=True
        )

        st.markdown(
            "<div style='text-align:center;font-size:11px;color:#888;margin-top:8px'>"
            "Pour s'abonner : <strong>+221 76 264 17 51</strong>"
            "</div>",
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    afficher_login()