import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { dispatch } from "./router";

function send(res: ServerResponse, status: number, body: unknown) {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store");
  res.end(JSON.stringify(body));
}

function fail(res: ServerResponse, status: number, code: string, message: string, details: Record<string, unknown> = {}) {
  send(res, status, { error: { code, message, details } });
}

async function readJson(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw) return {};
  return JSON.parse(raw) as unknown;
}

export function earthscopeMock(): Plugin {
  const handle = (req: IncomingMessage, res: ServerResponse, next: (error?: unknown) => void) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    if (!url.pathname.startsWith("/api/v1")) {
      next();
      return;
    }
    void (async () => {
      const body = req.method === "GET" || req.method === "HEAD" ? undefined : await readJson(req);
      const result = await dispatch(req.method ?? "GET", url, body);
      send(res, result.status, result.body);
    })().catch((error: unknown) => {
      if (error instanceof SyntaxError) {
        fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["body"] });
        return;
      }
      console.error(error);
      fail(res, 500, "INTERNAL", "Le service est indisponible.");
    });
  };
  return {
    name: "earthscope-mock",
    configureServer(server) {
      server.middlewares.use(handle);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handle);
    },
  };
}
