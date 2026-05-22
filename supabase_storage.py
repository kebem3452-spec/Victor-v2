import os
import joblib
from supabase import create_client
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BUCKET_NAME = "models" # Assure-toi que ton bucket s'appelle bien "models" sur Supabase

def telecharger_modele(nom_fichier):
    """Télécharge un modèle depuis Supabase Storage vers le dossier local models/"""
    os.makedirs("models", exist_ok=True)
    chemin_local = os.path.join("models", nom_fichier)
    
    # Si le modèle est déjà là, on ne le re-télécharge pas
    if os.path.exists(chemin_local):
        return chemin_local
        
    try:
        with open(chemin_local, "wb+") as f:
            res = supabase.storage.from_(BUCKET_NAME).download(nom_fichier)
            f.write(res)
        print(f"✅ Modèle {nom_fichier} téléchargé.")
        return chemin_local
    except Exception as e:
        print(f"❌ Erreur lors du téléchargement de {nom_fichier} : {e}")
        return None

def charger_modele_local(nom_fichier):
    """Charge un modèle pkl en mémoire."""
    chemin = telecharger_modele(nom_fichier)
    if chemin:
        return joblib.load(chemin)
    return None