"""Latency X-ray: renders `SearchDiagnostics` as a per-stage bar chart."""

from typing import Any

import pandas as pd
import streamlit as st
from i18n import t

# (SearchDiagnostics field, i18n label key) in pipeline order.
STAGES = (
    ("embedding_ms", "stage_embedding"),
    ("dense_ms", "stage_dense"),
    ("sparse_ms", "stage_sparse"),
    ("rrf_fusion_ms", "stage_rrf"),
    ("rerank_ms", "stage_rerank"),
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
    stage_col = t("diag_col_stage")
    for field, label_key in STAGES:
        value = _as_float(diagnostics.get(field))
        if value is not None:
            rows.append({stage_col: t(label_key), "ms": round(value, 2)})
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
    tools = [tool for tool in tool_events or [] if isinstance(tool, dict)]
    if not rows and duration_ms is None and not tools:
        st.caption(t("diag_none"))
        return

    with st.container(horizontal=True):
        st.metric(t("diag_search_total"), _fmt_ms(diag.get("total_ms")), border=True)
        if duration_ms is not None:
            st.metric(t("diag_turn_total"), _fmt_ms(duration_ms), border=True)
        st.metric(t("diag_database"), str(diag.get("db_dialect") or "—"), border=True)
        candidates = f"{diag.get('raw_candidates_count', '—')} / {diag.get('deduped_blocks_count', '—')}"
        st.metric(t("diag_candidates"), candidates, border=True)

    if rows:
        st.bar_chart(
            pd.DataFrame(rows),
            x=t("diag_col_stage"),
            y="ms",
            horizontal=True,
            sort=False,
            x_label=t("diag_x_label"),
            y_label="",
            alt=t("diag_alt"),
        )
    if tools:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        t("diag_col_tool"): str(tool.get("tool_name", "?")),
                        t("diag_col_duration"): _fmt_ms(tool.get("duration_ms")),
                    }
                    for tool in tools
                ]
            ),
            hide_index=True,
            alt=t("diag_tools_alt"),
        )
