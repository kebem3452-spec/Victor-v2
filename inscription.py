"""
VICTOR V2 — pages/inscription.py
==================================
Page d'inscription libre — sans confirmation email.
Le compte est créé immédiatement avec 3 jours d'essai.
"""

import streamlit as st
import secrets
import time
from datetime import date, timedelta

# ✅ CORRECTION : imports manquants ajoutés
from auth.supabase_client import get_client, hasher_mot_de_passe


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
    "Congo (+242)"        : "+242",
    "France (+33)"        : "+33",
    "Autre"               : "autre",
}


def render_phone_input(prefix="ins"):
    col1, col2 = st.columns([1, 2])
    with col1:
        selection = st.selectbox("Pays", list(AFRICA_CODES.keys()),
                                  index=0, key=f"{prefix}_pays")
    with col2:
        if AFRICA_CODES[selection] == "autre":
            indicatif = st.text_input("Indicatif", placeholder="+xxx",
                                       key=f"{prefix}_indic")
            num = st.text_input("Numéro", key=f"{prefix}_num")
        else:
            indicatif = AFRICA_CODES[selection]
            st.text_input("Indicatif (fixe)", value=indicatif,
                           disabled=True, key=f"{prefix}_indic_auto")
            num = st.text_input("Numéro (sans indicatif)",
                                 placeholder="77 000 00 00",
                                 key=f"{prefix}_num_auto")

    clean = f"{indicatif.replace('+','').replace(' ','')}{num.replace(' ','')}"
    return f"+{clean}"


def afficher_inscription():
    st.markdown("""
    <style>
    .ins-title { font-size:2rem; font-weight:700; color:#1D9E75; text-align:center; }
    .ins-sub   { font-size:1rem; color:#888; text-align:center; margin-bottom:1.5rem; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 4, 1])
    with col2:
        st.markdown('<div class="ins-title">🏇 VICTOR V2</div>', unsafe_allow_html=True)
        st.markdown('<div class="ins-sub">Créer votre compte gratuit</div>',
                    unsafe_allow_html=True)

        nom       = st.text_input("👤 Prénom et Nom")
        telephone = render_phone_input("ins")
        password  = st.text_input("🔒 Créer un mot de passe", type="password",
                                   key="ins_pwd")
        password2 = st.text_input("🔒 Confirmer le mot de passe", type="password",
                                   key="ins_pwd2")

        if st.button("✅ Créer mon compte", use_container_width=True, type="primary"):

            # Validations
            if not nom.strip():
                st.error("⚠️ Entrez votre prénom et nom.")
                st.stop()
            if len(telephone) < 8:
                st.error("⚠️ Numéro de téléphone incomplet.")
                st.stop()
            if len(password) < 4:
                st.error("⚠️ Le mot de passe doit faire au moins 4 caractères.")
                st.stop()
            if password != password2:
                st.error("⚠️ Les deux mots de passe ne correspondent pas.")
                st.stop()

            client = get_client()
            if not client:
                st.error("❌ Erreur de connexion au serveur. Réessayez.")
                st.stop()

            try:
                # Vérifier si le numéro existe déjà
                res = client.table("abonnes").select("telephone")\
                            .eq("telephone", telephone).execute()
                if res.data:
                    st.error("❌ Ce numéro est déjà utilisé. Connectez-vous.")
                    st.stop()

                # ✅ CORRECTION : token sécurisé avec secrets.token_hex
                session_token = secrets.token_hex(32)
                date_exp      = (date.today() + timedelta(days=3)).isoformat()
                mdp_hash      = hasher_mot_de_passe(password)

                # Créer le compte
                client.table("abonnes").insert({
                    "telephone"       : telephone,
                    "mot_de_passe"    : mdp_hash,
                    "nom"             : nom.strip(),
                    "plan"            : "essentiel",
                    "date_expiration" : date_exp,
                    "actif"           : True,
                    "session_token"   : session_token,
                    "derniere_connexion": None,
                }).execute()

                # Auto-connexion immédiate
                st.session_state["connecte"]      = True
                st.session_state["telephone"]     = telephone
                st.session_state["nom"]           = nom.strip()
                st.session_state["plan"]          = "essentiel"
                st.session_state["jours_restants"]= 3
                st.session_state["session_token"] = session_token

                st.success(f"✅ Bienvenue {nom.strip()} ! Votre compte est créé.")
                time.sleep(1)
                st.rerun()

            except Exception as e:
                st.error(f"❌ Erreur : {e}")

        st.markdown("---")
        st.markdown(
            "<div style='text-align:center;font-size:12px;color:#888'>"
            "Déjà un compte ? "
            "</div>",
            unsafe_allow_html=True
        )
        if st.button("🔑 Se connecter", use_container_width=True):
            st.session_state["page"] = "login"
            st.rerun()


if __name__ == "__main__":
    afficher_inscription()