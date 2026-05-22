"""
VICTOR V2 — auth/supabase_client.py
====================================
Connexion unique à Supabase.
Toutes les fonctions d'authentification sont ici.
"""

import os
import hashlib
import secrets
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_client():
    """Retourne le client Supabase."""
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        return None


def hasher_mot_de_passe(mdp: str) -> str:
    """Chiffre le mot de passe avec SHA256."""
    return hashlib.sha256(mdp.encode()).hexdigest()


def verifier_connexion(telephone: str, mot_de_passe: str) -> dict:
    """
    Vérifie si le numéro + mot de passe sont corrects
    ET si l'abonnement est encore valide.

    Retourne :
    - {"succes": True, "abonne": {...}} si tout est OK
    - {"succes": False, "message": "..."} si problème
    """
    client = get_client()
    if not client:
        return {"succes": False, "message": "Erreur de connexion au serveur."}

    # Nettoyer le numéro (enlever espaces)
    telephone = telephone.strip().replace(" ", "")
    mdp_hash  = hasher_mot_de_passe(mot_de_passe.strip())

    try:
        # Chercher l'abonné
        res = client.table("abonnes").select("*").eq(
            "telephone", telephone).execute()

        if not res.data:
            return {"succes": False, "message": "Numéro de téléphone introuvable."}

        abonne = res.data[0]

        # Vérifier le mot de passe
        if abonne["mot_de_passe"] != mdp_hash:
            return {"succes": False, "message": "Mot de passe incorrect."}

        # Vérifier si le compte est actif
        if not abonne["actif"]:
            return {"succes": False, "message": "Compte désactivé. Contactez le support."}

        # Vérifier la date d'expiration
        expiration = date.fromisoformat(abonne["date_expiration"])
        if expiration < date.today():
            jours = (date.today() - expiration).days
            return {
                "succes": False,
                "message": f"Abonnement expiré depuis {jours} jour(s).\nContactez-nous au +221 76 264 17 51 pour renouveler."
            }

        # Générer un token de session unique (anti-partage)
        session_token = secrets.token_hex(32)
        client.table("abonnes").update({
            "session_token"     : session_token,
            "derniere_connexion": datetime.now().isoformat()
        }).eq("telephone", telephone).execute()

        abonne["session_token"]     = session_token
        abonne["jours_restants"]    = (expiration - date.today()).days

        return {"succes": True, "abonne": abonne}

    except Exception as e:
        return {"succes": False, "message": f"Erreur serveur : {e}"}


def verifier_session(telephone: str, session_token: str) -> bool:
    """
    Vérifie que la session est toujours valide.
    Si quelqu'un d'autre s'est connecté avec le même compte,
    le token aura changé → session invalide → déconnexion.
    """
    client = get_client()
    if not client:
        return False

    try:
        res = client.table("abonnes").select(
            "session_token, date_expiration, actif"
        ).eq("telephone", telephone).execute()

        if not res.data:
            return False

        abonne = res.data[0]

        # Vérifier token (anti-partage de compte)
        if abonne["session_token"] != session_token:
            return False

        # Vérifier expiration
        if date.fromisoformat(abonne["date_expiration"]) < date.today():
            return False

        # Vérifier compte actif
        if not abonne["actif"]:
            return False

        return True

    except Exception:
        return False


def deconnecter(telephone: str):
    """Efface le token de session (déconnexion)."""
    client = get_client()
    if client:
        try:
            client.table("abonnes").update(
                {"session_token": None}
            ).eq("telephone", telephone).execute()
        except Exception:
            pass


# ─────────────────────────────────────────────
# FONCTIONS ADMIN
# ─────────────────────────────────────────────

def creer_abonne(telephone: str, mot_de_passe: str,
                  nom: str, jours: int = 30, plan: str = "pro") -> dict:
    """Crée un nouvel abonné depuis le panneau admin."""
    client = get_client()
    if not client:
        return {"succes": False, "message": "Erreur connexion Supabase"}

    from datetime import timedelta
    telephone   = telephone.strip().replace(" ", "")
    mdp_hash    = hasher_mot_de_passe(mot_de_passe.strip())
    expiration  = (date.today() + timedelta(days=jours)).isoformat()

    try:
        res = client.table("abonnes").insert({
            "telephone"       : telephone,
            "mot_de_passe"    : mdp_hash,
            "nom"             : nom,
            "plan"            : plan,
            "date_expiration" : expiration,
            "actif"           : True,
        }).execute()
        return {"succes": True, "message": f"Abonné {nom} créé. Expire le {expiration}"}
    except Exception as e:
        return {"succes": False, "message": f"Erreur : {e}"}


def lister_abonnes() -> list:
    """Liste tous les abonnés pour le panneau admin."""
    client = get_client()
    if not client:
        return []
    try:
        res = client.table("abonnes").select(
            "telephone, nom, plan, date_expiration, actif, derniere_connexion"
        ).order("date_expiration").execute()
        return res.data or []
    except Exception:
        return []


def renouveler_abonne(telephone: str, jours: int = 30) -> dict:
    """Renouvelle l'abonnement d'un client."""
    client = get_client()
    if not client:
        return {"succes": False, "message": "Erreur connexion"}

    from datetime import timedelta
    try:
        res = client.table("abonnes").select(
            "date_expiration").eq("telephone", telephone).execute()
        if not res.data:
            return {"succes": False, "message": "Abonné introuvable"}

        exp_actuelle = date.fromisoformat(res.data[0]["date_expiration"])
        # Si déjà expiré → repart d'aujourd'hui, sinon prolonge
        base       = max(exp_actuelle, date.today())
        nouvelle   = (base + timedelta(days=jours)).isoformat()

        client.table("abonnes").update({
            "date_expiration": nouvelle,
            "actif"          : True
        }).eq("telephone", telephone).execute()

        return {"succes": True, "message": f"Renouvelé jusqu'au {nouvelle}"}
    except Exception as e:
        return {"succes": False, "message": str(e)}