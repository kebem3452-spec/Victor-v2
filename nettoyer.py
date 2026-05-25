def nettoyer_fichier(chemin):
    with open(chemin, 'r', encoding='utf-8-sig') as f:
        lignes = f.readlines()
    
    # On garde seulement les lignes qui ne contiennent pas les marqueurs Git
    lignes_propres = [l for l in lignes if not any(m in l for m in ['<<<<<<<', '=======', '>>>>>>>'])]
    
    with open(chemin, 'w', encoding='utf-8-sig') as f:
        f.writelines(lignes_propres)
    print(f"Nettoyage terminé pour {chemin}")

nettoyer_fichier('data/dataset_final.csv')