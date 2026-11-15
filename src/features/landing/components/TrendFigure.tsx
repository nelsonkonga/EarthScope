import { useAnalyticsQuery, useSeriesQueries, useVariableCatalog } from "../../../api/queries";
import { format, monthYear, useI18n, type Locale } from "../../../i18n";

const ZONE = "zone_yaounde";
const VARIABLE = "var_soil_moisture_deep";

function number(value: number, locale: Locale, digits = 2) {
  return new Intl.NumberFormat(locale === "fr" ? "fr-FR" : "en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
}

/**
 * Real series from the platform API: GLDAS Noah 2.0 soil moisture 10–40 cm over Yaoundé,
 * with the Theil-Sen line and the Mann-Kendall verdict computed by the backend.
 * When the API is unreachable the figure says so and draws nothing.
 */
export function TrendFigure() {
  const { t, locale } = useI18n();
  const copy = t.mission.trends;
  const catalog = useVariableCatalog();
  const variable = catalog.data?.variables.find((item) => item.id === VARIABLE) ?? null;
  const [series] = useSeriesQueries(variable ? ZONE : null, variable ? [variable] : []);
  const analytics = useAnalyticsQuery(variable ? ZONE : null, variable ? VARIABLE : null, null, null);
  const failed = catalog.isError || series?.isError || analytics.isError || (catalog.isSuccess && !variable);
  const points = (series?.data?.observations ?? []).filter((item) => item.value != null) as { date: string; value: number }[];
  const sen = analytics.data?.theilSen;
  const kendall = analytics.data?.mannKendall;

  if (failed) {
    return (
      <div className="ts-chart ts-chart-empty" role="status">
        <p>{copy.unavailable}</p>
      </div>
    );
  }
  if (!points.length || !sen || !kendall) {
    return (
      <div className="ts-chart ts-chart-empty" role="status" aria-busy="true">
        <span className="ts-chart-skeleton" aria-hidden="true" />
        <p>{copy.loading}</p>
      </div>
    );
  }

  const W = 640;
  const H = 260;
  const pad = { l: 44, r: 12, t: 16, b: 30 };
  const times = points.map((point) => Date.parse(point.date));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const values = points.map((point) => point.value);
  const v0 = Math.min(...values);
  const v1 = Math.max(...values);
  const span = v1 - v0 || 1;
  const lo = v0 - span * 0.08;
  const hi = v1 + span * 0.08;
  const x = (date: string) => pad.l + ((Date.parse(date) - t0) / (t1 - t0 || 1)) * (W - pad.l - pad.r);
  const y = (value: number) => pad.t + (1 - (value - lo) / (hi - lo)) * (H - pad.t - pad.b);
  const line = points.map((point, index) => `${index ? "L" : "M"}${x(point.date).toFixed(1)} ${y(point.value).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points[points.length - 1].date).toFixed(1)} ${H - pad.b} L${x(points[0].date).toFixed(1)} ${H - pad.b} Z`;
  const trendOk = sen.startValue != null && sen.endValue != null && sen.periodStart && sen.periodEnd;
  const falling = kendall.significant && kendall.trend === "down";
  const firstYear = new Date(t0).getUTCFullYear();
  const lastYear = new Date(t1).getUTCFullYear();
  const ticks = [] as number[];
  for (let year = Math.ceil((firstYear + 1) / 3) * 3; year <= lastYear; year += 3) ticks.push(year);
  const direction = copy.directions[(kendall.trend as keyof typeof copy.directions) ?? "insufficient"] ?? copy.directions.insufficient;
  const method = kendall.method.toLowerCase().includes("saison") ? (locale === "fr" ? "Mann-Kendall saisonnier" : "Seasonal Mann-Kendall") : "Mann-Kendall";
  const p = kendall.pValue == null ? "p —" : kendall.pValue < 0.001 ? `p < ${number(0.001, locale, 3)}` : `p = ${number(kendall.pValue, locale, 3)}`;
  const unit = series?.data?.unit ?? variable?.unit ?? "";
  const verdict = format(copy.verdict, {
    method,
    direction,
    p,
    slope: sen.changePerDecade == null ? "—" : number(sen.changePerDecade, locale),
    unit,
  });

  return (
    <figure className="ts-chart">
      <figcaption className="ts-chart-head">
        <span className="ts-chart-title">{copy.chartTitle}</span>
        <span className="ts-chart-legend" aria-hidden="true">
          <span className="ts-key ts-key-series" /> {copy.chartLegendSeries}
          <span className={falling ? "ts-key ts-key-trend is-alert" : "ts-key ts-key-trend"} /> {copy.chartLegendTrend}
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${copy.chartAlt} ${verdict}`} className="ts-chart-svg">
        {[0, 0.5, 1].map((ratio) => {
          const value = lo + (hi - lo) * ratio;
          return (
            <g key={ratio}>
              <line x1={pad.l} x2={W - pad.r} y1={y(value)} y2={y(value)} className="ts-chart-grid" />
              <text x={pad.l - 8} y={y(value) + 4} textAnchor="end" className="ts-chart-axis">
                {number(value, locale, 0)}
              </text>
            </g>
          );
        })}
        {ticks.map((year) => {
          const xx = x(`${year}-01-01`);
          return (
            <text key={year} x={xx} y={H - 8} textAnchor="middle" className="ts-chart-axis">
              {year}
            </text>
          );
        })}
        <path d={area} className="ts-chart-area" />
        <path d={line} className="ts-chart-line" />
        {trendOk && (
          <path
            d={`M${x(sen.periodStart as string)} ${y(sen.startValue as number)} L${x(sen.periodEnd as string)} ${y(sen.endValue as number)}`}
            className={falling ? "ts-chart-trend is-alert" : "ts-chart-trend"}
          />
        )}
        <text x={pad.l} y={pad.t - 4} className="ts-chart-axis">
          {unit}
        </text>
      </svg>
      <p className={falling ? "ts-chart-verdict is-alert" : "ts-chart-verdict"}>{verdict}</p>
      <p className="ts-chart-caption">{format(copy.chartCaption, { start: monthYear(points[0].date, locale), end: monthYear(points[points.length - 1].date, locale) })}</p>
    </figure>
  );
}
