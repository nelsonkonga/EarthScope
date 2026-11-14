import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import type { ChatMessage, ChatSession } from "../src/domain/types";
import { answer, categories, DATASET, layerFor, rank, seriesFor, SUGGESTED_PROMPTS, variables, zones } from "./engine";

type StoredSession = ChatSession & { expiresAt: number };

const sessions: Map<string, StoredSession> =
  (globalThis as { __earthscopeSessions?: Map<string, StoredSession> }).__earthscopeSessions ??
  new Map();
(globalThis as { __earthscopeSessions?: Map<string, StoredSession> }).__earthscopeSessions = sessions;

const HOUR = 12 * 60 * 60 * 1000;

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

function meta() {
  return { crs: "EPSG:4326", datasetVersion: DATASET, limit: 200, nextCursor: null, complete: true };
}

export function earthscopeMock(): Plugin {
  const handle = (req: IncomingMessage, res: ServerResponse, next: (error?: unknown) => void) => {
    const url = new URL(req.url ?? "/", "http://localhost");
    if (!url.pathname.startsWith("/api/v1")) {
      next();
      return;
    }
    void route(req, res, url).catch((error: unknown) => {
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

async function route(req: IncomingMessage, res: ServerResponse, url: URL) {
  const path = url.pathname.replace(/\/$/, "");
  const method = req.method ?? "GET";

  if (method === "GET" && path === "/api/v1/zones") {
    const q = fold(url.searchParams.get("q") ?? "");
    const list = zones().filter((zone) => {
      if (!q) return true;
      const haystack = [zone.name, zone.country, ...(zone.aliases ?? [])].map(fold).join(" ");
      return haystack.includes(q);
    });
    send(res, 200, { _notice: NOTICE, meta: meta(), zones: list });
    return;
  }

  const zoneMatch = path.match(/^\/api\/v1\/zones\/([^/]+)$/);
  if (method === "GET" && zoneMatch) {
    const zone = zones().find((item) => item.id === decodeURIComponent(zoneMatch[1]));
    if (!zone) return fail(res, 404, "ZONE_NOT_FOUND", "Aucune zone pour cet identifiant.");
    send(res, 200, { _notice: NOTICE, zone });
    return;
  }

  if (method === "GET" && path === "/api/v1/variables") {
    send(res, 200, { _notice: NOTICE, meta: { datasetVersion: DATASET }, categories: categories(), variables: variables() });
    return;
  }

  if (method === "GET" && path === "/api/v1/timeseries") {
    const zoneId = url.searchParams.get("zoneId") ?? "";
    const variableId = url.searchParams.get("variableId") ?? "";
    const resolution = url.searchParams.get("resolution") ?? "year";
    if (!zoneId || !variableId) return fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["zoneId", "variableId"] });
    const series = seriesFor(zoneId, variableId, resolution);
    if (series === "zone") return fail(res, 404, "ZONE_NOT_FOUND", "Aucune zone pour cet identifiant.");
    if (series === "variable") return fail(res, 404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    if (series === "resolution") return fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["resolution"] });
    send(res, 200, { _notice: NOTICE, series });
    return;
  }

  if (method === "GET" && path === "/api/v1/layers") {
    const variableId = url.searchParams.get("variableId") ?? "";
    const date = url.searchParams.get("date") ?? "";
    if (!variableId || !date) return fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["variableId", "date"] });
    const layer = layerFor(variableId, date);
    if (layer === "variable") return fail(res, 404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    if (layer === "date") return fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["date"] });
    send(res, 200, { _notice: NOTICE, layer });
    return;
  }

  if (method === "GET" && path === "/api/v1/rankings") {
    const variableId = url.searchParams.get("variableId") ?? "";
    const metric = url.searchParams.get("metric") === "changeOverPeriod" ? "changeOverPeriod" : "changePerDecade";
    const table = rank(variableId, metric);
    if (table === "variable") return fail(res, 404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    const variable = variables().find((item) => item.id === variableId);
    send(res, 200, {
      _notice: NOTICE,
      ranking: { variableId, metric, unit: variable?.unit ?? "", datasetVersion: DATASET, entries: table },
    });
    return;
  }

  if (method === "GET" && path === "/api/v1/comparisons") {
    const variableId = url.searchParams.get("variableId") ?? "";
    const zoneIds = url.searchParams.getAll("zoneId");
    if (zoneIds.length < 2 || zoneIds.length > 6) {
      return fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["zoneId"] });
    }
    const series = zoneIds.map((zoneId) => seriesFor(zoneId, variableId));
    if (series.some((item) => item === "variable")) return fail(res, 404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    if (series.some((item) => item === "zone")) return fail(res, 404, "ZONE_NOT_FOUND", "Aucune zone pour cet identifiant.");
    send(res, 200, { _notice: NOTICE, comparison: { variableId, unit: variables().find((item) => item.id === variableId)?.unit ?? "", series } });
    return;
  }

  if (method === "POST" && path === "/api/v1/assistant/sessions") {
    const now = new Date();
    const session: StoredSession = {
      id: crypto.randomUUID(),
      createdAt: now.toISOString(),
      suggestedPrompts: SUGGESTED_PROMPTS,
      messages: [],
      expiresAt: now.getTime() + HOUR,
    };
    sessions.set(session.id, session);
    send(res, 200, { id: session.id, createdAt: session.createdAt, suggestedPrompts: session.suggestedPrompts, messages: [] });
    return;
  }

  const messageMatch = path.match(/^\/api\/v1\/assistant\/sessions\/([^/]+)\/messages$/);
  if (method === "POST" && messageMatch) {
    const session = liveSession(decodeURIComponent(messageMatch[1]));
    if (!session) return fail(res, 404, "SESSION_NOT_FOUND", "Conversation expirée ou inconnue.");
    const body = (await readJson(req)) as { text?: unknown; clientContext?: Record<string, unknown> };
    const text = typeof body.text === "string" ? body.text.trim() : "";
    if (!text || text.length > 2000) return fail(res, 400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["text"] });
    const context = {
      selectedZoneId: typeof body.clientContext?.selectedZoneId === "string" ? body.clientContext.selectedZoneId : null,
      activeVariableIds: Array.isArray(body.clientContext?.activeVariableIds) ? body.clientContext.activeVariableIds.filter((id): id is string => typeof id === "string") : [],
      primaryVariableId: typeof body.clientContext?.primaryVariableId === "string" ? body.clientContext.primaryVariableId : null,
      selectedDate: typeof body.clientContext?.selectedDate === "string" ? body.clientContext.selectedDate : null,
    };
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      text,
      createdAt: new Date().toISOString(),
    };
    const result = answer(text, context);
    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "assistant",
      text: result.text,
      createdAt: new Date().toISOString(),
      actions: result.actions,
      dataReferences: result.dataReferences,
      suggestedFollowUps: result.suggestedFollowUps,
    };
    session.messages.push(userMessage, assistantMessage);
    send(res, 200, { _notice: NOTICE, message: assistantMessage });
    return;
  }

  const sessionMatch = path.match(/^\/api\/v1\/assistant\/sessions\/([^/]+)$/);
  if (method === "GET" && sessionMatch) {
    const session = liveSession(decodeURIComponent(sessionMatch[1]));
    if (!session) return fail(res, 404, "SESSION_NOT_FOUND", "Conversation expirée ou inconnue.");
    send(res, 200, {
      id: session.id,
      createdAt: session.createdAt,
      suggestedPrompts: session.suggestedPrompts,
      messages: session.messages,
    });
    return;
  }

  fail(res, 404, "NOT_FOUND", "Ressource inconnue.");
}

function liveSession(id: string): StoredSession | undefined {
  const session = sessions.get(id);
  if (!session) return undefined;
  if (session.expiresAt < Date.now()) {
    sessions.delete(id);
    return undefined;
  }
  return session;
}

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

const NOTICE = "STRUCTURE ILLUSTRATIVE. Les nombres ne sont pas des mesures d'observation de la Terre.";
