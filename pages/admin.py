"""
VICTOR V2 — pages/admin.py
============================
Panneau d'administration — visible uniquement par toi.
Gérer les abonnés, voir les statistiques, renouveler.
"""

import streamlit as st
from datetime import date
from auth.supabase_client import (
    creer_abonne, lister_abonnes,
    renouveler_abonne, hasher_mot_de_passe
)
import os
from dotenv import load_dotenv
load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "victor_admin_2026")


def afficher_admin():
    """Page admin complète."""

    # Vérification mot de passe admin
    if "admin_connecte" not in st.session_state:
        st.session_state["admin_connecte"] = False

    if not st.session_state["admin_connecte"]:
        st.title("🔐 Panneau Administrateur")
        mdp = st.text_input("Mot de passe admin :", type="password")
        if st.button("Entrer"):
            if mdp == ADMIN_PASSWORD:
                st.session_state["admin_connecte"] = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
        return

    st.title("⚙️ Panneau Administrateur — Victor V2")

    # ─── Statistiques rapides ───
    abonnes = lister_abonnes()
    aujourd_hui = date.today()

    actifs   = [a for a in abonnes if a["actif"] and
                date.fromisoformat(a["date_expiration"]) >= aujourd_hui]
    expires  = [a for a in abonnes if date.fromisoformat(
                a["date_expiration"]) < aujourd_hui]
    bientot  = [a for a in actifs if
                (date.fromisoformat(a["date_expiration"]) - aujourd_hui).days <= 5]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total abonnés", len(abonnes))
    col2.metric("Actifs", len(actifs), delta=f"+{len(actifs)}")
    col3.metric("Expirés", len(expires), delta=f"-{len(expires)}", delta_color="inverse")
    col4.metric("Expirent dans 5j", len(bientot), delta_color="inverse")

    st.markdown("---")

    # ─── Créer un abonné ───
    with st.expander("➕ Créer un nouvel abonné", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            tel_new  = st.text_input("Téléphone", placeholder="+221 76 XXX XX XX", key="new_tel")
            nom_new  = st.text_input("Nom", placeholder="Prénom Nom", key="new_nom")
        with c2:
            mdp_new  = st.text_input("Code secret", placeholder="ex: VICTEUR2026", key="new_mdp")
            plan_new = st.selectbox("Plan", ["essentiel", "pro", "vip"], index=1, key="new_plan")
            jours_new= st.number_input("Durée (jours)", min_value=1, max_value=365,
                                        value=30, key="new_jours")

        if st.button("✅ Créer l'abonné", type="primary"):
            if tel_new and mdp_new and nom_new:
                result = creer_abonne(tel_new, mdp_new, nom_new, jours_new, plan_new)
                if result["succes"]:
                    st.success(f"✅ {result['message']}")
                    # Message WhatsApp prêt à copier
                    st.code(
                        f"Bonjour {nom_new} ! 🏇\n"
                        f"Votre accès Victor V2 est activé.\n"
                        f"Lien : https://victor-sniper.streamlit.app\n"
                        f"Téléphone : {tel_new}\n"
                        f"Code secret : {mdp_new}\n"
                        f"Valable {jours_new} jours.\n"
                        f"Bonne chance ! 🍀",
                        language="text"
                    )
                else:
                    st.error(result["message"])
            else:
                st.warning("Remplissez tous les champs.")

    # ─── Liste des abonnés ───
    st.subheader("📋 Liste des abonnés")

    filtre = st.selectbox("Filtrer :", ["Tous", "Actifs", "Expirés", "Expire bientôt (5j)"])

    if filtre == "Actifs":
        liste = actifs
    elif filtre == "Expirés":
        liste = expires
    elif filtre == "Expire bientôt (5j)":
        liste = bientot
    else:
        liste = abonnes

    for a in sorted(liste, key=lambda x: x["date_expiration"]):
        exp       = date.fromisoformat(a["date_expiration"])
        jours_r   = (exp - aujourd_hui).days
        statut    = "✅" if jours_r >= 0 else "❌"
        couleur   = "🟡" if 0 <= jours_r <= 5 else statut

        with st.expander(
            f"{couleur} {a.get('nom','?')} — {a['telephone']} — "
            f"Expire : {a['date_expiration']} ({jours_r}j)"
        ):
            c1, c2, c3 = st.columns(3)
            with c1:
                st.write(f"**Plan :** {a.get('plan','?')}")
                st.write(f"**Dernière connexion :** {a.get('derniere_connexion','jamais')}")
            with c2:
                jours_r2 = st.number_input(
                    "Renouveler (jours)", min_value=1, max_value=365,
                    value=30, key=f"ren_{a['telephone']}"
                )
            with c3:
                if st.button("🔄 Renouveler", key=f"btn_{a['telephone']}"):
                    result = renouveler_abonne(a["telephone"], jours_r2)
                    if result["succes"]:
                        st.success(result["message"])
                        st.rerun()
                    else:
                        st.error(result["message"])

    # ─── Bouton déconnexion admin ───
    st.markdown("---")
    if st.button("🚪 Quitter le panneau admin"):
        st.session_state["admin_connecte"] = False
        st.rerun()