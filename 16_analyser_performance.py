"""
VICTOR V2 — Module 16 : Analyse de Performance
================================================
Compare les pronostics sauvegardés avec les résultats réels.
Répond aux questions :
- Quel % du top1 Victor est dans les vrais 5 premiers ?
- Quelle discipline Victor maîtrise le mieux ?
- À partir de quelle confiance Victor est fiable ?
- Y a-t-il des patterns gagnants répétables ?
- Quels hippodromes sont les meilleurs pour Victor ?

Usage :
    python 16_analyser_performance.py
    python 16_analyser_performance.py 2026-05-01 2026-05-31
"""

import sys
import json
import datetime
from datetime import date, timedelta
from auth.supabase_client import get_client


def charger_donnees(d_debut: date, d_fin: date) -> tuple:
    """Charge pronostics et résultats depuis Supabase."""
    client = get_client()
    if not client:
        print("❌ Connexion Supabase échouée")
        return [], []

    # Pronostics
    res_pronos = client.table("pronostics_jour")\
        .select("*")\
        .gte("date", str(d_debut))\
        .lte("date", str(d_fin))\
        .execute()

    # Résultats
    res_results = client.table("historique_courses")\
        .select("*")\
        .gte("date", str(d_debut))\
        .lte("date", str(d_fin))\
        .execute()

    return res_pronos.data or [], res_results.data or []


def analyser(pronos: list, resultats: list) -> dict:
    """
    Pour chaque course où on a un pronostic ET un résultat,
    calcule les métriques de performance.
    """
    # Index des résultats par (date, code_course)
    index_resultats = {}
    for r in resultats:
        if r.get("resultat_reel"):
            cle = (str(r["date"]), r["code_course"])
            index_resultats[cle] = r["resultat_reel"]

    stats = {
        "total"              : 0,
        "top1_dans_top5"     : 0,
        "top1_est_gagnant"   : 0,
        "precision_quinte"   : [],  # nb chevaux corrects sur 5
        "par_discipline"     : {},
        "par_confiance"      : {"<50": [], "50-60": [], "60-70": [], ">70": []},
        "par_hippodrome"     : {},
        "patterns_gagnants"  : [],
        "erreurs_frequentes" : [],
    }

    for p in pronos:
        cle = (str(p["date"]), p["code_course"])
        if cle not in index_resultats:
            continue  # Pas encore de résultat pour cette course

        resultat_str = index_resultats[cle]
        top5_reel    = [int(x.strip()) for x in resultat_str.split("·")
                        if x.strip().isdigit()][:5]

        if not top5_reel:
            continue

        # Décoder le pronostic Victor
        try:
            top8_nums = [int(x) for x in p["top8_nums"].split(",")]
            confiances = [float(x) for x in p["top8_confiances"].split(",")]
            cotes      = [float(x) for x in p["top8_cotes"].split(",")]
        except Exception:
            continue

        if not top8_nums:
            continue

        top5_victor  = top8_nums[:5]
        top1_victor  = top8_nums[0]
        conf_top1    = confiances[0]
        cote_top1    = cotes[0]
        discipline   = p.get("discipline", "INCONNU")
        hippodrome   = p.get("hippodrome", "INCONNU")

        # Métriques
        top1_correct = top1_victor in top5_reel
        est_gagnant  = (len(top5_reel) > 0 and top1_victor == top5_reel[0])
        communs      = len(set(top5_victor) & set(top5_reel))

        stats["total"] += 1
        if top1_correct: stats["top1_dans_top5"] += 1
        if est_gagnant:  stats["top1_est_gagnant"] += 1
        stats["precision_quinte"].append(communs)

        # Par discipline
        if discipline not in stats["par_discipline"]:
            stats["par_discipline"][discipline] = {"total":0,"corrects":0,"gagnants":0,"quinte":[]}
        d = stats["par_discipline"][discipline]
        d["total"] += 1
        if top1_correct: d["corrects"] += 1
        if est_gagnant:  d["gagnants"] += 1
        d["quinte"].append(communs)

        # Par niveau de confiance
        if conf_top1 < 50:   tranche = "<50"
        elif conf_top1 < 60: tranche = "50-60"
        elif conf_top1 < 70: tranche = "60-70"
        else:                tranche = ">70"
        stats["par_confiance"][tranche].append(top1_correct)

        # Par hippodrome
        if hippodrome not in stats["par_hippodrome"]:
            stats["par_hippodrome"][hippodrome] = {"total":0,"corrects":0,"quinte":[]}
        h = stats["par_hippodrome"][hippodrome]
        h["total"] += 1
        if top1_correct: h["corrects"] += 1
        h["quinte"].append(communs)

        # Patterns gagnants
        if top1_correct and conf_top1 >= 65:
            stats["patterns_gagnants"].append({
                "date"      : str(p["date"]),
                "course"    : p["code_course"],
                "hippodrome": hippodrome,
                "discipline": discipline,
                "confiance" : conf_top1,
                "cote"      : cote_top1,
                "communs"   : communs,
            })

        # Erreurs fréquentes (Victor confiant mais faux)
        if not top1_correct and conf_top1 >= 65:
            stats["erreurs_frequentes"].append({
                "date"      : str(p["date"]),
                "course"    : p["code_course"],
                "hippodrome": hippodrome,
                "discipline": discipline,
                "confiance" : conf_top1,
                "cote"      : cote_top1,
                "top1_victor": top1_victor,
                "vrai_top5" : top5_reel,
            })

    return stats


def afficher_rapport(stats: dict, d_debut: date, d_fin: date):
    """Affiche le rapport complet de performance."""
    total = stats["total"]
    if total == 0:
        print("❌ Aucune course avec pronostic ET résultat sur cette période.")
        print("   Lance d'abord le workflow 'pronostics' puis 'soir'.")
        return

    print()
    print("=" * 60)
    print(f"📊 RAPPORT DE PERFORMANCE VICTOR V2")
    print(f"   Du {d_debut} au {d_fin} — {total} courses analysées")
    print("=" * 60)

    # ── Résultats globaux ──
    pct_top5    = stats["top1_dans_top5"] / total * 100
    pct_gagnant = stats["top1_est_gagnant"] / total * 100
    moy_quinte  = sum(stats["precision_quinte"]) / len(stats["precision_quinte"])

    print(f"\n🎯 RÉSULTATS GLOBAUX")
    print(f"  Top1 Victor dans le vrai Top5 : {stats['top1_dans_top5']}/{total} "
          f"({pct_top5:.1f}%)")
    print(f"  Top1 Victor = Vrai Gagnant     : {stats['top1_est_gagnant']}/{total} "
          f"({pct_gagnant:.1f}%)")
    print(f"  Précision Quinté moyenne       : {moy_quinte:.2f}/5 chevaux corrects")

    # ── Par discipline ──
    print(f"\n🏇 PAR DISCIPLINE")
    for disc, d in sorted(stats["par_discipline"].items(),
                          key=lambda x: x[1]["total"], reverse=True):
        if d["total"] < 2:
            continue
        pct = d["corrects"] / d["total"] * 100
        mq  = sum(d["quinte"]) / len(d["quinte"])
        emoji = "✅" if pct >= 65 else ("⚠️" if pct >= 50 else "❌")
        print(f"  {emoji} {disc:<15} : {pct:.0f}% correct · "
              f"{mq:.1f}/5 Quinté · {d['total']} courses")

    # ── Par confiance ──
    print(f"\n📈 FIABILITÉ PAR NIVEAU DE CONFIANCE")
    for tranche in ["<50", "50-60", "60-70", ">70"]:
        vals = stats["par_confiance"][tranche]
        if not vals:
            continue
        pct   = sum(vals) / len(vals) * 100
        emoji = "✅" if pct >= 65 else ("⚠️" if pct >= 50 else "❌")
        print(f"  {emoji} Confiance {tranche}% : {pct:.0f}% correct "
              f"({len(vals)} courses)")

    # ── Par hippodrome (top 5 avec le plus de courses) ──
    print(f"\n📍 TOP HIPPODROMES (min 3 courses)")
    hippos_tri = sorted(
        [(h, d) for h, d in stats["par_hippodrome"].items() if d["total"] >= 3],
        key=lambda x: x[1]["corrects"] / x[1]["total"],
        reverse=True
    )[:8]
    for hippo, d in hippos_tri:
        pct = d["corrects"] / d["total"] * 100
        mq  = sum(d["quinte"]) / len(d["quinte"])
        emoji = "✅" if pct >= 65 else ("⚠️" if pct >= 50 else "❌")
        print(f"  {emoji} {hippo:<20} : {pct:.0f}% · "
              f"{mq:.1f}/5 · {d['total']} courses")

    # ── Patterns gagnants ──
    pg = stats["patterns_gagnants"]
    print(f"\n🏆 PATTERNS GAGNANTS (confiance >65% ET top1 correct)")
    print(f"  {len(pg)} occurrences sur {total} courses")
    if pg:
        # Trouver les disciplines les plus fiables
        disc_gagnants = {}
        for p in pg:
            d = p["discipline"]
            if d not in disc_gagnants:
                disc_gagnants[d] = {"total":0,"moy_conf":[],"moy_cote":[]}
            disc_gagnants[d]["total"] += 1
            disc_gagnants[d]["moy_conf"].append(p["confiance"])
            disc_gagnants[d]["moy_cote"].append(p["cote"])

        print(f"  Disciplines les plus fiables quand confiance >65% :")
        for disc, info in sorted(disc_gagnants.items(),
                                  key=lambda x: x[1]["total"], reverse=True):
            moy_c = sum(info["moy_conf"]) / len(info["moy_conf"])
            moy_k = sum(info["moy_cote"]) / len(info["moy_cote"])
            print(f"    → {disc}: {info['total']} fois · "
                  f"conf moy {moy_c:.0f}% · cote moy {moy_k:.1f}")

    # ── Erreurs fréquentes ──
    ef = stats["erreurs_frequentes"]
    print(f"\n⚠️  ERREURS FRÉQUENTES (confiance >65% mais faux)")
    print(f"  {len(ef)} fois sur {total} courses")
    if ef:
        disc_erreurs = {}
        for e in ef:
            d = e["discipline"]
            disc_erreurs[d] = disc_erreurs.get(d, 0) + 1
        print(f"  Disciplines où Victor se trompe malgré la confiance :")
        for disc, nb in sorted(disc_erreurs.items(),
                                key=lambda x: x[1], reverse=True):
            print(f"    → {disc}: {nb} erreurs")

    # ── Recommandations ──
    print(f"\n💡 RECOMMANDATIONS BASÉES SUR LES DONNÉES")

    # Trouver la discipline la plus fiable
    meilleure_disc = None
    meilleur_pct   = 0
    for disc, d in stats["par_discipline"].items():
        if d["total"] >= 5:
            pct = d["corrects"] / d["total"] * 100
            if pct > meilleur_pct:
                meilleur_pct   = pct
                meilleure_disc = disc

    if meilleure_disc:
        print(f"  ✅ Jouer en priorité le {meilleure_disc} "
              f"({meilleur_pct:.0f}% de réussite)")

    # Seuil de confiance optimal
    meilleur_seuil = None
    meilleur_seuil_pct = 0
    for tranche, vals in stats["par_confiance"].items():
        if len(vals) >= 5:
            pct = sum(vals) / len(vals) * 100
            if pct > meilleur_seuil_pct:
                meilleur_seuil_pct = pct
                meilleur_seuil     = tranche

    if meilleur_seuil:
        print(f"  ✅ Ne jouer que quand confiance {meilleur_seuil}% "
              f"({meilleur_seuil_pct:.0f}% de réussite)")

    # ROI estimé
    if pct_gagnant > 0:
        roi_estime = pct_gagnant / 100 * 5.0 - 1  # estimation grossière cote moy 5
        emoji_roi  = "✅" if roi_estime > 0 else "❌"
        print(f"  {emoji_roi} ROI estimé Gagnant : {roi_estime*100:+.0f}% "
              f"(basé sur cote moyenne 5.0)")

    print("=" * 60)


def main():
    # Période d'analyse
    if len(sys.argv) >= 3:
        d_debut = datetime.datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        d_fin   = datetime.datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
    else:
        # Par défaut : les 30 derniers jours
        d_fin   = date.today()
        d_debut = d_fin - timedelta(days=30)

    print(f"🔍 Analyse du {d_debut} au {d_fin}...")

    pronos, resultats = charger_donnees(d_debut, d_fin)
    print(f"   {len(pronos)} pronostics chargés")
    print(f"   {len(resultats)} résultats chargés")

    if not pronos:
        print("\n⚠️  Aucun pronostic trouvé.")
        print("   Le script 15_sauvegarder_pronostics.py doit tourner d'abord.")
        return

    stats = analyser(pronos, resultats)
    afficher_rapport(stats, d_debut, d_fin)


if __name__ == "__main__":
    main()
