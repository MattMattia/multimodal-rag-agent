# ADR 004 — BFF en Next.js con un fallback de showcase serverless

## Estado

Aceptada (implementada en `web/src/app/api/*`, `web/src/lib/server/backend.ts` y `web/src/lib/showcase/*`).

## Contexto

Un revisor debería poder abrir el proyecto en cualquier momento, incluso cuando la máquina de la API está apagada. Exponer el
backend FastAPI directamente al navegador tiene dos problemas. El navegador necesitaría la clave de API del backend o reglas CORS
para cada origen, y cualquier caída del backend se vería como una página rota.

La aplicación web es Next.js 15.5.29 con React 19.2.9. Sus rutas se ejecutan en el servidor, así que la URL del backend y la
clave de API nunca llegan al bundle del navegador.

## Decisión

La aplicación Next.js es un backend-for-frontend (BFF). Sus route handlers en `web/src/app/api/*` llaman primero a FastAPI
y recurren a un motor de showcase embebido solo cuando el backend no es accesible.

### Configuración (solo del lado del servidor)

| Variable | Valor por defecto | Uso |
|----------|---------|-----|
| `FASTAPI_URL` | sin definir | URL base del backend. Si no está definida, el showcase sirve todas las rutas. |
| `API_KEY` | sin definir | Se envía como `X-API-Key` al backend. Solo se lee en el servidor y nunca es una variable `NEXT_PUBLIC_*`. |
| `FASTAPI_TIMEOUT_MS` | `3000` | Tiempo de espera de las cabeceras de respuesta. El streaming del chat usa 15 s y las subidas usan 30 s. |

### Cuándo se ejecuta el fallback

`callBackend` en `web/src/lib/server/backend.ts` clasifica el resultado:

| Resultado | Efecto |
|---------|--------|
| `FASTAPI_URL` no está definida | Fallback (`unreachable`) |
| Error de red o tiempo agotado mientras se esperan las cabeceras | Fallback (`unreachable`) |
| HTTP 502 o 504 | Fallback (`unreachable`) |
| Cualquier otro estado HTTP, incluidos 2xx, 4xx, 500 y 503 | Se transmite al navegador sin cambios |
| El cliente cerró la petición | Sin fallback; la petición upstream se cancela |

La regla de transmitir un 503 en vivo es deliberada: un backend en vivo puede devolverlo a propósito. Solo la situación de "no hay backend detrás del proxy" activa el showcase.

Cada respuesta incluye `x-rag-source` (`fastapi` o `showcase`), para que un cliente pueda saber qué motor respondió. Cada fallback escribe una advertencia en el servidor que indica la ruta y el motivo, nunca la URL ni la clave.

### Motor de showcase

El showcase es un conjunto de módulos TypeScript sin dependencias en `web/src/lib/showcase/`:

| Módulo | Función |
|--------|------|
| `corpus.ts` y `golden-corpus.json` | El Golden Corpus, generado desde el backend con los mismos divisores e ids que el seeder (ADR 001). |
| `dense.ts` | Sustituto denso: feature hashing FNV-1a de tokens con stemming y trigramas de caracteres en 512 dimensiones, con normalización L2. No es un modelo de lenguaje. |
| `lexical.ts` | Port a TypeScript de `app/services/lexical.py`, con BM25 (`k1 = 1.5`, `b = 0.75`). |
| `search.ts` | Las mismas etapas que el backend: ramas densa y dispersa, RRF con `k = 60`, ventana de candidatos `min(top_k × 4, 80)`, deduplicación por bloque padre, ventana de reranking `top_k × 3`. |
| `agent.ts` | Turno determinista y extractivo con forma de ReAct. Ejecuta la búsqueda como una llamada a herramienta y transmite en streaming una respuesta construida a partir del texto recuperado. |
| `evaluation.ts` | Réplica de `RAGEvaluationService` sobre el corpus embebido. |
| `reports.ts` y `pdf.ts` | Generación de PDF sin estado para los informes. |

Las subidas no están disponibles en el showcase. El fallback de `POST /api/documents` responde con una explicación de que las subidas necesitan el backend en vivo y de que el showcase sirve el Golden Corpus de solo lectura.

### Rutas que usan el fallback

Rutas que llaman a `liveOrShowcase`: `search`, `documents` (lista, detalle, imagen, subida), `reports/[filename]`, `sessions` (lista, detalle, historial, exportación), `feedback`, `demo/seed`, `demo/evaluate`. El stream del chat (`chat/stream`) llama directamente a `callBackend` y recurre a `showcaseStream`.

## Consecuencias

Positivas:

- El showcase público funciona sin un backend en ejecución y sigue ejercitando la forma del pipeline de búsqueda (densa, dispersa, RRF, reranking, expansión al padre).
- Los secretos se quedan en el servidor. El navegador solo llama a `/api/*` en el mismo origen.
- Una única forma de respuesta para ambos motores: el showcase devuelve los mismos tipos JSON que FastAPI, definidos en `web/src/lib/contracts.ts`. La cabecera `x-rag-source` los distingue.

Compromisos y limitaciones:

- **El showcase no es la recuperación real.** Su rama densa es un sustituto basado en hashing y su reranking es un sustituto léxico. Su rama dispersa es BM25, que coincide con el backend SQLite, no con la rama de texto completo de PostgreSQL. La respuesta de evaluación incluye `SHOWCASE_EVALUATION_WARNING` en `warnings`, y la vista de benchmark muestra esa lista.
- **El agente no es un modelo de lenguaje.** `agent.ts` responde con evidencia extraída del corpus, así que el texto transmitido no proviene de Gemini.
- **El corpus es una instantánea.** Cambiar el Golden Corpus requiere regenerar `golden-corpus.json` desde el backend.
- **Un fallback puede ocultar una caída.** Los usuarios ven una página funcional mientras el backend está caído. La cabecera `x-rag-source` y el log del servidor son las únicas señales.
- **Los tiempos de espera son cortos por defecto.** Un host de backend en reposo que responde en más de 3 s se trata como no disponible, aunque hubiera respondido más tarde.
- **El showcase no almacena las escrituras de subidas ni de feedback.** Esas acciones requieren el backend en vivo.

## Alternativas consideradas

| Alternativa | Por qué no se eligió |
|-------------|----------------|
| El navegador llama a FastAPI directamente | Expone la gestión de CORS y de claves al navegador y no ofrece una vista sin conexión. |
| Solo una exportación estática del Golden Corpus | No puede mostrar el turno ReAct, los diagnósticos de búsqueda ni la lógica del benchmark. El motor de showcase los mantiene en código. |
| Ejecutar FastAPI en una función serverless | Trasladaría la base de datos, las llamadas a Gemini y el reranker a un runtime serverless. El proyecto mantiene FastAPI como backend del stack completo y usa el showcase solo como fallback de solo lectura. |
| Quedarse en Streamlit | Streamlit necesita un proceso de Python en ejecución; se conserva para el modo enterprise completo. |

## Siguiente paso

Vuelve al ADR 003 para ver los tres modos, o consulta la sección del README sobre los modos de ejecución.
