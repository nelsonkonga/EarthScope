import { navigate } from "../../app/router";
import { ui } from "../../config/strings";
import type { PanelId } from "../../domain/types";
import { Icon } from "../../ui/icons";
import { IconButton } from "../../ui/IconButton";

export function LeftToolbar({ active, onSelect }: { active: PanelId | null; onSelect: (panel: PanelId) => void }) {
  return (
    <nav className="toolbar" aria-label={ui.appName}>
      <IconButton label={ui.backHome} onClick={() => navigate("/")}>
        <Icon name="home" />
      </IconButton>
      <IconButton label={ui.variables} pressed={active === "variables"} onClick={() => onSelect("variables")}>
        <Icon name="variables" />
      </IconButton>
      <IconButton label={ui.zones} pressed={active === "zones"} onClick={() => onSelect("zones")}>
        <Icon name="zones" />
      </IconButton>
      <IconButton label={ui.assistant} pressed={active === "assistant"} onClick={() => onSelect("assistant")}>
        <Icon name="chat" />
      </IconButton>
    </nav>
  );
}
