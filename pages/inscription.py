import streamlit as st
from supabase import create_client
import hashlib
import time
from datetime import date, timedelta  # Import nécessaire pour gérer les dates

# Connexion directe à Supabase pour éviter les erreurs d'importation
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def hasher_mot_de_passe(mdp):
    return hashlib.sha256(mdp.encode()).hexdigest()

def afficher_inscription():
    st.markdown("<h2 style='text-align: center; color: #1D9E75;'>📝 Créer un compte</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Bienvenue sur Victor V2 !</p>", unsafe_allow_html=True)
    
    with st.form("form_inscription"):
        nom = st.text_input("👤 Votre Prénom et Nom")
        telephone = st.text_input("📱 Numéro de téléphone (ex: +22176...)")
        password = st.text_input("🔒 Créer un mot de passe", type="password")
        password_confirm = st.text_input("🔒 Confirmer le mot de passe", type="password")
        
        submit = st.form_submit_button("S'inscrire", type="primary", use_container_width=True)
        
        if submit:
            if not nom or not telephone or not password:
                st.error("⚠️ Veuillez remplir tous les champs.")
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
                        # 2. Calculer la date d'expiration (Aujourd'hui + 3 jours)
                        date_exp = date.today() + timedelta(days=3)
                        
                        # 3. Inscription
                        mdp_hash = hasher_mot_de_passe(password)
                        nouveau_profil = {
                            "nom": nom,
                            "telephone": telephone,
                            "mot_de_passe": mdp_hash,
                            "plan": "essentiel",
                            "jours_restants": 3,
                            "date_expiration": date_exp.isoformat() # Envoi de la date au format YYYY-MM-DD
                        }
                        
                        supabase.table("abonnes").insert(nouveau_profil).execute()
                        st.success("✅ Compte créé avec succès ! Redirection...")
                        time.sleep(2)
                        st.session_state["auth_mode"] = "login"
                        st.rerun()
                except Exception as e:
                    st.error(f"Une erreur est survenue avec la base de données : {e}")

# Permet l'exécution si on clique directement dessus
if __name__ == "__main__":
    afficher_inscription()