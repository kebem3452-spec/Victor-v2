"""
VICTOR V2 — Kelly Criterion : Calcul de la mise optimale
=========================================================
Le Kelly Criterion est une formule mathématique qui répond à :
"Combien dois-je miser sur ce pari pour maximiser mes gains
à long terme sans risque de tout perdre ?"

Formule de Kelly :
    f = (p * b - (1 - p)) / b

Où :
    f = fraction de ta bankroll à miser (ex: 0.05 = 5%)
    p = probabilité estimée de gagner (sortie de l'IA, ex: 0.35)
    b = gain net si tu gagnes (cote - 1, ex: cote 5.0 → b = 4.0)

Exemple concret :
    Cheval avec confiance IA 35% et cote 5.0
    p = 0.35, b = 4.0
    f = (0.35 * 4.0 - 0.65) / 4.0 = (1.40 - 0.65) / 4.0 = 0.19
    → Miser 19% de ta bankroll

Mais 19% c'est trop risqué ! On utilise le "Kelly fractionné"
(Half-Kelly ou Quarter-Kelly) pour réduire la variance :
    Half-Kelly   : miser f/2  → 9.5%
    Quarter-Kelly: miser f/4  → 4.75%  ← recommandé pour débutants

Ce module est utilisable :
1. En standalone (python kelly.py) pour calculer une mise manuellement
2. Importé dans 5_interface_web.py pour afficher les mises dans l'interface
"""

# ─────────────────────────────────────────────
# FORMULE KELLY
# ─────────────────────────────────────────────

def kelly_fraction(probabilite: float, cote: float) -> dict:
    """
    Calcule la fraction Kelly et ses variantes.

    probabilite : entre 0 et 1 (sortie de l'IA divisée par 100)
                  ex: confiance IA 35% → probabilite = 0.35
    cote        : cote PMU (ex: 5.0)

    Retourne un dict avec :
    - kelly_pur    : fraction brute (peut être > 1, dangereux)
    - half_kelly   : Kelly / 2 (recommandé)
    - quarter_kelly: Kelly / 4 (conservateur, pour débuter)
    - valeur_attendue : gain espéré par unité misée
    - conseil      : texte d'explication
    """
    if cote <= 1.0 or probabilite <= 0 or probabilite >= 1:
        return {
            "kelly_pur"      : 0.0,
            "half_kelly"     : 0.0,
            "quarter_kelly"  : 0.0,
            "valeur_attendue": 0.0,
            "conseil"        : "❌ Pari non rentable (cote ou probabilité invalide)",
        }

    b = cote - 1.0              # gain net pour 1 unité misée
    p = probabilite
    q = 1.0 - p                 # probabilité de perdre

    kelly_pur = (p * b - q) / b

    # Si Kelly négatif → pari mathématiquement perdant, ne pas jouer
    if kelly_pur <= 0:
        valeur_attendue = round(p * b - q, 4)
        return {
            "kelly_pur"      : 0.0,
            "half_kelly"     : 0.0,
            "quarter_kelly"  : 0.0,
            "valeur_attendue": valeur_attendue,
            "conseil"        : f"❌ Pari à valeur négative ({valeur_attendue:.2f}). Ne pas jouer.",
        }

    # Plafonner à 25% de la bankroll même si Kelly dit plus
    kelly_pur       = min(kelly_pur, 0.25)
    half_kelly      = kelly_pur / 2
    quarter_kelly   = kelly_pur / 4
    valeur_attendue = round(p * b - q, 4)

    # Conseil selon le niveau de confiance
    if kelly_pur >= 0.15:
        conseil = "🟢 Fort signal — Half-Kelly recommandé"
    elif kelly_pur >= 0.07:
        conseil = "🟡 Signal moyen — Quarter-Kelly prudent"
    else:
        conseil = "🟠 Signal faible — Mise minimale ou abstention"

    return {
        "kelly_pur"      : round(kelly_pur,     4),
        "half_kelly"     : round(half_kelly,    4),
        "quarter_kelly"  : round(quarter_kelly, 4),
        "valeur_attendue": valeur_attendue,
        "conseil"        : conseil,
    }


def calculer_mise(bankroll: float, probabilite: float, cote: float,
                   methode: str = "quarter") -> dict:
    """
    Calcule le montant exact à miser en euros/FCFA selon ta bankroll.

    bankroll    : capital total disponible pour les paris (ex: 10000 FCFA)
    probabilite : confiance IA / 100 (ex: 0.35 pour 35%)
    cote        : cote PMU
    methode     : "full", "half" ou "quarter" (recommandé: "quarter")

    Retourne :
    - montant_mise   : en unités monétaires
    - gain_potentiel : si le pari gagne
    - profit_potentiel : gain - mise
    - roi_potentiel  : en %
    """
    fractions = kelly_fraction(probabilite, cote)

    if methode == "full":
        fraction = fractions["kelly_pur"]
    elif methode == "half":
        fraction = fractions["half_kelly"]
    else:  # quarter (défaut)
        fraction = fractions["quarter_kelly"]

    montant_mise      = round(bankroll * fraction, 0)
    gain_potentiel    = round(montant_mise * cote, 0)
    profit_potentiel  = round(gain_potentiel - montant_mise, 0)
    roi_potentiel     = round((profit_potentiel / max(montant_mise, 1)) * 100, 1)

    return {
        "fraction"        : fraction,
        "montant_mise"    : montant_mise,
        "gain_potentiel"  : gain_potentiel,
        "profit_potentiel": profit_potentiel,
        "roi_potentiel"   : roi_potentiel,
        "conseil"         : fractions["conseil"],
        "valeur_attendue" : fractions["valeur_attendue"],
    }


def analyser_course(participants_df, bankroll: float = 10000,
                     methode: str = "quarter") -> None:
    """
    Affiche une analyse Kelly complète pour tous les chevaux d'une course.
    participants_df : DataFrame avec colonnes 'nom_cheval', 'cote', 'Confiance IA'
    """
    print(f"\n{'='*65}")
    print(f"  💰 ANALYSE KELLY — Bankroll : {bankroll:,.0f}")
    print(f"  Méthode : {methode.upper()}-Kelly")
    print(f"{'='*65}")
    print(f"  {'Cheval':<22} {'Cote':>6} {'Conf%':>6} {'Mise':>8} {'Gain':>10}  Conseil")
    print(f"  {'-'*62}")

    for _, row in participants_df.iterrows():
        nom    = str(row.get("nom_cheval", row.get("Cheval", "?")))[:22]
        cote   = float(row.get("cote",        row.get("Cote", 10.0)))
        conf   = float(row.get("Confiance IA", row.get("proba", 20.0)))
        proba  = conf / 100

        result = calculer_mise(bankroll, proba, cote, methode)

        if result["montant_mise"] > 0:
            print(f"  {nom:<22} {cote:>6.1f} {conf:>5.1f}%"
                  f" {result['montant_mise']:>8,.0f}"
                  f" {result['gain_potentiel']:>10,.0f}"
                  f"  {result['conseil']}")
        else:
            print(f"  {nom:<22} {cote:>6.1f} {conf:>5.1f}%"
                  f"  {'—':>8}  {'—':>10}  ❌ Pas de valeur")

    print(f"{'='*65}")


# ─────────────────────────────────────────────
# MODE INTERACTIF (standalone)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("💰 VICTOR V2 — CALCULATEUR KELLY CRITERION")
    print("=" * 50)

    # Exemple de calcul manuel
    print("\n📌 Exemples de calcul :\n")

    exemples = [
        ("Favori solide",   0.45, 2.5,  "quarter"),
        ("Bon signal IA",   0.38, 5.0,  "quarter"),
        ("Signal moyen",    0.28, 8.0,  "half"),
        ("Outsider risqué", 0.15, 25.0, "quarter"),
        ("Pari sans valeur",0.10, 3.0,  "quarter"),
    ]

    bankroll = 10000

    for nom, proba, cote, methode in exemples:
        r = calculer_mise(bankroll, proba, cote, methode)
        print(f"  {nom:<22} p={proba:.0%}  cote={cote:.1f}  "
              f"mise={r['montant_mise']:>6,.0f}  "
              f"gain potentiel={r['gain_potentiel']:>7,.0f}  "
              f"{r['conseil']}")

    print()
    print("─" * 50)
    print("Pour utiliser dans l'interface Streamlit :")
    print("  from kelly import calculer_mise")
    print("  result = calculer_mise(bankroll=10000, probabilite=0.35, cote=5.0)")
    print("─" * 50)

    # Mode interactif
    print("\n🎮 Mode interactif (Ctrl+C pour quitter)")
    try:
        while True:
            print()
            bankroll = float(input("  Bankroll (ex: 10000) : "))
            conf     = float(input("  Confiance IA en % (ex: 35) : "))
            cote     = float(input("  Cote PMU (ex: 5.0) : "))

            result = calculer_mise(bankroll, conf / 100, cote, "quarter")

            print(f"\n  Quarter-Kelly → Mise : {result['montant_mise']:,.0f}")
            print(f"  Gain potentiel       : {result['gain_potentiel']:,.0f}")
            print(f"  Profit potentiel     : {result['profit_potentiel']:,.0f}")
            print(f"  {result['conseil']}")
    except (KeyboardInterrupt, EOFError):
        print("\n\n✅ Calculateur Kelly fermé.")