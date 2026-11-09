# ADR 001 — Chunking jerárquico padre-hijo

## Estado

Aceptada (implementada en el pipeline de ingesta y en el seeder del Golden Corpus).

## Contexto

Las páginas largas mezclan varios temas. Generar el embedding de una página completa diluye el vector, de modo que una consulta sobre un párrafo
obtiene una puntuación baja frente a ella. Generar el embedding de fragmentos muy pequeños conserva la precisión, pero elimina el contexto circundante
que el LLM necesita para responder. Un único tamaño de chunk no puede cubrir ambas necesidades.

El pipeline de ingesta (`app/services/ingestion.py`) recibe texto de PDF, Markdown de tablas y descripciones de diagramas generadas por Gemini Vision.
Todos pasan por el mismo par de divisores.

## Decisión

Cada texto se divide en dos niveles con `RecursiveCharacterTextSplitter` (separadores `\n\n`, `\n`, `. `, ` `, cadena vacía):

| Nivel | Tamaño / solapamiento | Configuración | Se almacena como | Con embedding |
|-------|----------------|----------|-----------|----------|
| Bloque padre | 1200 / 120 caracteres | `PARENT_CHUNK_SIZE` / `PARENT_CHUNK_OVERLAP` | `DocumentChunk` con `parent_id = NULL` y `chunk_metadata.level = "parent"` | No, cuando tiene hijos |
| Chunk hijo | 350 / 40 caracteres | `CHILD_CHUNK_SIZE` / `CHILD_CHUNK_OVERLAP` | `DocumentChunk` con `parent_id` apuntando a su padre | Sí |

Reglas que aplica el código:

- **Solo los chunks hoja reciben embeddings.** Un padre que tiene hijos mantiene `embedding = NULL`. Las hojas son los chunks a los que ninguna otra fila referencia mediante `parent_id` (`_embed_leaf_chunks` en el seeder y el bloque equivalente en `IngestionService`). Un padre nunca compite con sus propios hijos en el top-k.
- **Los hijos se crean solo cuando el padre se divide.** `_add_hierarchical_chunks` crea hijos solo cuando el divisor de hijos devuelve más de un fragmento. Por lo tanto, un padre que cabe en un único fragmento del tamaño de un hijo no tiene hijos, es él mismo una hoja y recibe embedding.
- **Las tablas son chunks independientes de nivel padre** (`chunk_type = "table"`, `parent_id = NULL`). No tienen hijos, así que son hojas y reciben embeddings.
- **Las descripciones de visión** de diagramas y recibos se dividen con el mismo par (`chunk_type = "image_description"`). Una descripción que empieza con el prefijo de error de visión se conserva como nota en `DocumentImage` y no se indexa.
- **La recuperación deduplica por bloque padre y expande al padre.** Cada candidato pertenece al bloque `parent_id or chunk_id`. Solo se conserva el candidato mejor clasificado de cada bloque (`_dedupe_by_parent_block`). Después, `attach_parent_context` carga el texto del padre en `parent_content`, que es el contexto que se envía al reranker y al agente.

## Consecuencias

Positivas:

- Los vectores describen pasajes acotados (350 caracteres), mientras que el contexto de la respuesta es el bloque de 1200 caracteres.
- El contenido de tablas y diagramas se puede buscar sin código de recuperación especial.
- Un padre no puede desplazar a sus propios hijos fuera del top-k, porque los padres no tienen vector.

Compromisos y limitaciones:

- **Dos ventanas de solapamiento cuestan almacenamiento y tiempo.** Las filas padre se almacenan como texto, y el divisor de hijos se ejecuta sobre cada padre.
- **Los datos existentes no se migran.** Las filas con embedding anteriores a la regla de solo hojas (R2-BUG-04) pueden seguir teniendo vectores en los padres. Deben volver a procesarse, y el registro del proyecto indica que los embeddings existentes en PostgreSQL se generaron con un modelo anterior o con vectores simulados.
- **Los tamaños son valores por defecto fijos.** Están ajustados para el Golden Corpus y para el modelo `gemini-embedding-001` de 768 dimensiones. Cambiarlos no reindexa los documentos existentes.
- **Los embeddings simulados no tienen significado.** Sin `GOOGLE_API_KEY`, las hojas reciben vectores SHA-256 deterministas. La jerarquía funciona entonces de forma mecánica, pero la similitud densa no mide semántica.

## Alternativas consideradas

| Alternativa | Por qué no se eligió |
|-------------|----------------|
| Generar embeddings de páginas completas | Vectores diluidos; poca precisión en páginas largas con temas mezclados. |
| Un único tamaño de chunk plano (por ejemplo 350 o 1200) | Obliga a elegir entre precisión y contexto. |
| Generar embeddings de todos los chunks, padres incluidos | Los padres compiten con sus hijos e inflan el conjunto de candidatos con contexto duplicado. |
| Recuperación por ventana de oraciones o late chunking | Más compleja de implementar y de razonar en SQL. El modelo padre-hijo solo necesita una columna `parent_id`. |

## Siguiente paso

Lee el ADR 002 (`docs/adr/002-hybrid-rrf-and-semantic-reranking.md`) para ver cómo se recuperan y fusionan las hojas.
