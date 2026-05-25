import requests

url = "https://offline.turfinfo.api.pmu.fr/rest/client/7/programme/23052026/R1/C4/participants"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
params = {"specialisation": "OFFLINE"}

response = requests.get(url, headers=headers, params=params)
data = response.json()

if "participants" in data:
    for p in data["participants"]:
        # On vérifie si la clé existe et sa valeur
        est_np = p.get("estNonPartant", "Clé non trouvée")
        nom = p.get("nom", "Inconnu")
        print(f"Cheval: {nom} | Non-partant? -> {est_np}")
else:
    print("Erreur : Pas de liste de participants trouvée.")