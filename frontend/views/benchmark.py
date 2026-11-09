"""Benchmark Lab: dense vs sparse vs hybrid retrieval quality (`POST /api/v1/demo/evaluate`)."""

from typing import Any

import api_client
import pandas as pd
import streamlit as st
from i18n import current_lang, t

RESULT_KEY = "benchmark_result"
ERROR_KEY = "benchmark_error"
QUALITY_METRICS = (("hit_rate_at_k", "Hit rate@k"), ("mrr", "MRR"), ("ndcg_at_k", "NDCG@k"))


def summary_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for mode, metrics in (result.get("modes") or {}).items():
        if not isinstance(metrics, dict):
            continue
        row: dict[str, Any] = {t("bench_col_mode"): mode}
        for field, label in QUALITY_METRICS:
            row[label] = metrics.get(field)
        row[t("bench_col_latency")] = metrics.get("avg_latency_ms")
        row[t("bench_col_semantic")] = t("yes") if metrics.get("semantic") else t("no")
        rows.append(row)
    return rows


def _render_embedding_banner(result: dict[str, Any]) -> None:
    mode = result.get("embedding_mode", t("emb_unknown"))
    if mode == "gemini":
        st.success(t("emb_gemini"), title=t("emb_title", mode="gemini"))
    else:
        st.warning(t("emb_mock"), title=t("emb_title", mode=mode))
    for warning in result.get("warnings") or []:
        st.warning(str(warning), icon=":material/warning:")


def _render_charts(rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(rows)
    mode_col, metric_col, value_col = t("bench_col_mode"), t("bench_col_metric"), t("bench_col_value")
    quality = frame.melt(
        id_vars=mode_col, value_vars=[label for _, label in QUALITY_METRICS], var_name=metric_col, value_name=value_col
    )
    col_quality, col_latency = st.columns(2)
    with col_quality:
        st.subheader(t("bench_quality"))
        st.bar_chart(quality, x=mode_col, y=value_col, color=metric_col, stack=False, alt=t("bench_quality_alt"))
    with col_latency:
        st.subheader(t("bench_latency"))
        st.bar_chart(frame, x=mode_col, y=t("bench_col_latency"), alt=t("bench_latency_alt"))


def _render_per_query(result: dict[str, Any]) -> None:
    with st.expander(t("bench_per_query")):
        for mode, metrics in (result.get("modes") or {}).items():
            per_query = (metrics or {}).get("per_query") or []
            if not per_query:
                continue
            st.markdown(f"**{mode}**")
            st.dataframe(
                pd.DataFrame(per_query).drop(columns=["relevances"], errors="ignore"),
                hide_index=True,
                alt=t("bench_per_query_alt", mode=mode),
            )


def render_benchmark_lab() -> None:
    st.header(t("bench_header"), anchor=False)
    st.caption(t("bench_caption"))

    with st.container(horizontal=True, vertical_alignment="bottom"):
        top_k = st.number_input(t("bench_k"), min_value=1, max_value=20, value=5, key="benchmark_top_k")
        if st.button(t("bench_run"), icon=":material/science:", type="primary", key="run_benchmark"):
            with st.spinner(t("bench_spinner")):
                res = api_client.evaluate_retrieval(int(top_k), current_lang())
            st.session_state[RESULT_KEY] = res["data"] if res["success"] else None
            st.session_state[ERROR_KEY] = None if res["success"] else res
    error = st.session_state.get(ERROR_KEY)
    if error:
        hint = t("bench_hint_unseeded") if error.get("status_code") == 409 else ""
        st.error(t("bench_error", error=str(error.get("error")).rstrip("."), hint=hint))

    result = st.session_state.get(RESULT_KEY)
    if not isinstance(result, dict):
        st.info(t("bench_empty"))
        return

    _render_embedding_banner(result)
    st.caption(t("bench_meta", k=result.get("top_k", "—"), queries=result.get("num_queries", "—")))
    rows = summary_rows(result)
    if not rows:
        st.info(t("bench_no_modes"))
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, alt=t("bench_summary_alt"))
    _render_charts(rows)
    _render_per_query(result)
