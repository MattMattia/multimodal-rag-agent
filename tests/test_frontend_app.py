"""Behavior tests for the Streamlit dashboard (`frontend/app.py`) using AppTest.

All HTTP traffic is intercepted at the `httpx` module level (request/get/post/stream),
so no test touches the network and the assertions hold regardless of how the app
wraps its HTTP calls.
"""

import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

# The session-scoped conftest fixture imports app.tools, which is circular unless app.main loads first.
import app.main  # noqa: F401, E402

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
APP_PATH = str(FRONTEND_DIR / "app.py")
APP_TIMEOUT = 15

DOC_ID = str(uuid.uuid4())
SESSION_ID = str(uuid.uuid4())
MESSAGE_ID = str(uuid.uuid4())

DEMO_STATUS = {
    "db_dialect": "sqlite",
    "demo_seeded": True,
    "total_documents": 3,
    "total_chunks": 42,
    "total_images": 3,
    "gemini_configured": False,
    "langfuse_enabled": False,
    "active_models": {},
    "embedding_mode": "mock",
}

MOCK_WARNING = "Embeddings simulados: las métricas densas no son semánticas."


def _mode(hit: float, mrr: float, ndcg: float, latency: float, semantic: bool = False) -> Dict[str, Any]:
    return {
        "semantic": semantic,
        "hit_rate_at_k": hit,
        "mrr": mrr,
        "ndcg_at_k": ndcg,
        "avg_latency_ms": latency,
        "per_query": [
            {
                "id": "q1",
                "query": "¿Cuál es el EBITDA?",
                "category": "table",
                "hit": True,
                "reciprocal_rank": 1.0,
                "ndcg": 1.0,
                "latency_ms": latency,
                "relevances": [1, 0],
                "top_documents": ["Reporte_Financiero_Q3_GlobalTech.pdf"],
            }
        ],
    }


EVALUATION = {
    "top_k": 5,
    "num_queries": 8,
    "embedding_mode": "mock",
    "warnings": [MOCK_WARNING],
    "modes": {
        "dense": _mode(0.75, 0.39, 0.45, 12.0),
        "sparse": _mode(0.875, 0.81, 0.83, 4.0, semantic=True),
        "hybrid": _mode(0.875, 0.73, 0.77, 20.0),
    },
}


class FakeStream:
    def __init__(self, lines: List[str], status_code: int = 200):
        self.status_code = status_code
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        yield from self._lines

    def read(self) -> bytes:
        return b""


def sse(event: Dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}"


class FakeApi:
    """Routes `(METHOD, path)` to canned responses and records every call."""

    def __init__(self):
        self.calls: List[Tuple[str, str, Dict[str, Any]]] = []
        self.stream_calls: List[Dict[str, Any]] = []
        self.stream_lines: List[str] = [sse({"type": "token", "content": "Hola"}), sse({"type": "metadata"})]
        self.routes: Dict[Tuple[str, str], Tuple[int, Any]] = {
            ("GET", "/health"): (200, {"status": "ok", "environment": "test"}),
            ("GET", "/api/v1/documents"): (
                200,
                [{"id": DOC_ID, "filename": "manual.pdf", "status": "completed", "file_type": "pdf"}],
            ),
            ("GET", "/api/v1/agent/sessions"): (200, []),
            ("GET", "/api/v1/demo/status"): (200, DEMO_STATUS),
        }

    def set(self, method: str, path: str, status: int, body: Any = None) -> None:
        self.routes[(method, path)] = (status, body)

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        path = urlsplit(str(url)).path
        method = method.upper()
        self.calls.append((method, path, kwargs))
        if (method, path) in self.routes:
            status, body = self.routes[(method, path)]
        elif method == "GET" and path.endswith("/history"):
            status, body = 200, {"session_id": path.split("/")[-2], "total_messages": 0, "messages": []}
        else:
            status, body = 404, {"detail": "Not Found"}
        if isinstance(body, bytes):
            return httpx.Response(status, content=body)
        if body is None:
            return httpx.Response(status)
        return httpx.Response(status, json=body)

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)

    def stream(self, method: str, url: str, **kwargs) -> FakeStream:
        self.stream_calls.append({"method": method, "path": urlsplit(str(url)).path, **kwargs})
        return FakeStream(self.stream_lines)

    def called(self, method: str, path: str) -> bool:
        return any(m == method and p == path for m, p, _ in self.calls)


@pytest.fixture
def fake_api(monkeypatch) -> FakeApi:
    monkeypatch.syspath_prepend(str(FRONTEND_DIR))
    api = FakeApi()
    for name in ("request", "get", "post", "delete", "stream"):
        monkeypatch.setattr(httpx, name, getattr(api, name))
    st.cache_data.clear()
    return api


def run_app(session_id: Optional[str] = None) -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=APP_TIMEOUT)
    if session_id:
        at.session_state["session_id"] = session_id
    return at.run()


def history(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"session_id": SESSION_ID, "total_messages": len(messages), "messages": messages}


def assistant_message(**extra) -> Dict[str, Any]:
    return {
        "id": MESSAGE_ID,
        "session_id": SESSION_ID,
        "role": "assistant",
        "content": "Respuesta del agente",
        "citations": [],
        "executed_tools": [],
        "created_at": "2026-11-08T10:00:00Z",
        **extra,
    }


def all_text(at: AppTest) -> str:
    parts = []
    for collection in (at.markdown, at.caption, at.warning, at.success, at.error, at.info):
        for element in collection:
            parts.append(str(element.value))
            title = getattr(element.proto, "title", "")
            if title:
                parts.append(str(title))
    return "\n".join(parts)


def _forget_frontend_modules() -> None:
    for name in [m for m in sys.modules if m == "api_client" or m == "views" or m.startswith("views.")]:
        sys.modules.pop(name, None)


# ------------------------------------------------------------------------------ hyperparameters
def test_chat_stream_payload_includes_sidebar_hyperparameters(fake_api):
    at = run_app(SESSION_ID)
    assert not at.exception

    at.get_by_key("hp_search_mode").set_value("sparse")
    at.slider(key="hp_top_k").set_value(7)
    at.toggle(key="hp_enable_rerank").set_value(False)
    at.toggle(key="hp_override").set_value(True)
    at.run()
    at.slider(key="hp_temperature").set_value(0.7)
    at.slider(key="hp_max_turns").set_value(3)
    at.selectbox(key="hp_filter_document_id").select(DOC_ID)
    at.chat_input[0].set_value("¿Qué dice el manual?").run()

    assert not at.exception
    assert len(fake_api.stream_calls) == 1
    call = fake_api.stream_calls[0]
    assert call["path"] == "/api/v1/agent/chat/stream"
    assert call["json"] == {
        "message": "¿Qué dice el manual?",
        "session_id": SESSION_ID,
        "search_mode": "sparse",
        "top_k": 7,
        "enable_rerank": False,
        "temperature": 0.7,
        "max_turns": 3,
        "filter_document_id": DOC_ID,
    }


def test_chat_payload_defaults_leave_temperature_and_turns_to_backend(fake_api):
    at = run_app(SESSION_ID)
    at.chat_input[0].set_value("hola").run()

    assert not at.exception
    payload = fake_api.stream_calls[0]["json"]
    assert payload["search_mode"] == "hybrid"
    assert payload["top_k"] == 5
    assert payload["enable_rerank"] is True
    assert payload["temperature"] is None
    assert payload["max_turns"] is None
    assert payload["filter_document_id"] is None


# ------------------------------------------------------------------------------ benchmark lab
def test_benchmark_lab_renders_embedding_mode_and_warnings(fake_api):
    fake_api.set("POST", "/api/v1/demo/evaluate", 200, EVALUATION)
    at = run_app()
    at.get_by_key("main_view").set_value("Benchmark Lab").run()
    at.button(key="run_benchmark").click().run()

    assert not at.exception
    evaluate_calls = [kw for m, p, kw in fake_api.calls if (m, p) == ("POST", "/api/v1/demo/evaluate")]
    assert evaluate_calls and evaluate_calls[0]["json"] == {"top_k": 5}
    warnings_text = "\n".join(f"{w.proto.title}\n{w.value}" for w in at.warning)
    assert "mock" in warnings_text
    assert MOCK_WARNING in warnings_text
    summary = at.dataframe[0].value
    assert list(summary["Modo"]) == ["dense", "sparse", "hybrid"]
    assert list(summary["MRR"]) == [0.39, 0.81, 0.73]


def test_benchmark_lab_explains_unseeded_corpus(fake_api):
    fake_api.set("POST", "/api/v1/demo/evaluate", 409, {"detail": "El Golden Corpus no está sembrado."})
    at = run_app()
    at.get_by_key("main_view").set_value("Benchmark Lab").run()
    at.button(key="run_benchmark").click().run()

    assert not at.exception
    assert any("Golden Corpus" in e.value for e in at.error)


# ------------------------------------------------------------------------------ golden corpus
def test_restore_corpus_button_calls_demo_seed(fake_api):
    fake_api.set(
        "POST",
        "/api/v1/demo/seed",
        200,
        {
            "documents_created": 3,
            "documents_skipped": 0,
            "files_created": 6,
            "chunks_created": 42,
            "images_created": 3,
            "duration_ms": 120.5,
            "demo_seeded": True,
        },
    )
    at = run_app()
    assert "sqlite" in all_text(at)
    assert not fake_api.called("POST", "/api/v1/demo/seed")

    at.button(key="restore_corpus").click().run()

    assert not at.exception
    assert fake_api.called("POST", "/api/v1/demo/seed")
    assert any("3 documentos nuevos" in s.value for s in at.success)


# ------------------------------------------------------------------------------ sessions
def test_session_delete_calls_delete_endpoint_and_starts_new_session(fake_api):
    fake_api.set(
        "GET",
        "/api/v1/agent/sessions",
        200,
        [
            {
                "session_id": SESSION_ID,
                "title": "Pregunta sobre el manual",
                "created_at": "2026-11-08T10:00:00Z",
                "updated_at": "2026-11-08T10:05:00Z",
                "message_count": 2,
            }
        ],
    )
    fake_api.set("DELETE", f"/api/v1/agent/sessions/{SESSION_ID}", 204)
    at = run_app(SESSION_ID)
    assert not at.exception

    at.button(key="delete_session").click().run()

    assert not at.exception
    assert fake_api.called("DELETE", f"/api/v1/agent/sessions/{SESSION_ID}")
    assert at.session_state["session_id"] != SESSION_ID


def test_feedback_thumbs_up_posts_rating(fake_api):
    fake_api.set("GET", f"/api/v1/agent/sessions/{SESSION_ID}/history", 200, history([assistant_message()]))
    fake_api.set(
        "POST", "/api/v1/agent/feedback", 200, {"status": "ok", "message_id": MESSAGE_ID, "rating": 1}
    )
    at = run_app(SESSION_ID)
    at.get_by_key(f"fb_{MESSAGE_ID}").set_value(1).run()

    assert not at.exception
    feedback = [kw for m, p, kw in fake_api.calls if (m, p) == ("POST", "/api/v1/agent/feedback")]
    assert feedback and feedback[0]["json"]["rating"] == 1
    assert feedback[0]["json"]["message_id"] == MESSAGE_ID
    assert feedback[0]["json"]["session_id"] == SESSION_ID


# ------------------------------------------------------------------------------ latency x-ray
@pytest.mark.parametrize(
    "diagnostics",
    [
        {"total_ms": 12.5},
        {"embedding_ms": "n/a", "dense_ms": None, "rerank_ms": 3},
        {},
    ],
)
def test_history_diagnostics_with_missing_fields_do_not_crash(fake_api, diagnostics):
    tools = [{"tool_name": "search_documents", "tool_input": {}, "tool_output": [], "diagnostics": diagnostics}]
    fake_api.set(
        "GET",
        f"/api/v1/agent/sessions/{SESSION_ID}/history",
        200,
        history([assistant_message(executed_tools=tools)]),
    )
    at = run_app(SESSION_ID)

    assert not at.exception
    assert "Respuesta del agente" in all_text(at)


def test_streamed_turn_renders_xray_without_diagnostics(fake_api):
    fake_api.stream_lines = [
        sse({"type": "tool_end", "tool_name": "search_documents"}),
        sse({"type": "token", "content": "Listo"}),
        sse({"type": "metadata", "citations": [], "executed_tools": [], "diagnostics": None, "duration_ms": 87.0}),
    ]
    at = run_app(SESSION_ID)
    at.chat_input[0].set_value("hola").run()

    assert not at.exception
    assert any("Rayos X" in e.label for e in at.expander)
    assert any(m.value == "87.0 ms" for m in at.metric)


def test_streamed_turn_renders_stage_metrics(fake_api):
    diagnostics = {
        "db_dialect": "sqlite",
        "embedding_ms": 1.5,
        "dense_ms": 4.0,
        "sparse_ms": 2.0,
        "rrf_fusion_ms": 0.5,
        "rerank_ms": 0.0,
        "total_ms": 8.0,
        "raw_candidates_count": 20,
        "deduped_blocks_count": 5,
    }
    fake_api.stream_lines = [
        sse({"type": "tool_end", "tool_name": "search_documents", "duration_ms": 9.0, "diagnostics": diagnostics}),
        sse({"type": "token", "content": "Listo"}),
        sse({"type": "metadata", "diagnostics": diagnostics, "duration_ms": 50.0}),
    ]
    at = run_app(SESSION_ID)
    at.chat_input[0].set_value("hola").run()

    assert not at.exception
    metric_values = {m.label: m.value for m in at.metric}
    assert metric_values["Búsqueda total"] == "8.0 ms"
    assert metric_values["Base de datos"] == "sqlite"
    assert metric_values["Candidatos / bloques"] == "20 / 5"


# ------------------------------------------------------------------------------ existing features
def test_report_download_fetches_pdf_with_api_headers(fake_api, monkeypatch):
    monkeypatch.setenv("API_KEY", "test-key")
    _forget_frontend_modules()  # re-read API_KEY from the environment
    tools = [
        {
            "tool_name": "generate_report_pdf",
            "tool_input": {},
            "tool_output": {"status": "success", "download_url": "/reports/r.pdf", "filename": "r.pdf"},
        }
    ]
    history_path = f"/api/v1/agent/sessions/{SESSION_ID}/history"
    fake_api.set("GET", history_path, 200, history([assistant_message(executed_tools=tools)]))
    fake_api.set("GET", "/reports/r.pdf", 200, b"%PDF-1.4 fake")
    try:
        at = run_app(SESSION_ID)
    finally:
        _forget_frontend_modules()

    assert not at.exception
    pdf_calls = [kw for m, p, kw in fake_api.calls if (m, p) == ("GET", "/reports/r.pdf")]
    assert pdf_calls and pdf_calls[0]["headers"] == {"X-API-Key": "test-key"}
    assert any("r.pdf" in b.label for b in at.get("download_button"))


def test_diagnostics_rows_skip_missing_and_invalid_fields(fake_api):
    from views.diagnostics import diagnostics_rows

    assert diagnostics_rows(None) == []
    assert diagnostics_rows("garbage") == []
    assert diagnostics_rows({"dense_ms": "x", "rerank_ms": 2, "sparse_ms": True}) == [{"Etapa": "Reranking", "ms": 2.0}]
