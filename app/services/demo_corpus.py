"""Contenido del Golden Demo Corpus: 3 documentos empresariales multimodales (texto, tablas y diagramas).

Es solo datos: la generación de PDF/PNG y la siembra en base de datos viven en `demo_seeder.py`.
Todos los textos usan caracteres Latin-1 para que las fuentes estándar de ReportLab los rendericen sin fuentes externas.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenTable:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def to_markdown(self) -> str:
        lines = [
            "| " + " | ".join(self.header) + " |",
            "| " + " | ".join("---" for _ in self.header) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in self.rows)
        return "\n".join(lines)


@dataclass(frozen=True)
class GoldenPage:
    sections: tuple[tuple[str, str], ...] = ()  # (encabezado, texto)
    table: GoldenTable | None = None
    table_title: str = ""
    show_image: bool = False


@dataclass(frozen=True)
class GoldenDocument:
    filename: str
    title: str
    pages: tuple[GoldenPage, ...]
    image_filename: str
    image_kind: str  # "architecture" | "bars" | "matrix"
    image_caption: str
    image_description: str


ARQUITECTURA = GoldenDocument(
    filename="Arquitectura_Cloud_IA_2026.pdf",
    title="Arquitectura Cloud de IA 2026",
    image_filename="demo_arquitectura_microservicios.png",
    image_kind="architecture",
    image_caption="Figura 1. Diagrama de arquitectura de microservicios del sistema RAG.",
    image_description=(
        "Diagrama de arquitectura de microservicios: el Cliente (Streamlit o Next.js) llama al API Gateway FastAPI, "
        "que distribuye el tráfico hacia tres servicios: Ingesta, Búsqueda Híbrida y Agente Autónomo. Los tres "
        "persisten en PostgreSQL con pgvector (índice HNSW m=16, ef_construction=64) y reportan trazas a Langfuse. "
        "El servicio de Búsqueda combina recuperación densa y léxica con fusión RRF k=60 y un Reranker semántico."
    ),
    pages=(
        GoldenPage(
            sections=(
                (
                    "1. Visión general de microservicios",
                    "La plataforma se despliega como un conjunto de microservicios sobre contenedores. Un API Gateway "
                    "FastAPI expone el contrato REST /api/v1 y delega en tres servicios de dominio: Ingesta de "
                    "documentos (PDF e imágenes con chunking jerárquico padre-hijo), Búsqueda Híbrida (recuperación "
                    "densa, léxica, fusión y reranking) y Agente Autónomo (razonamiento ReAct con herramientas de "
                    "búsqueda, generación de reportes y webhooks). Todos comparten una única base PostgreSQL 16 con "
                    "la extensión pgvector y envían trazas de observabilidad a Langfuse.",
                ),
                (
                    "2. Topología del índice vectorial HNSW",
                    "Los embeddings de 768 dimensiones se almacenan en una columna vector(768) con un índice HNSW "
                    "(Hierarchical Navigable Small World) configurado con m=16 y ef_construction=64 usando la "
                    "operación vector_cosine_ops. El parámetro m=16 define las conexiones por nodo y "
                    "ef_construction=64 el tamaño de la lista de candidatos durante la construcción del grafo. "
                    "Solo los chunks hoja se vectorizan: los bloques padre aportan contexto sin competir con sus hijos.",
                ),
                (
                    "3. Fusión híbrida con Reciprocal Rank Fusion",
                    "La búsqueda híbrida combina el ranking denso (similitud de coseno) con el ranking léxico "
                    "(full-text search BM25) mediante Reciprocal Rank Fusion: RRF(d) = suma de 1 / (k + rank_i), "
                    "con la constante de suavizado k=60. Después de la fusión se deduplica por bloque padre y se "
                    "aplica un Reranker semántico sobre los mejores candidatos antes de expandir al contexto del padre.",
                ),
            ),
        ),
        GoldenPage(
            sections=(
                (
                    "4. Latencias del pipeline de búsqueda",
                    "Las latencias medidas por etapa con time.perf_counter() se resumen en la tabla siguiente. "
                    "La latencia P50 total es de 175 ms y la P95 total de 430 ms, dominadas por el Reranker semántico.",
                ),
            ),
            table_title="Latencias por etapa (P50 y P95)",
            table=GoldenTable(
                header=("Etapa", "P50 (ms)", "P95 (ms)"),
                rows=(
                    ("Embedding de la consulta", "38", "92"),
                    ("Búsqueda densa HNSW", "6", "14"),
                    ("Búsqueda léxica BM25", "4", "11"),
                    ("Fusión RRF", "1", "2"),
                    ("Reranker semántico", "120", "310"),
                    ("Total", "175", "430"),
                ),
            ),
            show_image=True,
        ),
    ),
)

FINANCIERO = GoldenDocument(
    filename="Reporte_Financiero_Q3_GlobalTech.pdf",
    title="Reporte Financiero Q3 - GlobalTech",
    image_filename="demo_ingresos_por_region.png",
    image_kind="bars",
    image_caption="Figura 1. Gráfico de barras de ingresos por región (USD millones).",
    image_description=(
        "Gráfico de barras de ingresos del tercer trimestre por región en millones de dólares: Norteamérica $45M "
        "(la barra más alta), EMEA $28M y LATAM $19M, para un total de $92M. El gráfico muestra que Norteamérica "
        "concentra cerca de la mitad de los ingresos de GlobalTech."
    ),
    pages=(
        GoldenPage(
            sections=(
                (
                    "Resumen ejecutivo del tercer trimestre",
                    "GlobalTech cerró el tercer trimestre con ingresos totales de $92M, impulsados por la adopción de "
                    "su plataforma de IA generativa en clientes empresariales. El EBITDA alcanzó el 34% de los "
                    "ingresos, equivalente a $31.3M, mejorando el margen frente al trimestre anterior gracias a la "
                    "eficiencia operativa y a la reducción de los costos de inferencia.",
                ),
                (
                    "Costos de inferencia",
                    "Los costos de inferencia de modelos de lenguaje sumaron $6.4M, cerca del 7% de los ingresos y un "
                    "18% menos que en el segundo trimestre. La reducción proviene del uso de modelos flash para "
                    "tareas de clasificación, del caché de embeddings y del batching de solicitudes. Se prevé "
                    "mantener el margen EBITDA por encima del 33% durante el cuarto trimestre.",
                ),
            ),
        ),
        GoldenPage(
            sections=(
                (
                    "Ingresos por región",
                    "La tabla resume los ingresos por región. Norteamérica aporta $45M, EMEA $28M y LATAM $19M.",
                ),
            ),
            table_title="Ingresos por región, tercer trimestre",
            table=GoldenTable(
                header=("Región", "Ingresos (USD M)", "Participación"),
                rows=(
                    ("Norteamérica", "$45M", "48.9%"),
                    ("EMEA", "$28M", "30.4%"),
                    ("LATAM", "$19M", "20.7%"),
                    ("Total", "$92M", "100%"),
                ),
            ),
            show_image=True,
        ),
    ),
)

SEGURIDAD = GoldenDocument(
    filename="Manual_Seguridad_ZeroTrust_OWASP.pdf",
    title="Manual de Seguridad Zero Trust y OWASP",
    image_filename="demo_matriz_riesgo_zerotrust.png",
    image_kind="matrix",
    image_caption="Figura 1. Matriz de riesgo OWASP (probabilidad por impacto).",
    image_description=(
        "Matriz de riesgo OWASP de 3x3 que cruza probabilidad e impacto. Los riesgos A01 Control de acceso roto, "
        "A03 Inyección y A10 SSRF aparecen en la zona alta (rojo) y están mitigados con X-API-Key, ORM parametrizado "
        "y allow-list de hosts; A04 Diseño inseguro y A09 Registro y monitoreo aparecen en la zona media (amarillo)."
    ),
    pages=(
        GoldenPage(
            sections=(
                (
                    "1. Principios Zero Trust",
                    "El sistema aplica Zero Trust: nunca se confía en una solicitud por su origen de red y cada "
                    "petición se autentica, se autoriza y se valida. Los privilegios son mínimos, los secretos "
                    "viven en variables de entorno y toda entrada externa (cuerpos JSON, archivos, URLs) se "
                    "considera no confiable hasta ser validada.",
                ),
                (
                    "2. Controles anti-SSRF",
                    "Para prevenir Server-Side Request Forgery (SSRF) en los webhooks salientes, el sistema usa una "
                    "allow-list de hosts (ALLOWED_WEBHOOK_HOSTS), exige https salvo hosts explícitamente permitidos, "
                    "bloquea direcciones privadas, de loopback y link-local (como 169.254.169.254) y valida el "
                    "puerto de destino contra una lista de puertos permitidos.",
                ),
                (
                    "3. Sanitización de archivos",
                    "Cada archivo subido se valida por su firma real (magic bytes %PDF- o cabecera PNG) y no solo por "
                    "su extensión, respeta un tamaño máximo configurable (MAX_UPLOAD_SIZE_MB), se guarda con un "
                    "nombre normalizado con UUID y solo se sirve mediante rutas autenticadas con contención de ruta "
                    "para evitar path traversal.",
                ),
            ),
        ),
        GoldenPage(
            sections=(
                (
                    "4. Autenticación y auditoría continua",
                    "Todos los endpoints /api/v1 exigen la cabecera X-API-Key, comparada en tiempo constante con "
                    "secrets.compare_digest, y un limitador de ventana deslizante restringe las solicitudes por IP. "
                    "La auditoría continua se apoya en trazas de Langfuse y en registros estructurados de cada "
                    "herramienta ejecutada por el agente.",
                ),
            ),
            table_title="Matriz de riesgo OWASP",
            table=GoldenTable(
                header=("Riesgo OWASP", "Severidad", "Control", "Estado"),
                rows=(
                    ("A01 Control de acceso roto", "Alta", "X-API-Key y contención de rutas", "Mitigado"),
                    ("A03 Inyección", "Alta", "ORM parametrizado", "Mitigado"),
                    ("A10 SSRF", "Alta", "allow-list de hosts y puertos", "Mitigado"),
                    ("A04 Diseño inseguro", "Media", "Modelado de amenazas", "Parcial"),
                    ("A09 Registro y monitoreo", "Media", "Auditoría continua con Langfuse", "Mitigado"),
                ),
            ),
            show_image=True,
        ),
    ),
)

GOLDEN_DOCUMENTS: tuple[GoldenDocument, ...] = (ARQUITECTURA, FINANCIERO, SEGURIDAD)
GOLDEN_FILENAMES: tuple[str, ...] = tuple(d.filename for d in GOLDEN_DOCUMENTS)
