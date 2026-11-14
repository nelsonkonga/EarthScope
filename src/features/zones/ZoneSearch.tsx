import { useMemo, useState } from "react";
import { useZoneCatalog } from "../../api/queries";
import { fr } from "../../config/strings.fr";
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
    return [...filtered].sort((a, b) => a.name.localeCompare(b.name, "fr"));
  }, [complete, query, remote.data?.zones, zones]);

  return (
    <div className="panel-body">
      <h2>{fr.zones}</h2>
      <input
        id="zone-search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={fr.searchPlaceholder}
        aria-label={fr.searchPlaceholder}
        autoComplete="off"
      />
      {zones.length === 0 && <p className="hint">{fr.noZones}</p>}
      {query.trim() && results.length === 0 && <p className="hint">{fr.noZoneMatch}</p>}
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
