// Shared HTTP plumbing: CORS, bearer auth, a best-effort rate limit, and one
// uniform error envelope across every route.

export interface Env {
  AI: Ai;
  VECTORIZE: VectorizeIndex;
  ANAC_RAG_TOKEN?: string;
  LLM_BASE_URL?: string;
  LLM_API_KEY?: string;
  LLM_MODEL?: string;
  INDEX_NAMESPACE: string;
  MODEL_ID: string;
  TOP_K_SEMANTIC: string;
  TOP_K_FINAL: string;
  MIN_SCORE: string;
  MAX_QUERY_CHARS: string;
  MAX_CONTEXT_CHARS: string;
  MAX_CHUNK_CHARS: string;
  RATE_LIMIT_PER_MIN: string;
  CORS_ORIGINS: string;
}

export class HttpError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly retryable = false,
  ) {
    super(message);
  }
}

/** Constant-time string compare. `===` short-circuits and leaks length/prefix. */
export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function corsHeaders(request: Request, env: Env): HeadersInit {
  const allowed = (env.CORS_ORIGINS || "")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean);
  const origin = request.headers.get("Origin") || "";

  // Echo the origin only when it is on the allowlist. Never "*": this API
  // requires a bearer token, and "*" cannot be combined with credentials.
  const headers: Record<string, string> = {
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "authorization, content-type",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin",
  };
  if (origin && allowed.includes(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
}

export function withCors(response: Response, request: Request, env: Env): Response {
  const cors = corsHeaders(request, env);
  const out = new Response(response.body, response);
  for (const [key, value] of Object.entries(cors)) out.headers.set(key, value);
  return out;
}

export function jsonResponse(
  payload: unknown,
  status: number,
  request: Request,
  env: Env,
): Response {
  return withCors(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "content-type": "application/json; charset=utf-8" },
    }),
    request,
    env,
  );
}

export function errorResponse(
  status: number,
  code: string,
  message: string,
  retryable: boolean,
  request: Request,
  env: Env,
): Response {
  return jsonResponse({ error: { code, message, retryable } }, status, request, env);
}

export function requireAuth(request: Request, env: Env): void {
  const expected = env.ANAC_RAG_TOKEN;
  if (!expected) throw new HttpError(500, "not_configured", "ANAC_RAG_TOKEN is not set", false);
  const header = request.headers.get("Authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!token || !timingSafeEqual(token, expected)) {
    throw new HttpError(401, "unauthorized", "Invalid or missing bearer token", false);
  }
}

/**
 * Best-effort runaway-loop guard, NOT a security control.
 *
 * Worker isolates are ephemeral and spread across colos, so a determined caller
 * simply gets a fresh bucket. The bearer token is the real access control. This
 * exists so an accidental tight loop fails fast instead of burning the account's
 * Workers AI daily neuron allowance.
 */
const buckets = new Map<string, number[]>();

export function rateLimit(request: Request, env: Env, key: string): void {
  const limit = Number(env.RATE_LIMIT_PER_MIN) || 30;
  const now = Date.now();
  const windowStart = now - 60_000;
  const ip = request.headers.get("CF-Connecting-IP") || "unknown";

  const hits = (buckets.get(key) || []).filter((t) => t > windowStart);
  if (hits.length >= limit) {
    throw new HttpError(429, "rate_limited", "Too many requests, slow down", true);
  }
  hits.push(now);
  buckets.set(key, hits);
  // Opportunistic cleanup so the map does not grow without bound on a
  // long-lived isolate.
  if (buckets.size > 512) {
    for (const [k, v] of buckets) {
      if (!v.some((t) => t > windowStart)) buckets.delete(k);
    }
  }
}

export async function readJsonBody<T>(request: Request, maxBytes = 64_000): Promise<T> {
  const raw = await request.text();
  if (raw.length > maxBytes) {
    throw new HttpError(400, "bad_request", "Request body too large", false);
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    throw new HttpError(400, "bad_request", "Body is not valid JSON", false);
  }
}