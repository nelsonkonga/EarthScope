import { ui } from "../../config/strings";
import type { Variable, VariableCategory } from "../../domain/types";
import { useWorkspace } from "../../state/workspaceStore";
import { useZoneCatalog } from "../../api/queries";
import { VariableItem } from "./VariableItem";

export function VariablePanel({ variables, categories }: { variables: Variable[]; categories: VariableCategory[] }) {
  const active = useWorkspace((state) => state.activeVariableIds);
  const zoneId = useWorkspace((state) => state.selectedZoneId);
  const toggle = useWorkspace((state) => state.toggleVariable);
  const clear = useWorkspace((state) => state.clearVariables);
  const zones = useZoneCatalog();
  const zone = zones.data?.zones.find((item) => item.id === zoneId);
  const known = new Set(categories.map((category) => category.id));
  const groups = [...categories].sort((a, b) => a.order - b.order);
  const extras = variables.some((variable) => !known.has(variable.categoryId));

  return (
    <div className="panel-body">
      <div className="panel-head">
        <h2>{ui.variables}</h2>
        <button type="button" className="text-btn" onClick={clear} disabled={active.length === 0}>
          {ui.clearAll}
        </button>
      </div>
      {variables.length === 0 && <p className="hint">{ui.noVariables}</p>}
      {groups.map((category) => {
        const items = variables.filter((variable) => variable.categoryId === category.id);
        if (items.length === 0) return null;
        return (
          <section key={category.id} className="variable-group">
            <h3>{category.name}</h3>
            {items.map((variable) => (
              <VariableItem
                key={variable.id}
                variable={variable}
                active={active.includes(variable.id)}
                unavailable={Boolean(zone && !zone.availableVariableIds.includes(variable.id))}
                onToggle={() => toggle(variable.id)}
              />
            ))}
          </section>
        );
      })}
      {extras && (
        <section className="variable-group">
          <h3>{ui.otherCategory}</h3>
          {variables
            .filter((variable) => !known.has(variable.categoryId))
            .map((variable) => (
              <VariableItem
                key={variable.id}
                variable={variable}
                active={active.includes(variable.id)}
                unavailable={Boolean(zone && !zone.availableVariableIds.includes(variable.id))}
                onToggle={() => toggle(variable.id)}
              />
            ))}
        </section>
      )}
    </div>
  );
}
