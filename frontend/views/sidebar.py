"""Sidebar: language selector, API health, sessions, hyperparameters, Golden Corpus, ingestion and document catalog."""

import uuid
from collections.abc import Callable
from typing import Any

import api_client
import streamlit as st
from i18n import DEFAULT_LANG, LANG_KEY, LANGUAGES, current_lang, t

SEARCH_MODES = ("hybrid", "dense", "sparse")
ALL_DOCUMENTS = "__all__"
TITLE_PREVIEW_CHARS = 48


# ---------------------------------------------------------------------------- language
def render_language_selector() -> None:
    """Compact es/en selector bound to `st.session_state.lang`; the change applies on the same rerun."""
    st.segmented_control(
        t("lang_label"),
        list(LANGUAGES),
        format_func=LANGUAGES.__getitem__,
        default=DEFAULT_LANG,
        required=True,
        key=LANG_KEY,
    )


# ---------------------------------------------------------------------------- sessions
def _start_new_session() -> None:
    st.session_state.session_id = str(uuid.uuid4())


def _on_session_picked() -> None:
    st.session_state.session_id = st.session_state.session_picker


def _delete_current_session() -> None:
    res = api_client.delete_session(st.session_state.session_id)
    if res["success"] or res.get("status_code") == 404:
        st.session_state.flash = ("success", t("session_deleted"))
        _start_new_session()
    else:
        st.session_state.flash = ("error", t("session_delete_failed", error=res.get("error")))


def _labels_formatter(labels: dict[str, str]) -> Callable[[str], str]:
    """`format_func` over labels translated at render time (stable even if called outside the script run)."""
    return lambda option: labels.get(option, str(option))


def _session_label(session: dict[str, Any] | None) -> str:
    if session is None:
        return t("session_new")
    title = str(session.get("title") or t("session_untitled"))
    if len(title) > TITLE_PREVIEW_CHARS:
        title = title[:TITLE_PREVIEW_CHARS] + "…"
    return t("session_label", title=title, count=session.get("message_count", 0))


def render_sessions() -> None:
    st.subheader(t("sessions_header"), anchor=False)
    sessions = api_client.list_sessions()
    if sessions is None:
        st.caption(t("sessions_unavailable"))
        sessions = []
    by_id = {str(s.get("session_id")): s for s in sessions if isinstance(s, dict)}
    current = st.session_state.session_id
    options = list(by_id) if current in by_id else [current, *by_id]

    st.session_state.session_picker = current
    st.selectbox(
        t("session_active"),
        options=options,
        format_func=_labels_formatter({sid: _session_label(by_id.get(sid)) for sid in options}),
        key="session_picker",
        on_change=_on_session_picked,
    )
    persisted = current in by_id
    with st.container(horizontal=True):
        st.button(t("session_btn_new"), icon=":material/add:", key="new_session", on_click=_start_new_session)
        st.button(
            t("session_btn_delete"),
            icon=":material/delete:",
            key="delete_session",
            on_click=_delete_current_session,
            disabled=not persisted,
        )
    if persisted:
        lang = current_lang()
        with st.container(horizontal=True):
            st.download_button(
                "Markdown",
                data=lambda: api_client.export_session(current, "markdown", lang),
                file_name=f"session-{current}.md",
                mime="text/markdown",
                icon=":material/description:",
                key="export_md",
                on_click="ignore",
            )
            st.download_button(
                "PDF",
                data=lambda: api_client.export_session(current, "pdf", lang),
                file_name=f"session-{current}.pdf",
                mime="application/pdf",
                icon=":material/picture_as_pdf:",
                key="export_pdf",
                on_click="ignore",
            )
    st.caption(t("session_id", session_id=current))


# ---------------------------------------------------------------------------- hyperparameters
def render_hyperparameters(documents: list[dict[str, Any]]) -> api_client.ChatOptions:
    with st.expander(t("hp_title"), icon=":material/tune:"):
        mode = st.segmented_control(
            t("hp_search_mode"), SEARCH_MODES, default="hybrid", required=True, key="hp_search_mode"
        )
        top_k = st.slider(t("hp_top_k"), min_value=1, max_value=50, value=5, key="hp_top_k")
        rerank = st.toggle(t("hp_rerank"), value=True, key="hp_enable_rerank")
        override = st.toggle(t("hp_override"), value=False, key="hp_override")
        temperature = st.slider(
            t("hp_temperature"), min_value=0.0, max_value=2.0, value=0.2, step=0.1, key="hp_temperature",
            disabled=not override,
        )
        max_turns = st.slider(
            t("hp_max_turns"), min_value=1, max_value=10, value=5, key="hp_max_turns", disabled=not override
        )
        doc_names = {str(d.get("id")): str(d.get("filename", d.get("id"))) for d in documents if d.get("id")}
        doc_filter = st.selectbox(
            t("hp_doc_filter"),
            options=[ALL_DOCUMENTS, *doc_names],
            format_func=_labels_formatter({ALL_DOCUMENTS: t("hp_all_docs"), **doc_names}),
            key="hp_filter_document_id",
        )
    return api_client.ChatOptions(
        search_mode=mode or "hybrid",
        top_k=int(top_k),
        enable_rerank=bool(rerank),
        temperature=float(temperature) if override else None,
        max_turns=int(max_turns) if override else None,
        filter_document_id=None if doc_filter in (None, ALL_DOCUMENTS) else doc_filter,
        language=current_lang(),
    )


# ---------------------------------------------------------------------------- golden corpus
def _restore_corpus() -> None:
    res = api_client.seed_demo()
    if res["success"]:
        data = res["data"] or {}
        st.session_state.flash = (
            "success",
            t(
                "corpus_restored",
                created=data.get("documents_created", 0),
                skipped=data.get("documents_skipped", 0),
                duration=data.get("duration_ms", 0),
            ),
        )
        st.session_state.cached_docs = api_client.fetch_documents()
    else:
        st.session_state.flash = ("error", t("corpus_restore_failed", error=res.get("error")))


def render_golden_corpus() -> None:
    st.subheader(t("corpus_header"), anchor=False)
    res = api_client.demo_status()
    if res["success"] and isinstance(res["data"], dict):
        status = res["data"]
        seeded = t("corpus_seeded") if status.get("demo_seeded") else t("corpus_unseeded")
        st.markdown(
            t(
                "corpus_status",
                seeded=seeded,
                db=status.get("db_dialect", "?"),
                embeddings=status.get("embedding_mode", "?"),
            )
        )
        st.caption(
            t(
                "corpus_counts",
                documents=status.get("total_documents", 0),
                chunks=status.get("total_chunks", 0),
                images=status.get("total_images", 0),
            )
        )
    else:
        st.caption(t("corpus_status_unavailable", error=res.get("error")))
    st.button(
        t("corpus_restore_btn"),
        icon=":material/restore:",
        key="restore_corpus",
        on_click=_restore_corpus,
        width="stretch",
    )


# ---------------------------------------------------------------------------- ingestion / catalog
def render_ingestion() -> None:
    st.subheader(t("ingest_header"), anchor=False)
    st.caption(t("ingest_caption"))
    uploaded_file = st.file_uploader(
        t("ingest_uploader"), type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed"
    )
    if uploaded_file is not None and st.button(t("ingest_btn"), icon=":material/upload:", width="stretch"):
        with st.spinner(t("ingest_spinner", name=uploaded_file.name)):
            res = api_client.upload_document_api(uploaded_file.getvalue(), uploaded_file.name)
        if res.get("success"):
            st.success(t("ingest_ok"))
            st.session_state.cached_docs = api_client.fetch_documents()
            st.rerun()
        else:
            st.error(t("ingest_failed", error=res.get("error")))


def render_catalog() -> None:
    st.subheader(t("catalog_header"), anchor=False)
    if st.button(t("catalog_refresh"), icon=":material/refresh:", width="stretch"):
        st.session_state.cached_docs = api_client.fetch_documents()
    docs = st.session_state.cached_docs
    if not docs:
        st.info(t("catalog_empty"))
        return
    st.caption(t("catalog_total", count=len(docs)))
    for doc in docs:
        status = doc.get("status", "pending")
        status_emoji = "🟢" if status == "completed" else "🟡" if status == "processing" else "🔴"
        with st.expander(f"{status_emoji} {doc.get('filename')}"):
            st.write(t("doc_type", value=doc.get("file_type")))
            st.write(t("doc_status", value=status))
            st.write(t("doc_chunks", value=doc.get("total_chunks", 0)))
            st.write(t("doc_date", value=str(doc.get("upload_date", ""))[:19]))
            st.code(f"ID: {doc.get('id')}", language="text")
