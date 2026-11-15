import os
import re
import unicodedata
import numpy as np
from sentence_transformers import SentenceTransformer

# 1. Chargement du modèle (hors-ligne si décompressé dans models/, sinon en ligne)
CHEMIN_MODELE_LOCAL = "models/modele_terrasense_final"
if os.path.exists(CHEMIN_MODELE_LOCAL):
    model = SentenceTransformer(CHEMIN_MODELE_LOCAL)
else:
    model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")

# 2. Catalogue des 11 variables (Climat 2003-2026 + SoilGrids + Giovanni)
CATALOGUE_VARIABLES = [
    {"id": "Humidite_Sol_Surface", "famille": "humidite_surface", "source": "climat_villes", "couverture": "2003-2026", "titre": "Humidité du sol en surface (0–7 cm)", "description": "Teneur en eau et saturation de la couche supérieure du sol près de la surface (0-7 cm), stagnation de l'eau, surface soil moisture."},
    {"id": "Humidite_Sol_Racines", "famille": "humidite_racines", "source": "climat_villes", "couverture": "2003-2026", "titre": "Humidité du sol aux racines (28–100 cm)", "description": "Réserve d'eau disponible profondément dans la zone racinaire (28-100 cm), sécheresse agricole, root zone water depletion."},
    {"id": "Precipitations_mm", "famille": "precipitations", "source": "climat_villes", "couverture": "2003-2026", "titre": "Précipitations mensuelles (mm)", "description": "Quantité de pluie tombée chaque mois, pluviométrie mensuelle, orages, monthly rainfall precipitation."},
    {"id": "Temp_Sol_Celsius", "famille": "temperature_sol", "source": "climat_villes", "couverture": "2003-2026", "titre": "Température du sol (°C)", "description": "Température du sol en degrés Celsius, chaleur thermique de la terre en surface et en profondeur, soil temperature."},
    {"id": "Evapotranspiration_mm", "famille": "evapotranspiration", "source": "climat_villes", "couverture": "2003-2026", "titre": "Évapotranspiration mensuelle (mm)", "description": "Perte d'eau du sol et transpiration des plantes vers l'atmosphère, bilan hydrique, evapotranspiration."},
    {"id": "Argile_Pct", "famille": "texture_argile", "source": "soilgrids_regions", "couverture": "statique_0_200cm", "titre": "Teneur en argile du sous-sol (%)", "description": "Composition naturelle du terrain, texture argileuse de 0 à 200 cm qui bloque l'absorption de l'eau et favorise la stagnation, soil clay content."},
    {"id": "Azote", "famille": "nutriments_azote", "source": "soilgrids_regions", "couverture": "statique_0_200cm", "titre": "Azote total du sol (cg/kg)", "description": "Richesse nutritive des terres, nutriments naturels disponibles pour la fertilité agricole, soil nitrogen fertility."},
    {"id": "Carbone_Organique", "famille": "carbone_organique", "source": "soilgrids_regions", "couverture": "statique_0_200cm", "titre": "Carbone organique du sol (dg/kg)", "description": "Teneur en matière organique, humus, santé biologique durable des sols agricoles, soil organic carbon."},
    {"id": "pH", "famille": "acidite_ph", "source": "soilgrids_regions", "couverture": "statique_0_200cm", "titre": "Potentiel Hydrogène (pH eau)", "description": "Degré d'acidité ou d'alcalinité chimique du sol de 0 à 200 cm, soil pH acidity."},
    {"id": "GLDAS21_RUNOFF", "famille": "ruissellement", "source": "giovanni", "couverture": "2002-2014", "titre": "Ruissellement de surface (NASA GLDAS)", "description": "Écoulements d'eau à la surface du sol après les fortes pluies, érosion des pentes, surface water runoff."},
    {"id": "MYD08_AOD", "famille": "aerosols_air", "source": "giovanni", "couverture": "2002-2014", "titre": "Épaisseur optique des aérosols (NASA MODIS)", "description": "Matières et poussières transportées dans l'air par les vents, brume sèche de l'Harmattan, atmospheric dust aerosols."}
]

VAR_TEXTS = [f"{v['titre']}. {v['description']}" for v in CATALOGUE_VARIABLES]
VAR_EMBEDDINGS = model.encode(VAR_TEXTS, normalize_embeddings=True)
REFERENTIEL_VILLES = {
    "maroua": ("Maroua", "Extreme-Nord"), "kaele": ("Maroua", "Extreme-Nord"), "maga": ("Maroua", "Extreme-Nord"),
    "garoua": ("Garoua", "Nord"), "ngaoundere": ("Ngaoundere", "Adamaoua"),
    "bafoussam": ("Bafoussam", "Ouest"), "bamenda": ("Bamenda", "Nord-Ouest"),
    "douala": ("Douala", "Littoral"), "bonaberi": ("Douala", "Littoral"), "edea": ("Douala", "Littoral"),
    "buea": ("Buea", "Sud-Ouest"), "limbe": ("Buea", "Sud-Ouest"),
    "yaounde": ("Yaounde", "Centre"), "bafia": ("Yaounde", "Centre"),
    "bertoua": ("Bertoua", "Est"), "ebolowa": ("Ebolowa", "Sud")
}

def _normaliser_texte(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")

def detecter_ville_cameroun(requete: str) -> dict:
    req_norm = _normaliser_texte(requete)
    for mot_cle, (ville, region) in REFERENTIEL_VILLES.items():
        if re.search(rf"\b{mot_cle}\b", req_norm):
            cle = f"{region}_{ville}"
            return {
                "ville": ville,
                "region": region,
                "fichiers": {
                    "climat": f"data/climat_villes/climat_{cle}.csv",
                    "soilgrids": f"data/soilgrids_regions/soilgrids_{cle}.csv",
                    "giovanni": f"data/giovanni/giovanni_{cle}.csv"
                }
            }
    return {
        "ville": "Yaounde (Par défaut)",
        "region": "Centre",
        "fichiers": {
            "climat": "data/climat_villes/climat_Centre_Yaounde.csv",
            "soilgrids": "data/soilgrids_regions/soilgrids_Centre_Yaounde.csv",
            "giovanni": "data/giovanni/giovanni_Centre_Yaounde.csv"
        }
    }
def analyser_requete(requete: str, top_k: int = 5) -> dict:
    # Découpage sur la ponctuation et les mots d'opposition (FR + EN)
    motif = (
        r'[.!?;:]|'
        r',\s*(?=(?:mais|cependant|sans|hormis|sauf|ni|but|however|except|without|while|excluding)\b)|'
        r'\s+(?=(?:but not|but exclude|sans pour autant|en excluant)\b)'
    )
    segments = re.split(motif, requete, flags=re.IGNORECASE)

    marqueurs_negatifs = [
        "ne t'occupe pas", "ne me parlez pas", "ne m'intéresse pas", "sans pour autant",
        "il serait inutile", "il serait également superflu", "fais abstraction", "laisse de côté",
        "hormis", "sauf", "mais pas", "en excluant", "ce n'est pas",
        "do not", "don't", "exclude", "excluding", "without", "ignore", "avoid", "but not", "except"
    ]

    phrases_pos = [s.strip() for s in segments if len(s.strip()) >= 6 and not any(n in s.lower() for n in marqueurs_negatifs)]
    phrases_neg = [s.strip() for s in segments if len(s.strip()) >= 6 and any(n in s.lower() for n in marqueurs_negatifs)]
    if not phrases_pos:
        phrases_pos = [requete]

    # Encodage multi-phrases
    emb_pos = model.encode(phrases_pos, normalize_embeddings=True)
    sims_pos_max = np.max(VAR_EMBEDDINGS @ emb_pos.T, axis=1)
    sims_neg_max = np.max(VAR_EMBEDDINGS @ model.encode(phrases_neg, normalize_embeddings=True).T, axis=1) if phrases_neg else np.zeros(len(CATALOGUE_VARIABLES))

    besoin_actuel = any(m in requete.lower() for m in ["aujourd'hui", "actuellement", "récent", "actuelle", "jusqu'à", "today", "current", "recent", "2026"])

    candidats, bannies = [], []
    for i, var_info in enumerate(CATALOGUE_VARIABLES):
        s_sem, s_neg = float(sims_pos_max[i]), float(sims_neg_max[i])

        # Hard Filter : Bannissement strict des variables exclues par négation
        if s_neg > 0.34 and s_neg >= (s_sem - 0.04):
            bannies.append({"id": var_info["id"], "raison": f"Exclue par négation (Score négatif: {s_neg:.2f})"})
            continue

        s_temp = 1.0 if var_info["couverture"] in ["2003-2026", "statique_0_200cm"] else (0.45 if besoin_actuel else 0.85)
        s_final = (0.70 * s_sem) + (0.30 * s_temp)
        candidats.append((s_final, var_info))

    # Tri et déduplication par famille physique
    candidats.sort(key=lambda x: x[0], reverse=True)
    selection, familles_vues = [], set()
    for s_final, var_info in candidats:
        if var_info["famille"] not in familles_vues and len(selection) < top_k:
            selection.append({
                "id": var_info["id"],
                "titre": var_info["titre"],
                "source": var_info["source"],
                "score": round(s_final, 4)
            })
            familles_vues.add(var_info["famille"])

    return {
        "localisation": detecter_ville_cameroun(requete),
        "variables_retenues": selection,
        "variables_bannies": bannies
    }
if __name__ == "__main__":
    requete_en = "Analyze root zone water depletion and soil nitrogen fertility in Maroua, but exclude surface temperature and Harmattan dust."
    requete_fr = "Autour de Bonabéri à Douala, l'eau stagne en surface, les réserves profondes baissent et le terrain bloque l'absorption. Vérifie la richesse nutritive et la matière organique, sans mesurer la pluie mensuelle ni la température du sol."

    for req in [requete_en, requete_fr]:
        res = analyser_requete(req, top_k=5)
        print(f"\n📍 Ville : {res['localisation']['ville']} -> {res['localisation']['fichiers']['climat']}")
        print("✅ Retenues :", [v["id"] for v in res["variables_retenues"]])
        print("🚫 Bannies  :", [b["id"] for b in res["variables_bannies"]])
