from fastapi.testclient import TestClient

from app.main import app
from app.services.assistant import answer
from app.services.catalog import get_catalog

client = TestClient(app)


def test_yaounde_july_2002_keeps_raw_values_and_the_aod_gap():
    catalog = get_catalog()
    moisture = catalog.get("zone_yaounde", "var_soil_moisture").as_map()["2002-07-01"]
    temperature = catalog.get("zone_yaounde", "var_soil_temp").as_map()["2002-07-01"]
    aerosol = catalog.get("zone_yaounde", "var_aod").as_map()["2002-07-01"]
    assert moisture == 30.409008
    assert abs(temperature - (296.970276 - 273.15)) < 1e-9
    assert aerosol is None


def test_analytics_are_computed_for_the_requested_window():
    response = client.get(
        "/api/v1/analytics",
        params={"zoneId": "zone_yaounde", "variableId": "var_soil_temp", "startDate": "2003-01-01", "endDate": "2005-12-01"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["period"]["start"] == "2003-01-01"
    assert body["period"]["end"] == "2005-12-01"
    assert body["mannKendall"]["sampleCount"] > 0
    assert body["theilSen"]["slopePerYear"] is not None
    assert len(body["climatology"]) == 12


def test_multivariable_correlation_is_not_a_constant():
    response = client.get(
        "/api/v1/analytics/multivariable",
        params={"zoneId": "zone_yaounde", "variableIds": "var_soil_temp,var_soil_moisture"},
    )
    body = response.json()
    coefficient = body["correlation"]["pearsonR"]
    assert -1 <= coefficient <= 1
    assert body["correlation"]["interpretation"]
    july = next(row for row in body["alignedObservations"] if row["date"] == "2002-07-01")
    assert july["values"]["var_soil_moisture"] == 30.409008
    assert july["normalized"]["var_soil_temp"] is not None
    aerosol = client.get("/api/v1/timeseries", params={"zoneId": "zone_yaounde", "variableId": "var_aod", "resolution": "month"})
    july_aod = next(row for row in aerosol.json()["series"]["observations"] if row["date"] == "2002-07-01")
    assert july_aod["value"] is None
    assert july_aod["status"] == "missing"


def test_assistant_selects_yaounde_soil_variables_and_superposition():
    result = answer(
        "Compare l'évolution de la température et de l'humidité du sol à Yaoundé",
        {},
    )
    types = [action["type"] for action in result["actions"]]
    assert "SELECT_ZONE" in types
    activate = next(action for action in result["actions"] if action["type"] == "ACTIVATE_VARIABLES")
    assert activate["mode"] == "replace"
    assert "var_soil_moisture" in activate["variableIds"]
    assert "var_soil_temp" in activate["variableIds"]
    assert len(activate["variableIds"]) <= 3
    assert any(action["type"] == "SET_VIEW_MODE" for action in result["actions"])
    assert "Mann-Kendall" in result["text"]
    assert "−" not in result["text"] or "r =" not in result["text"]


def test_catalog_publishes_only_the_yaounde_cell():
    zones = client.get("/api/v1/zones").json()["zones"]
    assert [zone["id"] for zone in zones] == ["zone_yaounde"]
    assert zones[0]["footprint"] == [11.4, 3.75, 11.65, 3.98]
    variables = client.get("/api/v1/variables").json()["variables"]
    ids = {item["id"] for item in variables}
    assert "var_soil_temp" in ids
    assert "var_t2m" not in ids
    assert "var_sea_ice" not in ids
    temperature = next(item for item in variables if item["id"] == "var_soil_temp")
    assert temperature["colorScale"]["stops"][0]["color"] == "#1B2A6B"
    assert temperature["colorScale"]["stops"][-1]["color"] == "#FFF1D6"


def test_paris_selects_nothing():
    result = answer("Quelle est la température à Paris ?", {})
    assert result["actions"] == []


def test_another_cameroon_city_is_not_drawn_as_yaounde():
    result = answer("Montre le ruissellement à Douala", {})
    assert result["actions"] == []
    assert "Douala" in result["text"]


def test_aerosol_question_activates_the_published_series():
    result = answer("Montre l'épaisseur optique des aérosols à Yaoundé", {})
    activate = next(action for action in result["actions"] if action["type"] == "ACTIVATE_VARIABLES")
    assert activate["variableIds"][0] == "var_aod"
    assert len(activate["variableIds"]) <= 3
