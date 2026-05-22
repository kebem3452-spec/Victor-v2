"""
VICTOR V2 — pages/login.py
============================
Page de connexion — premier écran que voit l'abonné.
"""

import streamlit as st
from auth.supabase_client import verifier_connexion


def afficher_login():
    """
    Affiche la page de connexion.
    Retourne True si connexion réussie.
    """
    # Style visuel de la page login
    st.markdown("""
    <style>
    .login-box {
        max-width: 420px;
        margin: 0 auto;
        padding: 2rem;
        text-align: center;
    }
    .login-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1D9E75;
        margin-bottom: 0.25rem;
    }
    .login-sub {
        font-size: 1rem;
        color: #888;
        margin-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligence Artificielle PMU</div>', unsafe_allow_html=True)
        st.markdown("---")

        telephone = st.text_input(
            "📱 Numéro de téléphone",
            placeholder="+221 76 XXX XX XX",
            key="login_tel"
        )
        mot_de_passe = st.text_input(
            "🔒 Code secret",
            type="password",
            placeholder="Votre code",
            key="login_mdp"
        )

        if st.button("🚀 Se connecter", use_container_width=True, type="primary"):
            if not telephone or not mot_de_passe:
                st.error("Remplissez tous les champs.")
                return False

            with st.spinner("Vérification..."):
                result = verifier_connexion(telephone, mot_de_passe)

            if result["succes"]:
                abonne = result["abonne"]
                # Sauvegarder la session
                st.session_state["connecte"]      = True
                st.session_state["telephone"]     = abonne["telephone"]
                st.session_state["nom"]           = abonne.get("nom", "Abonné")
                st.session_state["plan"]          = abonne.get("plan", "pro")
                st.session_state["session_token"] = abonne["session_token"]
                st.session_state["jours_restants"]= abonne["jours_restants"]
                st.rerun()
            else:
                st.error(f"❌ {result['message']}")

        st.markdown("---")
        st.markdown(
            "<div style='text-align:center;font-size:12px;color:#888'>"
            "Pour s'abonner : <strong>+221 76 264 17 51</strong>"
            "</div>",
            unsafe_allow_html=True
        )

    return False