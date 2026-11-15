"""Rule-based assistant. It names catalog entries and emits actions. It does not invent measurements."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.config import MANN_KENDALL_ALPHA, MIN_SAMPLES
from app.services.catalog import VARIABLES, Catalog, get_catalog
from app.services.mann_kendall import mann_kendall, sen_slope
from app.services.statistics import decimal_year, is_missing
from app.services import llm
from app.services.variable_selector import analyser_requete

PROMPTS = [
    "Compare l'évolution de la température et de l'humidité du sol à Yaoundé",
    "Montre l'épaisseur optique des aérosols à Yaoundé",
    "Comment évolue la température du sol à Yaoundé ?",
    "Superpose l'humidité du sol et l'évaporation à Yaoundé",
    "Montre le ruissellement à Yaoundé",
]

_sessions: dict[str, dict] = {}
_PORTABLE = re.compile(r"^es1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty(session_id: str) -> dict:
    return {"id": session_id, "createdAt": _now(), "suggestedPrompts": PROMPTS, "messages": []}


def create_session() -> dict:
    session_id = f"es1-{uuid.uuid4()}"
    _sessions[session_id] = _empty(session_id)
    return _sessions[session_id]


def get_session(session_id: str) -> dict | None:
    if session_id in _sessions:
        return _sessions[session_id]
    if _PORTABLE.match(session_id):
        _sessions[session_id] = _empty(session_id)
        return _sessions[session_id]
    return None


def fold(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFD", value)
    return "".join(character for character in normalized if unicodedata.category(character) != "Mn").lower()


def _zones_in(text: str, catalog: Catalog) -> list[dict]:
    folded = fold(text)
    found = []
    for zone in catalog.zones():
        names = [fold(zone["name"]), *[fold(alias) for alias in zone.get("aliases", [])]]
        if any(name and name in folded for name in names):
            found.append(zone)
    return found


def _published(catalog: Catalog, variable_id: str) -> bool:
    return any(variable == variable_id for _zone, variable in catalog.series)


def _variables_in(text: str, zone_id: str | None, catalog: Catalog) -> list[str]:
    folded = fold(text)
    chosen: list[str] = []

    def add(variable_id: str) -> None:
        if zone_id and catalog.get(zone_id, variable_id) is None:
            return
        if variable_id not in chosen:
            chosen.append(variable_id)

    soil = "sol" in folded
    if any(token in folded for token in ("aerosol", "aerosols", "aerien", "optique", "aod")):
        add("var_aod")
    if "neige" in folded:
        add("var_snow")
    if "glace" in folded or "banquise" in folded:
        add("var_sea_ice")
    if "ruissel" in folded:
        add("var_runoff")
    if "nuage" in folded:
        add("var_cloud")
    if "soleil" in folded or "rayonnement" in folded or "ensoleil" in folded:
        add("var_sunlight")
    if "tropopause" in folded:
        add("var_tropt")
    if "pression" in folded:
        add("var_slp")
    if "vapeur" in folded:
        add("var_tqv")
    if "vent" in folded:
        add("var_wind")
    if "precip" in folded or "pluie" in folded:
        add("var_precip")
    if "racin" in folded:
        add("var_root_wetness")
    if "humidite relative" in folded:
        add("var_rh")
    if soil and ("humid" in folded or "moisture" in folded):
        add("var_soil_moisture")
    elif "humid" in folded and "sol" not in folded and "relative" in folded:
        add("var_rh")
    if "evaporation des terres" in folded or "evland" in folded:
        add("var_evland")
    elif "evapor" in folded:
        add("var_evaporation" if zone_id == "zone_yaounde" or soil else "var_evland")
    if soil and ("temp" in folded or "rechauff" in folded):
        add("var_soil_temp_deep" if "profond" in folded else "var_soil_temp")
    elif "temperature de l'air" in folded or "temperature de lair" in folded or "air" in folded and "temp" in folded:
        add("var_soil_temp" if not _published(catalog, "var_t2m") else "var_t2m")
    elif ("temp" in folded or "rechauff" in folded) and not soil:
        add("var_soil_temp" if not _published(catalog, "var_t2m") else "var_t2m")
    if "surface" in folded and "temp" in folded and not soil:
        add("var_ts")
    if zone_id:
        available = {variable_id for zone, variable_id in catalog.series if zone == zone_id}
        chosen = [variable_id for variable_id in chosen if variable_id in available]
    return chosen


def _number(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _trend_sentence(catalog: Catalog, zone_id: str, variable_id: str) -> str:
    name, _description, _category, unit, *_rest = VARIABLES[variable_id]
    series = catalog.get(zone_id, variable_id)
    if series is None:
        return f"{name} : pas de série."
    pairs = [(decimal_year(date), float(value)) for date, value in zip(series.dates, series.values) if not is_missing(value)]
    if len(pairs) < 4:
        return f"{name} : série trop courte pour un Mann-Kendall."
    years = [year for year, _value in pairs]
    values = [value for _year, value in pairs]
    result = mann_kendall(values, autocorr=True, alpha=MANN_KENDALL_ALPHA)
    slope = sen_slope(years, values)
    unit_text = f" {unit}/an" if unit else "/an"
    slope_text = f", pente de Sen {_number(slope, 3)}{unit_text}" if slope == slope else ""
    if len(pairs) < MIN_SAMPLES or result["p"] != result["p"]:
        return f"{name} : effectif insuffisant pour conclure{slope_text}."
    if result["p"] < 0.001:
        p_text = "p < 0,001"
    else:
        p_text = f"p = {_number(result['p'], 3)}"
    if result["p"] < MANN_KENDALL_ALPHA and result["tau"] > 0:
        direction = "hausse significative"
    elif result["p"] < MANN_KENDALL_ALPHA and result["tau"] < 0:
        direction = "baisse significative"
    else:
        direction = "pas de tendance significative"
    return f"{name} : {direction} ({p_text}, tau = {_number(result['tau'], 2)}{slope_text})."


def _retrieved_ids(text: str, zone_id: str, catalog: Catalog, ranked: list[dict]) -> tuple[list[str], list[str]]:
    """Keep at most three published variables close to the best retrieval score."""
    if not ranked:
        return _variables_in(text, zone_id, catalog)[:3], []
    best = float(ranked[0]["score"])
    chosen: list[str] = []
    missing: list[str] = []
    for item in ranked:
        if best - float(item["score"]) > 0.10:
            break
        variable_id = item.get("earthscope_id")
        if variable_id and catalog.get(zone_id, variable_id) is not None and variable_id not in chosen and len(chosen) < 3:
            chosen.append(variable_id)
        elif not variable_id and item["titre"] not in missing:
            missing.append(item["titre"])
    if not chosen:
        return _variables_in(text, zone_id, catalog)[:3], []
    return chosen, missing


def _view_mode(text: str, count: int) -> str | None:
    folded = fold(text)
    if any(token in folded for token in ("normalis", "z-score", "z score", "anomalie")):
        return "normalized"
    if any(token in folded for token in ("superpos", "double axe", "ensemble")):
        return "superposition" if count == 2 else "normalized" if count > 2 else "single"
    if "compare" in folded or "comparaison" in folded:
        if count >= 3:
            return "normalized"
        if count == 2:
            return "superposition"
    return None


# Method explanations, in both interface languages. Keys are matched on the accent-folded question.
METHODS = (
    (
        ("mann-kendall", "mann kendall", "kendall"),
        "Le test de Mann-Kendall vérifie si une série monte ou descend de façon régulière plutôt que par hasard : il compare chaque mesure à toutes les suivantes. Une valeur p inférieure à 0,05 signifie qu'une tendance aussi nette aurait moins de 5 % de chances d'apparaître par hasard. Il ne dit rien de la cause.",
        "The Mann-Kendall test checks whether a series rises or falls consistently rather than by chance: it compares each measurement with every later one. A p-value below 0.05 means a trend this clear would have less than a 5% chance of appearing by chance. It says nothing about the cause.",
    ),
    (
        ("theil", "pente de sen", "sen slope"),
        "La pente de Theil-Sen est la médiane des pentes entre toutes les paires de mesures : elle donne la vitesse du changement (par an ou par décennie) sans se laisser tromper par une valeur extrême. Une pente non nulle n'est significative que si le test de Mann-Kendall l'est aussi.",
        "The Theil-Sen slope is the median of the slopes between all pairs of measurements: it gives the speed of change (per year or per decade) without being misled by an extreme value. A non-zero slope only matters if the Mann-Kendall test is significant too.",
    ),
    (
        ("valeur p", "p-value", "p value"),
        "La valeur p mesure la probabilité d'observer une tendance au moins aussi forte si, en réalité, il n'y en avait aucune. Sous 0,05, la plateforme parle de tendance significative.",
        "The p-value is the probability of seeing a trend at least this strong if there were in fact none. Below 0.05, the platform calls the trend significant.",
    ),
    (
        ("shap",),
        "SHAP attribue à chaque facteur sa part dans une prédiction. C'est un objectif futur : Terra Sense ne publie aujourd'hui aucun modèle SHAP.",
        "SHAP assigns each factor its share of a prediction. It is future work: Terra Sense publishes no SHAP model today.",
    ),
    (
        ("merra",),
        "GLDAS est un modèle de surface terrestre : il calcule l'humidité et la température du sol à partir d'observations (pluie, rayonnement). MERRA-2 est une réanalyse atmosphérique globale, à maille plus grossière (environ 0,5° × 0,625°). La visualisation publiée utilise GLDAS Noah 0,25° et MODIS, pas MERRA-2.",
        "GLDAS is a land-surface model: it computes soil moisture and soil temperature from observations (rainfall, radiation). MERRA-2 is a global atmospheric reanalysis on a coarser grid (about 0.5° × 0.625°). The published visualisation uses GLDAS Noah 0.25° and MODIS, not MERRA-2.",
    ),
    (
        ("interpreter une tendance", "interpret a trend", "interpret a soil", "interpreter une evolution"),
        "Une tendance se lit en deux temps : le test de Mann-Kendall dit si elle est assez régulière pour ne pas être due au hasard (p < 0,05), la pente de Theil-Sen dit à quelle vitesse la valeur change. Une tendance ne dit pas pourquoi elle existe.",
        "A trend is read in two steps: the Mann-Kendall test says whether it is regular enough not to be chance (p < 0.05), the Theil-Sen slope says how fast the value changes. A trend does not say why it exists.",
    ),
)


def _method_notes(folded: str, locale: str = "fr") -> list[str]:
    index = 2 if locale == "en" else 1
    return [entry[index] for entry in METHODS if any(key in folded for key in entry[0])]


def _names_data(text: str, catalog: Catalog) -> bool:
    """True when the question names a zone or a variable, so a data illustration is relevant."""
    if _zones_in(text, catalog) or _variables_in(text, None, catalog):
        return True
    folded = fold(text)
    return any(word in folded for word in ("humid", "moisture", "temperat", "sol ", "soil", "evapor", "ruissel", "runoff", "aerosol"))


def answer(text: str, context: dict, catalog: Catalog | None = None) -> dict:
    catalog = catalog or get_catalog()
    locale = "en" if context.get("locale") == "en" else "fr"
    notes = _method_notes(fold(text), locale)
    if notes and not _names_data(text, catalog):
        # A method question: explain it, without opening unrelated series on the globe.
        return {"text": " ".join(notes), "actions": [], "dataReferences": [], "suggestedFollowUps": []}
    result = _answer(text, context, catalog)
    if notes:
        bridge = " Illustration on the data (computed in French by the statistical engine): " if locale == "en" else " Illustration sur les données : "
        result["text"] = " ".join(notes) + bridge + result["text"]
    return result


def _answer(text: str, context: dict, catalog: Catalog | None = None) -> dict:
    catalog = catalog or get_catalog()
    zones = _zones_in(text, catalog)
    unknown = []
    folded = fold(text)
    if "paris" in folded and not zones:
        unknown.append("paris")
    zone = zones[0] if zones else None
    if zone is None and context.get("selectedZoneId") and any(token in folded for token in ("cette zone", "ici", "la zone")):
        record = next((item for item in catalog.zones() if item["id"] == context["selectedZoneId"]), None)
        zone = record
    if zone is None and not unknown:
        zone = next((item for item in catalog.zones() if item["id"] == "zone_yaounde"), None)
    zone_id = zone["id"] if zone else None
    retrieval = analyser_requete(text, top_k=8)
    named_city = retrieval["localisation"]["ville"]
    if named_city not in {"Yaounde", "Yaounde (Par défaut)"} and not zones:
        return {
            "text": f"{named_city} n'a pas de série publiée. Le catalogue actuel est la maille de Yaoundé, donc je ne sélectionne rien à la place.",
            "actions": [],
            "dataReferences": [],
            "suggestedFollowUps": [],
        }
    variable_ids, unavailable = _retrieved_ids(text, zone_id, catalog, retrieval["variables_retenues"]) if zone_id else ([], [])
    actions: list[dict] = []
    if zone_id:
        actions.append({"type": "SELECT_ZONE", "zoneId": zone_id})
        actions.append({"type": "OPEN_PANEL", "panel": "zoneCard"})
    if variable_ids:
        actions.append({"type": "ACTIVATE_VARIABLES", "variableIds": variable_ids, "mode": "replace"})
    mode = _view_mode(text, len(variable_ids))
    if mode:
        actions.append({"type": "SET_VIEW_MODE", "mode": mode})
    names = [VARIABLES[variable_id][0] for variable_id in variable_ids]
    if unknown and not zone_id:
        actions = []
        prose = "Ce lieu n'est pas dans le catalogue. Je n'ai sélectionné aucune zone."
    elif not zone_id and not variable_ids:
        prose = "Je n'ai reconnu ni une zone ni une variable du catalogue. Les graphiques restent inchangés."
    else:
        parts = []
        if zone:
            parts.append(zone["name"])
        if names:
            parts.append(", ".join(names))
        prose = "J'ouvre " + " — ".join(parts) + "."
        if mode == "superposition":
            prose += " Les deux séries seront superposées sur un double axe."
        elif mode == "normalized":
            prose += " Les séries seront affichées en indice normalisé."
        elif mode == "single":
            prose += " Une variable à la fois."
        if variable_ids and zone_id:
            prose += " Tendances sur les observations (Mann-Kendall, correction de Hamed et Rao) : " + " ".join(
                _trend_sentence(catalog, zone_id, variable_id) for variable_id in variable_ids
            )
        if unavailable:
            prose += " Sans série sur cette maille : " + ", ".join(unavailable) + "."
        prose += " Le globe et les graphiques utilisent cette liste comme une sélection manuelle."
    return {
        "text": prose,
        "actions": actions,
        "dataReferences": [{"kind": "zone", "id": zone_id}] if zone_id else [],
        "suggestedFollowUps": [],
    }


def post_message(session_id: str, text: str, context: dict) -> dict | None:
    session = get_session(session_id)
    if session is None:
        return None
    user = {"id": f"user-{uuid.uuid4()}", "role": "user", "text": text, "createdAt": _now()}
    result = answer(text, context)
    worded = llm.rewrite(text, result["text"], context, locale=str(context.get("locale") or "fr"), history=session["messages"])
    message = {
        "id": f"assistant-{uuid.uuid4()}",
        "role": "assistant",
        "text": worded or result["text"],
        "source": "gemini" if worded else "rules",
        "createdAt": _now(),
        "actions": result["actions"],
        "dataReferences": result["dataReferences"],
        "suggestedFollowUps": result["suggestedFollowUps"],
    }
    session["messages"].extend([user, message])
    return message
