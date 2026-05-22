# 🏇 VICTOR V2 — Guide des Commandes

---

## 🌅 CHAQUE MATIN (10 minutes · dans cet ordre)

```bash
python 6_maj_quotidienne.py
python 2_feature_engineering.py
streamlit run 5_interface_web.py
```

| Commande | Ce qu'elle fait | Durée |
|---|---|---|
| `6_maj_quotidienne.py` | Télécharge les résultats d'hier | ~3 min |
| `2_feature_engineering.py` | Recalcule les statistiques | ~4 min |
| `streamlit run 5_interface_web.py` | Lance le dashboard pour tes abonnés | Instantané |

---

## 📅 CHAQUE DIMANCHE (15 minutes · dans cet ordre)

```bash
python 3_entrainer_modele.py
python 10_dataset_simulation.py
python 11_superviseur.py
```

| Commande | Ce qu'elle fait | Durée |
|---|---|---|
| `3_entrainer_modele.py` | Réentraîne le modèle IA avec la semaine écoulée | ~5 min |
| `10_dataset_simulation.py` | Génère la mémoire du Superviseur | ~5 min |
| `11_superviseur.py` | Entraîne le Superviseur sur les nouvelles erreurs | ~3 min |

> ⚠️ Toujours lancer `3_entrainer_modele.py` AVANT `10_dataset_simulation.py`

---

## 📆 CHAQUE 1ER DU MOIS (30 minutes · dans cet ordre)

```bash
python 9_optimiser_optuna.py
python 7_backtesting.py
```

| Commande | Ce qu'elle fait | Durée |
|---|---|---|
| `9_optimiser_optuna.py` | Cherche les meilleurs paramètres LightGBM (100 essais) | ~25 min |
| `7_backtesting.py` | Vérifie que le ROI reste positif | ~2 min |

> 💡 Si le backtesting montre un ROI négatif → relance Optuna avec N_TRIALS=200

---

## 🔧 PONCTUEL (quand nécessaire)

### Nouvelle installation / premier lancement

```bash
python 1_collecteur_pmu.py          # Collecte les données historiques (300 jours)
python 2_feature_engineering.py     # Calcule les features
python 3_entrainer_modele.py        # Entraîne le modèle
python 10_dataset_simulation.py     # Génère la mémoire Superviseur
python 11_superviseur.py            # Entraîne le Superviseur
python 9_optimiser_optuna.py        # Optimise les paramètres
streamlit run 5_interface_web.py    # Lance l'interface
```

### Correction des cotes (si cotes aberrantes)

```bash
python fix_cote.py                  # Corrige les cotes dans raw_courses.csv
python 2_feature_engineering.py     # Recalcule les features
python 3_entrainer_modele.py        # Réentraîne le modèle
```

### Forcer un recalcul complet

```bash
python 2_feature_engineering.py
python 3_entrainer_modele.py
python 10_dataset_simulation.py
python 11_superviseur.py
streamlit run 5_interface_web.py
```

---

## 🖥️ INTERFACE STREAMLIT — Commandes utiles

```bash
# Lancer l'interface
streamlit run 5_interface_web.py

# Lancer sur un port différent (si 8501 est occupé)
streamlit run 5_interface_web.py --server.port 8502

# Accéder au panneau admin
# Dans le navigateur : http://localhost:8501?page=admin
```

---

## 📁 FICHIERS PRODUITS PAR CHAQUE COMMANDE

```
data/
  raw_courses.csv          ← produit par 1 et 6
  dataset_final.csv        ← produit par 2
  simulation.csv           ← produit par 10
  meteo_cache.csv          ← produit par 8 (automatique)

models/
  victor_v2_GLOBAL.pkl     ← produit par 3
  victor_v2_PLAT.pkl       ← produit par 3
  victor_v2_TROT_ATTELE.pkl ← produit par 3
  victor_v2_TROT_MONTE.pkl ← produit par 3
  victor_v2_CROSS.pkl      ← produit par 3
  victor_v2_OBSTACLE.pkl   ← produit par 3
  superviseur.pkl          ← produit par 11
  features.json            ← produit par 3
  best_params.json         ← produit par 9
  superviseur_meta.json    ← produit par 11
```

---

## ⚡ RÉSUMÉ EN 1 IMAGE

```
LUNDI → VENDREDI (matin)    DIMANCHE (matin)       1ER DU MOIS
─────────────────────────   ────────────────────   ─────────────────
python 6_maj_quotidienne     python 3_entrainer     python 9_optuna
python 2_feature_eng         python 10_simulation   python 7_backtest
streamlit run 5_interface    python 11_superviseur
```

---

## ❗ RÈGLES D'OR

1. **Ne jamais sauter le `6_maj_quotidienne.py`** — sans lui le modèle ne voit pas les résultats d'hier
2. **Toujours lancer `2_feature_engineering.py` après `6_maj_quotidienne.py`** — sinon les features sont obsolètes
3. **Ne pas lancer `3_entrainer_modele.py` tous les jours** — une fois par semaine suffit et c'est moins lourd
4. **Si tu changes `utils.py`** → relance toute la chaîne (2 → 3 → 10 → 11)
5. **Si Streamlit est déjà ouvert** → clique "🔄 Recharger le modèle IA" après un réentraînement

---

*Victor V2 — dernière mise à jour : Mai 2026*