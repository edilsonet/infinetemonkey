// Retrieval: embed the query, query Vectorize, return cited chunks.

import type { Env } from "./http";
import { HttpError } from "./http";

export interface RetrievedChunk {
  rank: number;
  score: number;
  chunk_id: string;
  cite: string;
  cites: string[];
  kind: string;
  code: string;
  family: string;
  document_title: string;
  section_title: string;
  text: string;
  source_path: string;
  page_url: string;
}

export interface QueryOptions {
  query: string;
  top_k?: number;
  kind?: string;
  family?: string;
  min_score?: number;
  namespace?: string;
}

/**
 * Ask for every metadata field. The binding takes a level ("all" | "indexed" |
 * "none"), not a list of keys; passing an array is a type error and, where it
 * was tolerated, silently returned no metadata at all.
 *
 * "all" rather than "indexed" because /query must return `text`, which is the
 * citation's own words and is not an indexed field.
 */
const METADATA_RETRIEVAL = "all" as const;

function escapeFilterValue(value: string): string {
  return value.replace(/['\\]/g, "");
}

/**
 * Number() never returns null or undefined, so `Number(x) ?? 0.55` was dead
 * code: a missing or malformed var yielded NaN, every score comparison became
 * false and every slice empty, and the endpoint reported that as a coverage
 * gap. A config error must never present as "this is not in the corpus".
 */
function num(value: unknown, fallback: number): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export async function embed(env: Env, texts: string[]): Promise<number[][]> {
  // AiResponse was removed in workers-types v4; the run result is a plain record
// narrowed by the cast below. Annotating it with the v3 type is a hard compile
// error under strict mode.
let response: Record<string, unknown>;
  try {
    response = await env.AI.run(env.MODEL_ID, { text: texts });
  } catch (err) {
    throw new HttpError(
      502,
      "upstream_error",
      `Embedding failed: ${err instanceof Error ? err.message : String(err)}`,
      true,
    );
  }
  const data = (response as { data?: number[][] }).data;
  if (!Array.isArray(data) || data.length === 0) {
    throw new HttpError(502, "upstream_error", "Embedding returned no vectors", true);
  }
  return data;
}

export async function retrieve(env: Env, options: QueryOptions): Promise<RetrievedChunk[]> {
  const query = (options.query || "").trim();
  if (!query) {
    throw new HttpError(400, "bad_request", "query must not be empty", false);
  }
  const maxChars = Number(env.MAX_QUERY_CHARS) || 2000;
  if (query.length > maxChars) {
    throw new HttpError(
      400,
      "bad_request",
      `query exceeds ${maxChars} characters`,
      false,
    );
  }

  const namespace = options.namespace || env.INDEX_NAMESPACE;
  const [vector] = await embed(env, [query]);
  if (!vector) {
    throw new HttpError(502, "upstream_error", "Embedding returned no vector", true);
  }

  // The binding takes a structured filter object, not a SQL-ish string. Passing
// "kind = 'rbac'" was both a type error and, had it been tolerated, a filter
// that matched nothing.
const filter: Record<string, string> = {};
  if (options.kind) filter.kind = escapeFilterValue(options.kind);
  if (options.family) filter.family = escapeFilterValue(options.family);

  let matches: VectorizeMatches;
  try {
    matches = await env.VECTORIZE.query(vector, {
      namespace,
      topK: Number(env.TOP_K_SEMANTIC) || 8,
      ...(Object.keys(filter).length ? { filter } : {}),
      returnMetadata: METADATA_RETRIEVAL,
    });
  } catch (err) {
    throw new HttpError(
      502,
      "upstream_error",
      `Vector query failed: ${err instanceof Error ? err.message : String(err)}`,
      true,
    );
  }

  const minScore = options.min_score ?? num(env.MIN_SCORE, 0.55);
  const topK = Math.min(options.top_k ?? num(env.TOP_K_FINAL, 6), 50);

  return (matches.matches || [])
    .filter((m) => (m.score ?? 0) >= minScore)
    .slice(0, topK)
    .map((m, i) => {
      const meta = (m.metadata || {}) as Record<string, string | string[]>;
      const cite =
        typeof meta.cite === "string"
          ? meta.cite
          : typeof meta.cite_base === "string"
            ? meta.cite_base
            : "";
      return {
        rank: i + 1,
        score: Number((m.score ?? 0).toFixed(4)),
        chunk_id: m.id,
        cite,
        cites: Array.isArray(meta.cites) ? (meta.cites as string[]) : cite ? [cite] : [],
        kind: String(meta.kind || ""),
        code: String(meta.code || ""),
        family: String(meta.family || ""),
        document_title: String(meta.document_title || ""),
        section_title: String(meta.section_title || ""),
        text: String(meta.text || ""),
        source_path: String(meta.source_path || ""),
        page_url: String(meta.page_url || ""),
      };
    });
}

export function coveragePayload(chunks: RetrievedChunk[]): Record<string, unknown> {
  return {
    cited_documents: [...new Set(chunks.map((c) => c.code).filter(Boolean))],
    // A gap is an answer, not an error: the caller is told where the missing
    // documents are catalogued rather than left to assume coverage.
    gaps_file: "knowledge/anac-legislacao/synthesis/lacunas-de-cobertura.md",
  };
}