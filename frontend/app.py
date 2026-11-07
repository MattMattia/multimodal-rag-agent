import html
import json
import os
import uuid
from typing import Any, Dict, List, Optional
import httpx
import streamlit as st

# ==============================================================================
# CONFIGURACIÓN GENERAL Y ESTILOS
# ==============================================================================
st.set_page_config(
    page_title="RAG Multimodal & Agente IA Autónomo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = os.getenv("API_URL", "http://localhost:8000")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000")

# CSS personalizado para pulir la interfaz
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .tool-badge {
        display: inline-block;
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 0.2rem 0.5rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    .citation-box {
        background-color: #F3F4F6;
        border-left: 4px solid #3B82F6;
        padding: 0.6rem 0.8rem;
        border-radius: 4px;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# CLIENTE HTTP Y FUNCIONES API
# ==============================================================================
def check_api_health() -> Dict[str, Any]:
    """Consulta el estado del servicio backend FastAPI."""
    try:
        resp = httpx.get(f"{API_URL}/health", headers=API_HEADERS, timeout=3.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"status": "error"}


def fetch_documents() -> List[Dict[str, Any]]:
    """Obtiene la lista de documentos registrados en el sistema."""
    try:
        resp = httpx.get(f"{API_URL}/api/v1/documents", headers=API_HEADERS, timeout=5.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return []


def upload_document_api(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Sube un documento a la API para su procesamiento multimodal."""
    try:
        files = {"file": (filename, file_bytes)}
        resp = httpx.post(f"{API_URL}/api/v1/documents/upload", files=files, headers=API_HEADERS, timeout=60.0)
        if resp.status_code in (200, 201, 202):
            return {"success": True, "data": resp.json() if resp.text else {}}
        else:
            return {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_session_history(session_id: str) -> List[Dict[str, Any]]:
    """Recupera el historial de mensajes de una sesión desde PostgreSQL."""
    try:
        resp = httpx.get(f"{API_URL}/api/v1/agent/sessions/{session_id}/history", headers=API_HEADERS, timeout=5.0)
        if resp.status_code == 200:
            return resp.json().get("messages", [])
    except Exception:
        pass
    return []


def send_chat_message(message: str, session_id: str) -> Dict[str, Any]:
    """Envía un mensaje al Agente IA Autónomo para razonamiento y ejecución."""
    try:
        payload = {"message": message, "session_id": session_id}
        resp = httpx.post(f"{API_URL}/api/v1/agent/chat", json=payload, headers=API_HEADERS, timeout=60.0)
        if resp.status_code == 200:
            return {"success": True, "data": resp.json()}
        else:
            return {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}


def stream_chat_response(message: str, session_id: str, metadata_container: Dict[str, Any]):
    """Generador que consume el endpoint SSE /api/v1/agent/chat/stream emitiendo tokens en tiempo real."""
    payload = {"message": message, "session_id": session_id}
    try:
        with httpx.stream(
            "POST",
            f"{API_URL}/api/v1/agent/chat/stream",
            json=payload,
            headers=API_HEADERS,
            timeout=120.0,
        ) as response:
            if response.status_code != 200:
                err_text = response.read().decode("utf-8", errors="ignore")
                metadata_container["error"] = f"HTTP {response.status_code}: {err_text}"
                yield f"⚠️ Error del servidor ({response.status_code}): {err_text}"
                return

            for line in response.iter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if not data_str:
                        continue
                    try:
                        event = json.loads(data_str)
                        ev_type = event.get("type")
                        if ev_type == "token":
                            yield event.get("content", "")
                        elif ev_type == "metadata":
                            metadata_container.update(event)
                    except json.JSONDecodeError:
                        continue  # malformed SSE payload: skip it
    except Exception as e:
        metadata_container["error"] = str(e)
        yield f"\n\n⚠️ Error de conexión durante la transmisión en streaming: {str(e)}"


@st.cache_data(ttl=300, show_spinner=False)
def fetch_file_bytes(relative_url: str) -> Optional[bytes]:
    """Descarga los bytes de un archivo estático servido por la API."""
    try:
        clean_url = relative_url.lstrip("/")
        resp = httpx.get(f"{API_URL}/{clean_url}", headers=API_HEADERS, timeout=15.0)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        pass
    return None


# ==============================================================================
# INICIALIZACIÓN DEL ESTADO DE SESIÓN
# ==============================================================================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "known_sessions" not in st.session_state:
    st.session_state.known_sessions = [st.session_state.session_id]

if "cached_docs" not in st.session_state:
    st.session_state.cached_docs = []


# ==============================================================================
# PANEL LATERAL (SIDEBAR)
# ==============================================================================
with st.sidebar:
    st.title("⚙️ Panel de Control")
    st.caption("Sistema RAG Multimodal & Agente IA")

    # 1. Estado del Sistema
    health = check_api_health()
    if health.get("status") == "ok":
        st.success(f"🟢 **API Conectada** ({health.get('environment', 'dev')})")
    else:
        st.error("🔴 **API No Disponible** (Verifica contenedor `rag_api`)")

    st.markdown("---")

    # 2. Gestión de Sesiones y Memoria Multi-Turno
    st.subheader("💬 Memoria de Sesión")
    st.caption("Las conversaciones se persisten en PostgreSQL asociadas al Session ID.")

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        st.text_input("Session ID Activo", value=st.session_state.session_id, disabled=True)
    with col_s2:
        if st.button("➕", help="Crear nueva sesión limpia"):
            new_id = str(uuid.uuid4())
            st.session_state.session_id = new_id
            if new_id not in st.session_state.known_sessions:
                st.session_state.known_sessions.append(new_id)
            st.rerun()

    # Selector de sesiones previas
    if len(st.session_state.known_sessions) > 1:
        selected_session = st.selectbox(
            "Cambiar a otra sesión:",
            options=st.session_state.known_sessions,
            index=st.session_state.known_sessions.index(st.session_state.session_id),
        )
        if selected_session != st.session_state.session_id:
            st.session_state.session_id = selected_session
            st.rerun()

    st.markdown("---")

    # 3. Subida de Documentos (Ingesta Multimodal)
    st.subheader("📤 Ingesta de Documentos")
    st.caption("Sube PDFs o imágenes (facturas, diagramas, CVs).")

    uploaded_file = st.file_uploader(
        "Selecciona un archivo",
        type=["pdf", "png", "jpg", "jpeg"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        if st.button("🚀 Subir e Indexar", use_container_width=True):
            with st.spinner(f"Ingestando '{uploaded_file.name}'..."):
                file_bytes = uploaded_file.getvalue()
                res = upload_document_api(file_bytes, uploaded_file.name)
                if res.get("success"):
                    st.success("Archivo subido y encolado para procesamiento.")
                    st.session_state.cached_docs = fetch_documents()
                    st.rerun()
                else:
                    st.error(f"Error al subir: {res.get('error')}")

    st.markdown("---")

    # 4. Catálogo de Documentos Indexados
    st.subheader("📚 Documentos en Base de Datos")
    if st.button("🔄 Actualizar Documentos", use_container_width=True):
        st.session_state.cached_docs = fetch_documents()

    if not st.session_state.cached_docs:
        st.session_state.cached_docs = fetch_documents()

    docs = st.session_state.cached_docs
    if docs:
        st.caption(f"Total indexados: {len(docs)}")
        for doc in docs:
            status = doc.get("status", "pending")
            status_emoji = "🟢" if status == "completed" else "🟡" if status == "processing" else "🔴"
            with st.expander(f"{status_emoji} {doc.get('filename')}"):
                st.write(f"**Tipo:** {doc.get('file_type')}")
                st.write(f"**Estado:** `{status}`")
                chunks_count = doc.get("total_chunks", 0)
                st.write(f"**Fragmentos (Chunks):** {chunks_count}")
                st.write(f"**Fecha:** {doc.get('upload_date', '')[:19]}")
                st.code(f"ID: {doc.get('id')}", language="text")
    else:
        st.info("No hay documentos indexados aún.")


# ==============================================================================
# ÁREA PRINCIPAL: CHAT CON EL AGENTE IA AUTÓNOMO
# ==============================================================================
st.markdown('<div class="main-title">🤖 Agente IA Autónomo & RAG Multimodal</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Motor con razonamiento ReAct, búsqueda híbrida en PostgreSQL (pgvector), '
    'generación de informes ejecutivos en PDF y memoria conversacional persistente.</div>',
    unsafe_allow_html=True,
)

# Sugerencias rápidas de consulta en acordeón
with st.expander("💡 Ejemplos de instrucciones para interactuar con el agente", expanded=False):
    col_e1, col_e2, col_e3 = st.columns(3)
    with col_e1:
        st.info("🔍 **Consulta de Datos / CVs:**\n\n'¿Quién es Mattia Risso y qué experiencia técnica tiene?'")
    with col_e2:
        st.info("📄 **Generación de Reportes:**\n\n'Genera un reporte PDF con el resumen ejecutivo de la auditoría y sus conclusiones.'")
    with col_e3:
        st.info("🔔 **Notificación / Webhook:**\n\n'Notifica por webhook que se aprobó la factura INV-1002 por $1500.'")

# Cargar historial de conversación para la sesión actual
history_messages = fetch_session_history(st.session_state.session_id)

# Renderizar cada mensaje del historial
for msg in history_messages:
    role = msg.get("role", "user")
    content = msg.get("content", "")
    citations = msg.get("citations") or []
    executed_tools = msg.get("executed_tools") or []

    if role == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(content)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(content)

            # Acordeón de citas y fuentes bibliográficas
            if citations:
                with st.expander(f"📚 Fuentes y Citas ({len(citations)})", expanded=False):
                    for c in citations:
                        doc_name = html.escape(str(c.get("document_name", "Documento")))
                        page_num = c.get("page_number")
                        page_str = f"Pág. {page_num}" if page_num else "Pág. N/D"
                        chunk_type = html.escape(str(c.get("chunk_type", "text")))
                        st.markdown(
                            f"<div class='citation-box'>📄 <b>{doc_name}</b> ({page_str}) — Tipo: <code>{chunk_type}</code></div>",
                            unsafe_allow_html=True,
                        )

            # Acordeón de herramientas ejecutadas
            if executed_tools:
                with st.expander(f"🛠️ Herramientas Ejecutadas ({len(executed_tools)})", expanded=False):
                    for t in executed_tools:
                        tool_name = t.get("tool_name", "tool")
                        st.markdown(f"<span class='tool-badge'>⚡ {tool_name}</span>", unsafe_allow_html=True)
                        st.json({"Entrada": t.get("tool_input"), "Salida": t.get("tool_output")})

            # Botón de descarga si se generó un reporte PDF
            for t in executed_tools:
                if t.get("tool_name") == "generate_report_pdf":
                    output = t.get("tool_output", {})
                    if isinstance(output, dict) and output.get("status") == "success":
                        dl_url = output.get("download_url")
                        fn = output.get("filename", "reporte.pdf")
                        if dl_url:
                            pdf_data = fetch_file_bytes(dl_url)
                            col_b1, col_b2 = st.columns([1, 2])
                            with col_b1:
                                if pdf_data:
                                    st.download_button(
                                        label=f"📥 Descargar {fn}",
                                        data=pdf_data,
                                        file_name=fn,
                                        mime="application/pdf",
                                        key=f"dl_{msg.get('id', uuid.uuid4())}",
                                    )
                            with col_b2:
                                public_link = f"{PUBLIC_API_URL}{dl_url}"
                                st.markdown(f"[🔗 Abrir PDF directamente en el navegador]({public_link})")


# ==============================================================================
# ENTRADA DE MENSAJE DEL CHAT
# ==============================================================================
user_input = st.chat_input("Escribe tu consulta o instrucción para el Agente IA...")

if user_input:
    # 1. Mostrar mensaje del usuario inmediatamente en la UI
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    # 2. Ejecutar agente con streaming de respuestas en tiempo real (SSE)
    with st.chat_message("assistant", avatar="🤖"):
        stream_metadata: Dict[str, Any] = {}
        stream_gen = stream_chat_response(
            message=user_input,
            session_id=st.session_state.session_id,
            metadata_container=stream_metadata,
        )
        full_reply = st.write_stream(stream_gen)

        if stream_metadata.get("error"):
            response_data = {"success": False, "error": stream_metadata.get("error")}
        else:
            response_data = {"success": True, "data": stream_metadata}

        if response_data.get("success"):
            data = response_data.get("data", {})

            # Mostrar citas bibliográficas si vinieron en la metadata
            new_citations = data.get("citations", [])
            if new_citations:
                with st.expander(f"📚 Fuentes y Citas ({len(new_citations)})", expanded=False):
                    for c in new_citations:
                        doc_name = html.escape(str(c.get("document_name", "Documento")))
                        page_num = c.get("page_number")
                        page_str = f"Pág. {page_num}" if page_num else "Pág. N/D"
                        chunk_type = html.escape(str(c.get("chunk_type", "text")))
                        st.markdown(
                            f"<div class='citation-box'>📄 <b>{doc_name}</b> ({page_str}) — Tipo: <code>{chunk_type}</code></div>",
                            unsafe_allow_html=True,
                        )

            # Mostrar herramientas ejecutadas
            new_tools = data.get("executed_tools", [])
            if new_tools:
                with st.expander(f"🛠️ Herramientas Ejecutadas ({len(new_tools)})", expanded=False):
                    for t in new_tools:
                        tool_name = t.get("tool_name", "tool")
                        st.markdown(f"<span class='tool-badge'>⚡ {tool_name}</span>", unsafe_allow_html=True)
                        st.json({"Entrada": t.get("tool_input"), "Salida": t.get("tool_output")})

            # Botón de descarga si generó PDF
            for t in new_tools:
                if t.get("tool_name") == "generate_report_pdf":
                    output = t.get("tool_output", {})
                    if isinstance(output, dict) and output.get("status") == "success":
                        dl_url = output.get("download_url")
                        fn = output.get("filename", "reporte.pdf")
                        if dl_url:
                            pdf_data = fetch_file_bytes(dl_url)
                            col_b1, col_b2 = st.columns([1, 2])
                            with col_b1:
                                if pdf_data:
                                    st.download_button(
                                        label=f"📥 Descargar {fn}",
                                        data=pdf_data,
                                        file_name=fn,
                                        mime="application/pdf",
                                        key=f"dl_new_{uuid.uuid4()}",
                                    )
                            with col_b2:
                                public_link = f"{PUBLIC_API_URL}{dl_url}"
                                st.markdown(f"[🔗 Abrir PDF directamente en el navegador]({public_link})")

            # Recargar para sincronizar estado completo con PostgreSQL
            st.rerun()
        else:
            st.error(f"Error al comunicar con el agente: {response_data.get('error')}")