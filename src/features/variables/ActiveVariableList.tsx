import { fr } from "../../config/strings.fr";
import { kindForRole } from "../../domain/fieldView";
import { strategyForKind } from "../../domain/visualStrategies";
import type { Variable } from "../../domain/types";
import { useWorkspace } from "../../state/workspaceStore";
import { Icon } from "../../ui/icons";

export function ActiveVariableList({ variables }: { variables: Variable[] }) {
  const ids = useWorkspace((state) => state.activeVariableIds);
  const primary = useWorkspace((state) => state.primaryVariableId);
  const setPrimary = useWorkspace((state) => state.setPrimary);
  const remove = useWorkspace((state) => state.removeVariable);
  const active = ids.map((id) => variables.find((variable) => variable.id === id)).filter((item): item is Variable => Boolean(item));
  if (active.length === 0) return null;
  return (
    <div className="chips">
      {active.map((variable) => {
        const kind = kindForRole(variable.role);
        const chip = kind ? strategyForKind(kind).chip : variable.unit;
        return (
        <div key={variable.id} className={variable.id === primary ? "chip primary" : "chip"}>
          <button type="button" className="chip-main" onClick={() => setPrimary(variable.id)} aria-label={`${fr.makePrimary} : ${variable.name}`}>
            <span className="swatch" style={{ background: variable.color }} />
            {variable.name}
            <span className="chip-tag">{chip}</span>
            {variable.id === primary && <span className="chip-tag">{fr.primary}</span>}
          </button>
          <button type="button" className="chip-x" aria-label={`${fr.removeVariable} ${variable.name}`} onClick={() => remove(variable.id)}>
            <Icon name="close" />
          </button>
        </div>
        );
      })}
    </div>
  );
}
