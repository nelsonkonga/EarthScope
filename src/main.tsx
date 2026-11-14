import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { EarthScopeApp } from "./app/EarthScopeApp";
import "./styles/tokens.css";
import "./styles/workspace.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <EarthScopeApp />
  </StrictMode>,
);
