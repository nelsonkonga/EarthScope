import { YEAR_TICKS, extent, linear, ticks } from "../lib/chart.js";
import { num } from "../lib/format.js";

export const AM = { l: 46, r: 14, t: 16, b: 26 };

/** Scales of a yearly chart: x over 1981–2026 (a year's dot at its middle), y over the values. */
export function annualScales(series, W, H, extra = []) {
  const dom = extent([...series.annual, ...extra], 0.12);
  const x = linear([1981, 2026], [AM.l, W - AM.r]);
  const y = linear(dom, [H - AM.b, AM.t]);
  const yt = ticks(dom[0], dom[1], H < 250 ? 4 : 5);
  const step = yt.length > 1 ? yt[1] - yt[0] : 1;
  return { x, y, yt, dig: step >= 1 ? 0 : step >= 0.1 ? 1 : 2, dom };
}

export function Axes({ sc, W, H, zero = true }) {
  const { x, y, yt, dig } = sc;
  return (
    <g>
      {yt.map((v) => (
        <g key={v}>
          <line x1={AM.l} x2={W - AM.r} y1={y(v)} y2={y(v)} stroke="var(--grid)" />
          <text className="tick" x={AM.l - 8} y={y(v) + 4} textAnchor="end">{num(v, dig, true)}</text>
        </g>
      ))}
      {zero && <line x1={AM.l} x2={W - AM.r} y1={y(0)} y2={y(0)} stroke="var(--axis)" />}
      {YEAR_TICKS.map((yr) => (
        <text key={yr} className="tick" x={x(yr + 0.5)} y={H - 6} textAnchor="middle">{yr}</text>
      ))}
    </g>
  );
}

export function Dots({ series, sc, active = -1, dim = false }) {
  return series.years.map((yr, j) => series.annual[j] != null && (
    <circle
      key={yr}
      cx={sc.x(yr + 0.5)}
      cy={sc.y(series.annual[j])}
      r={j === active ? 6 : 4}
      fill="var(--data)"
      opacity={dim && j !== active ? 0.55 : 1}
      stroke="var(--surface)"
      strokeWidth="2"
      style={{ transition: "r 0.15s, opacity 0.2s" }}
    />
  ));
}
