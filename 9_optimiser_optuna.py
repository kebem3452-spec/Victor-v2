"""
VICTOR V2 — Module 9 : Optimisation Optuna
============================================
Usage :
    python 9_optimiser_optuna.py

Optuna teste automatiquement des centaines de combinaisons
de paramètres LightGBM et trouve la meilleure configuration.

Analogie : au lieu de régler manuellement les boutons d'une radio
pour trouver la meilleure réception, Optuna les règle tous seul
en 100 essais et te dit quelle combinaison donne le meilleur son.

Durée : environ 20-40 minutes selon ta machine.
Résultat : models/best_params.json + modèle réentraîné avec ces params.
"""

import pandas as pd
import numpy as np
import lightgbm as lgb
import joblib
import json
import os
import optuna
from sklearn.metrics import roc_auc_score

optuna.logging.set_verbosity(optuna.logging.WARNING)

DOSSIER_DATA   = "data"
DOSSIER_MODELS = "models"
N_TRIALS       = 100   # Nombre d'essais (plus = meilleur mais plus long)
                        # 50 = rapide (~10 min), 100 = bon (~25 min), 200 = excellent (~1h)

# ─────────────────────────────────────────────
# CHARGEMENT
# ─────────────────────────────────────────────

def charger():
    chemin   = os.path.join(DOSSIER_DATA, "dataset_final.csv")
    meta_c   = os.path.join(DOSSIER_MODELS, "features.json")

    df = pd.read_csv(chemin, encoding="utf-8-sig")

    with open(meta_c) as f:
        meta = json.load(f)
    features = meta.get("features", [])
    features = [f for f in features if f in df.columns]

    df = df.dropna(subset=features + ["succes"])

    n     = len(df)
    seuil = int(n * 0.80)
    train = df.iloc[:seuil]
    test  = df.iloc[seuil:]

    print(f"📥 Train : {len(train)} | Test : {len(test)} | Features : {len(features)}")
    return train, test, features

# ─────────────────────────────────────────────
# FONCTION OBJECTIF OPTUNA
# ─────────────────────────────────────────────

def creer_objectif(train, test, features):
    """
    Retourne la fonction que Optuna va optimiser.
    Chaque 'trial' = un essai avec des paramètres différents.
    Optuna cherche à MAXIMISER l'AUC.
    """
    X_train, y_train = train[features], train["succes"]
    X_test,  y_test  = test[features],  test["succes"]
    ratio = max(1.0, (y_train == 0).sum() / max((y_train == 1).sum(), 1))

    def objectif(trial):
        params = {
            "objective"         : "binary",
            "metric"            : "auc",
            "verbose"           : -1,
            "random_state"      : 42,
            "scale_pos_weight"  : ratio,

            # Paramètres explorés par Optuna
            # suggest_int = entier entre min et max
            # suggest_float = décimal entre min et max
            "learning_rate"     : trial.suggest_float("learning_rate",   0.01, 0.15, log=True),
            "n_estimators"      : trial.suggest_int("n_estimators",       300, 2000),
            "num_leaves"        : trial.suggest_int("num_leaves",          20,  200),
            "max_depth"         : trial.suggest_int("max_depth",            4,   12),
            "min_child_samples" : trial.suggest_int("min_child_samples",    5,   50),
            "feature_fraction"  : trial.suggest_float("feature_fraction", 0.5,  1.0),
            "bagging_fraction"  : trial.suggest_float("bagging_fraction", 0.5,  1.0),
            "bagging_freq"      : trial.suggest_int("bagging_freq",         1,   10),
            "reg_alpha"         : trial.suggest_float("reg_alpha",        0.0,  1.0),
            "reg_lambda"        : trial.suggest_float("reg_lambda",       0.0,  1.0),
            "min_split_gain"    : trial.suggest_float("min_split_gain",   0.0,  0.5),
        }

        model = lgb.LGBMClassifier(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[
                lgb.early_stopping(stopping_rounds=30, verbose=False),
                lgb.log_evaluation(period=-1),
            ],
        )

        y_proba = model.predict_proba(X_test)[:, 1]
        return roc_auc_score(y_test, y_proba)

    return objectif

# ─────────────────────────────────────────────
# ENTRAÎNEMENT FINAL AVEC LES MEILLEURS PARAMS
# ─────────────────────────────────────────────

def entrainer_meilleurs_params(train, test, features, best_params):
    X_train, y_train = train[features], train["succes"]
    X_test,  y_test  = test[features],  test["succes"]
    ratio = max(1.0, (y_train == 0).sum() / max((y_train == 1).sum(), 1))

    params_finaux = {**best_params, "objective": "binary", "metric": "auc",
                     "verbose": -1, "random_state": 42, "scale_pos_weight": ratio}

    model = lgb.LGBMClassifier(**params_finaux)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50, verbose=False),
            lgb.log_evaluation(period=100),
        ],
    )

    y_proba = model.predict_proba(X_test)[:, 1]
    auc     = roc_auc_score(y_test, y_proba)
    return model, auc

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("🔬 VICTOR V2 — OPTIMISATION OPTUNA")
    print("=" * 55)
    print(f"   Nombre d'essais : {N_TRIALS}")
    print(f"   (modifie N_TRIALS en haut du fichier pour plus/moins)")
    print("=" * 55)

    train, test, features = charger()

    # Lancer l'optimisation
    study = optuna.create_study(direction="maximize")
    print(f"\n🚀 Démarrage — {N_TRIALS} essais en cours...")
    print("   (une barre de progression s'affiche ci-dessous)\n")

    objectif = creer_objectif(train, test, features)

    # Barre de progression manuelle
    from tqdm import tqdm
    with tqdm(total=N_TRIALS, desc="Optuna", unit="essai") as pbar:
        def callback(study, trial):
            pbar.update(1)
            pbar.set_postfix({"meilleur AUC": f"{study.best_value*100:.2f}%"})
        study.optimize(objectif, n_trials=N_TRIALS, callbacks=[callback])

    best_params = study.best_params
    best_auc    = study.best_value

    print(f"\n✅ Optimisation terminée !")
    print(f"   Meilleurs paramètres trouvés — AUC : {best_auc*100:.2f}%")
    print()
    for k, v in best_params.items():
        print(f"   {k:<25} : {v}")

    # Réentraîner avec les meilleurs params
    print(f"\n🏋️  Réentraînement final avec les meilleurs paramètres...")
    model_opt, auc_final = entrainer_meilleurs_params(train, test, features, best_params)
    print(f"   AUC final : {auc_final*100:.2f}%")

    # Comparer avec le modèle actuel
    meta_c = os.path.join(DOSSIER_MODELS, "features.json")
    with open(meta_c) as f:
        meta = json.load(f)
    auc_actuel = meta.get("auc", 0.0)

    gain = (auc_final - auc_actuel) * 100
    print(f"\n📊 Comparaison :")
    print(f"   AUC avant Optuna : {auc_actuel*100:.2f}%")
    print(f"   AUC après Optuna : {auc_final*100:.2f}%")
    print(f"   Gain             : {gain:+.2f}%")

    # Sauvegarder
    chemin_params = os.path.join(DOSSIER_MODELS, "best_params.json")
    with open(chemin_params, "w") as f:
        json.dump({"params": best_params, "auc": round(auc_final, 4)}, f, indent=2)

    # Remplacer le modèle global seulement si meilleur
    if auc_final > auc_actuel:
        joblib.dump(model_opt, os.path.join(DOSSIER_MODELS, "victor_v2.pkl"))
        joblib.dump(model_opt, os.path.join(DOSSIER_MODELS, "victor_v2_GLOBAL.pkl"))
        meta["auc"]      = round(auc_final, 4)
        meta["features"] = features
        if "modeles" in meta:
            meta["modeles"]["GLOBAL"]["auc"] = round(auc_final, 4)
        with open(meta_c, "w") as f:
            json.dump(meta, f, indent=2)
        print(f"\n💾 Nouveau modèle sauvegardé (meilleur que l'ancien) !")
    else:
        print(f"\n⚠️  L'ancien modèle est meilleur — on le garde.")

    print("\n" + "=" * 55)
    print("🏆 Optimisation Optuna terminée !")
    print(f"   Paramètres sauvegardés dans : {chemin_params}")
    print("=" * 55)

if __name__ == "__main__":
    main()