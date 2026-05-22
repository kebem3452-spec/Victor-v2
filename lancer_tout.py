"""
VICTOR V2 — Lancement automatique complet
==========================================
Ce script attend que la collecte soit terminée,
puis lance toute la chaîne dans l'ordre automatiquement.

Usage :
    python lancer_tout.py

Il va lancer dans l'ordre :
    1. python 2_feature_engineering.py
    2. python 3_entrainer_modele.py
    3. python 10_dataset_simulation.py
    4. python 11_superviseur.py
    5. python 7_backtesting.py

Puis affiche un résumé final.
Va dormir — il fait tout tout seul.
"""

import subprocess
import sys
import os
import time
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Python à utiliser (le tien sur Windows)
PYTHON = sys.executable

# Commandes à lancer dans l'ordre
ETAPES = [
    {
        "nom"     : "Feature Engineering",
        "emoji"   : "⚙️ ",
        "commande": "2_feature_engineering.py",
        "duree"   : "~5 min",
    },
    {
        "nom"     : "Entraînement du modèle",
        "emoji"   : "🧠",
        "commande": "3_entrainer_modele.py",
        "duree"   : "~5 min",
    },
    {
        "nom"     : "Dataset de simulation",
        "emoji"   : "🔬",
        "commande": "10_dataset_simulation.py",
        "duree"   : "~5 min",
    },
    {
        "nom"     : "Entraînement du Superviseur",
        "emoji"   : "🎓",
        "commande": "11_superviseur.py",
        "duree"   : "~3 min",
    },
    {
        "nom"     : "Backtesting ROI",
        "emoji"   : "💰",
        "commande": "7_backtesting.py",
        "duree"   : "~2 min",
    },
]

LOG_FILE = "lancer_tout_log.txt"

# ─────────────────────────────────────────────
# FONCTIONS
# ─────────────────────────────────────────────

def log(message):
    """Affiche et écrit dans le fichier log."""
    horodatage = datetime.now().strftime("%H:%M:%S")
    ligne      = f"[{horodatage}] {message}"
    print(ligne)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(ligne + "\n")


def lancer_etape(etape):
    """Lance une étape et retourne True si succès."""
    log(f"{etape['emoji']} Démarrage : {etape['nom']} ({etape['duree']})")
    debut = time.time()

    try:
        result = subprocess.run(
            [PYTHON, etape["commande"]],
            capture_output=False,   # affiche la sortie en temps réel
            text=True,
        )

        duree = round(time.time() - debut, 1)

        if result.returncode == 0:
            log(f"  ✅ {etape['nom']} terminé en {duree}s")
            return True
        else:
            log(f"  ❌ {etape['nom']} ÉCHOUÉ (code {result.returncode})")
            return False

    except Exception as e:
        log(f"  ❌ Erreur : {e}")
        return False


def attendre_collecte():
    """
    Vérifie que la collecte 1_collecteur_pmu.py est bien terminée
    en regardant si le processus tourne encore.
    Attend s'il tourne encore.
    """
    import psutil

    log("🔍 Vérification si la collecte est encore en cours...")

    while True:
        collecte_active = False
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "1_collecteur_pmu" in cmdline or "collecteur" in cmdline.lower():
                    collecte_active = True
                    break
            except Exception:
                pass

        if not collecte_active:
            log("✅ Aucune collecte active détectée — on peut démarrer !")
            break
        else:
            log("⏳ Collecte encore en cours... vérification dans 5 minutes")
            time.sleep(300)  # 5 minutes


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    # Initialiser le log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"VICTOR V2 — Lancement automatique\n")
        f.write(f"Démarré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n")
        f.write("="*50 + "\n\n")

    print()
    print("="*55)
    print("🤖 VICTOR V2 — LANCEMENT AUTOMATIQUE COMPLET")
    print("="*55)
    print(f"   Démarré : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
    print(f"   Log     : {LOG_FILE}")
    print("="*55)
    print()

    # Vérifier si psutil est disponible pour détecter la collecte
    try:
        import psutil
        attendre_collecte()
    except ImportError:
        log("⚠️  psutil non installé — démarrage immédiat sans attendre la collecte")
        log("   (installe psutil avec : pip install psutil)")

    print()
    log(f"🚀 Lancement de {len(ETAPES)} étapes...")
    print()

    # Lancer chaque étape
    resultats = []
    for i, etape in enumerate(ETAPES, 1):
        print()
        print(f"{'─'*55}")
        print(f"  ÉTAPE {i}/{len(ETAPES)} — {etape['nom']}")
        print(f"{'─'*55}")
        succes = lancer_etape(etape)
        resultats.append((etape["nom"], succes))

        if not succes:
            log(f"⚠️  Étape échouée. Les étapes suivantes vont quand même être tentées.")

    # Résumé final
    print()
    print("="*55)
    print("📊 RÉSUMÉ FINAL")
    print("="*55)

    nb_succes = sum(1 for _, s in resultats if s)
    nb_echec  = len(resultats) - nb_succes

    for nom, succes in resultats:
        emoji = "✅" if succes else "❌"
        print(f"  {emoji} {nom}")

    print()
    if nb_echec == 0:
        print("🏆 TOUT S'EST BIEN PASSÉ !")
        print()
        print("   Pour lancer l'interface :")
        print("   streamlit run 5_interface_web.py")
    else:
        print(f"⚠️  {nb_echec} étape(s) ont échoué.")
        print("   Regarde les messages d'erreur ci-dessus.")
        print(f"   Détails dans : {LOG_FILE}")

    print()
    print(f"   Terminé : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
    print("="*55)

    log(f"\n{'='*50}")
    log(f"Terminé : {nb_succes}/{len(ETAPES)} étapes réussies")


if __name__ == "__main__":
    main()