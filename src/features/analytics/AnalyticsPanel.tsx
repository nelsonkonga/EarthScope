import { useEffect, useState } from "react";
import { useAnalyticsQuery, useMultivariableQuery, useSeriesQueries } from "../../api/queries";
import { fr } from "../../config/strings.fr";
import { formatDate, formatNumber } from "../../domain/format";
import type { AnalyticsView, Variable, Zone } from "../../domain/types";
import { useWorkspace } from "../../state/workspaceStore";
import { Modal } from "../../ui/Modal";
import { Icon } from "../../ui/icons";
import { InteractiveTimeSeriesChart, type ChartLine } from "./InteractiveTimeSeriesChart";
import { MultivariableInsightCard } from "./MultivariableInsightCard";

const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];

function trendWord(direction: string) {
  if (direction === "up") return "hausse";
  if (direction === "down") return "baisse";
  if (direction === "flat") return "stable";
  return "données insuffisantes";
}

function pText(value: number | null) {
  if (value == null) return "p non calculée";
  if (value < 0.001) return "p < 0,001";
  return `p = ${formatNumber(value)}`;
}

export function AnalyticsPanel({ zone, variables }: { zone: Zone; variables: Variable[] }) {
  const activeIds = useWorkspace((state) => state.activeVariableIds);
  const primaryId = useWorkspace((state) => state.primaryVariableId);
  const date = useWorkspace((state) => state.selectedDate);
  const view = useWorkspace((state) => state.analyticsView);
  const setView = useWorkspace((state) => state.setAnalyticsView);
  const setPrimary = useWorkspace((state) => state.setPrimary);
  const setDate = useWorkspace((state) => state.setDate);
  const expandedId = useWorkspace((state) => state.expandedChartVariableId);
  const setExpanded = useWorkspace((state) => state.setExpandedChart);
  const active = activeIds.map((id) => variables.find((variable) => variable.id === id)).filter((item): item is Variable => Boolean(item));
  const available = active.filter((variable) => zone.availableVariableIds.includes(variable.id));
  const [windowed, setWindowed] = useState<{ start: string; end: string } | null>(null);
  const key = `${zone.id}:${available.map((variable) => variable.id).join(",")}`;
  useEffect(() => setWindowed(null), [key]);
  const primary = available.find((variable) => variable.id === primaryId) ?? available[0] ?? null;
  const seriesQueries = useSeriesQueries(zone.id, available);
  const analytics = useAnalyticsQuery(zone.id, primary?.id ?? null, windowed?.start ?? null, windowed?.end ?? null);
  const multi = useMultivariableQuery(
    zone.id,
    available.map((variable) => variable.id),
    windowed?.start ?? null,
    windowed?.end ?? null,
  );
  if (available.length === 0) return null;
  const effective: "single" | "dual" | "normalized" =
    view === "superposition" && available.length === 2
      ? "dual"
      : view === "normalized" && available.length >= 2
        ? "normalized"
        : view === "superposition" && available.length > 2
          ? "normalized"
          : "single";

  const singleSeries = seriesQueries[available.indexOf(primary as Variable)]?.data;
  const climatology = analytics.data?.climatology ?? [];
  const means = new Map(climatology.map((row) => [row.month, row.mean]));
  const singleLine: ChartLine | null = primary && singleSeries
    ? {
        id: primary.id,
        name: primary.name,
        color: primary.color,
        unit: primary.unit,
        points: singleSeries.observations
          .filter((observation) => !windowed || (observation.date >= windowed.start && observation.date <= windowed.end))
          .map((observation) => {
            const month = Number(observation.date.slice(5, 7));
            const mean = means.get(month);
            return {
              date: observation.date,
              value: observation.value,
              anomaly: observation.value == null || mean == null ? null : observation.value - mean,
            };
          }),
      }
    : null;
  const multiLines: ChartLine[] = effective === "single" || !multi.data
    ? []
    : available.map((variable) => ({
        id: variable.id,
        name: variable.name,
        color: variable.color,
        unit: effective === "normalized" ? "σ" : variable.unit,
        points: multi.data.alignedObservations.map((row) => ({
          date: row.date,
          value: effective === "normalized" ? row.normalized[variable.id] : row.values[variable.id],
          anomaly: row.anomalies[variable.id],
        })),
      }));
  const lines = effective === "single" && singleLine ? [singleLine] : multiLines;
  const sen = analytics.data?.theilSen;
  const kendall = analytics.data?.mannKendall;

  return (
    <section className="zone-section analytics">
      <h3>{fr.analytics}</h3>
      <div className="view-switch">
        {([
          ["single", fr.viewSingle],
          ["superposition", fr.viewSuperposition],
          ["normalized", fr.viewNormalized],
        ] as const).map(([mode, label]) => (
          <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode as AnalyticsView)} disabled={mode !== "single" && available.length < 2}>
            {label}
          </button>
        ))}
      </div>
      {view === "superposition" && available.length > 2 && <p className="hint">{fr.dualNeedsTwo}</p>}
      {effective === "single" && available.length > 1 && (
        <div className="view-switch">
          {available.map((variable) => (
            <button key={variable.id} type="button" aria-pressed={variable.id === primary?.id} onClick={() => setPrimary(variable.id)}>
              <span className="swatch" style={{ background: variable.color }} /> {variable.name}
            </button>
          ))}
        </div>
      )}
      {effective === "single" && analytics.isError && (
        <p>
          {fr.statsFailed}{" "}
          <button type="button" className="text-btn" onClick={() => analytics.refetch()}>
            {fr.retry}
          </button>
        </p>
      )}
      {effective === "single" && sen && kendall && (
        <p className="hint">
          {sen.changePerDecade == null ? "Pente non calculée." : `Pente de Sen : ${formatNumber(sen.changePerDecade)} ${primary?.unit ?? ""} par décennie.`}{" "}
          {kendall.method} : {trendWord(kendall.trend)}
          {kendall.pValue != null ? ` (${pText(kendall.pValue)})` : ""}.
        </p>
      )}
      {effective === "single" && climatology.some((row) => row.count > 0) && (
        <div>
          <p className="hint">{fr.seasonal}</p>
          <svg viewBox="0 0 340 92" className="boxplot" role="img" aria-label={fr.seasonal}>
            {climatology.map((row, index) => {
              const finite = climatology.flatMap((item) => (item.min == null || item.max == null ? [] : [item.min, item.max]));
              const min = Math.min(...finite);
              const max = Math.max(...finite);
              const span = max - min || 1;
              const y = (value: number) => 8 + (1 - (value - min) / span) * 68;
              const x = 14 + index * 27;
              if (row.min == null || row.max == null || row.q1 == null || row.q3 == null || row.median == null) return null;
              return (
                <g key={row.month}>
                  <line x1={x} x2={x} y1={y(row.min)} y2={y(row.max)} stroke={primary?.color} />
                  <rect x={x - 6} y={y(row.q3)} width={12} height={Math.max(1, y(row.q1) - y(row.q3))} fill={primary?.color} opacity={0.85} />
                  <line x1={x - 6} x2={x + 6} y1={y(row.median)} y2={y(row.median)} stroke="#ebe7df" />
                  <text x={x} y={90} textAnchor="middle" className="axis-label">
                    {MONTHS[index]}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}
      {effective !== "single" && multi.isError && (
        <p>
          {fr.statsFailed}{" "}
          <button type="button" className="text-btn" onClick={() => multi.refetch()}>
            {fr.retry}
          </button>
        </p>
      )}
      {effective !== "single" && multi.data && <MultivariableInsightCard pairs={multi.data.pairs} />}
      {lines.length > 0 && lines.some((line) => line.points.some((point) => point.value != null)) && (
        <>
          <div className="chart-head">
            <p className="hint">{fr.gapHint}</p>
            <button type="button" className="icon-btn" aria-label={fr.expandChart} onClick={() => primary && setExpanded(primary.id)}>
              <Icon name="expand" />
            </button>
          </div>
          <InteractiveTimeSeriesChart
            lines={lines}
            mode={effective}
            selectedDate={date}
            trend={
              effective === "single" && sen?.startValue != null && sen.endValue != null && sen.periodStart && sen.periodEnd
                ? { start: sen.periodStart, end: sen.periodEnd, startValue: sen.startValue, endValue: sen.endValue }
                : null
            }
            onSelectDate={setDate}
            onBrush={(start, end) => setWindowed({ start, end })}
          />
        </>
      )}
      {expandedId && lines.length > 0 && (
        <Modal
          wide
          title={lines.find((line) => line.id === expandedId)?.name ?? primary?.name ?? fr.chartStage}
          onClose={() => setExpanded(null)}
          onKeyDown={(event) => {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
            const dates = [...new Set(lines.flatMap((line) => line.points.map((point) => point.date)))].sort();
            const index = date ? dates.indexOf(date) : -1;
            const next = dates[index + (event.key === "ArrowRight" ? 1 : -1)];
            if (!next) return;
            setDate(next);
            event.preventDefault();
          }}
        >
          <p className="unit">
            {zone.name} · {zone.country}
            {primary ? ` · ${primary.unit} · ${primary.datasetVersion}` : ""}
            {date ? ` · ${formatDate(date)}` : ""}
          </p>
          <div className="stage-readout">
            {lines.map((line) => {
              const point = line.points.find((item) => item.date === date);
              return (
                <p key={line.id}>
                  <span className="swatch" style={{ background: line.color }} />
                  {line.name} : {point?.value == null ? "—" : `${formatNumber(point.value)} ${line.unit}`}
                </p>
              );
            })}
          </div>
          {effective === "single" && sen && kendall && (
            <p className="hint">
              {sen.changePerDecade == null ? "Pente non calculée." : `Pente de Sen : ${formatNumber(sen.changePerDecade)} ${primary?.unit ?? ""} par décennie.`}{" "}
              {kendall.method} : {trendWord(kendall.trend)}
              {kendall.pValue != null ? ` (${pText(kendall.pValue)})` : ""}. {primary?.availableDateRange.start} – {primary?.availableDateRange.end}.
            </p>
          )}
          <InteractiveTimeSeriesChart
            lines={lines}
            mode={effective}
            layout="stage"
            selectedDate={date}
            trend={
              effective === "single" && sen?.startValue != null && sen.endValue != null && sen.periodStart && sen.periodEnd
                ? { start: sen.periodStart, end: sen.periodEnd, startValue: sen.startValue, endValue: sen.endValue }
                : null
            }
            onSelectDate={setDate}
            onBrush={(start, end) => setWindowed({ start, end })}
          />
          {windowed && (
            <button type="button" className="text-btn" onClick={() => setWindowed(null)}>
              {fr.resetZoom}
            </button>
          )}
        </Modal>
      )}
      {windowed && (
        <button type="button" className="text-btn" onClick={() => setWindowed(null)}>
          {fr.resetZoom}
        </button>
      )}
    </section>
  );
}
