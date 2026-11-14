import { useEffect, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { fetchLayer } from "../../api/resources";
import { fr } from "../../config/strings.fr";
import { buildSteps, nearestStep, shiftStep } from "../../domain/time";
import type { Variable } from "../../domain/types";
import { formatDate } from "../../domain/format";
import { useWorkspace } from "../../state/workspaceStore";
import { Icon } from "../../ui/icons";
import { IconButton } from "../../ui/IconButton";

export function Timeline({ variables }: { variables: Variable[] }) {
  const date = useWorkspace((state) => state.selectedDate);
  const playback = useWorkspace((state) => state.playback);
  const speed = useWorkspace((state) => state.playbackSpeed);
  const primaryId = useWorkspace((state) => state.primaryVariableId);
  const setDate = useWorkspace((state) => state.setDate);
  const setPlayback = useWorkspace((state) => state.setPlayback);
  const setSpeed = useWorkspace((state) => state.setSpeed);
  const primary = variables.find((variable) => variable.id === primaryId) ?? variables[0];
  const extentStart = variables.reduce<string | null>(
    (start, variable) => (start == null || variable.availableDateRange.start < start ? variable.availableDateRange.start : start),
    null,
  );
  const extentEnd = variables.reduce<string | null>(
    (end, variable) => (end == null || variable.availableDateRange.end > end ? variable.availableDateRange.end : end),
    null,
  );
  const resolution = primary?.defaultResolution;
  const steps = useMemo(
    () => (extentStart && extentEnd && resolution ? buildSteps(extentStart, extentEnd, resolution) : []),
    [extentEnd, extentStart, resolution],
  );
  const index = date ? steps.indexOf(nearestStep(steps, date) ?? "") : -1;
  const queryClient = useQueryClient();

  useEffect(() => {
    if (playback !== "playing" || steps.length === 0) return;
    const delay = speed === 1 ? 800 : speed === 2 ? 400 : 200;
    const timer = window.setInterval(() => {
      const current = useWorkspace.getState().selectedDate;
      if (!current) return;
      const next = shiftStep(steps, current, 1);
      if (!next) {
        useWorkspace.getState().setPlayback("paused");
        return;
      }
      useWorkspace.getState().setDate(next);
    }, delay);
    return () => window.clearInterval(timer);
  }, [playback, speed, steps]);

  useEffect(() => {
    if (playback !== "playing" || !primary || !date) return;
    const next = shiftStep(steps, date, 1);
    if (!next) return;
    void queryClient.prefetchQuery({
      queryKey: ["layer", primary.id, next, primary.datasetVersion],
      queryFn: ({ signal }) => fetchLayer(primary.id, next, signal),
      staleTime: Infinity,
    });
  }, [date, playback, primary, queryClient, steps]);

  const disabled = steps.length === 0;
  return (
    <section className="timeline" aria-label={fr.timeline}>
      <div className="timeline-controls">
        <IconButton label={fr.stepBack} disabled={disabled || index <= 0} onClick={() => date && setDate(shiftStep(steps, date, -1) ?? date)}>
          <Icon name="back" />
        </IconButton>
        <IconButton
          label={playback === "playing" ? fr.pause : fr.play}
          disabled={disabled}
          onClick={() => setPlayback(playback === "playing" ? "paused" : "playing")}
        >
          <Icon name={playback === "playing" ? "pause" : "play"} />
        </IconButton>
        <IconButton label={fr.stepForward} disabled={disabled || index >= steps.length - 1} onClick={() => date && setDate(shiftStep(steps, date, 1) ?? date)}>
          <Icon name="forward" />
        </IconButton>
        <label className="speed">
          {fr.speed}
          <select value={speed} aria-label={fr.speed} onChange={(event) => setSpeed(Number(event.target.value) as 1 | 2 | 4)}>
            <option value={1}>1×</option>
            <option value={2}>2×</option>
            <option value={4}>4×</option>
          </select>
        </label>
      </div>
      <label className="timeline-slider">
        <span>{date ? formatDate(date) : "—"}</span>
        <input
          type="range"
          min={0}
          max={Math.max(steps.length - 1, 0)}
          value={Math.max(index, 0)}
          disabled={disabled}
          aria-valuetext={date ? formatDate(date) : undefined}
          onChange={(event) => {
            const next = steps[Number(event.target.value)];
            if (next) setDate(next);
          }}
        />
      </label>
    </section>
  );
}
