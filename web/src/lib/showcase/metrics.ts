/** Port of the metric functions in `app/services/evaluation.py` (binary relevance, results in rank order). */

export function hitRateAtK(relevances: readonly number[], k: number): number {
  return relevances.slice(0, k).some(Boolean) ? 1 : 0;
}

export function reciprocalRank(relevances: readonly number[], k?: number): number {
  const window = k === undefined ? relevances : relevances.slice(0, k);
  const index = window.findIndex(Boolean);
  return index === -1 ? 0 : 1 / (index + 1);
}

function dcg(relevances: readonly number[]): number {
  return relevances.reduce((sum, rel, i) => sum + rel / Math.log2(i + 2), 0);
}

/**
 * NDCG@k = DCG@k / IDCG@k. With `totalRelevant` (relevant blocks in the corpus) the ideal ranking has
 * min(k, totalRelevant) relevant hits, so NDCG also reflects recall; without it the retrieved list is re-sorted.
 */
export function ndcgAtK(relevances: readonly number[], k: number, totalRelevant?: number): number {
  const ideal =
    totalRelevant === undefined
      ? dcg([...relevances].sort((a, b) => b - a).slice(0, k))
      : dcg(new Array<number>(Math.min(k, totalRelevant)).fill(1));
  if (ideal === 0) return 0;
  return dcg(relevances.slice(0, k)) / ideal;
}

export function mean(values: readonly number[]): number {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
}

export interface RelevanceCandidate {
  document_name?: string | null;
  content?: string | null;
  parent_content?: string | null;
}

export function isRelevant(
  result: RelevanceCandidate,
  expectedDocs: readonly string[],
  expectedKeywords: readonly string[],
): boolean {
  if (!result.document_name || !expectedDocs.includes(result.document_name)) return false;
  if (expectedKeywords.length === 0) return true;
  const haystack = `${result.content ?? ""} ${result.parent_content ?? ""}`.toLowerCase();
  return expectedKeywords.some((keyword) => haystack.includes(keyword.toLowerCase()));
}
