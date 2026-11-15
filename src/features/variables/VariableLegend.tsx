import { useState } from "react";
import { derivedStops } from "../../domain/colorScale";
import type { MapLayer, Variable } from "../../domain/types";
import { formatDate, formatNumber } from "../../domain/format";
import { fr } from "../../config/strings.fr";

export type LegendEntry = {
  variable: Variable;
  value: number | null;
  chip: string;
  legend: string;
  primary: boolean;
};

export function VariableLegend({
  primary,
  layer,
  caption,
  entries,
  date,
  reading,
  updating,
  failed,
  unsupported,
  narrow,
}: {
  primary: Variable | null;
  layer: MapLayer | undefined;
  caption: string;
  entries: LegendEntry[];
  date: string | null;
  reading: number | null;
  updating: boolean;
  failed: boolean;
  unsupported: boolean;
  narrow: boolean;
}) {
  const [open, setOpen] = useState(false);
  if (!primary) return null;
  const stops = primary.colorScale?.stops?.length ? primary.colorScale.stops : derivedStops(primary.color);
  const gradient = `linear-gradient(90deg, ${stops.map((stop) => `${stop.color} ${stop.at * 100}%`).join(", ")})`;
  const min = layer?.scale?.min ?? primary.displayScale?.min;
  const max = layer?.scale?.max ?? primary.displayScale?.max;
  const position = reading == null || min == null || max == null || max === min ? null : Math.min(1, Math.max(0, (reading - min) / (max - min)));
  if (narrow && !open) {
    return (
      <button type="button" className="legend legend-collapsed" onClick={() => setOpen(true)}>
        <span className="swatch" style={{ background: primary.color }} />
        {primary.name}
      </button>
    );
  }
  return (
    <aside className="legend" aria-label={primary.name}>
      {narrow && (
        <button type="button" className="text-btn" onClick={() => setOpen(false)}>
          {fr.close}
        </button>
      )}
      <div className="legend-title">
        <span className="swatch" style={{ background: primary.color }} />
        <strong>{primary.name}</strong>
        <span className="unit">{primary.unit}</span>
      </div>
      {reading != null && (
        <p className="value">
          {formatNumber(reading)} {primary.unit}
        </p>
      )}
      <div className="ramp" style={{ background: gradient }}>
        {position != null && <i className="ramp-now" style={{ left: `${position * 100}%` }} />}
      </div>
      <div className="ramp-labels">
        <span>{min == null ? "—" : formatNumber(min)}</span>
        <span>{max == null ? "—" : formatNumber(max)}</span>
      </div>
      {date && <p className="hint">{formatDate(date)}</p>}
      {caption && <p className="hint">{caption}</p>}
      <p className="hint">{fr.legendFootprint}</p>
      {entries.find((entry) => entry.primary)?.legend && <p className="hint">{entries.find((entry) => entry.primary)?.legend}</p>}
      {layer && reading == null && <p className="hint">{fr.legendGap}</p>}
      {entries.some((entry) => !entry.primary) && (
        <ul className="legend-rings">
          {entries
            .filter((entry) => !entry.primary)
            .map((entry) => (
              <li key={entry.variable.id}>
                <span>
                  <span className="swatch ring" style={{ borderColor: entry.variable.color }} />
                  {entry.variable.name}
                  <span className="unit"> {entry.chip}</span>
                </span>
                <span>{entry.value == null ? "—" : `${formatNumber(entry.value)} ${entry.variable.unit}`}</span>
              </li>
            ))}
        </ul>
      )}
      {unsupported && <p className="hint">{fr.unsupportedLayer}</p>}
      {updating && <p className="hint">{fr.updating}</p>}
      {failed && <p className="hint">{fr.updateFailed}</p>}
    </aside>
  );
}
