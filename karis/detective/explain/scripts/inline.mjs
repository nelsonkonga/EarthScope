// After `vite build`: one standalone HTML file (script and styles inlined), to open from the disk.
// Written to data/earth/report/eva_explique.html, next to the detective's report.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dist = resolve(here, "..", "dist");
const out = resolve(here, "..", "..", "..", "data", "earth", "report", "eva_explique.html");

let html = readFileSync(join(dist, "index.html"), "utf8");
html = html.replace(/<script type="module" crossorigin src="\.\/([^"]+)"><\/script>/g, (_, src) => {
  const js = readFileSync(join(dist, src), "utf8").replace(/<\/script/gi, "<\\/script");
  return `<script type="module">${js}</script>`;
});
html = html.replace(/<link rel="stylesheet" crossorigin href="\.\/([^"]+)">/g, (_, href) =>
  `<style>${readFileSync(join(dist, href), "utf8")}</style>`);
if (/src="\.\/assets|href="\.\/assets/.test(html)) throw new Error("an asset was not inlined");
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, html);
console.log(`${out} (${Math.round(html.length / 1024)} KB)`);
