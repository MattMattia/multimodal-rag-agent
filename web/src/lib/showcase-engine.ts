/**
 * Vercel Serverless 24/7 Showcase Engine — public API.
 *
 * Pure, dependency-free modules that answer every BFF route when FastAPI is unreachable:
 * the embedded Golden Corpus, hybrid retrieval (dense lexical-hashing stand-in + BM25, RRF k=60),
 * the agent SSE stream, stateless PDF reports and the RAG benchmark.
 */
export { GOLDEN_DOCUMENTS, GOLDEN_EVAL_QUERIES, allChunks, findDocument, leafChunks } from "./showcase/corpus";
export type { CorpusChunk, GoldenDocument, GoldenEvalQuery, GoldenImage } from "./showcase/corpus";
export { bm25Scores, tokenize } from "./showcase/lexical";
export { cosine, hashEmbedding } from "./showcase/dense";
export { RRF_K, SHOWCASE_DB_DIALECT, assertSearchableDocument, rrfFuse, searchCorpus } from "./showcase/search";
export { hitRateAtK, isRelevant, mean, ndcgAtK, reciprocalRank } from "./showcase/metrics";
export { EVALUATION_MODES, SHOWCASE_EVALUATION_WARNING, evaluateCorpus } from "./showcase/evaluation";
export { chunkText, composeAnswer, encodeSse, streamAgentTurn } from "./showcase/agent";
export { buildPdf } from "./showcase/pdf";
export { buildReportPdf, decodeReportFilename, decodeReportLocale, exportTranscript, reportFilenameFor } from "./showcase/reports";
export { detectLocale, resolveLocale } from "./showcase/i18n";
export type { ChatLanguage, ShowcaseLocale } from "./showcase/i18n";
export { documentDetail, findImage, listDocuments, showcaseSeed, showcaseStatus } from "./showcase/catalog";
export { renderDiagramSvg } from "./showcase/diagrams";
export { ShowcaseError } from "./showcase/errors";
