"""
VICTOR V2 — Étape 11 : Entraînement du Superviseur
====================================================
Le Superviseur est un méta-modèle qui apprend les faiblesses de Victor.
Il répond à une question simple : "Victor est-il fiable sur cette course ?"

Entrée  : data/simulation.csv (généré par 10_dataset_simulation.py)
Sortie  : models/superviseur.pkl
          models/superviseur_meta.json

Usage :
    python 11_superviseur.py
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import json
import os
from sklearn.metrics import roc_auc_score, classification_report

DOSSIER_DATA   = "data"
DOSSIER_MODELS = "models"

# Features que le Superviseur va analyser
# Ce sont les signaux de contexte — pas les features des chevaux
FEATURES_SUPERVISEUR = [
    # Signal Victor
    "confiance_top1",      # À quel point Victor est confiant
    "cote_top1",           # La cote du cheval qu'il préfère
    "ecart_top2",          # Est-ce que Victor est sûr ou hésitant ?
    "std_probas",          # Course ouverte ou dominée ?

    # Contexte course
    "discipline_code",     # PLAT, TROT, OBSTACLE...
    "distance",            # Sprint vs Fond
    "nb_partants",         # Petite ou grande course
    "taux_hippo",          # Hippodrome facile ou difficile pour Victor

    # Météo
    "temperature",
    "precipitation",
    "vent_kmh",
    "terrain_lourd",
]

# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

def charger():
    chemin = os.path.join(DOSSIER_DATA, "simulation.csv")
    if not os.path.exists(chemin):
        print("❌ simulation.csv introuvable.")
        print("   Lance d'abord : python 10_dataset_simulation.py")
        exit()

    df = pd.read_csv(chemin, encoding="utf-8-sig")

    # Encoder la discipline en numérique
    disc_map = {"CROSS":0,"OBSTACLE":1,"PLAT":2,"TROT_ATTELE":3,"TROT_MONTE":4}
    df["discipline_code"] = df["discipline"].map(disc_map).fillna(2)

    # Garder seulement les features disponibles
    feats_dispo = [f for f in FEATURES_SUPERVISEUR if f in df.columns]
    manquantes  = [f for f in FEATURES_SUPERVISEUR if f not in df.columns]
    if manquantes:
        print(f"⚠️  Features absentes : {manquantes} — remplacées par 0")
        for f in manquantes:
            df[f] = 0.0

    df = df.dropna(subset=feats_dispo + ["victor_correct"])

    print(f"📥 Simulation : {len(df)} courses")
    print(f"   Victor correct : {df['victor_correct'].sum()} "
          f"({df['victor_correct'].mean()*100:.1f}%)")
    return df, feats_dispo


# ─────────────────────────────────────────────
# ENTRAÎNEMENT
# ─────────────────────────────────────────────

def entrainer_superviseur(df, features):
    """
    Split temporel : les 80% premières courses pour entraîner,
    les 20% dernières pour tester.
    Le Superviseur apprend les patterns d'erreurs passés de Victor.
    """
    n     = len(df)
    seuil = int(n * 0.80)
    train = df.iloc[:seuil]
    test  = df.iloc[seuil:]

    X_train, y_train = train[features], train["victor_correct"]
    X_test,  y_test  = test[features],  test["victor_correct"]

    print(f"\n✂️  Train : {len(train)} | Test : {len(test)}")

    ratio = max(1.0, (y_train == 0).sum() / max((y_train == 1).sum(), 1))

    params = {
        "objective"        : "binary",
        "metric"           : "auc",
        "learning_rate"    : 0.05,
        "n_estimators"     : 500,
        "num_leaves"       : 31,
        "max_depth"        : 5,
        "min_child_samples": 10,
        "scale_pos_weight" : ratio,
        "verbose"          : -1,
        "random_state"     : 42,
    }

    model = lgb.LGBMClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[
            lgb.early_stopping(stopping_rounds=30, verbose=False),
            lgb.log_evaluation(period=100),
        ],
    )

    y_proba = model.predict_proba(X_test)[:, 1]
    auc     = roc_auc_score(y_test, y_proba)
    print(f"\n  ✅ Superviseur AUC : {auc*100:.1f}%")

    # Importance des features
    print("\n── Ce que le Superviseur a appris ──")
    importances = pd.Series(
        model.feature_importances_, index=features
    ).sort_values(ascending=False)
    for feat, imp in importances.head(8).items():
        barre = "█" * int(imp / importances.max() * 20)
        print(f"  {feat:<25} {barre} {imp:.0f}")

    return model, auc, importances.to_dict()


# ─────────────────────────────────────────────
# ANALYSE DES POINTS FAIBLES
# ─────────────────────────────────────────────

def analyser_points_faibles(df, model, features):
    """
    Identifie les situations où Victor se trompe systématiquement.
    C'est le "manuel d'erreurs" que le Superviseur va corriger.
    """
    df = df.copy()
    df["proba_superviseur"] = model.predict_proba(df[features])[:, 1]

    print("\n" + "="*58)
    print("🔍 POINTS FAIBLES DE VICTOR (selon le Superviseur)")
    print("="*58)

    # Situations dangereuses = le Superviseur est peu confiant
    df["risque"] = df["proba_superviseur"] < 0.35

    risque_discipline = df.groupby("discipline").agg(
        risque_moyen=("risque","mean"),
        nb_courses=("risque","count")
    ).sort_values("risque_moyen", ascending=False)

    print("\n── Disciplines à risque ──")
    for disc, row in risque_discipline.iterrows():
        emoji = "🔴" if row["risque_moyen"] > 0.5 else ("🟡" if row["risque_moyen"] > 0.35 else "🟢")
        print(f"  {emoji} {disc:<15} : {row['risque_moyen']*100:.0f}% de courses risquées "
              f"({int(row['nb_courses'])} courses)")

    print("\n── Niveau de confiance Victor vs réalité ──")
    df["tranche"] = pd.cut(df["confiance_top1"],
                            bins=[0,30,45,55,65,100],
                            labels=["<30%","30-45%","45-55%","55-65%",">65%"])
    for t, g2 in df.groupby("tranche", observed=True):
        taux_reel = g2["victor_correct"].mean() * 100
        conf_moy  = g2["confiance_top1"].mean()
        ecart     = conf_moy - taux_reel
        emoji     = "🔴" if ecart > 15 else ("🟡" if ecart > 5 else "🟢")
        print(f"  {emoji} Victor dit {str(t):<8} → réalité {taux_reel:.0f}% "
              f"(écart {ecart:+.0f}%)")

    print("="*58)
    return df


# ─────────────────────────────────────────────
# SAUVEGARDE
# ─────────────────────────────────────────────

def sauvegarder(model, auc, features, importances):
    chemin_model = os.path.join(DOSSIER_MODELS, "superviseur.pkl")
    chemin_meta  = os.path.join(DOSSIER_MODELS, "superviseur_meta.json")

    joblib.dump(model, chemin_model)

    meta = {
        "auc"         : round(auc, 4),
        "features"    : features,
        "importances" : {k: float(v) for k, v in importances.items()},
        "seuil_confiance": 0.40,  # En dessous = Victor peu fiable → réduire mise
        "seuil_danger"   : 0.30,  # En dessous = Victor dangereux → éviter
    }
    with open(chemin_meta, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n💾 Sauvegardé : {chemin_model}")
    print(f"   AUC Superviseur : {auc*100:.1f}%")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("🧠 VICTOR V2 — ENTRAÎNEMENT DU SUPERVISEUR")
    print("="*58)

    df, features = charger()
    model, auc, importances = entrainer_superviseur(df, features)
    analyser_points_faibles(df, model, features)
    sauvegarder(model, auc, features, importances)

    print("\n" + "="*58)
    print("🏆 Superviseur entraîné !")
    print("   Il connaît maintenant les faiblesses de Victor.")
    print("\n   Lance maintenant :")
    print("   streamlit run 5_interface_web.py")
    print("   (le Superviseur s'intègre automatiquement)")
    print("="*58)

if __name__ == "__main__":
    main()