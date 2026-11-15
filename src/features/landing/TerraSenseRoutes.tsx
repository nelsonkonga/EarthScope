import React from 'react';
import { isWorkspacePath, navigate, usePath } from '../../app/router';
import TerraSenseLanding, { type TerraSenseLandingProps } from './TerraSenseLanding';

/** Navigates between the landing page ("/") and the workspace ("/app"), query string included. */
export function navigateTerraSense(path: string) {
  navigate(path);
}

type Props = TerraSenseLandingProps & {
  workspace: React.ReactNode;
};

/**
 * Dependency-free History API switch shared with the rest of the app (src/app/router.ts).
 * `workspace` is the real, lazily loaded visualization workspace: Cesium is never imported by
 * the landing page.
 */
export function TerraSenseRoutes({ workspace, assistantController }: Props) {
  const path = usePath();
  if (isWorkspacePath(path)) return <>{workspace}</>;
  return <TerraSenseLanding assistantController={assistantController} onNavigateToApp={() => navigateTerraSense('/app')} />;
}
