import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// base "./": the built page opens straight from the disk (file://), no server needed.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", assetsInlineLimit: 100000000, cssCodeSplit: false },
});
