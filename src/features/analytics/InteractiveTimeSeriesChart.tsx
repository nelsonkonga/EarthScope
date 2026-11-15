import { useRef, useState, type PointerEvent } from "react";
import { formatDate, formatNumber } from "../../domain/format";

export type ChartPoint = { date: string; value: number | null; anomaly?: number | null };

export type ChartLine = {
  id: string;
  name: string;
  color: string;
  unit: string;
  points: ChartPoint[];
};

type TrendOverlay = { start: string; end: string; startValue: number; endValue: number };

type Props = {
  lines: ChartLine[];
  mode: "single" | "dual" | "normalized";
  selectedDate: string | null;
  trend?: TrendOverlay | null;
  layout?: "compact" | "stage";
  onSelectDate: (date: string) => void;
  onBrush: (start: string, end: string) => void;
};

function extent(values: number[]) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return { y0: min - span * 0.08, y1: max + span * 0.08 };
}

function pathFor(points: ChartPoint[], xOf: (date: string) => number, yOf: (value: number) => number) {
  const segments: string[] = [];
  let current = "";
  for (const point of points) {
    if (point.value == null) {
      if (current) segments.push(current);
      current = "";
      continue;
    }
    const command = `${current ? "L" : "M"}${xOf(point.date).toFixed(2)} ${yOf(point.value).toFixed(2)}`;
    current = current ? `${current} ${command}` : command;
  }
  if (current) segments.push(current);
  return segments;
}

export function InteractiveTimeSeriesChart({ lines, mode, selectedDate, trend, layout = "compact", onSelectDate, onBrush }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<{ x: number; date: string } | null>(null);
  const [hover, setHover] = useState<{ date: string; x: number } | null>(null);
  const [brush, setBrush] = useState<{ x0: number; x1: number } | null>(null);
  const stage = layout === "stage";
  const WIDTH = stage ? 960 : 340;
  const HEIGHT = stage ? 480 : 200;
  const pad = { l: stage ? 64 : 34, r: mode === "dual" ? (stage ? 64 : 34) : stage ? 16 : 8, t: stage ? 24 : 12, b: stage ? 36 : 22 };
  const innerW = WIDTH - pad.l - pad.r;
  const innerH = HEIGHT - pad.t - pad.b;
  const dates = lines.flatMap((line) => line.points.map((point) => point.date));
  if (dates.length === 0) return null;
  const times = dates.map((date) => Date.parse(date));
  const t0 = Math.min(...times);
  const t1 = Math.max(...times);
  const xOf = (date: string) => pad.l + ((Date.parse(date) - t0) / (t1 - t0 || 1)) * innerW;
  const dateAt = (x: number) => {
    const ratio = Math.min(1, Math.max(0, (x - pad.l) / innerW));
    const target = t0 + ratio * (t1 - t0);
    return dates.reduce((best, date) => (Math.abs(Date.parse(date) - target) < Math.abs(Date.parse(best) - target) ? date : best));
  };
  const leftValues = lines[0]?.points.flatMap((point) => (point.value == null ? [] : [point.value])) ?? [];
  const rightValues = lines[1]?.points.flatMap((point) => (point.value == null ? [] : [point.value])) ?? [];
  const left = extent(leftValues.length ? leftValues : [0, 1]);
  const right = extent(rightValues.length ? rightValues : leftValues.length ? leftValues : [0, 1]);
  const yLeft = (value: number) => pad.t + (1 - (value - left.y0) / (left.y1 - left.y0)) * innerH;
  const yRight = (value: number) => pad.t + (1 - (value - right.y0) / (right.y1 - right.y0)) * innerH;
  const yOf = (index: number, value: number) => (mode === "dual" && index === 1 ? yRight(value) : yLeft(value));
  const marker = selectedDate ? xOf(selectedDate) : null;
  const hovered = hover ? lines.map((line) => line.points.find((point) => point.date === hover.date) ?? null) : [];

  const localX = (event: PointerEvent<SVGSVGElement>) => {
    const bounds = svgRef.current?.getBoundingClientRect();
    if (!bounds) return 0;
    return ((event.clientX - bounds.left) / bounds.width) * WIDTH;
  };

  return (
    <div className={stage ? "chart stage" : "chart"}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={lines.map((line) => line.name).join(", ")}
        onPointerDown={(event) => {
          const x = localX(event);
          drag.current = { x, date: dateAt(x) };
          setBrush(null);
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          const x = localX(event);
          const date = dateAt(x);
          setHover({ date, x });
          if (drag.current) setBrush({ x0: drag.current.x, x1: x });
        }}
        onPointerUp={(event) => {
          const x = localX(event);
          const origin = drag.current;
          drag.current = null;
          setBrush(null);
          if (!origin) return;
          if (Math.abs(x - origin.x) < 8) onSelectDate(dateAt(x));
          else {
            const start = dateAt(Math.min(origin.x, x));
            const end = dateAt(Math.max(origin.x, x));
            if (start !== end) onBrush(start, end);
          }
        }}
        onPointerLeave={() => {
          setHover(null);
          if (!drag.current) setBrush(null);
        }}
      >
        <line x1={pad.l} y1={pad.t} x2={pad.l} y2={HEIGHT - pad.b} className="axis" />
        <line x1={pad.l} y1={HEIGHT - pad.b} x2={WIDTH - pad.r} y2={HEIGHT - pad.b} className="axis" />
        {mode === "dual" && <line x1={WIDTH - pad.r} y1={pad.t} x2={WIDTH - pad.r} y2={HEIGHT - pad.b} className="axis" />}
        <text x={2} y={pad.t + 8} className="axis-label" fill={lines[0]?.color}>
          {formatNumber(left.y1)}
        </text>
        <text x={2} y={HEIGHT - pad.b} className="axis-label" fill={lines[0]?.color}>
          {formatNumber(left.y0)}
        </text>
        {mode === "dual" && lines[1] && (
          <>
            <text x={WIDTH - 2} y={pad.t + 8} textAnchor="end" className="axis-label" fill={lines[1].color}>
              {formatNumber(right.y1)}
            </text>
            <text x={WIDTH - 2} y={HEIGHT - pad.b} textAnchor="end" className="axis-label" fill={lines[1].color}>
              {formatNumber(right.y0)}
            </text>
          </>
        )}
        {brush && <rect x={Math.min(brush.x0, brush.x1)} y={pad.t} width={Math.abs(brush.x1 - brush.x0)} height={innerH} className="brush" />}
        {lines.map((line, index) =>
          pathFor(line.points, xOf, (value) => yOf(index, value)).map((segment) => (
            <path key={`${line.id}-${segment.slice(0, 24)}`} d={segment} fill="none" stroke={line.color} strokeWidth={stage ? 2.4 : 1.5} />
          )),
        )}
        {trend && mode !== "dual" && (
          <path
            d={`M${xOf(trend.start)} ${yLeft(trend.startValue)} L${xOf(trend.end)} ${yLeft(trend.endValue)}`}
            fill="none"
            stroke={lines[0]?.color ?? "#fff"}
            strokeDasharray="4 3"
            strokeWidth={1}
          />
        )}
        {marker != null && <line x1={marker} x2={marker} y1={pad.t} y2={HEIGHT - pad.b} className="cursor-line" />}
        {hover && <line x1={hover.x} x2={hover.x} y1={pad.t} y2={HEIGHT - pad.b} className="axis" />}
      </svg>
      {hover && (
        <div className="chart-tip">
          <div>{formatDate(hover.date)}</div>
          {lines.map((line, index) => {
            const point = hovered[index];
            return (
              <div key={line.id}>
                {line.name} : {point?.value == null ? "—" : `${formatNumber(point.value)} ${line.unit}`}
                {point?.anomaly != null ? ` (${point.anomaly > 0 ? "+" : ""}${formatNumber(point.anomaly)} / normal)` : ""}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
