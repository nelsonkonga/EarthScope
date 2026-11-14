import { MainWorkspace } from "./MainWorkspace";
import { Providers } from "./providers";

export function EarthScopeApp() {
  return (
    <Providers>
      <MainWorkspace />
    </Providers>
  );
}
