from unittest.mock import MagicMock
import uuid

import pytest

from app.core.telemetry import (
    DummySpan,
    DummyTrace,
    TelemetryService,
)


@pytest.fixture(autouse=True)
def _isolated_active_parent():
    """Start every telemetry test with no active parent and restore it afterwards."""
    from app.core.telemetry import _active_telemetry_parent

    token = _active_telemetry_parent.set(None)
    yield
    _active_telemetry_parent.reset(token)


def test_dummy_span_and_trace_resilience():
    """Verifica que DummySpan y DummyTrace respondan a toda la interfaz sin lanzar excepciones."""
    trace = DummyTrace(name="test_trace", id="session-123")
    assert trace.name == "test_trace"
    assert trace.id == "session-123"
    assert trace.trace_id == "dummy_trace_id"

    # Verificación de métodos no-op
    trace.update(output={"status": "ok"})
    trace.end()
    trace.event(name="sample_event")

    # Creación de child span
    child_span = trace.span("child_tool")
    assert isinstance(child_span, DummySpan)
    child_span.update(output="result")
    child_span.end()

    # Creación de child observation (Langfuse v4)
    obs = trace.start_observation(name="v4_tool", as_type="tool")
    assert isinstance(obs, DummySpan)

    # Generation no-op
    gen = trace.generation(name="llm_gen", model="gemini-1.5-pro")
    assert isinstance(gen, DummySpan)

    # Context manager protocol
    with trace as t:
        assert t is trace

    with child_span as s:
        assert s is child_span


def test_telemetry_service_disabled_mode():
    """Verifica el comportamiento seguro de TelemetryService cuando está deshabilitado."""
    service = TelemetryService()
    service._enabled = False
    service._client = None

    assert not service.is_enabled

    # start_trace debe retornar DummyTrace
    trace = service.start_trace(
        name="test_turn",
        session_id=str(uuid.uuid4()),
        input={"prompt": "Hola"},
    )
    assert isinstance(trace, DummyTrace)

    # span context manager debe devolver DummySpan
    with service.span(parent=trace, name="tool:test") as span:
        assert isinstance(span, DummySpan)
        span.update(output="done")

    # record_generation debe devolver DummySpan
    gen = service.record_generation(
        parent=trace,
        name="test_gen",
        model="gemini-1.5-pro",
        input="hola",
        output="mundo",
    )
    assert isinstance(gen, DummySpan)

    # flush no debe lanzar error
    service.flush()


def test_telemetry_service_v2_client_integration():
    """Verifica la instrumentación con cliente mockeado de Langfuse v2 (trace, span, generation)."""
    service = TelemetryService()
    service._enabled = True

    mock_client = MagicMock()
    mock_trace = MagicMock()
    mock_child = MagicMock()

    mock_client.trace.return_value = mock_trace
    mock_trace.span.return_value = mock_child

    service._client = mock_client
    assert service.is_enabled

    # 1. Iniciar traza raíz
    trace = service.start_trace(
        name="agent_turn",
        session_id="test-session-42",
        input={"query": "test query"},
    )
    mock_client.trace.assert_called_once_with(
        name="agent_turn",
        session_id="test-session-42",
        user_id=None,
        input={"query": "test query"},
        metadata={},
        tags=[],
    )
    assert trace == mock_trace

    # 2. Instrumentar span hijo con context manager
    with service.span(parent=trace, name="tool:search", span_type="tool", input={"query": "test"}) as s:
        assert s == mock_child
        mock_trace.span.assert_called_with(
            name="tool:search",
            input={"query": "test"},
            metadata={},
        )
    mock_child.end.assert_called_once()

    # 3. Registrar generación
    mock_gen = MagicMock()
    mock_trace.generation.return_value = mock_gen
    gen = service.record_generation(
        parent=trace,
        name="gemini_turn_0",
        model="gemini-1.5-pro",
        input="pregunta",
        output="respuesta",
        usage={"input": 10, "output": 20, "total": 30},
    )
    mock_trace.generation.assert_called_with(
        name="gemini_turn_0",
        model="gemini-1.5-pro",
        input="pregunta",
        output="respuesta",
        usage={"input": 10, "output": 20, "total": 30},
        metadata={},
    )

    # 4. Flush
    service.flush()
    mock_client.flush.assert_called_once()


def test_telemetry_service_v4_client_integration():
    """Verifica la instrumentación con cliente mockeado de Langfuse v4 (start_observation sin trace)."""
    service = TelemetryService()
    service._enabled = True

    mock_client = MagicMock()
    del mock_client.trace  # Asegurar que no tenga trace

    mock_obs = MagicMock()
    del mock_obs.span
    del mock_obs.generation

    mock_child = MagicMock()

    mock_client.start_observation.return_value = mock_obs
    mock_obs.start_observation.return_value = mock_child

    service._client = mock_client
    assert service.is_enabled

    # 1. Iniciar traza raíz
    trace = service.start_trace(
        name="agent_turn",
        session_id="test-session-42",
        input={"query": "test query"},
    )
    mock_client.start_observation.assert_called_once_with(
        name="agent_turn",
        as_type="agent",
        input={"query": "test query"},
        metadata={},
    )
    assert trace == mock_obs

    # 2. Instrumentar span hijo con context manager
    with service.span(parent=trace, name="tool:search", span_type="tool", input={"query": "test"}) as s:
        assert s == mock_child
        mock_obs.start_observation.assert_called_with(
            name="tool:search",
            as_type="tool",
            input={"query": "test"},
            metadata={},
        )
    mock_child.end.assert_called_once()

    # 3. Registrar generación
    mock_gen = MagicMock()
    mock_obs.start_observation.return_value = mock_gen
    gen = service.record_generation(
        parent=trace,
        name="gemini_turn_0",
        model="gemini-1.5-pro",
        input="pregunta",
        output="respuesta",
        usage={"input": 10, "output": 20, "total": 30},
    )
    mock_obs.start_observation.assert_called_with(
        name="gemini_turn_0",
        as_type="generation",
        model="gemini-1.5-pro",
        input="pregunta",
        output="respuesta",
        usage_details={"input": 10, "output": 20, "total": 30},
        metadata={},
    )
    mock_gen.end.assert_called_once()

    # 4. Flush
    service.flush()
    mock_client.flush.assert_called_once()


def test_telemetry_service_exception_resilience():
    """Verifica que cualquier fallo interno en el SDK de Langfuse sea capturado silenciosamente."""
    service = TelemetryService()
    service._enabled = True

    failing_client = MagicMock()
    failing_client.trace.side_effect = RuntimeError("Langfuse API unreachable")
    failing_client.start_observation.side_effect = RuntimeError("Langfuse API unreachable")
    failing_client.flush.side_effect = RuntimeError("Network error")

    service._client = failing_client

    # No debe propagar la excepción, debe retornar DummyTrace
    trace = service.start_trace(name="failing_trace")
    assert isinstance(trace, DummyTrace)

    # Span context manager debe capturar el error y producir DummySpan
    with service.span(parent=trace, name="failing_span") as span:
        assert isinstance(span, DummySpan)

    # Flush fallido debe manejarse de forma silenciosa
    service.flush()


def test_nested_span_resolves_active_parent_from_contextvar():
    """span(parent=None) inside an active span must nest under it and restore the var on exit."""
    from app.core.telemetry import _active_telemetry_parent

    service = TelemetryService()
    service._enabled = True
    service._client = MagicMock()

    class FakeParent:
        def __init__(self, label):
            self.label = label
            self.children = []

        def span(self, name, **kwargs):
            child = FakeParent(name)
            self.children.append(child)
            return child

        def end(self, *a, **k):
            pass

    root = FakeParent("root")
    token = _active_telemetry_parent.set(root)
    try:
        with service.span(parent=None, name="outer") as outer:
            assert _active_telemetry_parent.get() is outer
            with service.span(parent=None, name="inner") as inner:
                assert _active_telemetry_parent.get() is inner
            assert _active_telemetry_parent.get() is outer
        assert _active_telemetry_parent.get() is root
    finally:
        _active_telemetry_parent.reset(token)

    assert [c.label for c in root.children] == ["outer"]
    assert [c.label for c in root.children[0].children] == ["inner"]
    assert _active_telemetry_parent.get() is None


def test_span_sets_active_parent_and_works_when_disabled():
    from app.core.telemetry import _active_telemetry_parent

    service = TelemetryService()
    service._enabled = False
    with service.span(parent=None, name="child") as child:
        assert isinstance(child, DummySpan)
        assert _active_telemetry_parent.get() is child
    assert _active_telemetry_parent.get() is None


def test_record_generation_falls_back_to_active_parent():
    from app.core.telemetry import _active_telemetry_parent

    service = TelemetryService()
    service._enabled = True
    service._client = MagicMock()
    parent = MagicMock()
    token = _active_telemetry_parent.set(parent)
    try:
        service.record_generation(parent=None, name="g", model="m", input="i", output="o")
    finally:
        _active_telemetry_parent.reset(token)
    parent.generation.assert_called_once()

