"""Latency X-ray: renders `SearchDiagnostics` as a per-stage bar chart."""

from typing import Any

import pandas as pd
import streamlit as st

# (SearchDiagnostics field, Spanish label) in pipeline order.
STAGES = (
    ("embedding_ms", "Embedding"),
    ("dense_ms", "Densa (vector)"),
    ("sparse_ms", "Léxica (BM25)"),
    ("rrf_fusion_ms", "Fusión RRF"),
    ("rerank_ms", "Reranking"),
)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def diagnostics_rows(diagnostics: Any) -> list[dict[str, Any]]:
    """Stage rows present in `diagnostics`; missing or non-numeric fields are skipped."""
    if not isinstance(diagnostics, dict):
        return []
    rows = []
    for field, label in STAGES:
        value = _as_float(diagnostics.get(field))
        if value is not None:
            rows.append({"Etapa": label, "ms": round(value, 2)})
    return rows


def last_diagnostics(executed_tools: Any) -> dict[str, Any] | None:
    """Diagnostics of the last tool record that carries them (persisted `executed_tools`)."""
    if not isinstance(executed_tools, list):
        return None
    for record in reversed(executed_tools):
        if isinstance(record, dict) and isinstance(record.get("diagnostics"), dict):
            return record["diagnostics"]
    return None


def _fmt_ms(value: Any) -> str:
    number = _as_float(value)
    return f"{number:.1f} ms" if number is not None else "—"


def render_diagnostics(diagnostics: Any, *, duration_ms: Any = None, tool_events: Any = None) -> None:
    """Renders the X-ray; tolerates `None`, partial dicts and malformed values."""
    rows = diagnostics_rows(diagnostics)
    diag = diagnostics if isinstance(diagnostics, dict) else {}
    tools = [t for t in tool_events or [] if isinstance(t, dict)]
    if not rows and duration_ms is None and not tools:
        st.caption("Sin diagnósticos de latencia para esta respuesta.")
        return

    with st.container(horizontal=True):
        st.metric("Búsqueda total", _fmt_ms(diag.get("total_ms")), border=True)
        if duration_ms is not None:
            st.metric("Turno completo", _fmt_ms(duration_ms), border=True)
        st.metric("Base de datos", str(diag.get("db_dialect") or "—"), border=True)
        candidates = f"{diag.get('raw_candidates_count', '—')} / {diag.get('deduped_blocks_count', '—')}"
        st.metric("Candidatos / bloques", candidates, border=True)

    if rows:
        st.bar_chart(
            pd.DataFrame(rows),
            x="Etapa",
            y="ms",
            horizontal=True,
            sort=False,
            x_label="Milisegundos",
            y_label="",
            alt="Latencia por etapa de la búsqueda RAG",
        )
    if tools:
        st.dataframe(
            pd.DataFrame(
                [
                    {"Herramienta": str(t.get("tool_name", "?")), "Duración": _fmt_ms(t.get("duration_ms"))}
                    for t in tools
                ]
            ),
            hide_index=True,
            alt="Duración de cada herramienta ejecutada",
        )
