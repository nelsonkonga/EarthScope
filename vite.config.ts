import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import cesium from "vite-plugin-cesium";
import { earthscopeMock } from "./mock/plugin";

export default defineConfig({
  plugins: [react(), cesium(), earthscopeMock()],
  server: { host: "0.0.0.0", port: 5173 },
  preview: { host: "0.0.0.0", port: 4173 },
  test: {
    environment: "node",
    include: ["src/domain/**/*.test.ts"],
  },
});
