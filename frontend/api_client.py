"""HTTP client for the FastAPI backend used by the Streamlit dashboard.

Every function returns plain data and never raises on network/HTTP errors, so the
views can render a friendly message instead of a traceback.
"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterator, List, Optional

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "")
API_HEADERS = {"X-API-Key": API_KEY} if API_KEY else {}

API_PREFIX = "/api/v1"
SHORT_TIMEOUT = 5.0
UPLOAD_TIMEOUT = 60.0
STREAM_TIMEOUT = 120.0
EVALUATE_TIMEOUT = 180.0
FILE_TIMEOUT = 15.0
ERROR_PREVIEW_CHARS = 500


@dataclass(frozen=True)
class ChatOptions:
    """Per-request agent hyperparameters (fields of `AgentChatRequest`). `None` = backend default."""

    search_mode: str = "hybrid"
    top_k: int = 5
    enable_rerank: bool = True
    temperature: Optional[float] = None
    max_turns: Optional[int] = None
    filter_document_id: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        return asdict(self)


def build_chat_payload(message: str, session_id: str, options: ChatOptions) -> Dict[str, Any]:
    """Request body for `/agent/chat` and `/agent/chat/stream`."""
    return {"message": message, "session_id": session_id, **options.to_payload()}


def _result(success: bool, data: Any = None, error: Optional[str] = None, status_code: Optional[int] = None):
    return {"success": success, "data": data, "error": error, "status_code": status_code}


def _error_text(resp: httpx.Response) -> str:
    try:
        detail = resp.json().get("detail")
        if detail:
            return str(detail)
    except (ValueError, AttributeError):
        pass
    return resp.text[:ERROR_PREVIEW_CHARS] or f"HTTP {resp.status_code}"


def _call(method: str, path: str, *, timeout: float = SHORT_TIMEOUT, raw: bool = False, **kwargs) -> Dict[str, Any]:
    """Performs one request against the API; `raw=True` returns the body bytes instead of JSON."""
    try:
        resp = httpx.request(method, f"{API_URL}{path}", headers=API_HEADERS, timeout=timeout, **kwargs)
    except httpx.HTTPError as exc:
        return _result(False, error=f"Error de conexión: {exc}")
    if not resp.is_success:
        return _result(False, error=_error_text(resp), status_code=resp.status_code)
    if raw:
        return _result(True, data=resp.content, status_code=resp.status_code)
    if resp.status_code == 204 or not resp.content:
        return _result(True, data=None, status_code=resp.status_code)
    try:
        return _result(True, data=resp.json(), status_code=resp.status_code)
    except ValueError:
        return _result(False, error="Respuesta no JSON del servidor", status_code=resp.status_code)


# ---------------------------------------------------------------------------- health / documents
def check_api_health() -> Dict[str, Any]:
    res = _call("GET", "/health", timeout=3.0)
    return res["data"] if res["success"] and isinstance(res["data"], dict) else {"status": "error"}


def fetch_documents() -> List[Dict[str, Any]]:
    res = _call("GET", f"{API_PREFIX}/documents")
    return res["data"] if res["success"] and isinstance(res["data"], list) else []


def upload_document_api(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    return _call(
        "POST", f"{API_PREFIX}/documents/upload", timeout=UPLOAD_TIMEOUT, files={"file": (filename, file_bytes)}
    )


@st.cache_data(ttl=300, show_spinner=False)
def fetch_file_bytes(relative_url: str) -> Optional[bytes]:
    """Downloads a static file served by the API (authenticated with `API_HEADERS`)."""
    res = _call("GET", "/" + relative_url.lstrip("/"), timeout=FILE_TIMEOUT, raw=True)
    return res["data"] if res["success"] else None


# ---------------------------------------------------------------------------- sessions
def list_sessions() -> Optional[List[Dict[str, Any]]]:
    """`SessionSummary` list ordered by `updated_at DESC`; `None` when the endpoint is unavailable."""
    res = _call("GET", f"{API_PREFIX}/agent/sessions")
    return res["data"] if res["success"] and isinstance(res["data"], list) else None


def fetch_session_history(session_id: str) -> List[Dict[str, Any]]:
    res = _call("GET", f"{API_PREFIX}/agent/sessions/{session_id}/history")
    if res["success"] and isinstance(res["data"], dict):
        return res["data"].get("messages", [])
    return []


def delete_session(session_id: str) -> Dict[str, Any]:
    return _call("DELETE", f"{API_PREFIX}/agent/sessions/{session_id}")


def export_session(session_id: str, export_format: str) -> bytes:
    """Markdown or PDF export; returns an empty payload on failure (used as a lazy download callable)."""
    res = _call(
        "GET",
        f"{API_PREFIX}/agent/sessions/{session_id}/export",
        timeout=UPLOAD_TIMEOUT,
        raw=True,
        params={"format": export_format},
    )
    return res["data"] if res["success"] else b""


def submit_feedback(session_id: str, message_id: str, rating: int, comment: Optional[str] = None) -> Dict[str, Any]:
    payload = {"session_id": session_id, "message_id": message_id, "rating": rating, "comment": comment}
    return _call("POST", f"{API_PREFIX}/agent/feedback", json=payload)


# ---------------------------------------------------------------------------- search / agent
def search_knowledge_base(query: str, options: ChatOptions) -> Dict[str, Any]:
    payload = {
        "query": query,
        "top_k": options.top_k,
        "mode": options.search_mode,
        "rerank": options.enable_rerank,
        "filter_document_id": options.filter_document_id,
    }
    return _call("POST", f"{API_PREFIX}/search", timeout=UPLOAD_TIMEOUT, json=payload)


def stream_chat_response(
    message: str, session_id: str, options: ChatOptions, metadata_container: Dict[str, Any]
) -> Iterator[str]:
    """Consumes the SSE stream, yielding tokens; `tool_end` and `metadata` events land in `metadata_container`."""
    payload = build_chat_payload(message, session_id, options)
    tool_events: List[Dict[str, Any]] = metadata_container.setdefault("tool_events", [])
    try:
        with httpx.stream(
            "POST",
            f"{API_URL}{API_PREFIX}/agent/chat/stream",
            json=payload,
            headers=API_HEADERS,
            timeout=STREAM_TIMEOUT,
        ) as response:
            if response.status_code != 200:
                err_text = response.read().decode("utf-8", errors="ignore")[:ERROR_PREVIEW_CHARS]
                metadata_container["error"] = f"HTTP {response.status_code}: {err_text}"
                yield f"⚠️ Error del servidor ({response.status_code}): {err_text}"
                return
            for line in response.iter_lines():
                event = _parse_sse_line(line)
                if event is None:
                    continue
                ev_type = event.get("type")
                if ev_type == "token":
                    yield str(event.get("content", ""))
                elif ev_type == "tool_end":
                    tool_events.append(event)
                elif ev_type == "metadata":
                    metadata_container.update(event)
    except httpx.HTTPError as exc:
        metadata_container["error"] = str(exc)
        yield f"\n\n⚠️ Error de conexión durante la transmisión en streaming: {exc}"


def _parse_sse_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line.startswith("data: "):
        return None
    data_str = line[6:].strip()
    if not data_str:
        return None
    try:
        event = json.loads(data_str)
    except json.JSONDecodeError:
        return None  # malformed SSE payload: skip it
    return event if isinstance(event, dict) else None


# ---------------------------------------------------------------------------- demo / evaluation
def demo_status() -> Dict[str, Any]:
    return _call("GET", f"{API_PREFIX}/demo/status")


def seed_demo() -> Dict[str, Any]:
    return _call("POST", f"{API_PREFIX}/demo/seed", timeout=UPLOAD_TIMEOUT)


def evaluate_retrieval(top_k: int) -> Dict[str, Any]:
    return _call("POST", f"{API_PREFIX}/demo/evaluate", timeout=EVALUATE_TIMEOUT, json={"top_k": top_k})
