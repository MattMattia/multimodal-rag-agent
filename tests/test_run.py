"""Tests for the universal launcher (run.py)."""

import json

import pytest

import run


def test_parse_args_defaults():
    args = run.parse_args([])
    assert args.export_openapi is False
    assert args.host == "127.0.0.1"
    assert args.port == 8000


def test_parse_args_flags():
    args = run.parse_args(["--export-openapi", "--host", "0.0.0.0", "--port", "9000"])  # noqa: S104
    assert args.export_openapi is True
    assert args.host == "0.0.0.0"  # noqa: S104
    assert args.port == 9000


def test_parse_args_rejects_unknown_flag():
    with pytest.raises(SystemExit):
        run.parse_args(["--nope"])


def test_export_openapi_writes_valid_31_schema(tmp_path):
    target = tmp_path / "docs" / "openapi.json"
    written = run.export_openapi(target)
    assert written == target
    schema = json.loads(target.read_text(encoding="utf-8"))
    assert schema["openapi"].startswith("3.1")
    assert "/api/v1/demo/evaluate" in schema["paths"]


def test_main_export_does_not_start_server(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(run, "serve", lambda *a, **k: called.append(1))
    monkeypatch.setattr(run, "OPENAPI_PATH", tmp_path / "openapi.json")
    assert run.main(["--export-openapi"]) == 0
    assert (tmp_path / "openapi.json").exists()
    assert called == []
