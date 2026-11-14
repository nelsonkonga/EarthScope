import { dispatch } from "../mock/router";

type NodeRequest = {
  method?: string;
  url?: string;
  headers: { host?: string | string[]; [key: string]: string | string[] | undefined };
  body?: unknown;
};

type NodeResponse = {
  statusCode: number;
  setHeader: (name: string, value: string) => void;
  end: (body: string) => void;
};

function header(req: NodeRequest, name: string): string | undefined {
  const value = req.headers[name];
  return Array.isArray(value) ? value[0] : value;
}

function requestUrl(req: NodeRequest): URL {
  const host = header(req, "host") ?? "localhost";
  const candidates = [req.url, header(req, "x-forwarded-uri"), header(req, "x-vercel-original-url")].filter(
    (value): value is string => Boolean(value),
  );
  const raw = candidates.find((value) => value.includes("/api/v1")) ?? candidates[0] ?? "/";
  return raw.startsWith("http") ? new URL(raw) : new URL(raw, `https://${host}`);
}

async function readBody(req: NodeRequest): Promise<unknown> {
  if (req.method === "GET" || req.method === "HEAD") return undefined;
  if (typeof req.body === "string") return req.body ? (JSON.parse(req.body) as unknown) : {};
  if (req.body && typeof req.body === "object") return req.body;
  const stream = req as AsyncIterable<Uint8Array | string>;
  if (typeof stream[Symbol.asyncIterator] !== "function") return {};
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  const raw = Buffer.concat(chunks).toString("utf8");
  if (!raw) return {};
  return JSON.parse(raw) as unknown;
}

export default async function handler(req: NodeRequest, res: NodeResponse) {
  try {
    const result = await dispatch(req.method ?? "GET", requestUrl(req), await readBody(req));
    res.statusCode = result.status;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.setHeader("Cache-Control", "no-store");
    res.end(JSON.stringify(result.body));
  } catch (error) {
    const invalid = error instanceof SyntaxError;
    res.statusCode = invalid ? 400 : 500;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(
      JSON.stringify({
        error: {
          code: invalid ? "VALIDATION_ERROR" : "INTERNAL",
          message: invalid ? "Paramètres invalides." : "Le service est indisponible.",
          details: invalid ? { fields: ["body"] } : {},
        },
      }),
    );
  }
}
