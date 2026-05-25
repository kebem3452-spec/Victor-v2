"""
VICTOR V2 — Lancement automatique complet
==========================================
Attend la fin de la collecte puis lance toute la chaîne.
✅ CORRECTION : timeout de 3h maximum pour éviter la boucle infinie.
"""

import subprocess
import sys
import time
from datetime import datetime

PYTHON   = sys.executable
LOG_FILE = "lancer_tout_log.txt"

ETAPES = [
    {"nom": "Feature Engineering",        "emoji": "⚙️ ", "commande": "2_feature_engineering.py",  "duree": "~5 min"},
    {"nom": "Entraînement du modèle",      "emoji": "🧠",  "commande": "3_entrainer_modele.py",      "duree": "~5 min"},
    {"nom": "Dataset de simulation",       "emoji": "🔬",  "commande": "10_dataset_simulation.py",   "duree": "~5 min"},
    {"nom": "Entraînement du Superviseur", "emoji": "🎓",  "commande": "11_superviseur.py",          "duree": "~3 min"},
    {"nom": "Backtesting ROI",             "emoji": "💰",  "commande": "7_backtesting.py",           "duree": "~2 min"},
]


def log(message):
    h    = datetime.now().strftime("%H:%M:%S")
    line = f"[{h}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def lancer_etape(etape):
    log(f"{etape['emoji']} Démarrage : {etape['nom']} ({etape['duree']})")
    debut = time.time()
    try:
        result = subprocess.run([PYTHON, etape["commande"]], text=True)
        duree  = round(time.time() - debut, 1)
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
    Attend que 1_collecteur_pmu.py soit terminé.
    ✅ CORRECTION : timeout de 3h maximum (36 × 5 minutes).
    Si la collecte prend plus de 3h, on démarre quand même.
    """
    try:
        import psutil
    except ImportError:
        log("⚠️  psutil non installé — démarrage immédiat")
        return

    log("🔍 Vérification si la collecte est encore en cours...")
    MAX_ATTENTE = 36  # 36 × 5 min = 3h maximum

    for tentative in range(MAX_ATTENTE):
        collecte_active = False
        try:
            for proc in psutil.process_iter(["cmdline"]):
                cmdline = " ".join(proc.info["cmdline"] or [])
                if "1_collecteur_pmu" in cmdline:
                    collecte_active = True
                    break
        except Exception:
            pass

        if not collecte_active:
            log("✅ Collecte terminée — démarrage de la chaîne !")
            return

        restant = (MAX_ATTENTE - tentative) * 5
        log(f"⏳ Collecte en cours... vérification dans 5 min "
            f"(timeout dans {restant} min)")
        time.sleep(300)

    # ✅ CORRECTION : timeout atteint → on démarre quand même
    log("⚠️  Timeout 3h atteint — démarrage forcé de la chaîne.")


def main():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"VICTOR V2 — {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n{'='*50}\n\n")

    print("="*55)
    print("🤖 VICTOR V2 — LANCEMENT AUTOMATIQUE COMPLET")
    print("="*55)

    attendre_collecte()

    print()
    log(f"🚀 Lancement de {len(ETAPES)} étapes...")

    resultats = []
    for i, etape in enumerate(ETAPES, 1):
        print(f"\n{'─'*55}")
        print(f"  ÉTAPE {i}/{len(ETAPES)} — {etape['nom']}")
        print(f"{'─'*55}")
        succes = lancer_etape(etape)
        resultats.append((etape["nom"], succes))

    # Résumé
    print("\n" + "="*55)
    print("📊 RÉSUMÉ FINAL")
    print("="*55)
    nb_ok = sum(1 for _, s in resultats if s)
    for nom, succes in resultats:
        print(f"  {'✅' if succes else '❌'} {nom}")
    print()
    if nb_ok == len(resultats):
        print("🏆 TOUT S'EST BIEN PASSÉ !")
        print("   Lance : streamlit run 5_interface_web.py")
    else:
        print(f"⚠️  {len(resultats)-nb_ok} étape(s) échouée(s).")
    print(f"\n   Terminé : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
    print("="*55)
    log(f"Terminé : {nb_ok}/{len(ETAPES)} étapes réussies")


if __name__ == "__main__":
    main()