# ADR 003 — Ejecución trimodal con un fallback a SQLite sin Docker

## Estado

Aceptada (implementada en `app/core/database.py`, `app/services/rag_search.py`, `app/services/lexical.py`, `app/services/demo_seeder.py`).

## Contexto

Un revisor debe poder ejecutar el proyecto en minutos, en cualquier máquina, sin conocer su infraestructura.
El stack completo necesita PostgreSQL con pgvector, Langfuse, Streamlit y la API. Un revisor que solo tiene Python
debería ver igualmente una recuperación funcional, y un revisor que tiene Docker debería obtener el stack completo. El showcase
en la nube es un tercer punto de entrada para cuando no hay ninguna máquina en ejecución.

Dos restricciones condicionan la elección. El mismo código debe ejecutarse en ambas bases de datos, y los resultados de recuperación en
SQLite deben ser correctos, aunque SQLite no tenga índice vectorial.

## Decisión

Tres modos de ejecución comparten un único código base. El dialecto de base de datos se elige a partir de `DATABASE_URL` y puede recurrir a un fallback al arrancar.

| Modo | Punto de entrada | Base de datos | Recuperación | Para quién es |
|------|-------------|----------|-----------|---------------|
| 1. Showcase en la nube | Next.js en Vercel, directorio raíz `web` | Ninguna en el servidor; el BFF sirve un Golden Corpus embebido | Motor de showcase en TypeScript (ver ADR 004) | Revisores que solo tienen un navegador |
| 2. Local sin Docker | `python run.py` (SQLite) | `sqlite+aiosqlite:///./rag_standalone.db` | Coseno exacto y BM25 en Python | Ingenieros con Python y sin Docker |
| 3. Enterprise completo | `docker compose up` | PostgreSQL 16 con pgvector | HNSW de pgvector y texto completo con GIN | Evaluación similar a producción, Langfuse y Streamlit |

### Fallback al arrancar

`init_db()` en `app/core/database.py` intenta `create_schema` sobre el motor configurado. Si falla y `AUTO_FALLBACK_SQLITE = true` (el valor por defecto), el motor se vuelve a enlazar a `sqlite+aiosqlite:///./rag_standalone.db` y el esquema se crea de nuevo. La decisión se toma una sola vez, al arrancar. Si ya está configurado SQLite, el fallback se omite.

Una vez creado el esquema, `_auto_seed_if_empty` carga el Golden Corpus cuando `AUTO_SEED_DEMO_CORPUS = true` y `documents` está vacía.

### Código específico de cada dialecto

- **Tipos de columna.** Los modelos usan `JSON().with_variant(JSONB, "postgresql")`, y `embedding` es `vector(EMBEDDING_DIMENSION)` en PostgreSQL y un array JSON de floats en SQLite.
- **Índices.** Los índices HNSW y GIN se crean solo en PostgreSQL. En SQLite, `create_schema` retorna antes de crearlos.
- **Rama densa.** PostgreSQL usa `cosine_distance` de pgvector. SQLite calcula el coseno exacto en Python sobre las hojas que tienen embedding.
- **Rama dispersa.** PostgreSQL usa `websearch_to_tsquery` en español e inglés. SQLite usa BM25 en Python (`app/services/lexical.py`), con eliminación de tildes, un stemmer ligero y stopwords en español e inglés. El tokenizador de Python está portado a TypeScript para el showcase, de modo que ambos lados clasifican de la misma forma.
- **Detección del dialecto.** `get_active_db_dialect()` devuelve `"sqlite"` o `"postgresql"`, y `HybridSearchService` lee el dialecto de la sesión que recibe.

### Golden Corpus

El seeder (`app/services/demo_seeder.py`) escribe tres documentos PDF generados, cada uno con una imagen PNG (archivos en `uploads/documents` y `uploads/images`, generados con ReportLab), y sus chunks con los mismos divisores que la ingesta (ADR 001). Sin `GOOGLE_API_KEY`, las hojas reciben vectores simulados deterministas. Con una clave, las hojas reciben embeddings a través de Gemini.

## Consecuencias

Positivas:

- Un revisor puede ejecutar la recuperación, el Golden Corpus y la evaluación sin Docker y sin clave de API.
- Las mismas pruebas se ejecutan en ambas bases de datos (ver la sección de pruebas del README, que usa `TEST_DATABASE_URL`).
- El stack completo sigue disponible con un solo comando, con índices de pgvector y trazas de Langfuse.

Compromisos y limitaciones:

- **La recuperación en SQLite es O(N).** Cada consulta calcula el coseno sobre cada hoja y BM25 sobre cada chunk. Es aceptable para el Golden Corpus y para un solo usuario, pero no escala a corpus grandes.
- **"Cero dependencias" significa cero servicios.** Los requisitos de Python siguen incluyendo `pgvector`, `aiosqlite` y `reportlab`. Lo que se elimina es la necesidad de Docker, PostgreSQL y un servidor vectorial.
- **El fallback se decide una sola vez, al arrancar.** El código selecciona la base de datos solo dentro de `init_db()`. Si PostgreSQL falla más tarde, el fallback no se activa en tiempo de ejecución.
- **Los resultados sin conexión no son semánticos.** Sin clave, la rama densa usa vectores simulados SHA-256. La evaluación lo indica (`embedding_mode: "mock"`).
- **El rate limiting es por proceso.** La ventana deslizante vive en memoria (`app/core/rate_limit.py`), indexada por la IP del socket. Varios workers mantendrían cada uno sus propios contadores. El limitador está desactivado bajo pytest.
- **Los datos escritos antes de la corrección de R2-BUG-04 no se corrigen.** Las filas existentes en PostgreSQL que tienen embeddings en los padres, o vectores de un modelo anterior, necesitan volver a generar sus embeddings.

## Alternativas consideradas

| Alternativa | Por qué no se eligió |
|-------------|----------------|
| Solo Docker | Excluye a los revisores sin Docker, que es la principal barrera de evaluación. |
| Solo SQLite | Sin pgvector, sin HNSW, sin GIN; la ruta enterprise no se pondría a prueba. |
| Un almacén vectorial local (FAISS, Chroma, LanceDB) como backend sin Docker | Un segundo stack de recuperación que habría que mantener coherente con PostgreSQL. La ruta de SQLite conserva la misma capa de servicios y el mismo modelo padre-hijo, y solo cambia las ramas densa y dispersa. |
| Solo una demo totalmente del lado del cliente | No puede mostrar la ingesta real, el agente con herramientas reales ni los servicios de Python. El modo 1 lo cubre para la vista de solo lectura. |

## Siguiente paso

Lee el ADR 004 (`docs/adr/004-nextjs-bff-and-24-7-serverless-showcase.md`) para ver el modo en la nube y sus reglas de fallback.
