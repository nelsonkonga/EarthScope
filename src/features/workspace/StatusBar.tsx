import { useSyncExternalStore } from "react";
import { fr } from "../../config/strings.fr";
import { formatAltitude, formatLatLon } from "../../domain/format";
import { getCameraSample, subscribeCamera } from "../globe/cameraBridge";

export function StatusBar({ fixture, notice, loadingZones }: { fixture: boolean; notice: string | null; loadingZones: boolean }) {
  const sample = useSyncExternalStore(subscribeCamera, getCameraSample);
  const position =
    sample.latitude == null || sample.longitude == null ? "—" : formatLatLon(sample.latitude, sample.longitude);
  return (
    <footer className="status-bar">
      <span>{loadingZones ? fr.loadingZones : position}</span>
      <span className="altitude">{sample.height == null ? "—" : formatAltitude(sample.height)}</span>
      <span className="scale" aria-label={sample.scale}>
        <i />
        {sample.scale}
      </span>
      <span className="notice" role="status">
        {notice}
      </span>
      <span className="sources">
        {fixture ? `${fr.fixture} · ` : ""}
        {fr.sources}
      </span>
    </footer>
  );
}
