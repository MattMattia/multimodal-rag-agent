/**
 * Dense retrieval STAND-IN for the serverless showcase.
 *
 * This is NOT a semantic embedding model: it is a deterministic lexical feature-hashing vectorizer
 * (stemmed tokens + character trigrams hashed with FNV-1a into a signed 512-dimension vector, then
 * L2-normalised). It lets the showcase exercise the real dense → RRF → rerank pipeline shape without
 * Gemini, but its scores only reflect surface-form overlap. The benchmark discloses this.
 */
import { tokenize } from "./lexical";

export const HASH_DIMENSIONS = 512;

function fnv1a(text: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function features(text: string): string[] {
  const tokens = tokenize(text);
  const grams: string[] = [];
  for (const token of tokens) {
    const padded = `#${token}#`;
    for (let i = 0; i + 3 <= padded.length; i += 1) grams.push(`3:${padded.slice(i, i + 3)}`);
  }
  return [...tokens.map((t) => `w:${t}`), ...grams];
}

export function hashEmbedding(text: string): Float64Array {
  const vector = new Float64Array(HASH_DIMENSIONS);
  for (const feature of features(text)) {
    const hash = fnv1a(feature);
    const weight = feature.startsWith("w:") ? 1 : 0.35;
    vector[hash % HASH_DIMENSIONS]! += hash & 0x80000000 ? -weight : weight;
  }
  let norm = 0;
  for (const value of vector) norm += value * value;
  norm = Math.sqrt(norm);
  if (norm > 0) for (let i = 0; i < vector.length; i += 1) vector[i]! /= norm;
  return vector;
}

/** Cosine similarity of two L2-normalised vectors, clipped to [0, 1] like the SQLite backend. */
export function cosine(a: Float64Array, b: Float64Array): number {
  let dot = 0;
  for (let i = 0; i < a.length; i += 1) dot += a[i]! * b[i]!;
  return Math.max(0, Math.min(1, dot));
}

export function isZeroVector(vector: Float64Array): boolean {
  return vector.every((v) => v === 0);
}
