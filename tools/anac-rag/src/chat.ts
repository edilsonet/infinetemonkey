// Chat: retrieve, then generate from any OpenAI-compatible endpoint.
//
// The endpoint is a retriever first and a chat surface second. With no LLM
// configured it still returns the full retrieval result, which is the default
// state on a fresh deploy.

import type { Env } from "./http";
import { HttpError } from "./http";
import type { RetrievedChunk } from "./rag";

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

/**
 * The retrieval doctrine, in the corpus's own language so the register matches.
 * The model is told what it may not do; src/index.ts then checks what it did.
 */
export function systemPrompt(gapsFile: string): string {
  return [
    "Voce responde perguntas sobre a legislacao da ANAC (RBAC, IS e IAC) usando SOMENTE os blocos fornecidos.",
    "Cite com o identificador do fragmento entre colchetes, no formato [43.1(a)], [Apendice A] ou [IS 43-001 5.1].",
    "Nunca invente um identificador que nao apareca nos blocos.",
    "RBAC e vinculante. IS explica como cumprir. IAC e historico e muitas vezes revogada.",
    "Se os blocos nao responderem a pergunta, diga que a cobertura esta ausente e aponte para " +
      gapsFile +
      ".",
    "Nao responda de memoria. Nao use conhecimento que nao esteja nos blocos.",
  ].join("\n");
}

export function buildContext(chunks: RetrievedChunk[], env: Env): string {
  const maxContext = Number(env.MAX_CONTEXT_CHARS) || 7200;
  const maxChunk = Number(env.MAX_CHUNK_CHARS) || 1200;
  const blocks: string[] = [];
  let used = 0;
  for (const chunk of chunks) {
    const citeLabel = chunk.cites.length > 1 ? chunk.cites.join(", ") : chunk.cite;
    const body = chunk.text.length > maxChunk ? chunk.text.slice(0, maxChunk) + "..." : chunk.text;
    const block = `[${citeLabel}] ${chunk.document_title}\n${body}`;
    if (used + block.length > maxContext) break;
    blocks.push(block);
    used += block.length;
  }
  return blocks.join("\n\n---\n\n");
}

interface LLMChoice {
  message?: { content?: string };
}

async function callLLM(env: Env, messages: ChatMessage[]): Promise<{ answer: string; model: string }> {
  const base = (env.LLM_BASE_URL || "").replace(/\/+$/, "");
  const model = env.LLM_MODEL || "";
  if (!base || !model) {
    throw new HttpError(
      503,
      "llm_unconfigured",
      "LLM_BASE_URL and LLM_MODEL are not set. Use POST /query for retrieval only.",
      false,
    );
  }

  const headers: Record<string, string> = { "content-type": "application/json" };
  if (env.LLM_API_KEY) headers.authorization = `Bearer ${env.LLM_API_KEY}`;

  // NOTE: a deployed Worker cannot reach 127.0.0.1. LLM_BASE_URL must be a
  // reachable OpenAI-compatible endpoint (LAN or Tailscale address, or a hosted
  // provider). Local LLM round-trips only work under `wrangler dev --local`.
  let response: Response;
  try {
    response = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify({ model, messages, temperature: 0, max_tokens: 900 }),
    });
  } catch (err) {
    throw new HttpError(
      502,
      "upstream_error",
      `LLM unreachable at LLM_BASE_URL: ${err instanceof Error ? err.message : String(err)}`,
      true,
    );
  }

  if (!response.ok) {
    const detail = (await response.text()).slice(0, 300);
    throw new HttpError(
      502,
      "upstream_error",
      `LLM returned ${response.status}: ${detail}`,
      response.status >= 500,
    );
  }

  const payload = (await response.json()) as { choices?: LLMChoice[] };
  const answer = payload.choices?.[0]?.message?.content ?? "";
  return { answer, model };
}

export interface CitationCheck {
  grounded: boolean;
  answer: string;
  citations: string[];
  dropped: string[];
}

/**
 * Enforce citation server-side.
 *
 * The prompt asks for bracketed cites; this verifies them. An answer with zero
 * verifiable citations is the exact failure that hard rule 2 in
 * knowledge/anac-legislacao/canon/core-doctrine.md exists to prevent, and no
 * amount of prompt wording reliably prevents it on its own.
 */
export function checkCitations(answer: string, chunks: RetrievedChunk[]): CitationCheck {
  const allowed = new Set<string>();
  for (const chunk of chunks) {
    for (const cite of chunk.cites) if (cite) allowed.add(cite);
    if (chunk.cite) allowed.add(chunk.cite);
  }

  const emitted = [...new Set((answer.match(/\[[^\[\]\n]{1,80}\]/g) || []).map((s) => s.slice(1, -1).trim()))];
  const valid = emitted.filter((c) => {
    if (allowed.has(c)) return true;
    // Windowed cites are displayed as "38.5 (janela 2)"; accept the base cite.
    return allowed.has(c.split(" (janela")[0].trim());
  });
  const dropped = emitted.filter((c) => !valid.includes(c));

  if (valid.length === 0) {
    return {
      grounded: false,
      answer:
        answer.trim() +
        "\n\n[aviso: nenhuma citacao verificavel foi recuperada para esta pergunta. " +
        "Verifique knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md.]",
      citations: [],
      dropped,
    };
  }
  return { grounded: true, answer, citations: valid, dropped };
}

export async function generate(
  env: Env,
  question: string,
  history: ChatMessage[],
  chunks: RetrievedChunk[],
  gapsFile: string,
): Promise<{
  mode: "grounded" | "retrieval-only";
  grounded: boolean;
  answer: string | null;
  citations: string[];
  dropped_citations: string[];
  llm: { base_url: string; model: string } | null;
  reason?: string;
}> {
  const llmConfigured = Boolean((env.LLM_BASE_URL || "").trim() && (env.LLM_MODEL || "").trim());
  if (!llmConfigured) {
    // Retrieval-only: still HTTP 200. /query covers this case too, but a caller
    // using /chat should never have to special-case an unconfigured deploy.
    return {
      mode: "retrieval-only",
      grounded: false,
      answer: null,
      citations: chunks.flatMap((c) => c.cites),
      dropped_citations: [],
      llm: null,
      reason: "llm_unconfigured",
    };
  }

  const context = buildContext(chunks, env);
  const messages: ChatMessage[] = [
    { role: "system", content: systemPrompt(gapsFile) },
    ...history,
    { role: "user", content: `Blocos recuperados:\n\n${context}\n\nPergunta: ${question}` },
  ];

  const { answer, model } = await callLLM(env, messages);
  const check = checkCitations(answer, chunks);
  return {
    mode: "grounded",
    grounded: check.grounded,
    answer: check.answer,
    citations: check.citations,
    dropped_citations: check.dropped,
    llm: { base_url: env.LLM_BASE_URL || "", model },
  };
}