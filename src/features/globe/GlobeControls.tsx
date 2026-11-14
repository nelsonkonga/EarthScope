import { fr } from "../../config/strings.fr";
import { Icon } from "../../ui/icons";
import { IconButton } from "../../ui/IconButton";
import { globe } from "./globeApi";

export function GlobeControls({ fullscreen, onFullscreen }: { fullscreen: boolean; onFullscreen: () => void }) {
  return (
    <div className="globe-controls">
      <IconButton label={fr.zoomIn} onClick={() => globe()?.zoomIn()}>
        <Icon name="plus" />
      </IconButton>
      <IconButton label={fr.zoomOut} onClick={() => globe()?.zoomOut()}>
        <Icon name="minus" />
      </IconButton>
      <IconButton label={fr.home} onClick={() => globe()?.home()}>
        <Icon name="compass" />
      </IconButton>
      <IconButton label={fullscreen ? fr.exitFullscreen : fr.fullscreen} onClick={onFullscreen}>
        <Icon name="expand" />
      </IconButton>
    </div>
  );
}
