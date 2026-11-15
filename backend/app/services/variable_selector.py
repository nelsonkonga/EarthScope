"""Retrieval of the variables closest to a question.

The ranking, the negation filter and the family deduplication follow the TerraSense
selector. Embeddings come from the local sentence-transformer when it is installed
and a model can be loaded. Otherwise the same scoring runs on lexical vectors, so the
API still answers without downloading a model.
"""

from __future__ import annotations

import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np

# earthscope_id is set only when this backend publishes a series for that concept.
CATALOGUE_VARIABLES = [
    {
        "id": "Humidite_Sol_Surface",
        "earthscope_id": "var_soil_moisture",
        "famille": "humidite_surface",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Humidité du sol en surface (0–10 cm)",
        "description": "Teneur en eau et saturation de la couche supérieure du sol près de la surface, stagnation de l'eau, surface soil moisture.",
    },
    {
        "id": "Humidite_Sol_Racines",
        "earthscope_id": "var_soil_moisture_deep",
        "famille": "humidite_racines",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Humidité du sol en profondeur (10–40 cm)",
        "description": "Réserve d'eau plus profonde, sécheresse du sol profond, root zone water, humidité racinaire approchée par la couche 10-40 cm.",
    },
    {
        "id": "Precipitations_mm",
        "earthscope_id": None,
        "famille": "precipitations",
        "source": "climat_villes",
        "couverture": "2003-2026",
        "titre": "Précipitations mensuelles (mm)",
        "description": "Quantité de pluie tombée chaque mois, pluviométrie mensuelle, orages, monthly rainfall precipitation.",
    },
    {
        "id": "Temp_Sol_Celsius",
        "earthscope_id": "var_soil_temp",
        "famille": "temperature_sol",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Température du sol (°C)",
        "description": "Température du sol en degrés Celsius, chaleur thermique de la terre en surface, soil temperature.",
    },
    {
        "id": "Temp_Sol_Profond",
        "earthscope_id": "var_soil_temp_deep",
        "famille": "temperature_sol_profond",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Température du sol profond (10–40 cm)",
        "description": "Température du sol en profondeur, couche 10 à 40 cm, chaleur plus sourde, deep soil temperature.",
    },
    {
        "id": "Evapotranspiration_mm",
        "earthscope_id": "var_evaporation",
        "famille": "evapotranspiration",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Évaporation mensuelle",
        "description": "Perte d'eau du sol vers l'atmosphère, évaporation, bilan hydrique, evapotranspiration.",
    },
    {
        "id": "Argile_Pct",
        "earthscope_id": None,
        "famille": "texture_argile",
        "source": "soilgrids_regions",
        "couverture": "statique_0_200cm",
        "titre": "Teneur en argile du sous-sol (%)",
        "description": "Composition naturelle du terrain, texture argileuse qui bloque l'absorption de l'eau et favorise la stagnation, soil clay content.",
    },
    {
        "id": "Azote",
        "earthscope_id": None,
        "famille": "nutriments_azote",
        "source": "soilgrids_regions",
        "couverture": "statique_0_200cm",
        "titre": "Azote total du sol",
        "description": "Richesse nutritive des terres, nutriments naturels, fertilité agricole, soil nitrogen fertility.",
    },
    {
        "id": "Carbone_Organique",
        "earthscope_id": None,
        "famille": "carbone_organique",
        "source": "soilgrids_regions",
        "couverture": "statique_0_200cm",
        "titre": "Carbone organique du sol",
        "description": "Teneur en matière organique, humus, santé biologique des sols, soil organic carbon.",
    },
    {
        "id": "pH",
        "earthscope_id": None,
        "famille": "acidite_ph",
        "source": "soilgrids_regions",
        "couverture": "statique_0_200cm",
        "titre": "Potentiel hydrogène (pH eau)",
        "description": "Degré d'acidité ou d'alcalinité chimique du sol, soil pH acidity.",
    },
    {
        "id": "GLDAS21_RUNOFF",
        "earthscope_id": "var_runoff",
        "famille": "ruissellement",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Ruissellement de surface (NASA GLDAS)",
        "description": "Écoulements d'eau à la surface du sol après les pluies, érosion, surface water runoff.",
    },
    {
        "id": "MYD08_AOD",
        "earthscope_id": "var_aod",
        "famille": "aerosols_air",
        "source": "giovanni",
        "couverture": "2002-2014",
        "titre": "Épaisseur optique des aérosols (NASA MODIS)",
        "description": "Matières et poussières transportées dans l'air, brume sèche de l'Harmattan, atmospheric dust aerosols, épaisseur optique.",
    },
]

VAR_TEXTS = [f"{item['titre']}. {item['description']}" for item in CATALOGUE_VARIABLES]
REFERENTIEL_VILLES = {
    "maroua": ("Maroua", "Extreme-Nord"),
    "kaele": ("Maroua", "Extreme-Nord"),
    "maga": ("Maroua", "Extreme-Nord"),
    "garoua": ("Garoua", "Nord"),
    "ngaoundere": ("Ngaoundere", "Adamaoua"),
    "bafoussam": ("Bafoussam", "Ouest"),
    "bamenda": ("Bamenda", "Nord-Ouest"),
    "douala": ("Douala", "Littoral"),
    "bonaberi": ("Douala", "Littoral"),
    "edea": ("Douala", "Littoral"),
    "buea": ("Buea", "Sud-Ouest"),
    "limbe": ("Buea", "Sud-Ouest"),
    "yaounde": ("Yaounde", "Centre"),
    "bafia": ("Yaounde", "Centre"),
    "bertoua": ("Bertoua", "Est"),
    "ebolowa": ("Ebolowa", "Sud"),
}

_SPLIT = re.compile(
    r"[.!?;:]|"
    r",\s*(?=(?:mais|cependant|sans|hormis|sauf|ni|but|however|except|without|while|excluding)\b)|"
    r"\s+(?=(?:but not|but exclude|sans pour autant|en excluant)\b)",
    re.IGNORECASE,
)
_NEGATIVE = (
    "ne t'occupe pas",
    "ne me parlez pas",
    "ne m'intéresse pas",
    "sans pour autant",
    "il serait inutile",
    "il serait également superflu",
    "fais abstraction",
    "laisse de côté",
    "hormis",
    "sauf",
    "mais pas",
    "en excluant",
    "ce n'est pas",
    "do not",
    "don't",
    "exclude",
    "excluding",
    "without",
    "ignore",
    "avoid",
    "but not",
    "except",
)
_CURRENT = ("aujourd'hui", "actuellement", "récent", "actuelle", "jusqu'à", "today", "current", "recent", "2026")
_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "modele_terrasense_final"


def _normaliser_texte(texte: str) -> str:
    return "".join(character for character in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(character) != "Mn")


def detecter_ville_cameroun(requete: str) -> dict:
    folded = _normaliser_texte(requete)
    for keyword, (ville, region) in REFERENTIEL_VILLES.items():
        if re.search(rf"\b{keyword}\b", folded):
            key = f"{region}_{ville}"
            return {
                "ville": ville,
                "region": region,
                "fichiers": {
                    "climat": f"data/climat_villes/climat_{key}.csv",
                    "soilgrids": f"data/soilgrids_regions/soilgrids_{key}.csv",
                    "giovanni": f"data/giovanni/giovanni_{key}.csv",
                },
            }
    return {
        "ville": "Yaounde (Par défaut)",
        "region": "Centre",
        "fichiers": {
            "climat": "data/climat_villes/climat_Centre_Yaounde.csv",
            "soilgrids": "data/soilgrids_regions/soilgrids_Centre_Yaounde.csv",
            "giovanni": "data/giovanni/giovanni_Centre_Yaounde.csv",
        },
    }


def _tokens(texte: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normaliser_texte(texte))


@lru_cache(maxsize=1)
def _vocabulary() -> dict[str, int]:
    words = {token for text in VAR_TEXTS for token in _tokens(text)}
    return {word: index for index, word in enumerate(sorted(words))}


def _lexical_embeddings(texts: list[str]) -> np.ndarray:
    vocabulary = _vocabulary()
    width = max(len(vocabulary), 1)
    matrix = np.zeros((len(texts), width), dtype=float)
    for row, text in enumerate(texts):
        for token in _tokens(text):
            column = vocabulary.get(token)
            if column is not None:
                matrix[row, column] += 1.0
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def _transformer():
    if os.environ.get("EARTHSCOPE_RETRIEVAL", "auto") == "lexical":
        return None
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    name = str(_MODEL_DIR) if _MODEL_DIR.exists() else "paraphrase-multilingual-mpnet-base-v2"
    try:
        return SentenceTransformer(name)
    except Exception:
        return None


@lru_cache(maxsize=1)
def _catalogue_embeddings() -> np.ndarray:
    model = _transformer()
    if model is not None:
        return np.asarray(model.encode(VAR_TEXTS, normalize_embeddings=True))
    return _lexical_embeddings(VAR_TEXTS)


def _encode(texts: list[str]) -> np.ndarray:
    model = _transformer()
    if model is not None:
        return np.asarray(model.encode(texts, normalize_embeddings=True))
    return _lexical_embeddings(texts)


def analyser_requete(requete: str, top_k: int = 3) -> dict:
    """Return at most ``top_k`` variables, one per physical family, after dropping negations."""
    segments = _SPLIT.split(requete)
    phrases_pos = [segment.strip() for segment in segments if len(segment.strip()) >= 6 and not any(marker in segment.lower() for marker in _NEGATIVE)]
    phrases_neg = [segment.strip() for segment in segments if len(segment.strip()) >= 6 and any(marker in segment.lower() for marker in _NEGATIVE)]
    if not phrases_pos:
        phrases_pos = [requete]

    catalogue = _catalogue_embeddings()
    positive = _encode(phrases_pos)
    positive_max = np.max(catalogue @ positive.T, axis=1)
    if phrases_neg:
        negative = _encode(phrases_neg)
        negative_max = np.max(catalogue @ negative.T, axis=1)
    else:
        negative_max = np.zeros(len(CATALOGUE_VARIABLES))

    wants_current = any(marker in requete.lower() for marker in _CURRENT)
    candidates = []
    banned = []
    for index, variable in enumerate(CATALOGUE_VARIABLES):
        semantic = float(positive_max[index])
        rejected = float(negative_max[index])
        if rejected > 0.34 and rejected >= (semantic - 0.04):
            banned.append({"id": variable["id"], "raison": f"Exclue par négation (Score négatif: {rejected:.2f})"})
            continue
        if variable["couverture"] in {"2003-2026", "statique_0_200cm"}:
            temporal = 1.0
        elif wants_current:
            temporal = 0.45
        else:
            temporal = 0.85
        score = (0.70 * semantic) + (0.30 * temporal)
        candidates.append((score, variable))

    candidates.sort(key=lambda item: item[0], reverse=True)
    selection = []
    seen: set[str] = set()
    for score, variable in candidates:
        if variable["famille"] in seen or len(selection) >= top_k:
            continue
        selection.append(
            {
                "id": variable["id"],
                "earthscope_id": variable["earthscope_id"],
                "titre": variable["titre"],
                "source": variable["source"],
                "score": round(score, 4),
            }
        )
        seen.add(variable["famille"])

    return {
        "localisation": detecter_ville_cameroun(requete),
        "variables_retenues": selection,
        "variables_bannies": banned,
    }
