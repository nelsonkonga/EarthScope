"""JSON shapes shared with the TypeScript client. Field names stay camelCase."""

from pydantic import BaseModel, ConfigDict


class Period(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    start: str | None = None
    end: str | None = None


class TheilSen(BaseModel):
    method: str
    slopePerYear: float | None
    changePerDecade: float | None = None
    intercept: float | None
    sampleCount: int
    periodStart: str | None = None
    periodEnd: str | None = None
    startValue: float | None = None
    endValue: float | None = None


class MannKendall(BaseModel):
    method: str
    s: float | None
    variance: float | None
    z: float | None
    pValue: float | None
    alpha: float
    significant: bool
    trend: str
    sampleCount: int


class ClimatologyMonth(BaseModel):
    month: int
    count: int
    mean: float | None
    std: float | None
    min: float | None
    q1: float | None
    median: float | None
    q3: float | None
    max: float | None


class UnivariateReport(BaseModel):
    zoneId: str
    variableId: str
    resolution: str
    unit: str
    period: Period
    sampleCount: int
    missingCount: int
    theilSen: TheilSen
    mannKendall: MannKendall
    climatology: list[ClimatologyMonth]


class CorrelationLag(BaseModel):
    steps: int
    unit: str
    pearsonR: float
    pValue: float
    sampleCount: int


class Correlation(BaseModel):
    variableIds: list[str] | None = None
    pearsonR: float | None
    pValue: float | None
    sampleCount: int
    relationship: str
    interpretation: str | None = None
    bestLag: CorrelationLag | None = None


class AlignedObservation(BaseModel):
    date: str
    values: dict[str, float | None]
    normalized: dict[str, float | None]
    anomalies: dict[str, float | None]


class MultivariableReport(BaseModel):
    zoneId: str
    period: Period
    variables: list[str]
    correlation: Correlation | None
    pairs: list[Correlation]
    alignedObservations: list[AlignedObservation]
