import type { Variable } from "../../domain/types";
import { fr } from "../../config/strings.fr";

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
  return (
    <div className="variable-item">
      <label>
        <input type="checkbox" checked={active} onChange={onToggle} />
        <span className="swatch" style={{ background: variable.color }} />
        <span className="variable-name">{variable.name}</span>
        <span className="unit">{variable.unit}</span>
      </label>
      {unavailable && <p className="hint">{fr.noDataHere}</p>}
      <p className="desc">{variable.description}</p>
    </div>
  );
}
