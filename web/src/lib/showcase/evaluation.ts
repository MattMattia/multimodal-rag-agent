/** Mirror of `RAGEvaluationService.evaluate` (app/services/evaluation.py) over the embedded corpus. */
import type { EvaluationModeName, EvaluationResponse, ModeEvaluation, QueryEvaluation } from "../contracts";
import { type GoldenEvalQuery, GOLDEN_EVAL_QUERIES, allChunks, chunkById } from "./corpus";
import { ShowcaseError } from "./errors";
import { hitRateAtK, isRelevant, mean, ndcgAtK, reciprocalRank } from "./metrics";
import { searchCorpus } from "./search";

export const EVALUATION_MODES: readonly EvaluationModeName[] = ["dense", "sparse", "hybrid"];

export const SHOWCASE_EVALUATION_WARNING =
  "Showcase engine: dense and hybrid scores come from a deterministic lexical feature-hashing stand-in, " +
  "not semantic embeddings, and the reranker is a lexical stand-in; only sparse (BM25) is meaningful here. " +
  "Run the benchmark against the live FastAPI backend with GOOGLE_API_KEY for semantic results.";

/** Blocks (parent or standalone chunk) of the expected documents that satisfy the relevance rule. */
function countRelevantBlocks(spec: GoldenEvalQuery): number {
  const blocks = new Set<string>();
  for (const chunk of allChunks()) {
    if (!spec.expected_doc_filenames.includes(chunk.document_name)) continue;
    const parent = chunk.parent_id ? chunkById(chunk.parent_id) : undefined;
    const candidate = { document_name: chunk.document_name, content: chunk.content, parent_content: parent?.content };
    if (isRelevant(candidate, spec.expected_doc_filenames, spec.expected_keywords)) {
      blocks.add(chunk.parent_id ?? chunk.id);
    }
  }
  return blocks.size;
}

function runQuery(spec: GoldenEvalQuery, mode: EvaluationModeName, topK: number, totalRelevant: number): QueryEvaluation {
  const started = performance.now();
  const response = searchCorpus({ query: spec.query, top_k: topK, mode, rerank: mode === "hybrid", include_parent: true });
  const latency = performance.now() - started;
  const relevances = response.results.map((item) =>
    isRelevant(item, spec.expected_doc_filenames, spec.expected_keywords) ? 1 : 0,
  );
  return {
    id: spec.id,
    query: spec.query,
    category: spec.category,
    hit: hitRateAtK(relevances, topK) === 1,
    reciprocal_rank: reciprocalRank(relevances, topK),
    ndcg: ndcgAtK(relevances, topK, totalRelevant),
    latency_ms: Number(latency.toFixed(3)),
    relevances,
    top_documents: response.results.map((item) => item.document_name),
  };
}

export function evaluateCorpus(topK: number = 5): EvaluationResponse {
  if (!Number.isInteger(topK) || topK < 1 || topK > 20) {
    throw new ShowcaseError(422, "top_k must be an integer between 1 and 20.");
  }
  const totals = GOLDEN_EVAL_QUERIES.map(countRelevantBlocks);
  const modes: Record<string, ModeEvaluation> = {};
  for (const mode of EVALUATION_MODES) {
    const rows = GOLDEN_EVAL_QUERIES.map((spec, i) => runQuery(spec, mode, topK, totals[i] ?? 0));
    modes[mode] = {
      semantic: mode === "sparse",
      hit_rate_at_k: mean(rows.map((r) => (r.hit ? 1 : 0))),
      mrr: mean(rows.map((r) => r.reciprocal_rank)),
      ndcg_at_k: mean(rows.map((r) => r.ndcg)),
      avg_latency_ms: mean(rows.map((r) => r.latency_ms)),
      per_query: rows,
    };
  }
  return {
    top_k: topK,
    num_queries: GOLDEN_EVAL_QUERIES.length,
    embedding_mode: "mock",
    warnings: [SHOWCASE_EVALUATION_WARNING],
    modes,
  };
}
