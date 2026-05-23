import streamlit as st
from supabase import create_client
import hashlib
import time
from datetime import date, timedelta

# Connexion directe à Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def hasher_mot_de_passe(mdp):
    return hashlib.sha256(mdp.encode()).hexdigest()

def render_phone_input():
    """Sélecteur Afrique priorisé avec option manuelle"""
    
    # Dictionnaire classé avec les +2xx en priorité
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
        selection = st.selectbox("Pays", list(africa_codes.keys()), index=0)
    
    with col2:
        if africa_codes[selection] == "autre":
            prefix = st.text_input("Indicatif", placeholder="+xxx")
            num = st.text_input("Numéro")
        else:
            prefix = africa_codes[selection]
            num = st.text_input("Numéro (sans indicatif)", placeholder="77 000 00 00")
            
    # Nettoyage et formatage
    full_number = f"{prefix.replace('+', '')}{num.replace(' ', '')}"
    return f"+{full_number}"

def afficher_inscription():
    st.markdown("<h2 style='text-align: center; color: #1D9E75;'>📝 Créer un compte</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Bienvenue sur Victor V2 !</p>", unsafe_allow_html=True)
    
    with st.form("form_inscription"):
        nom = st.text_input("👤 Votre Prénom et Nom")
        telephone = render_phone_input()
        password = st.text_input("🔒 Créer un mot de passe", type="password")
        password_confirm = st.text_input("🔒 Confirmer le mot de passe", type="password")
        
        submit = st.form_submit_button("S'inscrire", type="primary", use_container_width=True)
        
        if submit:
            if not nom or len(telephone) < 7 or not password:
                st.error("⚠️ Veuillez remplir tous les champs correctement.")
            elif password != password_confirm:
                st.error("⚠️ Les mots de passe ne correspondent pas.")
            else:
                try:
                    supabase = init_supabase()
                    
                    # 1. Vérifier si le numéro existe déjà
                    res = supabase.table("abonnes").select("telephone").eq("telephone", telephone).execute()
                    if len(res.data) > 0:
                        st.error("❌ Ce numéro de téléphone est déjà utilisé.")
                    else:
                        # 2. Préparation
                        date_exp = date.today() + timedelta(days=3)
                        mdp_hash = hasher_mot_de_passe(password)
                        token_tmp = f"sess_{telephone}_{int(time.time())}"
                        
                        nouveau_profil = {
                            "nom": nom,
                            "telephone": telephone,
                            "mot_de_passe": mdp_hash,
                            "plan": "essentiel",
                            "jours_restants": 3,
                            "date_expiration": date_exp.isoformat(),
                            "session_token": token_tmp
                        }
                        
                        # 3. Insertion
                        supabase.table("abonnes").insert(nouveau_profil).execute()
                        
                        # 4. AUTO-CONNEXION (Session persistante)
                        st.session_state["connecte"] = True
                        st.session_state["nom"] = nom
                        st.session_state["telephone"] = telephone
                        st.session_state["plan"] = "essentiel"
                        st.session_state["jours_restants"] = 3
                        st.session_state["session_token"] = token_tmp
                        st.query_params["saved_phone"] = telephone
                        
                        st.success("✅ Compte créé ! Redirection...")
                        time.sleep(1)
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Erreur base de données : {e}")

if __name__ == "__main__":
    afficher_inscription()