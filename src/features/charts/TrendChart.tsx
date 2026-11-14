import { useState } from "react";
import { formatDate, formatNumber, formatTrend } from "../../domain/format";
import type { Observation, TimeSeries } from "../../domain/types";

type Props = {
  series: TimeSeries;
  color: string;
  selectedDate: string | null;
  label: string;
};

export function TrendChart({ series, color, selectedDate, label }: Props) {
  const [hover, setHover] = useState<Observation | null>(null);
  const observed = series.observations.filter((item) => item.value != null);
  const width = 320;
  const height = 180;
  const pad = { l: 42, r: 10, t: 12, b: 28 };
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const values = observed.map((item) => item.value as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const y0 = min - span * 0.12;
  const y1 = max + span * 0.12;
  const times = series.observations.map((item) => Date.parse(item.date));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const xOf = (date: string) => pad.l + ((Date.parse(date) - t0) / (t1 - t0 || 1)) * innerW;
  const yOf = (value: number) => pad.t + (1 - (value - y0) / (y1 - y0)) * innerH;
  const segments: string[] = [];
  let current = "";
  for (const observation of series.observations) {
    if (observation.value == null || observation.status === "missing") {
      if (current) segments.push(current);
      current = "";
      continue;
    }
    const command = `${current ? "L" : "M"} ${xOf(observation.date)} ${yOf(observation.value)}`;
    current = current ? `${current} ${command}` : command;
  }
  if (current) segments.push(current);
  const trend = series.trend;
  const trendLine =
    trend && trend.direction !== "insufficient" && trend.startValue != null && trend.endValue != null
      ? `M ${xOf(trend.periodStart)} ${yOf(trend.startValue)} L ${xOf(trend.periodEnd)} ${yOf(trend.endValue)}`
      : null;
  const marker = selectedDate ? xOf(selectedDate) : null;
  const summary = `${label}. ${formatTrend(trend, series.unit)}`;

  return (
    <div className="chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={summary}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          const px = ((event.clientX - bounds.left) / bounds.width) * width;
          let nearest: Observation | null = null;
          let distance = 18;
          for (const observation of series.observations) {
            const gap = Math.abs(xOf(observation.date) - px);
            if (gap < distance) {
              distance = gap;
              nearest = observation;
            }
          }
          setHover(nearest);
        }}
      >
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={height - pad.b} className="axis" />
        <line x1={pad.l} y1={height - pad.b} x2={width - pad.r} y2={height - pad.b} className="axis" />
        <text x={4} y={pad.t + 8} className="axis-label">
          {formatNumber(y1)}
        </text>
        <text x={4} y={height - pad.b} className="axis-label">
          {formatNumber(y0)}
        </text>
        {segments.map((path) => (
          <path key={path} d={path} fill="none" stroke={color} strokeWidth="1.5" />
        ))}
        {trendLine && <path d={trendLine} fill="none" stroke={color} strokeWidth="1" strokeDasharray="4 3" />}
        {series.observations.map((observation) =>
          observation.status === "estimated" && observation.value != null ? (
            <circle key={observation.date} cx={xOf(observation.date)} cy={yOf(observation.value)} r="3" fill="none" stroke={color} />
          ) : null,
        )}
        {marker != null && <line x1={marker} y1={pad.t} x2={marker} y2={height - pad.b} className="cursor-line" />}
        {hover?.value != null && <circle cx={xOf(hover.date)} cy={yOf(hover.value)} r="3.5" fill={color} />}
      </svg>
      {hover && (
        <p className="chart-tip">
          {formatDate(hover.date)} · {hover.value == null ? "indisponible" : `${formatNumber(hover.value)} ${series.unit}`} · {hover.status === "estimated" ? "estimée" : hover.status === "missing" ? "indisponible" : "mesurée"}
        </p>
      )}
    </div>
  );
}

export function ComparisonChart({
  items,
  selectedDate,
}: {
  items: { series: TimeSeries; color: string; name: string }[];
  selectedDate: string | null;
}) {
  const width = 320;
  const height = 180;
  const pad = { l: 42, r: 10, t: 12, b: 28 };
  const observations = items.flatMap((item) => item.series.observations.filter((observation) => observation.value != null));
  if (observations.length === 0) return <p className="hint">Pas de données pour cette comparaison.</p>;
  const values = observations.map((item) => item.value as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const y0 = min - span * 0.12;
  const y1 = max + span * 0.12;
  const times = observations.map((item) => Date.parse(item.date));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const xOf = (date: string) => pad.l + ((Date.parse(date) - t0) / (t1 - t0 || 1)) * (width - pad.l - pad.r);
  const yOf = (value: number) => pad.t + (1 - (value - y0) / (y1 - y0)) * (height - pad.t - pad.b);
  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Comparaison des séries">
      {items.map((item) => {
        let path = "";
        for (const observation of item.series.observations) {
          if (observation.value == null) {
            path += " ";
            continue;
          }
          path += `${path.trim().endsWith(" ") || path === "" ? "M" : "L"} ${xOf(observation.date)} ${yOf(observation.value)} `;
        }
        return <path key={item.name} d={path} fill="none" stroke={item.color} strokeWidth="1.5" />;
      })}
      {selectedDate && <line x1={xOf(selectedDate)} y1={pad.t} x2={xOf(selectedDate)} y2={height - pad.b} className="cursor-line" />}
    </svg>
  );
}
