"""Rule-based assistant. It names catalog entries and emits actions. It does not invent measurements."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

from app.services.catalog import VARIABLES, Catalog, get_catalog

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


def answer(text: str, context: dict, catalog: Catalog | None = None) -> dict:
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
    zone_id = zone["id"] if zone else None
    variable_ids = _variables_in(text, zone_id, catalog)
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
        prose += " Les pentes et les corrélations sont calculées sur les observations, pas écrites à l'avance."
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
    message = {
        "id": f"assistant-{uuid.uuid4()}",
        "role": "assistant",
        "text": result["text"],
        "createdAt": _now(),
        "actions": result["actions"],
        "dataReferences": result["dataReferences"],
        "suggestedFollowUps": result["suggestedFollowUps"],
    }
    session["messages"].extend([user, message])
    return message
