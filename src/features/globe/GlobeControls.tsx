import { ui } from "../../config/strings";
import { Icon } from "../../ui/icons";
import { IconButton } from "../../ui/IconButton";
import { globe } from "./globeApi";

export function GlobeControls({ fullscreen, onFullscreen }: { fullscreen: boolean; onFullscreen: () => void }) {
  return (
    <div className="globe-controls">
      <IconButton label={ui.zoomIn} onClick={() => globe()?.zoomIn()}>
        <Icon name="plus" />
      </IconButton>
      <IconButton label={ui.zoomOut} onClick={() => globe()?.zoomOut()}>
        <Icon name="minus" />
      </IconButton>
      <IconButton label={ui.home} onClick={() => globe()?.home()}>
        <Icon name="compass" />
      </IconButton>
      <IconButton label={fullscreen ? ui.exitFullscreen : ui.fullscreen} onClick={onFullscreen}>
        <Icon name="expand" />
      </IconButton>
    </div>
  );
}
