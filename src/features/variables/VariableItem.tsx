import { derivedStops } from "../../domain/colorScale";
import { kindForRole } from "../../domain/fieldView";
import { strategyForKind } from "../../domain/visualStrategies";
import type { Variable } from "../../domain/types";
import { ui } from "../../config/strings";

export function VariableItem({
  variable,
  active,
  unavailable,
  onToggle,
}: {
  variable: Variable;
  active: boolean;
  unavailable: boolean;
  onToggle: () => void;
}) {
  const stops = variable.colorScale?.stops?.length ? variable.colorScale.stops : derivedStops(variable.color);
  const gradient = `linear-gradient(90deg, ${stops.map((stop) => `${stop.color} ${stop.at * 100}%`).join(", ")})`;
  const kind = kindForRole(variable.role);
  const chip = kind ? strategyForKind(kind).chip : "";
  return (
    <div className="variable-item">
      <label>
        <input type="checkbox" checked={active} onChange={onToggle} />
        <span className="swatch" style={{ background: variable.color }} />
        <span className="variable-name">{variable.name}</span>
        {chip && <span className="mode-tag">{chip}</span>}
        <span className="unit">{variable.unit}</span>
      </label>
      <span className="mini-ramp" style={{ background: gradient }} />
      {unavailable && <p className="hint">{ui.noDataHere}</p>}
      <p className="desc">{variable.description}</p>
    </div>
  );
}
