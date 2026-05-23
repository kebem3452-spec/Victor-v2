import streamlit as st
from auth.supabase_client import verifier_connexion

def render_phone_input_login():
    """Sélecteur Afrique + Manuel avec gestion stable des états"""
    africa_codes = {
        "Sénégal (+221)": "+221", "Mali (+223)": "+223", "Côte d'Ivoire (+225)": "+225",
        "Burkina Faso (+226)": "+226", "Niger (+227)": "+227", "Togo (+228)": "+228",
        "Bénin (+229)": "+229", "Guinée (+224)": "+224", "Mauritanie (+222)": "+222",
        "Gambie (+220)": "+220", "Algérie (+213)": "+213", "Maroc (+212)": "+212",
        "Tunisie (+216)": "+216", "Libye (+218)": "+218", "Égypte (+20)": "+20",
        "Afrique du Sud (+27)": "+27", "Cameroun (+237)": "+237", "Gabon (+241)": "+241",
        "Congo (+242)": "+242", "RDC (+243)": "+243", "Angola (+244)": "+244",
        "Guinée Équatoriale (+240)": "+240", "Guinée-Bissau (+245)": "+245",
        "Kenya (+254)": "+254", "Ouganda (+256)": "+256", "Rwanda (+250)": "+250",
        "Tanzanie (+255)": "+255", "Burundi (+257)": "+257", "Djibouti (+253)": "+253",
        "Éthiopie (+251)": "+251", "Érythrée (+291)": "+291", "Somalie (+252)": "+252",
        "Soudan (+249)": "+249", "Soudan du Sud (+211)": "+211", "Tchad (+235)": "+235",
        "République Centrafricaine (+236)": "+236", "Ghana (+233)": "+233",
        "Libéria (+231)": "+231", "Sierra Leone (+232)": "+232", "Cap-Vert (+238)": "+238",
        "Sao Tomé-et-Principe (+239)": "+239", "Maurice (+230)": "+230",
        "Seychelles (+248)": "+248", "Comores (+269)": "+269", "Madagascar (+261)": "+261",
        "Malawi (+265)": "+265", "Mozambique (+258)": "+258", "Zambie (+260)": "+260",
        "Zimbabwe (+263)": "+263", "Namibie (+264)": "+264", "Botswana (+267)": "+267",
        "Eswatini (+268)": "+268", "Lesotho (+266)": "+266",
        "Autre (Saisir manuellement)": "autre"
    }

    col1, col2 = st.columns([1, 2])
    with col1:
        # On utilise une key fixe pour que le choix reste sélectionné
        selection = st.selectbox("Pays", list(africa_codes.keys()), index=0, key="login_select_pays")
    
    with col2:
        if africa_codes[selection] == "autre":
            # Si "Autre", on permet de taper l'indicatif manuellement
            prefix = st.text_input("Indicatif", placeholder="+xxx", key="login_manual_prefix")
            num = st.text_input("Numéro", key="login_num_manuel")
        else:
            # Sinon, on prend l'indicatif du dictionnaire
            prefix = africa_codes[selection]
            num = st.text_input("Numéro (sans indicatif)", placeholder="77 000 00 00", key="login_num_auto")
            
    # Nettoyage et formatage
    clean_prefix = prefix.replace('+', '')
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
            telephone = prefill_phone # On force le numéro connu
        else:
            telephone = render_phone_input_login()
            
        mot_de_passe = st.text_input("🔒 Code secret", type="password", key="login_mdp_field")

        if st.button("🚀 Se connecter", use_container_width=True, type="primary"):
            if len(telephone) < 7 or not mot_de_passe:
                st.error("Veuillez entrer un numéro et un mot de passe valides.")
            else:
                with st.spinner("Vérification..."):
                    result = verifier_connexion(telephone, mot_de_passe)

                if result["succes"]:
                    abonne = result["abonne"]
                    st.session_state["connecte"] = True
                    st.session_state["telephone"] = abonne["telephone"]
                    st.session_state["nom"] = abonne.get("nom", "Abonné")
                    st.session_state["plan"] = abonne.get("plan", "pro")
                    st.session_state["session_token"] = abonne["session_token"]
                    st.session_state["jours_restants"] = abonne["jours_restants"]
                    
                    # On mémorise pour le prochain retour
                    st.query_params["saved_phone"] = telephone
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")

        st.markdown("---")
        
        # Bouton WhatsApp avec message pré-rempli
        st.link_button(
            "🔒 J'ai perdu mon mot de passe", 
            "https://wa.me/221762641751?text=Bonjour, j'ai perdu mon mot de passe pour mon compte Victor V2.",
            use_container_width=True
        )

if __name__ == "__main__":
    afficher_login()