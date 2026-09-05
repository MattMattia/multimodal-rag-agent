from datetime import datetime
import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_MOCK_WEBHOOK_URL = "https://httpbin.org/post"


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

    body = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "data": payload,
        "source": "Sistema RAG Multimodal & Agente IA Autónomo",
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
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

