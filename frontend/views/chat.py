"""Chat with the autonomous agent: history, citations, tools, feedback, latency X-ray and streaming."""

import html
import uuid
from typing import Any

import api_client
import pandas as pd
import streamlit as st

from views.diagnostics import last_diagnostics, render_diagnostics

LAST_TURN_KEY = "last_turn_xray"
THUMBS_UP = 1  # st.feedback("thumbs") returns 1 for 👍 and 0 for 👎


def _render_citations(citations: list[dict[str, Any]]) -> None:
    with st.expander(f"📚 Fuentes y Citas ({len(citations)})", expanded=False):
        for c in citations:
            doc_name = html.escape(str(c.get("document_name", "Documento")))
            page_num = c.get("page_number")
            page_str = f"Pág. {html.escape(str(page_num))}" if page_num else "Pág. N/D"
            chunk_type = html.escape(str(c.get("chunk_type", "text")))
            st.markdown(
                f"<div class='citation-box'>📄 <b>{doc_name}</b> ({page_str}) — Tipo: <code>{chunk_type}</code></div>",
                unsafe_allow_html=True,
            )


def _render_tools(tools: list[dict[str, Any]]) -> None:
    with st.expander(f"🛠️ Herramientas Ejecutadas ({len(tools)})", expanded=False):
        for t in tools:
            tool_name = html.escape(str(t.get("tool_name", "tool")))
            st.markdown(f"<span class='tool-badge'>⚡ {tool_name}</span>", unsafe_allow_html=True)
            st.json({"Entrada": t.get("tool_input"), "Salida": t.get("tool_output")})


def _render_report_downloads(tools: list[dict[str, Any]], key_prefix: str) -> None:
    for index, t in enumerate(tools):
        if t.get("tool_name") != "generate_report_pdf":
            continue
        output = t.get("tool_output", {})
        if not (isinstance(output, dict) and output.get("status") == "success" and output.get("download_url")):
            continue
        filename = output.get("filename", "reporte.pdf")
        pdf_data = api_client.fetch_file_bytes(output["download_url"])
        if pdf_data:
            st.download_button(
                label=f"📥 Descargar {filename}",
                data=pdf_data,
                file_name=filename,
                mime="application/pdf",
                key=f"dl_{key_prefix}_{index}",
            )


def _send_feedback(session_id: str, message_id: str) -> None:
    value = st.session_state.get(f"fb_{message_id}")
    if value is None:
        return
    rating = 1 if value == THUMBS_UP else -1
    res = api_client.submit_feedback(session_id, message_id, rating)
    if res["success"]:
        st.session_state.flash = ("success", "Gracias por tu valoración.")
    else:
        st.session_state.flash = ("error", f"No se pudo registrar la valoración: {res.get('error')}")


def _render_assistant_extras(msg: dict[str, Any], session_id: str) -> None:
    citations = msg.get("citations") or []
    tools = msg.get("executed_tools") or []
    if citations:
        _render_citations(citations)
    if tools:
        _render_tools(tools)
    diagnostics = last_diagnostics(tools)
    if diagnostics:
        with st.expander("🩻 Rayos X de latencia", expanded=False):
            render_diagnostics(diagnostics, tool_events=tools)
    message_id = msg.get("id")
    _render_report_downloads(tools, key_prefix=str(message_id or uuid.uuid4()))
    if message_id:
        st.feedback(
            "thumbs",
            key=f"fb_{message_id}",
            on_change=_send_feedback,
            args=(session_id, str(message_id)),
        )


def render_history(session_id: str) -> None:
    for msg in api_client.fetch_session_history(session_id):
        if msg.get("role", "user") == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(msg.get("content", ""))
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(msg.get("content", ""))
                _render_assistant_extras(msg, session_id)


def render_last_turn() -> None:
    """X-ray of the latest streamed turn (its total duration is not persisted in the history)."""
    last_turn = st.session_state.get(LAST_TURN_KEY)
    if not isinstance(last_turn, dict):
        return
    with st.expander("🩻 Rayos X del último turno", expanded=True):
        render_diagnostics(
            last_turn.get("diagnostics"),
            duration_ms=last_turn.get("duration_ms"),
            tool_events=last_turn.get("tool_events"),
        )


def handle_user_input(user_input: str, session_id: str, options: api_client.ChatOptions) -> None:
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    with st.chat_message("assistant", avatar="🤖"):
        metadata: dict[str, Any] = {}
        st.write_stream(api_client.stream_chat_response(user_input, session_id, options, metadata))
        if metadata.get("error"):
            st.error(f"Error al comunicar con el agente: {metadata['error']}")
            return
        st.session_state[LAST_TURN_KEY] = {
            "diagnostics": metadata.get("diagnostics"),
            "duration_ms": metadata.get("duration_ms"),
            "tool_events": metadata.get("tool_events"),
        }
        new_citations = metadata.get("citations") or []
        new_tools = metadata.get("executed_tools") or []
        if new_citations:
            _render_citations(new_citations)
        if new_tools:
            _render_tools(new_tools)
        _render_report_downloads(new_tools, key_prefix=f"new_{uuid.uuid4()}")
    # Rerun to resync the full state (history, feedback widgets) with the database
    st.rerun()


def render_search_lab(options: api_client.ChatOptions) -> None:
    """Direct `POST /api/v1/search` with the sidebar hyperparameters, showing results and diagnostics."""
    st.header("Búsqueda RAG directa", anchor=False)
    st.caption("Ejecuta la búsqueda híbrida sin el agente, con los hiperparámetros del panel lateral.")
    with st.form("search_form", border=False):
        query = st.text_input("Consulta", key="search_query")
        submitted = st.form_submit_button("Buscar", icon=":material/search:", type="primary")
    if submitted and query.strip():
        with st.spinner("Buscando..."):
            st.session_state.search_result = api_client.search_knowledge_base(query.strip(), options)
    res = st.session_state.get("search_result")
    if not res:
        return
    if not res["success"]:
        st.error(f"Error en la búsqueda: {res.get('error')}")
        return
    data = res["data"] or {}
    render_diagnostics(data.get("diagnostics"))
    results = data.get("results") or []
    if not results:
        st.info("Sin resultados.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "#": r.get("rank"),
                    "Documento": r.get("document_name"),
                    "Pág.": r.get("page_number"),
                    "Tipo": r.get("chunk_type"),
                    "Score": r.get("score"),
                    "Rerank": r.get("rerank_score"),
                    "Contenido": str(r.get("content", ""))[:300],
                }
                for r in results
            ]
        ),
        hide_index=True,
        alt="Fragmentos recuperados",
    )
