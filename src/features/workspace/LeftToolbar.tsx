import { fr } from "../../config/strings.fr";
import type { PanelId } from "../../domain/types";
import { Icon } from "../../ui/icons";
import { IconButton } from "../../ui/IconButton";

export function LeftToolbar({ active, onSelect }: { active: PanelId | null; onSelect: (panel: PanelId) => void }) {
  return (
    <nav className="toolbar" aria-label={fr.appName}>
      <IconButton label={fr.variables} pressed={active === "variables"} onClick={() => onSelect("variables")}>
        <Icon name="variables" />
      </IconButton>
      <IconButton label={fr.zones} pressed={active === "zones"} onClick={() => onSelect("zones")}>
        <Icon name="zones" />
      </IconButton>
      <IconButton label={fr.assistant} pressed={active === "assistant"} onClick={() => onSelect("assistant")}>
        <Icon name="chat" />
      </IconButton>
    </nav>
  );
}
