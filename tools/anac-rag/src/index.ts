// ANAC semantic retrieval endpoint.
//
// Routes:
//   GET  /health  liveness, unauthenticated, no corpus content
//   POST /query   embed + retrieve cited chunks, no LLM
//   POST /chat    retrieve + generate from any OpenAI-compatible LLM
//
// This is the RECALL path. The keyword index in support/indexes/ remains the
// PRECISION path and is still served by tools/anac_ingest/query.py locally.

import type { Env } from "./http";
import {
  HttpError,
  errorResponse,
  jsonResponse,
  rateLimit,
  readJsonBody,
  requireAuth,
  withCors,
} from "./http";
import type { QueryOptions, RetrievedChunk } from "./rag";
import { coveragePayload, retrieve } from "./rag";
import type { ChatMessage } from "./chat";
import { generate } from "./chat";

const GAPS_FILE = "knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md";

function handleError(err: unknown, request: Request, env: Env): Response {
  if (err instanceof HttpError) {
    return errorResponse(err.status, err.code, err.message, err.retryable, request, env);
  }
  const message = err instanceof Error ? err.message : String(err);
  return errorResponse(500, "internal", message, true, request, env);
}

async function handleQuery(request: Request, env: Env): Promise<Response> {
  requireAuth(request, env);
  rateLimit(request, env, "query");
  const body = await readJsonBody<QueryOptions>(request);
  const started = Date.now();
  const chunks = await retrieve(env, body);
  return jsonResponse(
    {
      query: body.query,
      model: env.MODEL_ID,
      namespace: body.namespace || env.INDEX_NAMESPACE,
      took_ms: Date.now() - started,
      count: chunks.length,
      results: chunks,
      coverage: coveragePayload(chunks),
    },
    200,
    request,
    env,
  );
}

async function handleChat(request: Request, env: Env): Promise<Response> {
  requireAuth(request, env);
  rateLimit(request, env, "chat");
  const body = await readJsonBody<{
    message: string;
    history?: ChatMessage[];
    top_k?: number;
    kind?: string;
    family?: string;
    namespace?: string;
  }>(request);

  const message = (body.message || "").trim();
  if (!message) throw new HttpError(400, "bad_request", "message must not be empty", false);

  const started = Date.now();
  const chunks = await retrieve(env, {
    query: message,
    top_k: body.top_k,
    kind: body.kind,
    family: body.family,
    namespace: body.namespace,
  });

  // No chunks is a coverage gap, not a failure. Answer honestly rather than
  // letting the model improvise from nothing.
  if (chunks.length === 0) {
    return jsonResponse(
      {
        mode: "retrieval-only",
        grounded: false,
        answer: null,
        reason: "no_context",
        message:
          "Nenhum fragmento acima do limiar de similaridade. A cobertura pode estar ausente: " +
          GAPS_FILE,
        citations: [],
        dropped_citations: [],
        llm: null,
        retrieval: { results: [], coverage: coveragePayload([]) },
      },
      200,
      request,
      env,
    );
  }

  const result = await generate(
    env,
    message,
    Array.isArray(body.history) ? body.history : [],
    chunks,
    GAPS_FILE,
  );

  return jsonResponse(
    {
      mode: result.mode,
      grounded: result.grounded,
      answer: result.answer,
      reason: result.reason,
      citations: result.citations,
      dropped_citations: result.dropped_citations,
      llm: result.llm,
      took_ms: Date.now() - started,
      retrieval: {
        count: chunks.length,
        results: chunks as RetrievedChunk[],
        coverage: coveragePayload(chunks),
      },
    },
    200,
    request,
    env,
  );
}

function handleHealth(env: Env): Record<string, unknown> {
  return {
    ok: true,
    index: "anac-legislacao",
    namespace: env.INDEX_NAMESPACE,
    model: env.MODEL_ID,
    llm_configured: Boolean((env.LLM_BASE_URL || "").trim() && (env.LLM_MODEL || "").trim()),
    auth_required: true,
    retrieved_at: new Date().toISOString(),
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return withCors(new Response(null, { status: 204 }), request, env);
    }

    try {
      if (url.pathname === "/health" && request.method === "GET") {
        // Unauthenticated on purpose so liveness can be probed without holding
        // the token. Deliberately exposes no corpus content.
        return jsonResponse(handleHealth(env), 200, request, env);
      }
      if (url.pathname === "/query" && request.method === "POST") {
        return await handleQuery(request, env);
      }
      if (url.pathname === "/chat" && request.method === "POST") {
        return await handleChat(request, env);
      }
      return errorResponse(
        404,
        "not_found",
        `Unknown route ${request.method} ${url.pathname}`,
        false,
        request,
        env,
      );
    } catch (err) {
      return handleError(err, request, env);
    }
  },
} satisfies ExportedHandler<Env>;