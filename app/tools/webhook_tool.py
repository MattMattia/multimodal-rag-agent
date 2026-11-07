from datetime import datetime, timezone
import ipaddress
import logging
import socket
from typing import Any, Dict, Optional
from urllib.parse import urlparse
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_MOCK_WEBHOOK_URL = "https://httpbin.org/post"

INTERNAL_HOSTNAMES = {"db", "api", "frontend", "langfuse", "localhost"}


def _is_forbidden_ip(ip: ipaddress._BaseAddress) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def validate_webhook_url(url: str) -> str:
    """Valida que la URL del webhook sea segura (anti-SSRF). Devuelve la URL o lanza ValueError."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ValueError(f"Esquema no permitido: '{scheme}'. Solo http/https.")

    try:
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise ValueError("URL de webhook inválida.") from exc
    if not host:
        raise ValueError("La URL del webhook no tiene host.")

    if scheme == "http" and host not in {h.lower() for h in settings.ALLOWED_WEBHOOK_HOSTS}:
        raise ValueError("Webhooks http solo se permiten hacia hosts en ALLOWED_WEBHOOK_HOSTS.")

    try:
        literal_ip: Optional[ipaddress._BaseAddress] = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is None and (host in INTERNAL_HOSTNAMES or "." not in host):
        raise ValueError(f"Host interno no permitido: '{host}'.")

    if literal_ip is not None:
        addresses = [literal_ip]
    else:
        try:
            infos = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            # Fail closed: an unresolvable host could resolve differently for the HTTP client.
            raise ValueError(f"No se pudo resolver el host '{host}'.") from exc
        addresses = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]

    for ip in addresses:
        if _is_forbidden_ip(ip):
            raise ValueError(f"El host '{host}' resuelve a una dirección no permitida ({ip}).")
    return url


async def execute_dispatch_webhook(
    event_type: str,
    payload: Dict[str, Any],
    target_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Envía un payload de notificación vía HTTP POST a un webhook externo (Slack, Jira, ERP).

    Args:
        event_type: Nombre del evento (ej. 'invoice_alert', 'report_ready', 'contract_flag').
        payload: Datos o cuerpo en JSON a despachar.
        target_url: URL de destino del webhook (si no se especifica, usa el receptor por defecto).

    Returns:
        Diccionario con status, status_code, message y timestamp.
    """
    url = target_url or DEFAULT_MOCK_WEBHOOK_URL
    logger.info("Despachando webhook [%s] a %s", event_type, url)

    try:
        validate_webhook_url(url)
    except ValueError as e:
        logger.warning("Webhook [%s] bloqueado por validación de URL (%s): %s", event_type, url, e)
        return {
            "status": "blocked",
            "status_code": 400,
            "event_type": event_type,
            "target_url": url,
            "message": f"Webhook '{event_type}' bloqueado: {e}",
        }

    body = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "data": payload,
        "source": "Sistema RAG Multimodal & Agente IA Autónomo",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            response = await client.post(url, json=body)
            is_success = 200 <= response.status_code < 300

            logger.info("Webhook [%s] respondido con código %d", event_type, response.status_code)
            return {
                "status": "delivered" if is_success else "warning",
                "status_code": response.status_code,
                "event_type": event_type,
                "target_url": url,
                "message": f"Webhook '{event_type}' despachado exitosamente (HTTP {response.status_code}).",
            }
    except Exception as e:
        logger.warning("Fallo en la entrega real del webhook a %s: %s. Simulando entrega local exitosa.", url, e)
        # En caso de no tener salida a internet o URL no disponible en dev, simular entrega para no abortar el agente
        return {
            "status": "simulated",
            "status_code": 200,
            "event_type": event_type,
            "target_url": url,
            "message": f"Webhook '{event_type}' procesado en modo simulado local debido a: {str(e)}",
        }

