import streamlit as st
from auth.supabase_client import verifier_connexion

def render_phone_input_login():
    """Sélecteur Afrique + Manuel avec gestion stable des états"""
    africa_codes = {
        "Sénégal (+221)": "+221", "Mali (+223)": "+223", "Côte d'Ivoire (+225)": "+225",
        "Burkina Faso (+226)": "+226", "Niger (+227)": "+227", "Togo (+228)": "+228",
        "Bénin (+229)": "+229", "Guinée (+224)": "+224", "Mauritanie (+222)": "+222",
        "Autre (Saisir manuellement)": "autre"
    }

    col1, col2 = st.columns([1, 2])
    with col1:
        # On garde la sélection en mémoire avec une key
        selection = st.selectbox("Pays", list(africa_codes.keys()), index=0, key="login_select_pays")
    
    with col2:
        if africa_codes[selection] == "autre":
            # Mode Manuel : on sauvegarde la valeur dans session_state pour qu'elle survive au refresh
            prefix = st.text_input("Indicatif", placeholder="+xxx", key="login_manual_prefix")
            num = st.text_input("Numéro", key="login_num_manuel")
        else:
            # Mode Afrique : champ désactivé (pour éviter les erreurs)
            prefix = africa_codes[selection]
            st.text_input("Indicatif (fixe)", value=prefix, disabled=True, key="login_prefix_auto")
            num = st.text_input("Numéro (sans indicatif)", placeholder="77 000 00 00", key="login_num_auto")
            
    # Nettoyage et retour
    clean_prefix = prefix.replace('+', '').replace(' ', '')
    clean_num = num.replace(' ', '')
    return f"+{clean_prefix}{clean_num}"

def afficher_login(prefill_phone=None):
    st.markdown("""<style>
    .login-title { font-size: 2.5rem; font-weight: 700; color: #1D9E75; text-align: center; }
    .login-sub { font-size: 1rem; color: #888; text-align: center; margin-bottom: 2rem; }
    </style>""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="login-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Intelligence Artificielle PMU</div>', unsafe_allow_html=True)
        
        # --- LOGIQUE SMART LOGIN ---
        if prefill_phone:
            st.info(f"Bonjour ! Connexion pour : **{prefill_phone}**")
            telephone = prefill_phone
        else:
            telephone = render_phone_input_login()
            
        mot_de_passe = st.text_input("🔒 Code secret", type="password", key="login_mdp_field")

        if st.button("🚀 Se connecter", use_container_width=True, type="primary"):
            # Validation minimale : s'assurer qu'on a bien un indicatif et un numéro
            if len(telephone) < 5 or not mot_de_passe:
                st.error("Veuillez entrer un numéro complet et un mot de passe.")
            else:
                with st.spinner("Vérification..."):
                    result = verifier_connexion(telephone, mot_de_passe)

                if result["succes"]:
                    abonne = result["abonne"]
                    # Sauvegarde session
                    st.session_state["connecte"] = True
                    st.session_state["telephone"] = abonne["telephone"]
                    st.session_state["nom"] = abonne.get("nom", "Abonné")
                    st.session_state["plan"] = abonne.get("plan", "pro")
                    st.session_state["session_token"] = abonne["session_token"]
                    st.session_state["jours_restants"] = abonne["jours_restants"]
                    
                    st.query_params["saved_phone"] = telephone
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

        st.markdown("---")
        
        # Bouton WhatsApp
        st.link_button(
            "🔒 J'ai perdu mon mot de passe", 
            "https://wa.me/221762641751?text=Bonjour, j'ai perdu mon mot de passe pour mon compte Victor V2.",
            use_container_width=True
        )

if __name__ == "__main__":
    afficher_login()