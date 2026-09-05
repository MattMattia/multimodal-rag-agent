import asyncio
import logging
from pathlib import Path
from typing import Optional
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

# Intentar usar el SDK moderno oficial google-genai
_USE_MODERN_SDK = False
try:
    from google import genai
    _USE_MODERN_SDK = True
except ImportError:
    try:
        import google.generativeai as legacy_genai
        _USE_MODERN_SDK = False
    except ImportError:
        pass


PROMPT_TECHNICAL_IMAGE = """Eres un asistente de IA experto en análisis de documentos y visión por computadora.
Analiza detalladamente la imagen proporcionada (gráfico, diagrama, flujo o ilustración técnica extraída de un documento).
Proporciona una descripción sintética y precisa en español que contenga:
1. Tipo de imagen y temática central.
2. Elementos clave, etiquetas, ejes, valores numéricos o métricas visibles.
3. Conclusiones, correlaciones o significado técnico directo del contenido visual.
Sé riguroso, estructurado y exhaustivo con los datos que se observan."""

PROMPT_INVOICE_RECEIPT = """Eres un sistema OCR multimodal de alta precisión para documentos comerciales y financieros.
Analiza esta imagen (factura, recibo, comprobante o presupuesto).
Extrae y detalla de manera estructurada en español:
1. Emisor y Receptor (nombres, identificaciones fiscales o direcciones si aparecen).
2. Número de comprobante/factura y fechas relevantes (emisión, vencimiento).
3. Detalle de productos/servicios: descripción, cantidad, precio unitario e importe.
4. Resumen financiero: subtotal, descuentos, impuestos/IVA y TOTAL final.
5. Cualquier nota, condición o método de pago indicado."""


class VisionService:
    """Servicio para análisis multimodal y generación de descripciones con modelos de visión de Gemini."""

    def __init__(self):
        self.api_key = settings.GOOGLE_API_KEY
        self.model_name = settings.GEMINI_VISION_MODEL
        self._initialized = False
        self._client = None
        self._legacy_model = None

    def _ensure_client(self):
        """Inicializa o actualiza el cliente de Gemini si la API key se configuró dinámicamente."""
        import os
        current_key = os.getenv("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY
        if current_key and current_key != "tu_google_api_key_aqui" and (not self._initialized or self.api_key != current_key):
            self.api_key = current_key
            try:
                if _USE_MODERN_SDK:
                    self._client = genai.Client(api_key=self.api_key)
                    self._initialized = True
                    logger.info("VisionService configurado con SDK oficial google-genai y modelo %s", self.model_name)
                else:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=self.api_key)
                    self._legacy_model = legacy_genai.GenerativeModel(self.model_name)
                    self._initialized = True
                    logger.info("VisionService configurado con legacy genai y modelo %s", self.model_name)
            except Exception as e:
                logger.error("Error al configurar cliente de Gemini en VisionService: %s", e)

    async def describe_image(
        self, image_path: str, prompt_type: str = "technical"
    ) -> str:
        """Genera una descripción detallada de una imagen usando Gemini.

        Args:
            image_path: Ruta absoluta o relativa al archivo de imagen en disco.
            prompt_type: 'technical' para gráficos/diagramas o 'receipt' para facturas/recibos.

        Returns:
            str con la descripción generada o mensaje de contingencia.
        """
        path = Path(image_path)
        if not path.exists():
            return f"Error: Archivo de imagen no encontrado en {image_path}"

        self._ensure_client()

        if not self._initialized:
            filename = path.name
            return (
                f"[Descripción de imagen {filename}: GOOGLE_API_KEY no configurada en .env. "
                f"La imagen está almacenada en {image_path}]"
            )

        prompt = PROMPT_INVOICE_RECEIPT if prompt_type == "receipt" else PROMPT_TECHNICAL_IMAGE

        try:
            img = Image.open(path)

            if _USE_MODERN_SDK and self._client:
                # Probar modelo configurado y luego variantes modernas si Google deprecó versiones
                candidate_models = [self.model_name, "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest"]
                last_err = None
                for m_name in candidate_models:
                    if not m_name:
                        continue
                    try:
                        response = await self._client.aio.models.generate_content(
                            model=m_name,
                            contents=[img, prompt],
                        )
                        if response and response.text:
                            return response.text.strip()
                    except Exception as err:
                        last_err = err
                        err_str = str(err)
                        if "404" in err_str or "NOT_FOUND" in err_str or "429" in err_str:
                            logger.warning("Modelo %s no disponible en VisionService (%s). Probando siguiente...", m_name, err)
                            continue
                        raise err
                if last_err:
                    raise last_err
                return "Sin texto generado."
            else:
                loop = asyncio.get_event_loop()
                def _call_legacy():
                    res = self._legacy_model.generate_content([prompt, img])
                    return res.text if res and res.text else "Sin texto generado."

                description = await loop.run_in_executor(None, _call_legacy)
                return description.strip()

        except Exception as e:
            logger.error("Error al generar descripción con Gemini para %s: %s", image_path, e)
            return f"[Error al procesar imagen con Gemini: {str(e)}. Archivo: {path.name}]"


vision_service = VisionService()

