import type { ChatMessage, ChatSession } from "../src/domain/types.js";
import { answer, categories, DATASET, layerFor, rank, seriesFor, SUGGESTED_PROMPTS, variables, zones } from "./engine.js";

type StoredSession = ChatSession & { expiresAt: number };

const sessions: Map<string, StoredSession> =
  (globalThis as { __earthscopeSessions?: Map<string, StoredSession> }).__earthscopeSessions ?? new Map();
(globalThis as { __earthscopeSessions?: Map<string, StoredSession> }).__earthscopeSessions = sessions;

const HOUR = 12 * 60 * 60 * 1000;
const NOTICE = "STRUCTURE ILLUSTRATIVE. Les nombres ne sont pas des mesures d'observation de la Terre.";
const PORTABLE_SESSION = /^es1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export type ApiResult = { status: number; body: unknown };

function ok(body: unknown): ApiResult {
  return { status: 200, body };
}

function fail(status: number, code: string, message: string, details: Record<string, unknown> = {}): ApiResult {
  return { status, body: { error: { code, message, details } } };
}

function meta() {
  return { crs: "EPSG:4326", datasetVersion: DATASET, limit: 200, nextCursor: null, complete: true };
}

function fold(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
}

function liveSession(id: string): StoredSession | undefined {
  const session = sessions.get(id);
  if (session) {
    if (session.expiresAt < Date.now()) {
      sessions.delete(id);
      return undefined;
    }
    return session;
  }
  // The id itself is the credential. A fresh function instance can answer without a shared store.
  if (!PORTABLE_SESSION.test(id)) return undefined;
  const restored: StoredSession = {
    id,
    createdAt: new Date().toISOString(),
    suggestedPrompts: SUGGESTED_PROMPTS,
    messages: [],
    expiresAt: Date.now() + HOUR,
  };
  sessions.set(id, restored);
  return restored;
}

export async function dispatch(method: string, url: URL, body: unknown): Promise<ApiResult> {
  const path = url.pathname.replace(/\/$/, "");

  if (method === "GET" && path === "/api/v1/zones") {
    const q = fold(url.searchParams.get("q") ?? "");
    const list = zones().filter((zone) => {
      if (!q) return true;
      const haystack = [zone.name, zone.country, ...(zone.aliases ?? [])].map(fold).join(" ");
      return haystack.includes(q);
    });
    return ok({ _notice: NOTICE, meta: meta(), zones: list });
  }

  const zoneMatch = path.match(/^\/api\/v1\/zones\/([^/]+)$/);
  if (method === "GET" && zoneMatch) {
    const zone = zones().find((item) => item.id === decodeURIComponent(zoneMatch[1]));
    if (!zone) return fail(404, "ZONE_NOT_FOUND", "Aucune zone pour cet identifiant.");
    return ok({ _notice: NOTICE, zone });
  }

  if (method === "GET" && path === "/api/v1/variables") {
    return ok({ _notice: NOTICE, meta: { datasetVersion: DATASET }, categories: categories(), variables: variables() });
  }

  if (method === "GET" && path === "/api/v1/timeseries") {
    const zoneId = url.searchParams.get("zoneId") ?? "";
    const variableId = url.searchParams.get("variableId") ?? "";
    const resolution = url.searchParams.get("resolution") ?? "year";
    if (!zoneId || !variableId) return fail(400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["zoneId", "variableId"] });
    const series = seriesFor(zoneId, variableId, resolution);
    if (series === "zone") return fail(404, "ZONE_NOT_FOUND", "Aucune zone pour cet identifiant.");
    if (series === "variable") return fail(404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    if (series === "resolution") return fail(400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["resolution"] });
    return ok({ _notice: NOTICE, series });
  }

  if (method === "GET" && path === "/api/v1/layers") {
    const variableId = url.searchParams.get("variableId") ?? "";
    const date = url.searchParams.get("date") ?? "";
    if (!variableId || !date) return fail(400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["variableId", "date"] });
    const layer = layerFor(variableId, date);
    if (layer === "variable") return fail(404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    if (layer === "date") return fail(400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["date"] });
    return ok({ _notice: NOTICE, layer });
  }

  if (method === "GET" && path === "/api/v1/rankings") {
    const variableId = url.searchParams.get("variableId") ?? "";
    const metric = url.searchParams.get("metric") === "changeOverPeriod" ? "changeOverPeriod" : "changePerDecade";
    const table = rank(variableId, metric);
    if (table === "variable") return fail(404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    const variable = variables().find((item) => item.id === variableId);
    return ok({
      _notice: NOTICE,
      ranking: { variableId, metric, unit: variable?.unit ?? "", datasetVersion: DATASET, entries: table },
    });
  }

  if (method === "GET" && path === "/api/v1/comparisons") {
    const variableId = url.searchParams.get("variableId") ?? "";
    const zoneIds = url.searchParams.getAll("zoneId");
    if (zoneIds.length < 2 || zoneIds.length > 6) return fail(400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["zoneId"] });
    const series = zoneIds.map((zoneId) => seriesFor(zoneId, variableId));
    if (series.some((item) => item === "variable")) return fail(404, "VARIABLE_NOT_FOUND", "Aucune variable pour cet identifiant.");
    if (series.some((item) => item === "zone")) return fail(404, "ZONE_NOT_FOUND", "Aucune zone pour cet identifiant.");
    return ok({ _notice: NOTICE, comparison: { variableId, unit: variables().find((item) => item.id === variableId)?.unit ?? "", series } });
  }

  if (method === "POST" && path === "/api/v1/assistant/sessions") {
    const now = new Date();
    const session: StoredSession = {
      id: `es1-${crypto.randomUUID()}`,
      createdAt: now.toISOString(),
      suggestedPrompts: SUGGESTED_PROMPTS,
      messages: [],
      expiresAt: now.getTime() + HOUR,
    };
    sessions.set(session.id, session);
    return ok({ id: session.id, createdAt: session.createdAt, suggestedPrompts: session.suggestedPrompts, messages: [] });
  }

  const messageMatch = path.match(/^\/api\/v1\/assistant\/sessions\/([^/]+)\/messages$/);
  if (method === "POST" && messageMatch) {
    const session = liveSession(decodeURIComponent(messageMatch[1]));
    if (!session) return fail(404, "SESSION_NOT_FOUND", "Conversation expirée ou inconnue.");
    const payload = (body ?? {}) as { text?: unknown; clientContext?: Record<string, unknown> };
    const text = typeof payload.text === "string" ? payload.text.trim() : "";
    if (!text || text.length > 2000) return fail(400, "VALIDATION_ERROR", "Paramètres invalides.", { fields: ["text"] });
    const context = {
      selectedZoneId: typeof payload.clientContext?.selectedZoneId === "string" ? payload.clientContext.selectedZoneId : null,
      activeVariableIds: Array.isArray(payload.clientContext?.activeVariableIds)
        ? payload.clientContext.activeVariableIds.filter((id): id is string => typeof id === "string")
        : [],
      primaryVariableId: typeof payload.clientContext?.primaryVariableId === "string" ? payload.clientContext.primaryVariableId : null,
      selectedDate: typeof payload.clientContext?.selectedDate === "string" ? payload.clientContext.selectedDate : null,
    };
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", text, createdAt: new Date().toISOString() };
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
    return ok({ _notice: NOTICE, message: assistantMessage });
  }

  const sessionMatch = path.match(/^\/api\/v1\/assistant\/sessions\/([^/]+)$/);
  if (method === "GET" && sessionMatch) {
    const session = liveSession(decodeURIComponent(sessionMatch[1]));
    if (!session) return fail(404, "SESSION_NOT_FOUND", "Conversation expirée ou inconnue.");
    return ok({
      id: session.id,
      createdAt: session.createdAt,
      suggestedPrompts: session.suggestedPrompts,
      messages: session.messages,
    });
  }

  return fail(404, "NOT_FOUND", "Ressource inconnue.");
}
