import streamlit as st
import hashlib
from datetime import datetime, timedelta
# Assure-toi que cette fonction existe dans ton module auth/supabase_client.py
# ou un utilitaire de sécurité dédié.
from auth.supabase_client import get_supabase_client

st.set_page_config(page_title="Inscription - Victor V2", page_icon="🏇")

def hasher_mot_de_passe(password):
    return hashlib.sha256(password.encode()).hexdigest()

st.title("🏇 Inscription Victor V2")
st.markdown("Rejoins la communauté des pronostiqueurs.")

with st.form("inscription_form"):
    nom = st.text_input("Nom complet")
    telephone = st.text_input("Numéro de téléphone (ex: +22176...)")
    mot_de_passe = st.text_input("Code secret", type="password")
    submit = st.form_submit_button("Créer mon compte")

if submit:
    if not nom or not telephone or not mot_de_passe:
        st.error("Tous les champs sont obligatoires.")
    else:
        supabase = get_supabase_client()
        pwd_hash = hasher_mot_de_passe(mot_de_passe)
        
        # Calcul expiration par défaut (30 jours)
        date_exp = (datetime.now() + timedelta(days=30)).date().isoformat()
        
        try:
            data = {
                "telephone": telephone,
                "mot_de_passe": pwd_hash,
                "nom": nom,
                "plan": "pro",
                "date_expiration": date_exp,
                "actif": True
            }
            
            response = supabase.table("abonnes").insert(data).execute()
            
            if response.data:
                st.success("Compte créé avec succès ! Tu peux te connecter.")
                st.balloons()
            else:
                st.error("Erreur lors de la création du compte.")
        except Exception as e:
            st.error(f"Erreur technique : {str(e)}")

st.markdown("---")
if st.button("Retour à la connexion"):
    st.switch_page("pages/login.py")