import { lazy, Suspense } from "react";
import { LandingPage } from "../features/landing/LandingPage";
import { I18nProvider } from "../i18n";
import { Providers } from "./providers";
import { isWorkspacePath, usePath } from "./router";

// The globe (Cesium) is only downloaded when the visitor enters the workspace.
const MainWorkspace = lazy(() => import("./MainWorkspace").then((module) => ({ default: module.MainWorkspace })));

export function EarthScopeApp() {
  const path = usePath();
  return (
    <Providers>
      {isWorkspacePath(path) ? (
        <Suspense fallback={<div className="workspace-loading" role="status" aria-label="Chargement de la visualisation Terra Sense" />}>
          <MainWorkspace />
        </Suspense>
      ) : (
        <I18nProvider>
          <LandingPage />
        </I18nProvider>
      )}
    </Providers>
  );
}
