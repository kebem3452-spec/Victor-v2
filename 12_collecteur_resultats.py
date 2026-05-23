import requests
import datetime
from auth.supabase_client import get_supabase_client

supabase = get_supabase_client()

def collecter_resultats_jour():
    date_str = datetime.date.today().strftime("%d%m%Y")
    # URL PMU pour les résultats
    url = f"https://offline.turfinfo.api.pmu.fr/rest/client/7/programme/{date_str}"
    
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).json()
        for reunion in r.get("programme", {}).get("reunions", []):
            for course in reunion.get("courses", []):
                if course.get("statut") == "OFFICIEL": # Course terminée
                    code = f"R{reunion['numOfficiel']}C{course['numOrdre']}"
                    resultat = course.get("arriveeDefinitive", [])
                    
                    # Mise à jour dans Supabase
                    supabase.table("historique_courses").update({
                        "resultat_reel": str(resultat)
                    }).eq("code_course", code).execute()
        print("✅ Résultats collectés et mis à jour.")
    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    collecter_resultats_jour()