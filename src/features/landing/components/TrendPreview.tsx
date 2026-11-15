import { useMemo } from 'react';
import type { LandingCatalog, LandingObservation } from '../api/landingData';
import { format, useLandingLanguage } from '../context/LandingContext';
import { ChartIcon } from './Icons';

const W = 640;
const H = 230;
const PAD = 18;

function scales(points: LandingObservation[]) {
  const valid = points.filter((point): point is LandingObservation & { value: number } => point.value !== null && Number.isFinite(point.value));
  if (valid.length < 2) return null;
  const values = valid.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const low = min === max ? min - 1 : min;
  const high = min === max ? max + 1 : max;
  const first = Date.parse(valid[0].date);
  const last = Date.parse(valid[valid.length - 1].date);
  const span = Math.max(1, last - first);
  const x = (date: string) => PAD + ((Date.parse(date) - first) / span) * (W - PAD * 2);
  const y = (value: number) => H - PAD - ((value - low) / (high - low)) * (H - PAD * 2);
  const paths: string[] = [];
  let current: string[] = [];
  for (const point of points) {
    if (point.value === null || !Number.isFinite(point.value)) {
      if (current.length > 1) paths.push(current.join(' '));
      current = [];
      continue;
    }
    current.push(`${current.length ? 'L' : 'M'} ${x(point.date).toFixed(2)} ${y(point.value).toFixed(2)}`);
  }
  if (current.length > 1) paths.push(current.join(' '));
  return { paths, min, max, x, y, firstDate: valid[0].date, lastDate: valid[valid.length - 1].date };
}

/**
 * Real observations from the API, gaps kept as gaps. The dashed line and the verdict come from
 * /api/v1/analytics (Theil-Sen, Mann-Kendall); nothing is drawn when they are unavailable.
 */
export function TrendPreview({ catalog }: { catalog: LandingCatalog }) {
  const { t, locale } = useLandingLanguage();
  const s = t.science;
  const chart = useMemo(() => scales(catalog.observations), [catalog.observations]);
  const number = (value: number | null | undefined, digits = 2) =>
    value == null ? '—' : new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value);
  const month = (value: string) => new Intl.DateTimeFormat(locale, { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(value));
  const variable = catalog.selectedVariable;
  const zone = catalog.selectedZone;
  const title = variable ? `${variable.name}${zone ? ` · ${zone.name}` : ''}` : s.variableFallback;
  const unit = variable?.unit ?? '';
  const sen = catalog.trend?.theilSen;
  const kendall = catalog.trend?.mannKendall;
  const falling = Boolean(kendall?.significant && kendall.trend === 'down');
  const verdict = kendall && sen
    ? format(s.verdict, {
        method: /season|saison/i.test(kendall.method) ? s.seasonalMethod : s.plainMethod,
        direction: s.directions[(kendall.trend in s.directions ? kendall.trend : 'insufficient') as keyof typeof s.directions],
        p: kendall.pValue == null ? 'p —' : kendall.pValue < 0.001 ? `p < ${number(0.001, 3)}` : `p = ${number(kendall.pValue, 3)}`,
        slope: number(sen.changePerDecade),
        unit,
      })
    : null;
  const trendPath = chart && sen?.startValue != null && sen.endValue != null && sen.periodStart && sen.periodEnd
    ? `M ${chart.x(sen.periodStart).toFixed(1)} ${chart.y(sen.startValue).toFixed(1)} L ${chart.x(sen.periodEnd).toFixed(1)} ${chart.y(sen.endValue).toFixed(1)}`
    : null;

  return (
    <figure className="ts-trend-card">
      <div className="ts-trend-card__top">
        <div className="ts-trend-card__icon" aria-hidden="true"><ChartIcon /></div>
        <div><span className="ts-overline">{s.eyebrow}</span><h3>{title}</h3></div>
        <span className="ts-trend-card__live">{t.hero.liveCatalog}</span>
      </div>
      {catalog.isSeriesLoading ? (
        <div className="ts-chart-state" role="status">{s.trendLoading}</div>
      ) : catalog.isSeriesError ? (
        <div className="ts-chart-state" role="status">{s.trendError}</div>
      ) : chart ? (
        <>
          <div className="ts-trend-card__meta">
            <span><i className="ts-key ts-key--series" aria-hidden="true" />{s.seriesLabel}{unit ? ` · ${unit}` : ''}</span>
            {trendPath && <span><i className={`ts-key ts-key--trend ${falling ? 'is-alert' : ''}`} aria-hidden="true" />{s.trendLabel}</span>}
          </div>
          <div className="ts-trend-chart" role="img" aria-label={`${title}. ${month(chart.firstDate)} – ${month(chart.lastDate)}. ${verdict ?? ''}`}>
            <div className="ts-trend-chart__ylabels" aria-hidden="true"><span>{number(chart.max, 0)}</span><span>{number(chart.min, 0)}</span></div>
            <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
              {[38, 92, 146, 200].map((y) => <line key={y} x1={PAD} x2={W - PAD} y1={y} y2={y} className="ts-chart-grid" />)}
              {chart.paths.map((path, index) => <path key={index} d={path} className="ts-chart-line" />)}
              {trendPath && <path d={trendPath} className={`ts-chart-trend ${falling ? 'is-alert' : ''}`} />}
            </svg>
          </div>
          {verdict && <p className={`ts-trend-card__verdict ${falling ? 'is-alert' : ''}`}>{verdict}</p>}
          <figcaption className="ts-trend-card__footnote">{format(s.footnote, { start: month(chart.firstDate), end: month(chart.lastDate) })}</figcaption>
        </>
      ) : (
        <div className="ts-chart-state ts-chart-state--empty" role="status">{s.trendEmpty}</div>
      )}
    </figure>
  );
}
