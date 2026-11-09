# ADR 002 — Recuperación híbrida con RRF y reranking semántico

## Estado

Aceptada (implementada en `HybridSearchService` y `RerankerService`).

## Contexto

Los vectores densos pasan por alto tokens exactos como números de serie, siglas, identificadores fiscales y etiquetas de tablas. La búsqueda
léxica pasa por alto paráfrasis y preguntas entre idiomas. Cada señal falla en consultas distintas, y las dos
escalas de puntuación no son comparables: la similitud coseno y un rango de texto completo no se pueden sumar directamente.

Una vez fusionados los candidatos, una puntuación fusionada sigue midiendo solo la coincidencia de rangos. Un chunk que repite las
palabras de la consulta puede quedar bien clasificado sin responder a la pregunta.

## Decisión

La búsqueda se ejecuta en cuatro etapas.

1. **Recuperación de candidatos por rama.** Cada rama devuelve como máximo `retrieval_limit = min(top_k × SEARCH_CANDIDATE_MULTIPLIER, 80)` filas. Con los valores por defecto (`SEARCH_CANDIDATE_MULTIPLIER = 4`, `top_k = 5`), son 20 filas por rama.
2. **Reciprocal Rank Fusion.** `score(d) = Σ 1 / (RRF_K + rank_i(d))` sobre las dos listas, con `rank` empezando en 1 y `RRF_K = 60`. No se ajustan pesos. Un chunk encontrado por ambas ramas acumula ambas contribuciones.
3. **Deduplicación por bloque padre.** Los candidatos se reducen a uno por `parent_id or chunk_id` (ver ADR 001).
4. **Reranking semántico.** Los primeros `top_k × 3` bloques van a `RerankerService`, que pide a Gemini (`GEMINI_AGENT_MODEL`, por defecto `gemini-1.5-pro`) que puntúe cada fragmento de 0.0 a 1.0. Los fragmentos se recortan a `RERANK_MAX_SNIPPET_CHARS = 800`. La llamada está limitada a `RERANK_TIMEOUT_SECONDS = 8.0`. Se devuelven los mejores `top_k` con `rerank_score`.

Detalles de cada rama según el dialecto de base de datos:

| Rama | PostgreSQL | SQLite (zero-Docker) |
|-----|------------|----------------------|
| Densa | `embedding IS NOT NULL`, `cosine_distance` de pgvector sobre `vector(768)`, similitud = `1 − distance` acotada a [0, 1] | Coseno exacto calculado en Python sobre cada hoja con embedding |
| Dispersa | Texto completo: `websearch_to_tsquery` en `spanish` y `english`, combinados con OR; rango = `GREATEST(ts_rank_cd(es), ts_rank_cd(en))` | BM25 (`k1 = 1.5`, `b = 0.75`) calculado en Python sobre todos los chunks |
| Índice | HNSW (`vector_cosine_ops`, `m = 16`, `ef_construction = 64`); GIN sobre `to_tsvector('spanish', content)` y `to_tsvector('english', content)` | Ninguno (sin ANN, sin índice FTS) |

El parámetro `mode` selecciona `dense`, `sparse` o `hybrid`. Solo `hybrid` ejecuta RRF. `rerank=false` omite la etapa 4.

El reranker recurre al orden de RRF, sin llamar al modelo, en estos casos: no hay un cliente de Gemini utilizable, se agota el tiempo o se produce cualquier excepción. El fallback conserva el orden de RRF y asigna a `rerank_score` la puntuación de RRF.

## Consecuencias

Positivas:

- Sin calibración de puntuaciones. RRF depende solo de los rangos, así que las dos ramas no necesitan una escala común.
- Las coincidencias de términos exactos se conservan: la rama léxica recupera identificadores que los embeddings difuminan.
- El reranking puede rescatar a un candidato léxicamente fuerte pero fuera de tema, y está acotado por un tiempo de espera.
- Los diagnósticos exponen cada etapa (`embedding_ms`, `dense_ms`, `sparse_ms`, `rrf_fusion_ms`, `rerank_ms`, recuentos de candidatos), por lo que los compromisos son medibles.

Compromisos y limitaciones:

- **Dos pasos que dependen de modelos.** Cada consulta puede llamar a la API de embeddings y al reranker. La latencia y la cuota dependen de Gemini.
- **El fallback determinista no es una puntuación de relevancia.** Cuando el reranker recurre al fallback, `rerank_score` repite la puntuación de RRF. Ordena los resultados, pero no mide la relevancia.
- **La rama dispersa también indexa los bloques padre.** Los padres no tienen vectores pero sí texto, así que un padre puede coincidir léxicamente y luego fusionarse con sus hijos en la deduplicación.
- **Las ventanas de candidatos son pequeñas por diseño.** Con `top_k = 5`, la rama densa ve como máximo 20 filas, así que un chunk relevante que queda por debajo de la posición 20 en ambas ramas nunca pasa por el reranking.
- **Los benchmarks sin conexión no son semánticos.** Sin `GOOGLE_API_KEY`, los modos denso e híbrido usan vectores simulados. La evaluación informa `embedding_mode: "mock"`, una advertencia y `semantic: false` para esos modos. Solo los números de `sparse` son significativos sin conexión.

## Alternativas consideradas

| Alternativa | Por qué no se eligió |
|-------------|----------------|
| Fusión lineal ponderada de puntuaciones normalizadas | Requiere normalizar puntuaciones y ajustar pesos, que el proyecto no puede calibrar sin datos etiquetados. |
| Solo densa | Pasa por alto identificadores exactos y etiquetas de tablas, que el Golden Corpus pone a prueba. |
| Solo léxica | Pasa por alto paráfrasis y consultas entre idiomas; la evaluación incluye ambas. |
| Reranker cross-encoder local | Añade pesos de modelo y un segundo runtime. El proyecto ya usa Gemini y debe poder instalarse sin Docker. |
| Motor de búsqueda externo (Elasticsearch, OpenSearch) | Añade un servicio que el modo zero-Docker no puede proporcionar. |

## Siguiente paso

Lee el ADR 003 (`docs/adr/003-tri-modal-zero-dependency-architecture.md`) para ver cómo se ejecuta el mismo pipeline sobre SQLite sin pgvector.
