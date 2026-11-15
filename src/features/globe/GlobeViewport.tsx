import { useEffect, useRef, useState } from "react";
import { ui } from "../../config/strings";
import { useWorkspace } from "../../state/workspaceStore";
import { createGlobe } from "./globeRenderer";
import type { GlobeStatus } from "./globeApi";

export function GlobeViewport() {
  const containerRef = useRef<HTMLDivElement>(null);
  const creditsRef = useRef<HTMLDivElement>(null);
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<GlobeStatus>({ phase: "loading" });
  const selectZone = useWorkspace((state) => state.selectZone);
  const setNotice = useWorkspace((state) => state.setNotice);

  useEffect(() => {
    const container = containerRef.current;
    const credits = creditsRef.current;
    if (!container || !credits) return;
    const controller = createGlobe(container, credits, {
      onZone: (id) => selectZone(id),
      onEmpty: () => {
        setNotice(ui.uncovered);
        window.setTimeout(() => {
          if (useWorkspace.getState().notice === ui.uncovered) setNotice(null);
        }, 4000);
      },
      onStatus: setStatus,
    });
    const observer = new ResizeObserver(() => controller.resize());
    observer.observe(container);
    return () => {
      observer.disconnect();
      controller.destroy();
    };
  }, [attempt, selectZone, setNotice]);

  const message =
    status.phase === "error"
      ? status.message === "webgl"
        ? ui.webgl
        : status.message === "key"
          ? ui.globeKeyMissing
          : status.message === "ion"
            ? ui.ionFailed
            : ui.globeFailed
      : null;

  return (
    <div className="globe-viewport">
      <div ref={containerRef} className="globe-canvas" tabIndex={0} aria-label={ui.globeLabel} />
      <div ref={creditsRef} className="cesium-credits" />
      {status.phase === "loading" && <p className="globe-banner">{ui.loadingGlobe}</p>}
      {message && (
        <div className="globe-error" role="alert">
          <p>{message}</p>
          {status.phase === "error" && status.message !== "webgl" && (
            <button type="button" onClick={() => setAttempt((value) => value + 1)}>
              {ui.retry}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
