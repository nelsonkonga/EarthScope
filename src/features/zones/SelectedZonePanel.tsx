import { ZONE_COLORS, fr } from "../../config/strings.fr";
import { kindForRole } from "../../domain/fieldView";
import { strategyForKind } from "../../domain/visualStrategies";
import { formatLatLon, formatNumber, formatTrend, statusWord } from "../../domain/format";
import type { Variable, Zone } from "../../domain/types";
import { useComparisonQuery, useRankingQuery, useSeriesQueries } from "../../api/queries";
import { useWorkspace } from "../../state/workspaceStore";
import { AnalyticsPanel } from "../analytics/AnalyticsPanel";
import { ComparisonChart } from "../charts/TrendChart";
import { Icon } from "../../ui/icons";

export function SelectedZonePanel({ zones, variables }: { zones: Zone[]; variables: Variable[] }) {
  const zoneId = useWorkspace((state) => state.selectedZoneId);
  const cardOpen = useWorkspace((state) => state.zoneCardOpen);
  const closeCard = useWorkspace((state) => state.closeCard);
  const activeIds = useWorkspace((state) => state.activeVariableIds);
  const primaryId = useWorkspace((state) => state.primaryVariableId);
  const date = useWorkspace((state) => state.selectedDate);
  const comparison = useWorkspace((state) => state.comparison);
  const clearComparison = useWorkspace((state) => state.setComparison);
  const zone = zones.find((item) => item.id === zoneId) ?? null;
  const active = activeIds.map((id) => variables.find((variable) => variable.id === id)).filter((item): item is Variable => Boolean(item));
  const available = zone ? active.filter((variable) => zone.availableVariableIds.includes(variable.id)) : [];
  const seriesQueries = useSeriesQueries(zone && cardOpen ? zone.id : null, available);
  const ranking = useRankingQuery(comparison?.mode === "rank" ? comparison.variableId : null, comparison?.metric ?? null);
  const compared = useComparisonQuery(comparison?.mode === "compare" ? comparison.variableId : null, comparison?.mode === "compare" ? comparison.zoneIds : []);
  if ((!zone || !cardOpen) && !comparison) return null;

  return (
    <aside className="zone-card">
      {zone && cardOpen && (
        <>
          <div className="panel-head">
            <div>
              <h2>{zone.name}</h2>
              <p className="unit">{zone.country}</p>
              <p className="coords">{formatLatLon(zone.latitude, zone.longitude)}</p>
            </div>
            <button type="button" className="icon-btn" aria-label={fr.close} onClick={closeCard}>
              <Icon name="close" />
            </button>
          </div>
          {variables.some((variable) => variable.datasetVersion.startsWith("fixture")) && <p className="hint">{fr.fixtureValues}</p>}
          {active.length === 0 && <p>{fr.chooseVariable}</p>}
          {active.map((variable) => {
            const kind = kindForRole(variable.role);
            const allowed = zone.availableVariableIds.includes(variable.id);
            const query = seriesQueries[available.indexOf(variable)];
            const series = query?.data;
            const observation = series?.observations.find((item) => item.date === date);
            return (
              <section key={variable.id} className={variable.id === primaryId ? "zone-section is-primary" : "zone-section"}>
                <h3>
                  <span className="swatch" style={{ background: variable.color }} />
                  {variable.name}
                  {variable.id === primaryId && <span className="chip-tag">{fr.primary}</span>}
                </h3>
                {kind && <p className="hint">{strategyForKind(kind).legend}</p>}
                {!allowed && <p>{fr.noDataFor(variable.name, zone.name)}</p>}
                {allowed && query?.isError && (
                  <p>
                    {fr.seriesFailed}{" "}
                    <button type="button" className="text-btn" onClick={() => query.refetch()}>
                      {fr.retry}
                    </button>
                  </p>
                )}
                {allowed && series && (
                  <>
                    <p className="value">
                      {observation?.value == null ? (
                        "Indisponible"
                      ) : (
                        <>
                          {formatNumber(observation.value)} {variable.unit}
                          <span className="unit"> {statusWord(observation.status)}</span>
                        </>
                      )}
                    </p>
                    <p>{formatTrend(series.trend, variable.unit)}</p>
                    {!series.observations.some((item) => item.status !== "missing" && item.value != null) && (
                      <p>{fr.noDataFor(variable.name, zone.name)}</p>
                    )}
                  </>
                )}
              </section>
            );
          })}
          <AnalyticsPanel zone={zone} variables={variables} />
        </>
      )}
      {comparison && (
        <section className="zone-section">
          <div className="panel-head">
            <h2>{comparison.mode === "rank" ? fr.ranking : fr.comparison}</h2>
            <button type="button" className="text-btn" onClick={() => clearComparison(null)}>
              {fr.clearComparison}
            </button>
          </div>
          {comparison.mode === "rank" && (
            <>
              <p className="hint">{fr.rankingOrder}</p>
              <ol className="rank-list">
                {(ranking.data?.entries ?? []).map((entry) => {
                  const name = zones.find((item) => item.id === entry.zoneId)?.name ?? entry.zoneId;
                  return (
                    <li key={entry.zoneId}>
                      <button type="button" onClick={() => useWorkspace.getState().selectZone(entry.zoneId)}>
                        {entry.rank}. {name}
                        <span className="unit">
                          {entry.changePerDecade == null ? "—" : `${formatNumber(entry.changePerDecade)} ${ranking.data?.unit ?? ""}`}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ol>
            </>
          )}
          {comparison.mode === "compare" && compared.data && (
            <>
              <ul className="legend-rings">
                {compared.data.series.map((series, index) => (
                  <li key={series.zoneId}>
                    <span className="swatch" style={{ background: ZONE_COLORS[index % ZONE_COLORS.length] }} />
                    {zones.find((item) => item.id === series.zoneId)?.name ?? series.zoneId}
                  </li>
                ))}
              </ul>
              <ComparisonChart
                selectedDate={date}
                items={compared.data.series.map((series, index) => ({
                  series,
                  color: ZONE_COLORS[index % ZONE_COLORS.length],
                  name: zones.find((item) => item.id === series.zoneId)?.name ?? series.zoneId,
                }))}
              />
            </>
          )}
        </section>
      )}
    </aside>
  );
}
