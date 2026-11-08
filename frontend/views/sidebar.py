"""Sidebar: API health, sessions, hyperparameters, Golden Corpus, ingestion and document catalog."""

import uuid
from typing import Any

import api_client
import streamlit as st

SEARCH_MODES = ("hybrid", "dense", "sparse")
ALL_DOCUMENTS = "__all__"
TITLE_PREVIEW_CHARS = 48


# ---------------------------------------------------------------------------- sessions
def _start_new_session() -> None:
    st.session_state.session_id = str(uuid.uuid4())


def _on_session_picked() -> None:
    st.session_state.session_id = st.session_state.session_picker


def _delete_current_session() -> None:
    res = api_client.delete_session(st.session_state.session_id)
    if res["success"] or res.get("status_code") == 404:
        st.session_state.flash = ("success", "Sesión eliminada.")
        _start_new_session()
    else:
        st.session_state.flash = ("error", f"No se pudo eliminar la sesión: {res.get('error')}")


def _session_label(session: dict[str, Any] | None) -> str:
    if session is None:
        return "Nueva sesión (sin mensajes)"
    title = str(session.get("title") or "Sin título")
    if len(title) > TITLE_PREVIEW_CHARS:
        title = title[:TITLE_PREVIEW_CHARS] + "…"
    return f"{title} · {session.get('message_count', 0)} msgs"


def render_sessions() -> None:
    st.subheader("Sesiones", anchor=False)
    sessions = api_client.list_sessions()
    if sessions is None:
        st.caption("El listado de sesiones no está disponible en esta API.")
        sessions = []
    by_id = {str(s.get("session_id")): s for s in sessions if isinstance(s, dict)}
    current = st.session_state.session_id
    options = list(by_id) if current in by_id else [current, *by_id]

    st.session_state.session_picker = current
    st.selectbox(
        "Sesión activa",
        options=options,
        format_func=lambda sid: _session_label(by_id.get(sid)),
        key="session_picker",
        on_change=_on_session_picked,
    )
    persisted = current in by_id
    with st.container(horizontal=True):
        st.button("Nueva", icon=":material/add:", key="new_session", on_click=_start_new_session)
        st.button(
            "Eliminar",
            icon=":material/delete:",
            key="delete_session",
            on_click=_delete_current_session,
            disabled=not persisted,
        )
    if persisted:
        with st.container(horizontal=True):
            st.download_button(
                "Markdown",
                data=lambda: api_client.export_session(current, "markdown"),
                file_name=f"session-{current}.md",
                mime="text/markdown",
                icon=":material/description:",
                key="export_md",
                on_click="ignore",
            )
            st.download_button(
                "PDF",
                data=lambda: api_client.export_session(current, "pdf"),
                file_name=f"session-{current}.pdf",
                mime="application/pdf",
                icon=":material/picture_as_pdf:",
                key="export_pdf",
                on_click="ignore",
            )
    st.caption(f"ID: `{current}`")


# ---------------------------------------------------------------------------- hyperparameters
def render_hyperparameters(documents: list[dict[str, Any]]) -> api_client.ChatOptions:
    with st.expander("Hiperparámetros del agente", icon=":material/tune:"):
        mode = st.segmented_control(
            "Modo de búsqueda", SEARCH_MODES, default="hybrid", required=True, key="hp_search_mode"
        )
        top_k = st.slider("Fragmentos (top_k)", min_value=1, max_value=50, value=5, key="hp_top_k")
        rerank = st.toggle("Reranking semántico", value=True, key="hp_enable_rerank")
        override = st.toggle("Personalizar temperatura y turnos", value=False, key="hp_override")
        temperature = st.slider(
            "Temperatura", min_value=0.0, max_value=2.0, value=0.2, step=0.1, key="hp_temperature",
            disabled=not override,
        )
        max_turns = st.slider(
            "Máx. iteraciones ReAct", min_value=1, max_value=10, value=5, key="hp_max_turns", disabled=not override
        )
        doc_names = {str(d.get("id")): str(d.get("filename", d.get("id"))) for d in documents if d.get("id")}
        doc_filter = st.selectbox(
            "Restringir a documento",
            options=[ALL_DOCUMENTS, *doc_names],
            format_func=lambda doc_id: "Todos los documentos" if doc_id == ALL_DOCUMENTS else doc_names[doc_id],
            key="hp_filter_document_id",
        )
    return api_client.ChatOptions(
        search_mode=mode or "hybrid",
        top_k=int(top_k),
        enable_rerank=bool(rerank),
        temperature=float(temperature) if override else None,
        max_turns=int(max_turns) if override else None,
        filter_document_id=None if doc_filter in (None, ALL_DOCUMENTS) else doc_filter,
    )


# ---------------------------------------------------------------------------- golden corpus
def _restore_corpus() -> None:
    res = api_client.seed_demo()
    if res["success"]:
        data = res["data"] or {}
        st.session_state.flash = (
            "success",
            f"Golden Corpus restaurado: {data.get('documents_created', 0)} documentos nuevos, "
            f"{data.get('documents_skipped', 0)} existentes ({data.get('duration_ms', 0)} ms).",
        )
        st.session_state.cached_docs = api_client.fetch_documents()
    else:
        st.session_state.flash = ("error", f"No se pudo restaurar el Golden Corpus: {res.get('error')}")


def render_golden_corpus() -> None:
    st.subheader("Golden Corpus", anchor=False)
    res = api_client.demo_status()
    if res["success"] and isinstance(res["data"], dict):
        status = res["data"]
        seeded = "Sembrado" if status.get("demo_seeded") else "Sin sembrar"
        st.markdown(
            f"**{seeded}** · BD `{status.get('db_dialect', '?')}` · embeddings `{status.get('embedding_mode', '?')}`"
        )
        st.caption(
            f"{status.get('total_documents', 0)} documentos · {status.get('total_chunks', 0)} chunks · "
            f"{status.get('total_images', 0)} imágenes"
        )
    else:
        st.caption(f"Estado del demo no disponible ({res.get('error')}).")
    st.button(
        "Restaurar Golden Corpus",
        icon=":material/restore:",
        key="restore_corpus",
        on_click=_restore_corpus,
        width="stretch",
    )


# ---------------------------------------------------------------------------- ingestion / catalog
def render_ingestion() -> None:
    st.subheader("Ingesta de documentos", anchor=False)
    st.caption("Sube PDFs o imágenes (facturas, diagramas, CVs).")
    uploaded_file = st.file_uploader(
        "Selecciona un archivo", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed"
    )
    if uploaded_file is not None and st.button("Subir e indexar", icon=":material/upload:", width="stretch"):
        with st.spinner(f"Ingestando '{uploaded_file.name}'..."):
            res = api_client.upload_document_api(uploaded_file.getvalue(), uploaded_file.name)
        if res.get("success"):
            st.success("Archivo subido y encolado para procesamiento.")
            st.session_state.cached_docs = api_client.fetch_documents()
            st.rerun()
        else:
            st.error(f"Error al subir: {res.get('error')}")


def render_catalog() -> None:
    st.subheader("Documentos en base de datos", anchor=False)
    if st.button("Actualizar documentos", icon=":material/refresh:", width="stretch"):
        st.session_state.cached_docs = api_client.fetch_documents()
    docs = st.session_state.cached_docs
    if not docs:
        st.info("No hay documentos indexados aún.")
        return
    st.caption(f"Total indexados: {len(docs)}")
    for doc in docs:
        status = doc.get("status", "pending")
        status_emoji = "🟢" if status == "completed" else "🟡" if status == "processing" else "🔴"
        with st.expander(f"{status_emoji} {doc.get('filename')}"):
            st.write(f"**Tipo:** {doc.get('file_type')}")
            st.write(f"**Estado:** `{status}`")
            st.write(f"**Fragmentos (Chunks):** {doc.get('total_chunks', 0)}")
            st.write(f"**Fecha:** {str(doc.get('upload_date', ''))[:19]}")
            st.code(f"ID: {doc.get('id')}", language="text")
