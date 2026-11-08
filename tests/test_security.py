"""Tests de endurecimiento de seguridad (SEC-01 .. SEC-04). Sin red real ni escrituras en uploads/."""

import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.services.rag_search import hybrid_search_service
from app.tools.pdf_generator import execute_generate_report_pdf
from app.tools.webhook_tool import execute_dispatch_webhook, validate_webhook_url


def _addrinfo(ip: str):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return [(family, socket.SOCK_STREAM, 6, "", (ip, 0))]


# ---------------------------------------------------------------------------
# SEC-01: SSRF
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://127.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "http://db:5432",
        "http://10.0.0.5",
        "http://[::1]",
        "ftp://example.com",
        "https://[::ffff:127.0.0.1]/",
        "https://langfuse/",
    ],
)
def test_validate_webhook_url_rejects_unsafe_urls(url):
    with patch("app.tools.webhook_tool.socket.getaddrinfo", side_effect=socket.gaierror("no dns")):
        with pytest.raises(ValueError):
            validate_webhook_url(url)


def test_validate_webhook_url_rejects_public_name_resolving_to_private_ip():
    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=_addrinfo("10.1.2.3")):
        with pytest.raises(ValueError):
            validate_webhook_url("https://evil.example.com/hook")


def test_validate_webhook_url_rejects_if_any_resolved_address_is_private():
    infos = _addrinfo("93.184.216.34") + _addrinfo("192.168.1.10")
    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=infos):
        with pytest.raises(ValueError):
            validate_webhook_url("https://mixed.example.com/")


def test_validate_webhook_url_fails_closed_when_dns_does_not_resolve():
    with patch("app.tools.webhook_tool.socket.getaddrinfo", side_effect=socket.gaierror("no dns")):
        with pytest.raises(ValueError):
            validate_webhook_url("https://unresolvable.example.com/hook")


def test_validate_webhook_url_rejects_non_global_cgnat_address():
    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=_addrinfo("100.64.0.1")):
        with pytest.raises(ValueError):
            validate_webhook_url("https://cgnat.example.com/hook")


def test_validate_webhook_url_accepts_public_https():
    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
        assert validate_webhook_url("https://example.com") == "https://example.com"


def test_validate_webhook_url_http_only_for_allowed_hosts(monkeypatch):
    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
        with pytest.raises(ValueError):
            validate_webhook_url("http://example.com/hook")
        monkeypatch.setattr(settings, "ALLOWED_WEBHOOK_HOSTS", ["example.com"])
        assert validate_webhook_url("http://example.com/hook") == "http://example.com/hook"


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/meta-data", "http://db:5432", "ftp://example.com"])
async def test_dispatch_webhook_rejected_url_makes_no_request(url):
    client_cls = MagicMock()
    with patch("app.tools.webhook_tool.httpx.AsyncClient", client_cls):
        result = await execute_dispatch_webhook("evt", {"a": 1}, target_url=url)
    client_cls.assert_not_called()
    assert result["status"] == "blocked"
    assert result["status_code"] == 400
    assert result["event_type"] == "evt"
    assert result["target_url"] == url


@pytest.mark.asyncio
async def test_dispatch_webhook_valid_url_disables_redirects():
    response = SimpleNamespace(status_code=200)
    client = MagicMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client_cls = MagicMock(return_value=client)
    with patch("app.tools.webhook_tool.socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")), patch(
        "app.tools.webhook_tool.httpx.AsyncClient", client_cls
    ):
        result = await execute_dispatch_webhook("evt", {}, target_url="https://example.com/hook")
    assert client_cls.call_args.kwargs.get("follow_redirects") is False
    client.post.assert_awaited_once()
    assert result["status"] == "delivered"
    assert result["status_code"] == 200


# ---------------------------------------------------------------------------
# SEC-03: PDF markup injection
# ---------------------------------------------------------------------------
def test_pdf_generator_escapes_markup(tmp_path, monkeypatch):
    monkeypatch.setattr("app.tools.pdf_generator.REPORTS_DIR", tmp_path)
    nasty = "a < b & c > d <script>"
    result = execute_generate_report_pdf(
        title=nasty,
        summary=f"{nasty}\nsecond <b>line",
        key_points=[nasty, "<para>"],
        sections=[{"heading": nasty, "content": f"{nasty}\n<i>x"}],
    )
    pdf = Path(result["file_path"])
    assert result["status"] == "success"
    assert pdf.parent == tmp_path
    assert pdf.read_bytes().startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# SEC-04: API key, generic 500, reports download
# ---------------------------------------------------------------------------
def _empty_db():
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = []
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture
def fake_db():
    async def _override():
        yield _empty_db()

    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def http():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_api_key_required_when_configured(fake_db, http, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    async with http as client:
        missing = await client.get("/api/v1/documents")
        wrong = await client.get("/api/v1/documents", headers={"X-API-Key": "nope"})
        ok = await client.get("/api/v1/documents", headers={"X-API-Key": "s3cret"})
        health = await client.get("/health")
    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert ok.status_code == 200
    assert ok.json() == []
    assert health.status_code == 200


@pytest.mark.asyncio
async def test_api_key_open_when_not_configured(fake_db, http, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    async with http as client:
        resp = await client.get("/api/v1/documents")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("debug, expect_leak", [(False, False), (True, True)])
async def test_500_detail_is_generic_unless_debug(fake_db, http, monkeypatch, debug, expect_leak):
    monkeypatch.setattr(settings, "DEBUG", debug)
    monkeypatch.setattr(settings, "API_KEY", "")
    monkeypatch.setattr(hybrid_search_service, "search", AsyncMock(side_effect=RuntimeError("secret-db-password")))
    async with http as client:
        resp = await client.post("/api/v1/search", json={"query": "hola"})
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert ("secret-db-password" in detail) is expect_leak
    assert detail


@pytest.mark.asyncio
async def test_uploads_static_mount_removed(http):
    async with http as client:
        resp = await client.get("/uploads/documents/anything.pdf")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_report_download_serves_only_reports_dir(http, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "s3cret")
    monkeypatch.setattr("app.main.REPORTS_DIR", tmp_path)
    (tmp_path / "r.pdf").write_bytes(b"%PDF-1.4 data")
    (tmp_path.parent / "outside.pdf").write_bytes(b"%PDF-secret")
    headers = {"X-API-Key": "s3cret"}
    async with http as client:
        no_key = await client.get("/uploads/reports/r.pdf")
        ok = await client.get("/uploads/reports/r.pdf", headers=headers)
        traversal = await client.get("/uploads/reports/..%2Foutside.pdf", headers=headers)
        missing = await client.get("/uploads/reports/none.pdf", headers=headers)
    assert no_key.status_code == 401
    assert ok.status_code == 200
    assert ok.content == b"%PDF-1.4 data"
    assert traversal.status_code in (400, 404)
    assert b"secret" not in traversal.content
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# SEC-04: delete removes extracted image files
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_delete_document_removes_image_files(http, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "API_KEY", "")
    doc_file = tmp_path / "doc.pdf"
    doc_file.write_bytes(b"%PDF-")
    img1, img2 = tmp_path / "a.png", tmp_path / "b.png"
    img1.write_bytes(b"x")
    img2.write_bytes(b"y")
    missing = tmp_path / "gone.png"
    doc = SimpleNamespace(
        file_path=str(doc_file),
        images=[SimpleNamespace(image_path=str(p)) for p in (img1, missing, img2)],
    )
    session = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = doc
    session.execute = AsyncMock(return_value=result)
    session.delete = AsyncMock()
    session.commit = AsyncMock()

    async def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    try:
        async with http as client:
            resp = await client.delete("/api/v1/documents/00000000-0000-0000-0000-000000000001")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 204
    assert not doc_file.exists()
    assert not img1.exists()
    assert not img2.exists()
    session.delete.assert_awaited_once_with(doc)
    session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# R2-BUG-06: webhook port allow-list and error message hiding
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("port", ["", ":80", ":443", ":8000", ":8080", ":8443"])
def test_validate_webhook_url_allows_standard_ports(port):
    url = f"https://8.8.8.8{port}/hook"
    assert validate_webhook_url(url) == url


@pytest.mark.parametrize("port", [22, 5432, 6379, 9000])
def test_validate_webhook_url_rejects_non_standard_ports(port):
    with pytest.raises(ValueError, match="puerto"):
        validate_webhook_url(f"https://8.8.8.8:{port}/hook")


def test_validate_webhook_url_allows_non_standard_port_for_allow_listed_host(monkeypatch):
    monkeypatch.setattr(settings, "ALLOWED_WEBHOOK_HOSTS", ["8.8.8.8"])
    url = "https://8.8.8.8:9000/hook"
    assert validate_webhook_url(url) == url


@pytest.mark.asyncio
@pytest.mark.parametrize("debug, expect_detail", [(False, False), (True, True)])
async def test_dispatch_webhook_hides_error_detail_unless_debug(monkeypatch, debug, expect_detail):
    monkeypatch.setattr(settings, "DEBUG", debug)
    client = MagicMock()
    client.post = AsyncMock(side_effect=RuntimeError("internal-host-10.1.2.3 refused"))
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    with patch("app.tools.webhook_tool.httpx.AsyncClient", MagicMock(return_value=client)):
        result = await execute_dispatch_webhook("evt", {}, target_url="https://8.8.8.8/hook")
    assert result["status"] == "simulated"
    assert result["status_code"] == 200
    assert ("internal-host-10.1.2.3" in result["message"]) is expect_detail
    assert "evt" in result["message"]
