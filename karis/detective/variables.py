"""The suspects: Earth science variables the detective can investigate right away.

Each one is served without login by NASA POWER (``power.py``) and comes from a NASA dataset
that earthdata-mcp can find in the CMR (``collection`` / ``variable``: MERRA-2 monthly
collections at GES DISC; CERES for cloud and sunlight). ``simple`` is a definition written
for high-school and college students; ``keywords`` are the GCMD science keywords used to
look for every NASA dataset that measures the same thing (MODIS, GPM, AIRS, OMI, GLDAS...).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

TOPICS = {
    "heat": "Heat & temperature",
    "water": "Rain, soil & water vapour",
    "ice": "Ice & snow",
    "air": "Ozone, haze, clouds & sunlight",
    "wind": "Wind & pressure",
}


@dataclass(frozen=True)
class Variable:
    key: str  # POWER parameter
    label: str
    topic: str
    units: str
    simple: str  # plain-language definition
    source: str  # the NASA product behind the POWER series
    collection: str  # its CMR short name (provenance, looked up through earthdata-mcp)
    variable: str  # the variable's name in that collection
    keywords: tuple  # GCMD science keywords (get_keywords / get_collections)
    first_year: int = 1981
    lower: float | None = None  # physical bounds, in display units (a fraction in %: [0, 100])
    upper: float | None = None
    scale: float = 1.0  # display units = POWER units x scale (fractions shown in %, pressure in hPa)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["keywords"] = list(self.keywords)
        return d


VARIABLES: dict[str, Variable] = {v.key: v for v in [
    Variable("T2M", "Air temperature", "heat", "°C",
             "How warm the air is 2 metres above the ground — what a thermometer in the shade shows.",
             "MERRA-2", "M2TMNXSLV", "T2M", ("AIR TEMPERATURE", "SURFACE AIR TEMPERATURE")),
    Variable("TS", "Surface temperature", "heat", "°C",
             "The temperature of the surface itself — soil, rock, sea water or ice — which can be much "
             "hotter or colder than the air above it.",
             "MERRA-2", "M2TMNXSLV", "TS", ("SURFACE TEMPERATURE", "SKIN TEMPERATURE")),
    Variable("TROPT", "Tropopause temperature", "heat", "°C",
             "The temperature at the tropopause, the ceiling of the weather layer of the atmosphere: "
             "about 8 km up near the poles and 17 km up in the tropics.",
             "MERRA-2", "M2TMNXSLV", "TROPT", ("TROPOPAUSE", "UPPER AIR TEMPERATURE")),
    Variable("PRECTOTCORR", "Precipitation", "water", "mm/day",
             "How much rain and snow falls, in millimetres of water per day (1 mm on one square metre is "
             "one litre). MERRA-2 corrects its model rain with rain gauges and satellite observations.",
             "MERRA-2", "M2TMNXFLX", "PRECTOTCORR", ("PRECIPITATION AMOUNT", "PRECIPITATION RATE")),
    Variable("GWETROOT", "Root-zone soil wetness", "water", "%",
             "How wet the soil is where plant roots drink (roughly the top metre): 0 % is bone dry, "
             "100 % is completely soaked.",
             "MERRA-2", "M2TMNXLND", "GWETROOT", ("SOIL MOISTURE/WATER CONTENT", "ROOT ZONE SOIL MOISTURE"),
             lower=0.0, upper=100.0, scale=100.0),
    Variable("GWETTOP", "Surface soil wetness", "water", "%",
             "How wet the top few centimetres of soil are (0 % dry, 100 % soaked); it reacts within "
             "days to rain and sunshine.",
             "MERRA-2", "M2TMNXLND", "GWETTOP", ("SOIL MOISTURE/WATER CONTENT", "SURFACE SOIL MOISTURE"),
             lower=0.0, upper=100.0, scale=100.0),
    Variable("EVLAND", "Evaporation from land", "water", "mm/day",
             "Water rising from the land into the air — from wet soil, lakes and plant leaves "
             "(transpiration) — in millimetres per day.",
             "MERRA-2", "M2TMNXLND", "EVLAND", ("EVAPOTRANSPIRATION", "EVAPORATION")),
    Variable("RH2M", "Relative humidity", "water", "%",
             "How close the air is to being saturated with water vapour: at 100 % it cannot hold more "
             "and dew or fog forms.",
             "MERRA-2", "M2TMNXSLV", "QV2M", ("RELATIVE HUMIDITY", "HUMIDITY"), lower=0.0, upper=100.0),
    Variable("QV2M", "Specific humidity", "water", "g/kg",
             "The actual amount of water vapour in the air near the ground: grams of water per "
             "kilogram of air.",
             "MERRA-2", "M2TMNXSLV", "QV2M", ("SPECIFIC HUMIDITY", "HUMIDITY")),
    Variable("TQV", "Water vapour in the air column", "water", "kg/m²",
             "All the water vapour above a spot, from the ground to the top of the atmosphere — the "
             "millimetres of water you would get if it all rained out at once.",
             "MERRA-2", "M2TMNXSLV", "TQV", ("PRECIPITABLE WATER", "WATER VAPOR")),
    Variable("FRSEAICE", "Sea ice cover", "ice", "%",
             "The share of the ocean surface covered by floating sea ice: 0 % is open water, 100 % is "
             "fully frozen over.",
             "MERRA-2", "M2TMNXFLX", "FRSEAICE", ("SEA ICE CONCENTRATION", "SEA ICE"), lower=0.0, upper=100.0,
             scale=100.0),
    Variable("SNODP", "Snow depth", "ice", "cm",
             "How deep the snow lying on the ground is, in centimetres.",
             "MERRA-2", "M2TMNXLND", "SNODP", ("SNOW DEPTH", "SNOW"), lower=0.0),
    Variable("TO3", "Total ozone (ozone layer)", "air", "DU",
             "All the ozone in a column of air above a spot, in Dobson units. Most of it sits 15–35 km "
             "up and shields life from ultraviolet light; below about 220 DU scientists speak of an "
             "ozone hole.",
             "MERRA-2", "M2TMNXSLV", "TO3", ("TOTAL OZONE", "OZONE")),
    Variable("AOD_55_ADJ", "Aerosols (haze, dust, smoke)", "air", "—",
             "How much sunlight is dimmed by tiny particles — desert dust, smoke, pollution — on its "
             "way down: 0 is perfectly clear air, above 1 is very hazy.",
             "MERRA-2", "M2TMNXAER", "TOTEXTTAU", ("AEROSOL OPTICAL DEPTH/THICKNESS", "AEROSOLS"),
             first_year=2001, lower=0.0),
    Variable("CLOUD_AMT", "Cloud cover", "air", "%",
             "The percentage of the sky covered by clouds.",
             "CERES (GEWEX SRB before 2000)", "CER_SYN1deg-Month_Terra-Aqua-NOAA20", "cldarea_total_daynight_mon",
             ("CLOUD FRACTION", "CLOUD AMOUNT"), first_year=1984, lower=0.0, upper=100.0),
    Variable("ALLSKY_SFC_SW_DWN", "Sunlight at the surface", "air", "MJ/m²/day",
             "How much solar energy reaches the ground through clouds and haze, per square metre and "
             "per day.",
             "CERES (GEWEX SRB before 2000)", "CER_SYN1deg-Month_Terra-Aqua-NOAA20", "sfc_sw_down_all_mon",
             ("INCOMING SOLAR RADIATION", "SHORTWAVE RADIATION"), first_year=1984, lower=0.0),
    Variable("WS10M", "Wind speed", "wind", "m/s",
             "How fast the wind blows 10 metres above the ground (10 m/s is 36 km/h).",
             "MERRA-2", "M2TMNXSLV", "U10M", ("SURFACE WINDS", "WIND SPEED")),
    Variable("SLP", "Sea-level pressure", "wind", "hPa",
             "The weight of the air above a spot, as if measured at sea level (about 1013 hPa on "
             "average): low pressure brings storms, high pressure fair weather.",
             "MERRA-2", "M2TMNXSLV", "SLP", ("SEA LEVEL PRESSURE", "ATMOSPHERIC PRESSURE"), scale=10.0),
]}


def by_topic(topic: str | None = None) -> list[Variable]:
    return [v for v in VARIABLES.values() if topic in (None, "all", v.topic)]


# What the reader should know about a link between two series of one reanalysis (never given to
# Eva: she finds the links without it; the story adds it so that a link the model makes by its own
# construction is not taken for a discovery about the Earth).
_LAND = ("MERRA-2's land model computes evaporation from the water it holds in the soil, and is driven by "
         "observation-corrected precipitation: this link is partly the model's own land physics")
MODEL_LINKS: dict[frozenset, str] = {
    frozenset(("T2M", "TS")): "the 2-metre air temperature of a reanalysis is computed from the surface temperature "
                              "and the lowest model level: this link is partly the model's own arithmetic",
    frozenset(("FRSEAICE", "TS")): "the sea ice and the sea-surface temperature are given to MERRA-2 from observations, "
                                   "and the surface over ice is the ice itself: when the ice retreats, the surface warms "
                                   "partly by construction",
    frozenset(("GWETROOT", "EVLAND")): _LAND,
    frozenset(("GWETTOP", "EVLAND")): _LAND,
    frozenset(("GWETROOT", "GWETTOP")): "both are layers of the same soil column in MERRA-2's land model",
    frozenset(("PRECTOTCORR", "GWETROOT")): _LAND,
    frozenset(("PRECTOTCORR", "GWETTOP")): _LAND,
    frozenset(("PRECTOTCORR", "EVLAND")): _LAND,
    frozenset(("RH2M", "T2M")): "relative humidity is computed from temperature and humidity: warmer air holding the "
                                "same water is drier in relative terms, so part of this opposite link is arithmetic",
    frozenset(("RH2M", "QV2M")): "relative humidity is computed from the specific humidity (and temperature)",
}


def model_note(a: str, b: str) -> str | None:
    """Why a link between the POWER parameters ``a`` and ``b`` may come from the model itself."""
    if frozenset((a, b)) in MODEL_LINKS:
        return MODEL_LINKS[frozenset((a, b))]
    va, vb = VARIABLES.get(a), VARIABLES.get(b)
    if va and vb and va.source == vb.source == "MERRA-2":
        return ("both series come from the MERRA-2 reanalysis, not from two independent instruments: confirm it "
                "with an independent dataset before calling it a finding")
    return None
