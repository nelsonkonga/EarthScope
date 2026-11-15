import { lazy, Suspense } from "react";
import { PreferencesProvider } from "../context/Preferences";
import { TerraSenseRoutes } from "../features/landing";
import { Providers } from "./providers";

// The real visualization workspace. Cesium is only downloaded when the visitor enters /app.
const MainWorkspace = lazy(() => import("./MainWorkspace").then((module) => ({ default: module.MainWorkspace })));

export function EarthScopeApp() {
  return (
    <Providers>
      <PreferencesProvider>
        <TerraSenseRoutes
          workspace={
            <Suspense fallback={<div className="workspace-loading" role="status" aria-label="Loading the Terra Sense visualization" />}>
              <MainWorkspace />
            </Suspense>
          }
        />
      </PreferencesProvider>
    </Providers>
  );
}
