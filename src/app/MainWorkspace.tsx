import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useLayerQueries, useRankingQuery, useVariableCatalog, useZoneCatalog } from "../api/queries";
import { fr } from "../config/strings.fr";
import { composeField } from "../domain/fieldView";
import { markerAppearance } from "../domain/markers";
import { maxEnd } from "../domain/time";
import { AIChatPanel } from "../features/assistant/AIChatPanel";
import { globe, showField, showMarkers } from "../features/globe/globeApi";
import { GlobeControls } from "../features/globe/GlobeControls";
import { GlobeViewport } from "../features/globe/GlobeViewport";
import { Timeline } from "../features/time/Timeline";
import { ActiveVariableList } from "../features/variables/ActiveVariableList";
import { VariableLegend } from "../features/variables/VariableLegend";
import { VariablePanel } from "../features/variables/VariablePanel";
import { SelectedZonePanel } from "../features/zones/SelectedZonePanel";
import { ZoneSearch } from "../features/zones/ZoneSearch";
import { LeftToolbar } from "../features/workspace/LeftToolbar";
import { StatusBar } from "../features/workspace/StatusBar";
import { useWorkspace } from "../state/workspaceStore";
import { Modal } from "../ui/Modal";

function useNarrow() {
  const [narrow, setNarrow] = useState(() => window.matchMedia("(max-width: 1023px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 1023px)");
    const apply = () => setNarrow(media.matches);
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
  return narrow;
}

export function MainWorkspace() {
  const zonesQuery = useZoneCatalog();
  const variablesQuery = useVariableCatalog();
  const zones = zonesQuery.data?.zones ?? [];
  const variables = variablesQuery.data?.variables ?? [];
  const categories = variablesQuery.data?.categories ?? [];
  const activeIds = useWorkspace((state) => state.activeVariableIds);
  const primaryId = useWorkspace((state) => state.primaryVariableId);
  const selectedZoneId = useWorkspace((state) => state.selectedZoneId);
  const selectionNonce = useWorkspace((state) => state.selectionNonce);
  const comparison = useWorkspace((state) => state.comparison);
  const activePanel = useWorkspace((state) => state.activePanel);
  const notice = useWorkspace((state) => state.notice);
  const selectedDate = useWorkspace((state) => state.selectedDate);
  const playback = useWorkspace((state) => state.playback);
  const playbackSpeed = useWorkspace((state) => state.playbackSpeed);
  const cardOpen = useWorkspace((state) => state.zoneCardOpen);
  const togglePanel = useWorkspace((state) => state.togglePanel);
  const setPanel = useWorkspace((state) => state.setPanel);
  const closeCard = useWorkspace((state) => state.closeCard);
  const ensureDate = useWorkspace((state) => state.ensureDate);
  const narrow = useNarrow();
  const [reducedMotion, setReducedMotion] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReducedMotion(media.matches);
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
  const [fullscreen, setFullscreen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const primary = variables.find((variable) => variable.id === primaryId) ?? null;
  const secondaries = activeIds
    .filter((id) => id !== primaryId)
    .map((id) => variables.find((variable) => variable.id === id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item));
  const layerQueries = useLayerQueries(primary ? [primary, ...secondaries] : []);
  const primaryLayer = layerQueries[0]?.data;
  const studyZone = zones.find((zone) => zone.id === "zone_yaounde") ?? zones[0] ?? null;
  const readingKey = layerQueries
    .map((query) => {
      const layer = query.data;
      if (!layer) return "";
      return `${layer.variableId}:${layer.date}:${layer.scale?.min ?? ""}:${layer.scale?.max ?? ""}:${layer.zoneValues.map((value) => `${value.zoneId}:${value.status}:${value.value}`).join(",")}`;
    })
    .join("|");
  const primaryKey = primary ? `${primary.id}:${primary.datasetVersion}` : "";
  const secondaryKey = secondaries.map((variable) => `${variable.id}:${variable.datasetVersion}`).join(",");
  const footprintKey = studyZone ? `${studyZone.id}:${studyZone.footprint?.join(",") ?? ""}:${studyZone.boundary?.length ?? 0}` : "";
  const field = useMemo(
    () =>
      studyZone
        ? composeField({
            zone: studyZone,
            primary,
            secondaries,
            valueOf: (variableId) => {
              const layer = layerQueries.find((query) => query.data?.variableId === variableId)?.data;
              const row = layer?.zoneValues.find((value) => value.zoneId === studyZone.id);
              if (!row || row.status === "missing") return null;
              return row.value;
            },
            scaleOf: (variable) => {
              const layer = layerQueries.find((query) => query.data?.variableId === variable.id)?.data;
              return layer?.scale ?? variable.displayScale ?? null;
            },
          })
        : null,
    // Keys stand in for the catalog objects. The memo only rebuilds when a reading or the selection changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [footprintKey, primaryKey, readingKey, secondaryKey],
  );
  const reading = primaryLayer?.zoneValues.find((value) => value.zoneId === studyZone?.id) ?? null;
  const ranking = useRankingQuery(comparison?.mode === "rank" ? comparison.variableId : null, comparison?.metric ?? null);
  const highlighted =
    comparison?.mode === "compare"
      ? comparison.zoneIds
      : comparison?.mode === "rank" && ranking.data
        ? ranking.data.entries.map((entry) => entry.zoneId)
        : null;

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("ask")) setPanel("assistant");
    document.title = `Visualisation · ${fr.appName}`;
  }, [setPanel]);

  useEffect(() => {
    const end = maxEnd(variables);
    if (end) ensureDate(end);
  }, [ensureDate, variables]);

  useEffect(() => {
    const zone = zones.find((item) => item.id === selectedZoneId);
    if (zone) globe()?.flyTo(zone.longitude, zone.latitude);
  }, [selectionNonce, selectedZoneId, zones]);

  useEffect(() => {
    if (!primary || !studyZone) return;
    globe()?.flyTo(studyZone.longitude, studyZone.latitude);
  }, [primary?.id, studyZone]);

  useEffect(() => {
    showMarkers(
      zones.map((zone) => {
        const observation = primaryLayer?.zoneValues.find((value) => value.zoneId === zone.id) ?? null;
        const appearance = markerAppearance({
          zoneId: zone.id,
          selected: zone.id === selectedZoneId,
          primary,
          secondaries,
          observation,
          scale: primaryLayer?.scale ?? null,
          highlighted,
        });
        return {
          id: zone.id,
          name: zone.name,
          latitude: zone.latitude,
          longitude: zone.longitude,
          ...appearance,
        };
      }),
    );
  }, [highlighted, primary, primaryLayer, secondaries, selectedZoneId, zones]);

  useEffect(() => {
    showField(field ? { ...field, transitionMs: reducedMotion ? 0 : playback === "playing" ? Math.round(760 / playbackSpeed) : 720, animate: !reducedMotion } : null);
  }, [field, playback, playbackSpeed, reducedMotion]);

  useEffect(() => {
    const onChange = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.closest("input, textarea, select, .side-panel, .zone-card, .timeline, dialog");
      if (event.key === "?" && !target?.closest("input, textarea")) {
        setHelpOpen(true);
        event.preventDefault();
      }
      if (event.key === "Escape") {
        const state = useWorkspace.getState();
        if (helpOpen) setHelpOpen(false);
        else if (state.expandedChartVariableId) state.setExpandedChart(null);
        else if (state.activePanel) setPanel(null);
        else closeCard();
      }
      if (typing) return;
      if (event.key === "1") togglePanel("variables");
      if (event.key === "2") togglePanel("zones");
      if (event.key === "3") togglePanel("assistant");
      if (event.key === "/") {
        setPanel("zones");
        window.setTimeout(() => document.getElementById("zone-search")?.focus(), 0);
        event.preventDefault();
      }
      if (event.key === " " && target?.tagName !== "BUTTON") {
        const state = useWorkspace.getState();
        state.setPlayback(state.playback === "playing" ? "paused" : "playing");
        event.preventDefault();
      }
      if (event.key === "ArrowLeft") (event.shiftKey ? globe()?.orbit("left") : globe()?.pan("left"));
      if (event.key === "ArrowRight") (event.shiftKey ? globe()?.orbit("right") : globe()?.pan("right"));
      if (event.key === "ArrowUp") globe()?.pan("up");
      if (event.key === "ArrowDown") globe()?.pan("down");
      if (event.key === "+" || event.key === "=") globe()?.zoomIn();
      if (event.key === "-") globe()?.zoomOut();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeCard, helpOpen, setPanel, togglePanel]);

  const fixture = (variablesQuery.data?.meta.datasetVersion ?? zonesQuery.data?.meta.datasetVersion ?? "").startsWith("fixture");
  return (
    <div
      className={`workspace ${narrow ? "narrow" : "wide"} ${activePanel ? "panel-open" : ""} ${cardOpen ? "card-open" : ""} ${fullscreen ? "is-fullscreen" : ""}`}
      data-field={field?.theme ?? "neutral"}
      style={field ? ({ "--accent": field.accent } as CSSProperties) : undefined}
    >
      <h1 className="sr-only">{fr.appName}</h1>
      {(zonesQuery.isLoading || variablesQuery.isLoading) && <div className="load-line" />}
      <GlobeViewport />
      <ActiveVariableList variables={variables} />
      <LeftToolbar active={activePanel} onSelect={togglePanel} />
      {activePanel && (
        <section className="side-panel" aria-label={activePanel === "variables" ? fr.variables : activePanel === "zones" ? fr.zones : fr.assistant}>
          {zonesQuery.isError && activePanel === "zones" && (
            <p className="panel-body">
              {fr.zonesFailed}{" "}
              <button type="button" className="text-btn" onClick={() => zonesQuery.refetch()}>
                {fr.retry}
              </button>
            </p>
          )}
          {variablesQuery.isError && activePanel === "variables" && (
            <p className="panel-body">
              {fr.variablesFailed}{" "}
              <button type="button" className="text-btn" onClick={() => variablesQuery.refetch()}>
                {fr.retry}
              </button>
            </p>
          )}
          {activePanel === "variables" && !variablesQuery.isError && <VariablePanel variables={variables} categories={categories} />}
          {activePanel === "zones" && !zonesQuery.isError && <ZoneSearch zones={zones} complete={zonesQuery.data?.meta.complete ?? true} />}
          {activePanel === "assistant" && <AIChatPanel catalog={{ zones, variables }} />}
        </section>
      )}
      <SelectedZonePanel zones={zones} variables={variables} />
      <GlobeControls
        fullscreen={fullscreen}
        onFullscreen={() => {
          if (document.fullscreenElement) void document.exitFullscreen();
          else void document.querySelector(".workspace")?.requestFullscreen();
        }}
      />
      <VariableLegend
        primary={primary}
        layer={primaryLayer}
        caption={field?.caption ?? ""}
        date={selectedDate}
        entries={(primary ? [primary, ...secondaries] : []).map((variable) => {
          const row = layerQueries.find((query) => query.data?.variableId === variable.id)?.data?.zoneValues.find((value) => value.zoneId === studyZone?.id);
          const drawn = field?.layers.find((layer) => layer.variableId === variable.id);
          return {
            variable,
            value: !row || row.status === "missing" ? null : row.value,
            chip: drawn?.chip ?? "",
            legend: drawn?.legend ?? "",
            primary: variable.id === primary?.id,
          };
        })}
        reading={reading?.status === "missing" ? null : (reading?.value ?? null)}
        updating={layerQueries.some((query) => query.isFetching && !query.isLoading)}
        failed={Boolean(layerQueries[0]?.isError)}
        unsupported={primaryLayer?.mode === "raster-tiles"}
        narrow={narrow}
      />
      <Timeline variables={variables} />
      <StatusBar fixture={fixture} notice={notice} loadingZones={zonesQuery.isLoading} />
      {helpOpen && (
        <Modal title={fr.help} onClose={() => setHelpOpen(false)}>
          <ul className="shortcuts">
            {fr.shortcuts.map(([keys, description]) => (
              <li key={keys}>
                <kbd>{keys}</kbd>
                <span>{description}</span>
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </div>
  );
}
