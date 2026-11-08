"""Benchmark Lab: dense vs sparse vs hybrid retrieval quality (`POST /api/v1/demo/evaluate`)."""

from typing import Any

import api_client
import pandas as pd
import streamlit as st

RESULT_KEY = "benchmark_result"
ERROR_KEY = "benchmark_error"
QUALITY_METRICS = (("hit_rate_at_k", "Hit rate@k"), ("mrr", "MRR"), ("ndcg_at_k", "NDCG@k"))


def summary_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for mode, metrics in (result.get("modes") or {}).items():
        if not isinstance(metrics, dict):
            continue
        row: dict[str, Any] = {"Modo": mode}
        for field, label in QUALITY_METRICS:
            row[label] = metrics.get(field)
        row["Latencia media (ms)"] = metrics.get("avg_latency_ms")
        row["Semántico"] = "Sí" if metrics.get("semantic") else "No"
        rows.append(row)
    return rows


def _render_embedding_banner(result: dict[str, Any]) -> None:
    mode = result.get("embedding_mode", "desconocido")
    if mode == "gemini":
        st.success("Las métricas densas e híbridas usan embeddings reales de Gemini.", title="Embeddings: gemini")
    else:
        st.warning(
            "Los vectores son determinísticos y no semánticos: las métricas densas no reflejan calidad real.",
            title=f"Embeddings: {mode}",
        )
    for warning in result.get("warnings") or []:
        st.warning(str(warning), icon=":material/warning:")


def _render_charts(rows: list[dict[str, Any]]) -> None:
    frame = pd.DataFrame(rows)
    quality = frame.melt(
        id_vars="Modo", value_vars=[label for _, label in QUALITY_METRICS], var_name="Métrica", value_name="Valor"
    )
    col_quality, col_latency = st.columns(2)
    with col_quality:
        st.subheader("Calidad de recuperación")
        st.bar_chart(
            quality, x="Modo", y="Valor", color="Métrica", stack=False, alt="Hit rate, MRR y NDCG por modo"
        )
    with col_latency:
        st.subheader("Latencia media")
        st.bar_chart(frame, x="Modo", y="Latencia media (ms)", alt="Latencia media por modo de búsqueda")


def _render_per_query(result: dict[str, Any]) -> None:
    with st.expander("Desglose por consulta"):
        for mode, metrics in (result.get("modes") or {}).items():
            per_query = (metrics or {}).get("per_query") or []
            if not per_query:
                continue
            st.markdown(f"**{mode}**")
            st.dataframe(
                pd.DataFrame(per_query).drop(columns=["relevances"], errors="ignore"),
                hide_index=True,
                alt=f"Resultados por consulta en modo {mode}",
            )


def render_benchmark_lab() -> None:
    st.header("Benchmark Lab", anchor=False)
    st.caption("Compara las modalidades dense, sparse e hybrid sobre las consultas doradas del Golden Corpus.")

    with st.container(horizontal=True, vertical_alignment="bottom"):
        top_k = st.number_input("Ventana k", min_value=1, max_value=20, value=5, key="benchmark_top_k")
        if st.button("Ejecutar benchmark", icon=":material/science:", type="primary", key="run_benchmark"):
            with st.spinner("Evaluando las tres modalidades..."):
                res = api_client.evaluate_retrieval(int(top_k))
            st.session_state[RESULT_KEY] = res["data"] if res["success"] else None
            st.session_state[ERROR_KEY] = None if res["success"] else res
    error = st.session_state.get(ERROR_KEY)
    if error:
        hint = " Restaura el Golden Corpus desde el panel lateral." if error.get("status_code") == 409 else ""
        st.error(f"No se pudo ejecutar el benchmark: {str(error.get('error')).rstrip('.')}.{hint}")

    result = st.session_state.get(RESULT_KEY)
    if not isinstance(result, dict):
        st.info("Ejecuta el benchmark para ver las métricas.")
        return

    _render_embedding_banner(result)
    st.caption(f"k = {result.get('top_k', '—')} · {result.get('num_queries', '—')} consultas")
    rows = summary_rows(result)
    if not rows:
        st.info("La evaluación no devolvió modalidades.")
        return
    st.dataframe(pd.DataFrame(rows), hide_index=True, alt="Resumen de métricas por modo")
    _render_charts(rows)
    _render_per_query(result)
