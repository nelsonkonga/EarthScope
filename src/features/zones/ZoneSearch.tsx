import { useMemo, useState } from "react";
import { useZoneCatalog } from "../../api/queries";
import { ui } from "../../config/strings";
import { foldText } from "../../domain/format";
import type { Zone } from "../../domain/types";
import { useWorkspace } from "../../state/workspaceStore";

export function ZoneSearch({ zones, complete }: { zones: Zone[]; complete: boolean }) {
  const [query, setQuery] = useState("");
  const remote = useZoneCatalog(query, !complete && query.trim().length > 0);
  const selectZone = useWorkspace((state) => state.selectZone);
  const selectedId = useWorkspace((state) => state.selectedZoneId);
  const results = useMemo(() => {
    const source = !complete && query.trim() ? (remote.data?.zones ?? []) : zones;
    const folded = foldText(query.trim());
    const filtered = folded
      ? source.filter((zone) => foldText([zone.name, zone.country, ...(zone.aliases ?? [])].join(" ")).includes(folded))
      : source;
    return [...filtered].sort((a, b) => a.name.localeCompare(b.name, "en-US"));
  }, [complete, query, remote.data?.zones, zones]);

  return (
    <div className="panel-body">
      <h2>{ui.zones}</h2>
      <input
        id="zone-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={ui.searchPlaceholder}
        aria-label={ui.searchPlaceholder}
        autoComplete="off"
      />
      {zones.length === 0 && <p className="hint">{ui.noZones}</p>}
      {query.trim() && results.length === 0 && <p className="hint">{ui.noZoneMatch}</p>}
      <ul className="zone-list">
        {results.map((zone) => (
          <li key={zone.id}>
            <button type="button" aria-current={zone.id === selectedId} onClick={() => selectZone(zone.id)}>
              <span>{zone.name}</span>
              <span className="unit">{zone.country}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
