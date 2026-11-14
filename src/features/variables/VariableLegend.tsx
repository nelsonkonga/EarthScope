import { useState } from "react";
import { derivedStops } from "../../domain/colorScale";
import type { MapLayer, Variable } from "../../domain/types";
import { formatNumber } from "../../domain/format";
import { fr } from "../../config/strings.fr";

export function VariableLegend({
  primary,
  secondaries,
  layer,
  updating,
  failed,
  unsupported,
  narrow,
}: {
  primary: Variable | null;
  secondaries: Variable[];
  layer: MapLayer | undefined;
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
      <div className="ramp" style={{ background: gradient }} />
      <div className="ramp-labels">
        <span>{min == null ? "—" : formatNumber(min)}</span>
        <span>{max == null ? "—" : formatNumber(max)}</span>
      </div>
      <p className="hint">{fr.legendValue}</p>
      <p className="hint">{fr.legendPoint}</p>
      {secondaries.length > 0 && (
        <ul className="legend-rings">
          {secondaries.map((variable) => (
            <li key={variable.id}>
              <span className="swatch ring" style={{ borderColor: variable.color }} />
              {variable.name}
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
