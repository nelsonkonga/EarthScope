import { useEffect, useState } from "react";
import { useAnalyticsQuery, useMultivariableQuery, useSeriesQueries } from "../../api/queries";
import { ui } from "../../config/strings";
import { formatDate, formatNumber } from "../../domain/format";
import type { AnalyticsView, ClimatologyMonth, Variable, Zone } from "../../domain/types";
import { useWorkspace } from "../../state/workspaceStore";
import { Modal } from "../../ui/Modal";
import { ExpandableFigure } from "../../ui/ExpandableFigure";
import { InteractiveTimeSeriesChart, type ChartLine } from "./InteractiveTimeSeriesChart";
import { MultivariableInsightCard } from "./MultivariableInsightCard";

const MONTHS = ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"];
const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function trendWord(direction: string) {
  if (direction === "up") return "increase";
  if (direction === "down") return "decrease";
  if (direction === "flat") return "stable";
  return "not enough data";
}

function pText(value: number | null) {
  if (value == null) return "p not computed";
  if (value < 0.001) return "p < 0.001";
  return `p = ${formatNumber(value)}`;
}

function SeasonalBoxplot({ climatology, color, unit, large = false }: { climatology: ClimatologyMonth[]; color: string; unit: string; large?: boolean }) {
  const width = large ? 960 : 340;
  const height = large ? 420 : 92;
  const pad = large ? { l: 64, r: 16, t: 16, b: 32 } : { l: 14, r: 0, t: 8, b: 16 };
  const step = (width - pad.l - pad.r) / 12;
  const finite = climatology.flatMap((item) => (item.min == null || item.max == null ? [] : [item.min, item.max]));
  const min = Math.min(...finite);
  const max = Math.max(...finite);
  const span = max - min || 1;
  const y = (value: number) => pad.t + (1 - (value - min) / span) * (height - pad.t - pad.b);
  const box = large ? 22 : 6;
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="boxplot" role="img" aria-label={ui.seasonal}>
      {large && (
        <>
          <text x={4} y={pad.t + 10} className="axis-label">
            {formatNumber(max)} {unit}
          </text>
          <text x={4} y={height - pad.b} className="axis-label">
            {formatNumber(min)} {unit}
          </text>
        </>
      )}
      {climatology.map((row, index) => {
        const x = pad.l + step * index + (large ? step / 2 : 0);
        if (row.min == null || row.max == null || row.q1 == null || row.q3 == null || row.median == null) return null;
        return (
          <g key={row.month}>
            <line x1={x} x2={x} y1={y(row.min)} y2={y(row.max)} stroke={color} strokeWidth={large ? 2 : 1} />
            <rect x={x - box} y={y(row.q3)} width={box * 2} height={Math.max(1, y(row.q1) - y(row.q3))} fill={color} opacity={0.85} rx={large ? 3 : 0} />
            <line x1={x - box} x2={x + box} y1={y(row.median)} y2={y(row.median)} style={{ stroke: "var(--chart-median)" }} strokeWidth={large ? 2 : 1} />
            <text x={x} y={height - 2} textAnchor="middle" className="axis-label">
              {large ? MONTH_NAMES[index] : MONTHS[index]}
            </text>
          </g>
        );
      })}
    </svg>
  );
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
      <h3>{ui.analytics}</h3>
      <div className="view-switch">
        {([
          ["single", ui.viewSingle],
          ["superposition", ui.viewSuperposition],
          ["normalized", ui.viewNormalized],
        ] as const).map(([mode, label]) => (
          <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode as AnalyticsView)} disabled={mode !== "single" && available.length < 2}>
            {label}
          </button>
        ))}
      </div>
      {view === "superposition" && available.length > 2 && <p className="hint">{ui.dualNeedsTwo}</p>}
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
          {ui.statsFailed}{" "}
          <button type="button" className="text-btn" onClick={() => analytics.refetch()}>
            {ui.retry}
          </button>
        </p>
      )}
      {effective === "single" && sen && kendall && (
        <p className="hint">
          {sen.changePerDecade == null ? "Slope not computed." : `Sen slope: ${formatNumber(sen.changePerDecade)} ${primary?.unit ?? ""} per decade.`}{" "}
          {kendall.method}: {trendWord(kendall.trend)}
          {kendall.pValue != null ? ` (${pText(kendall.pValue)})` : ""}.
        </p>
      )}
      {effective === "single" && climatology.some((row) => row.count > 0) && (
        <div>
          <p className="hint">{ui.seasonal}</p>
          <ExpandableFigure
            title={`${ui.seasonal} · ${primary?.name ?? ""}`}
            subtitle={`${zone.name} · ${primary?.unit ?? ""}`}
            large={() => <SeasonalBoxplot climatology={climatology} color={primary?.color ?? "currentColor"} unit={primary?.unit ?? ""} large />}
          >
            <SeasonalBoxplot climatology={climatology} color={primary?.color ?? "currentColor"} unit={primary?.unit ?? ""} />
          </ExpandableFigure>
        </div>
      )}
      {effective !== "single" && multi.isError && (
        <p>
          {ui.statsFailed}{" "}
          <button type="button" className="text-btn" onClick={() => multi.refetch()}>
            {ui.retry}
          </button>
        </p>
      )}
      {effective !== "single" && multi.data && multi.data.pairs.length > 0 && (
        <ExpandableFigure title={ui.correlation} subtitle={`${zone.name} · ${available.map((variable) => variable.name).join(", ")}`}>
          <MultivariableInsightCard pairs={multi.data.pairs} />
        </ExpandableFigure>
      )}
      {effective !== "single" && multi.data && multi.data.pairs.length === 0 && <MultivariableInsightCard pairs={[]} />}
      {lines.length > 0 && lines.some((line) => line.points.some((point) => point.value != null)) && (
        <>
          <p className="hint">{ui.gapHint}</p>
          <ExpandableFigure interactive title={primary?.name ?? ui.chartStage} onExpand={() => primary && setExpanded(primary.id)}>
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
          </ExpandableFigure>
        </>
      )}
      {expandedId && lines.length > 0 && (
        <Modal
          wide
          title={lines.find((line) => line.id === expandedId)?.name ?? primary?.name ?? ui.chartStage}
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
              {sen.changePerDecade == null ? "Slope not computed." : `Sen slope: ${formatNumber(sen.changePerDecade)} ${primary?.unit ?? ""} per decade.`}{" "}
              {kendall.method}: {trendWord(kendall.trend)}
              {kendall.pValue != null ? ` (${pText(kendall.pValue)})` : ""}. {primary ? `${formatDate(primary.availableDateRange.start)} – ${formatDate(primary.availableDateRange.end)}` : ""}.
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
              {ui.resetZoom}
            </button>
          )}
        </Modal>
      )}
      {windowed && (
        <button type="button" className="text-btn" onClick={() => setWindowed(null)}>
          {ui.resetZoom}
        </button>
      )}
    </section>
  );
}
