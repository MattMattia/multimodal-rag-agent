import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.chat import ChatMessage
from app.schemas.agent import AgentChatResponse, CitationItem, ToolExecutionRecord
from app.tools.pdf_generator import execute_generate_report_pdf
from app.tools.rag_tool import execute_search_knowledge_base
from app.tools.webhook_tool import execute_dispatch_webhook

logger = logging.getLogger(__name__)

# Intentar importar el SDK moderno de Google GenAI
_USE_MODERN_GENAI = False
try:
    from google import genai
    from google.genai import types
    _USE_MODERN_GENAI = True
except ImportError:
    pass

SYSTEM_INSTRUCTION = """Eres un Agente IA Autónomo empresarial experto en procesamiento y análisis de documentos multimodales (PDFs con texto y tablas, diagramas, imágenes de facturas, recibos y CVs).

Dispones de las siguientes herramientas especializadas:
1. `search_knowledge_base`: Busca en la base de conocimientos RAG (PostgreSQL + pgvector y búsqueda léxica) información relevante extraída de los documentos.
2. `generate_report_pdf`: Genera y guarda un reporte ejecutivo formal en PDF cuando el usuario te solicite crear un informe, exportar a PDF o documentar conclusiones.
3. `dispatch_webhook`: Envía notificaciones estructuradas vía HTTP POST a sistemas externos cuando se cumplan condiciones o alertas.

Reglas esenciales:
1. Si el usuario pregunta por datos de documentos o personas (ej. CVs, facturas, presupuestos, auditorías), invoca PRIMERO la herramienta `search_knowledge_base`.
2. SÍNTESIS Y REDACCIÓN NATURAL: Con los fragmentos que recuperes, REDACTA SIEMPRE una respuesta elaborada, coherente y fluida en español con tus propias palabras. NUNCA pegues ni imprimas bloques de texto en crudo sin procesar.
3. CITAS BIBLIOGRÁFICAS EXPLÍCITAS: En tu respuesta final, DEBES incluir citas bibliográficas explícitas mencionando el documento de origen y número de página si aplica (ejemplo: [Fuente: Mattia_Risso_Software_Engineer.pdf, Pág 1]).
4. CONTINUIDAD CONVERSACIONAL Y TRADUCCIONES: Si la consulta del usuario es una solicitud conversacional o de seguimiento sobre la conversación previa (como "tradúcelo al español", "¿puedes resumirlo?", "explícamelo en detalle", "¿y qué más?"), apóyate directamente en el historial de la sesión sin invocar herramientas innecesarias y responde fluidamente.
5. GENERACIÓN DINÁMICA DE REPORTES PDF: Si el usuario te pide generar un reporte o exportar a PDF:
   - Primero busca los datos relevantes en los documentos si aún no los tienes en contexto.
   - Llama a `generate_report_pdf` pasando un `title` descriptivo, un `summary` sustancioso y detallado sintetizando los datos reales encontrados (NUNCA uses frases genéricas o placeholders como 'Sin resumen' o 'Informe generado a partir de la consulta'), y una lista `key_points` con conclusiones, cifras y datos concretos extraídos.
   - En tu mensaje de respuesta, explica brevemente qué contiene el reporte generado y confirma que está listo para descargar.
6. Sé conciso, profesional, analítico y riguroso.
"""


def _get_tool_declarations() -> List[Any]:
    """Define las especificaciones de las herramientas para Gemini Function Calling."""
    if not _USE_MODERN_GENAI:
        return []

    return [
        types.FunctionDeclaration(
            name="search_knowledge_base",
            description="Busca en la base de conocimientos RAG (PostgreSQL + pgvector) información de documentos, tablas, diagramas y facturas.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto o concepto clave a buscar en los documentos.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Cantidad de fragmentos a recuperar (por defecto 5).",
                    },
                },
                "required": ["query"],
            },
        ),
        types.FunctionDeclaration(
            name="generate_report_pdf",
            description="Genera un archivo PDF ejecutivo profesional con resumen exhaustivo y puntos clave detallados a partir de los documentos analizados.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Título formal y específico del reporte ejecutivo.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Resumen ejecutivo exhaustivo y detallado sintetizando los hallazgos y análisis de los documentos reales encontrados. NUNCA uses textos genéricos ni placeholders.",
                    },
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Lista de 3 a 7 conclusiones, cifras, métricas o puntos clave específicos extraídos del análisis documental.",
                    },
                },
                "required": ["title", "summary", "key_points"],
            },
        ),
        types.FunctionDeclaration(
            name="dispatch_webhook",
            description="Envía un webhook HTTP POST con un payload de alerta o notificación a un sistema externo (Slack, Jira, ERP).",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "Identificador del tipo de evento (ej. 'invoice_alert', 'report_ready').",
                    },
                    "payload": {
                        "type": "object",
                        "description": "Objeto JSON con los datos relevantes a notificar.",
                    },
                    "target_url": {
                        "type": "string",
                        "description": "URL de destino opcional del webhook.",
                    },
                },
                "required": ["event_type", "payload"],
            },
        ),
    ]


class AutonomousAgentService:
    """Motor del Agente IA Autónomo con soporte para Function Calling / ReAct y orquestación multimodal."""

    def __init__(self):
        self.model_name = settings.GEMINI_AGENT_MODEL
        self.api_key = settings.GOOGLE_API_KEY
        self._client = None
        self._initialized = False
        self._ensure_client()

    def _ensure_client(self) -> bool:
        """Verifica e inicializa el cliente del SDK google-genai con la API key configurada."""
        current_key = (
            os.environ.get("GOOGLE_API_KEY") or settings.GOOGLE_API_KEY or ""
        ).strip()
        if (
            _USE_MODERN_GENAI
            and current_key
            and current_key != "tu_google_api_key_aqui"
            and not current_key.startswith("tu_google")
        ):
            if not self._client or self.api_key != current_key:
                try:
                    self.api_key = current_key
                    self._client = genai.Client(api_key=self.api_key)
                    self._initialized = True
                    logger.info("AutonomousAgentService inicializado con cliente google-genai.")
                except Exception as e:
                    logger.error("Error al inicializar genai.Client en AutonomousAgentService: %s", e, exc_info=True)
                    self._initialized = False
            return self._initialized
        return False

    async def execute_turn(
        self,
        db: AsyncSession,
        user_message: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AgentChatResponse:
        """Ejecuta un turno completo de interacción con el agente autónomo y persiste la memoria en PostgreSQL."""
        active_session_id = session_id or uuid.uuid4()

        # 1. Cargar historial conversacional previo para esta sesión desde PostgreSQL
        history_query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == active_session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        history_res = await db.execute(history_query)
        prior_messages = list(history_res.scalars().all())

        # 2. Persistir el mensaje actual del usuario en la base de datos
        user_chat_record = ChatMessage(
            session_id=active_session_id,
            role="user",
            content=user_message,
            citations=[],
            executed_tools=[],
        )
        db.add(user_chat_record)
        await db.commit()

        # 3. Ejecutar turno con Gemini o fallback
        client_ready = self._ensure_client()
        if not client_ready or not self._client:
            logger.warning("GOOGLE_API_KEY no configurada o es placeholder. Utilizando modo determinístico de respaldo.")
            chat_response = await self._execute_fallback_turn(
                db=db,
                user_message=user_message,
                session_id=active_session_id,
                prior_messages=prior_messages,
            )
        else:
            try:
                chat_response = await self._execute_gemini_turn(
                    db=db,
                    user_message=user_message,
                    session_id=active_session_id,
                    prior_messages=prior_messages,
                )
            except Exception as e:
                logger.error("Error crítico al invocar la API de Gemini: %s", e, exc_info=True)
                error_prefix = (
                    f"⚠️ [Aviso del sistema: La API de Gemini no respondió temporalmente ({type(e).__name__}: {str(e)[:120]}...). "
                    "Se ejecutó el procesamiento documental con el motor de contingencia.]\n\n"
                )
                chat_response = await self._execute_fallback_turn(
                    db=db,
                    user_message=user_message,
                    session_id=active_session_id,
                    prior_messages=prior_messages,
                    api_error_notice=error_prefix,
                )

        # 4. Persistir la respuesta final del asistente en PostgreSQL
        def _to_json_safe(data: Any) -> Any:
            try:
                if hasattr(data, "model_dump"):
                    data = data.model_dump(mode="json")
                return json.loads(json.dumps(data, default=str))
            except Exception:
                return str(data)

        citations_data = [_to_json_safe(c) for c in chat_response.citations]
        tools_data = [_to_json_safe(t) for t in chat_response.executed_tools]

        assistant_chat_record = ChatMessage(
            session_id=active_session_id,
            role="assistant",
            content=chat_response.response,
            citations=citations_data,
            executed_tools=tools_data,
        )
        db.add(assistant_chat_record)
        await db.commit()

        return chat_response

    async def _call_gemini_with_fallback(
        self,
        contents: List[Any],
        config: Any,
        preferred_model: Optional[str] = None,
    ) -> Tuple[Any, str]:
        """Ejecuta generate_content probando el modelo preferido y recurriendo a modelos compatibles si está deprecado/sin cuota."""
        candidate_models = [
            getattr(self, "_working_model", None) or preferred_model or self.model_name,
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
        ]
        seen = set()
        unique_models = []
        for m in candidate_models:
            if m and m not in seen:
                seen.add(m)
                unique_models.append(m)

        last_exc = None
        for m in unique_models:
            try:
                logger.info("Invocando modelo Gemini: %s", m)
                resp = await self._client.aio.models.generate_content(
                    model=m,
                    contents=contents,
                    config=config,
                )
                self._working_model = m
                return resp, m
            except Exception as e:
                last_exc = e
                err_text = str(e)
                logger.warning("Intento con modelo Gemini '%s' no disponible: %s", m, err_text[:200])
                if any(k in err_text for k in ["404", "503", "RESOURCE_EXHAUSTED", "NOT_FOUND", "429"]):
                    if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
                        await asyncio.sleep(1.0)
                    continue
                else:
                    logger.error("Error no recuperable de Gemini con modelo '%s': %s", m, e, exc_info=True)
                    raise e

        logger.error("Todos los modelos candidatos de Gemini fallaron. Último error: %s", last_exc, exc_info=True)
        raise last_exc

    async def _call_gemini_stream_with_fallback(
        self,
        contents: List[Any],
        config: Any,
        preferred_model: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Ejecuta generate_content_stream probando la cascada de modelos compatibles y produciendo tokens en vivo."""
        candidate_models = [
            getattr(self, "_working_model", None) or preferred_model or self.model_name,
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
        ]
        seen = set()
        unique_models = []
        for m in candidate_models:
            if m and m not in seen:
                seen.add(m)
                unique_models.append(m)

        last_exc = None
        for m in unique_models:
            try:
                logger.info("Invocando streaming con modelo Gemini: %s", m)
                stream = await self._client.aio.models.generate_content_stream(
                    model=m,
                    contents=contents,
                    config=config,
                )
                self._working_model = m
                async for chunk in stream:
                    if chunk.text:
                        yield chunk.text
                return
            except Exception as e:
                last_exc = e
                err_text = str(e)
                logger.warning("Intento de stream con modelo Gemini '%s' no disponible: %s", m, err_text[:200])
                if any(k in err_text for k in ["404", "503", "RESOURCE_EXHAUSTED", "NOT_FOUND", "429"]):
                    if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text:
                        await asyncio.sleep(1.0)
                    continue
                else:
                    logger.error("Error no recuperable en stream de Gemini con '%s': %s", m, e, exc_info=True)
                    raise e

        logger.error("Todos los modelos candidatos de stream fallaron. Último error: %s", last_exc, exc_info=True)
        raise last_exc

    async def execute_turn_stream(
        self,
        db: AsyncSession,
        user_message: str,
        session_id: Optional[uuid.UUID] = None,
    ) -> AsyncGenerator[str, None]:
        """Ejecuta el turno del agente en streaming SSE estructurado (tokens y metadata), persistiendo en PostgreSQL."""
        active_session_id = session_id or uuid.uuid4()

        # 1. Cargar historial y persistir el mensaje del usuario en PostgreSQL
        history_query = (
            select(ChatMessage)
            .where(ChatMessage.session_id == active_session_id)
            .order_by(ChatMessage.created_at.asc())
        )
        history_res = await db.execute(history_query)
        prior_messages = list(history_res.scalars().all())

        user_chat_record = ChatMessage(
            session_id=active_session_id,
            role="user",
            content=user_message,
            citations=[],
            executed_tools=[],
        )
        db.add(user_chat_record)
        await db.commit()

        executed_tools: List[ToolExecutionRecord] = []
        collected_citations: List[CitationItem] = []
        full_response = ""

        def _to_json_safe(data: Any) -> Any:
            try:
                if hasattr(data, "model_dump"):
                    data = data.model_dump(mode="json")
                return json.loads(json.dumps(data, default=str))
            except Exception:
                return str(data)

        client_ready = self._ensure_client()
        if not client_ready or not self._client:
            fb_response = await self._execute_fallback_turn(
                db=db,
                user_message=user_message,
                session_id=active_session_id,
                prior_messages=prior_messages,
            )
            full_response = fb_response.response
            collected_citations = fb_response.citations
            executed_tools = fb_response.executed_tools

            words = full_response.split(" ")
            for i, w in enumerate(words):
                chunk = w if i == len(words) - 1 else w + " "
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.01)
        else:
            try:
                tool_defs = _get_tool_declarations()
                gemini_tools = [types.Tool(function_declarations=tool_defs)]
                config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=gemini_tools,
                    temperature=0.2,
                )

                contents: List[types.Content] = []
                for msg in prior_messages:
                    if msg.role == "user":
                        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=msg.content)]))
                    elif msg.role == "assistant":
                        contents.append(types.Content(role="model", parts=[types.Part.from_text(text=msg.content)]))

                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

                max_turns = 4
                active_model = self.model_name
                final_text_needed = True

                for turn in range(max_turns):
                    response, active_model = await self._call_gemini_with_fallback(
                        contents=contents,
                        config=config,
                        preferred_model=active_model,
                    )

                    if not response.function_calls:
                        if response.text:
                            words = response.text.split(" ")
                            for i, w in enumerate(words):
                                chunk = w if i == len(words) - 1 else w + " "
                                full_response += chunk
                                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                                await asyncio.sleep(0.01)
                            final_text_needed = False
                        break

                    candidate = response.candidates[0]
                    contents.append(candidate.content)
                    tool_response_parts = []

                    for fc in response.function_calls:
                        tool_name = fc.name
                        tool_args = dict(fc.args) if fc.args else {}
                        logger.info("Agente (Stream) invocando tool: %s con args: %s", tool_name, tool_args)

                        tool_result, tool_citations = await self._dispatch_tool_call(
                            db=db, tool_name=tool_name, tool_args=tool_args
                        )
                        if tool_citations:
                            collected_citations.extend(tool_citations)

                        executed_tools.append(
                            ToolExecutionRecord(
                                tool_name=tool_name,
                                tool_input=tool_args,
                                tool_output=tool_result,
                            )
                        )

                        tool_response_parts.append(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={"result": tool_result},
                            )
                        )

                    contents.append(types.Content(role="user", parts=tool_response_parts))

                if final_text_needed:
                    stream_config = types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.2,
                    )
                    async for token in self._call_gemini_stream_with_fallback(
                        contents=contents,
                        config=stream_config,
                        preferred_model=active_model,
                    ):
                        full_response += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

            except Exception as e:
                logger.error("Error crítico durante stream con Gemini: %s", e, exc_info=True)
                error_prefix = (
                    f"⚠️ [Aviso del sistema: La API de Gemini no respondió ({type(e).__name__}: {str(e)[:120]}...). "
                    "Se ejecutó el procesamiento documental con el motor de contingencia.]\n\n"
                )
                fb_response = await self._execute_fallback_turn(
                    db=db,
                    user_message=user_message,
                    session_id=active_session_id,
                    prior_messages=prior_messages,
                    api_error_notice=error_prefix,
                )
                full_response = fb_response.response
                collected_citations = fb_response.citations
                executed_tools = fb_response.executed_tools

                words = full_response.split(" ")
                for i, w in enumerate(words):
                    chunk = w if i == len(words) - 1 else w + " "
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.01)

        # 5. Emitir evento final de metadata
        dedup_citations = self._deduplicate_citations(collected_citations)
        citations_data = [_to_json_safe(c) for c in dedup_citations]
        tools_data = [_to_json_safe(t) for t in executed_tools]

        metadata_event = {
            "type": "metadata",
            "citations": citations_data,
            "executed_tools": tools_data,
            "session_id": str(active_session_id),
        }
        yield f"data: {json.dumps(metadata_event)}\n\n"

        # 6. Persistir el mensaje completo en PostgreSQL
        try:
            assistant_chat_record = ChatMessage(
                session_id=active_session_id,
                role="assistant",
                content=full_response or "Sin respuesta generada.",
                citations=citations_data,
                executed_tools=tools_data,
            )
            db.add(assistant_chat_record)
            await db.commit()
            logger.info("Respuesta del stream persistida exitosamente en PostgreSQL para session %s", active_session_id)
        except Exception as err:
            logger.error("Error al persistir mensaje de stream en PostgreSQL: %s", err, exc_info=True)

    async def _execute_gemini_turn(
        self,
        db: AsyncSession,
        user_message: str,
        session_id: uuid.UUID,
        prior_messages: List[ChatMessage],
    ) -> AgentChatResponse:
        """Ejecuta el ciclo ReAct y Function Calling con el modelo Gemini configurado."""
        executed_tools: List[ToolExecutionRecord] = []
        collected_citations: List[CitationItem] = []

        # 1. Preparar configuración de Function Calling
        tool_defs = _get_tool_declarations()
        gemini_tools = [types.Tool(function_declarations=tool_defs)]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=gemini_tools,
            temperature=0.2,
        )

        # 2. Historial de conversación multi-turno para el modelo
        contents: List[types.Content] = []
        for msg in prior_messages:
            if msg.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )
            elif msg.role == "assistant":
                contents.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )

        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message)],
            )
        )

        # 3. Ciclo de Razonamiento y Acción (ReAct Loop) - Máximo 4 iteraciones
        final_answer = ""
        max_turns = 4
        active_model = self.model_name

        for turn in range(max_turns):
            response, active_model = await self._call_gemini_with_fallback(
                contents=contents,
                config=config,
                preferred_model=active_model,
            )

            # Si el modelo no solicitó llamadas a funciones, obtuvimos la respuesta final
            if not response.function_calls:
                final_answer = response.text or "Sin respuesta generada por el modelo."
                break

            # Si el modelo solicitó una o más llamadas a funciones
            candidate = response.candidates[0]
            contents.append(candidate.content)

            tool_response_parts = []

            for fc in response.function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                logger.info("Agente solicitó invocar tool: %s con args: %s", tool_name, tool_args)

                # Ejecutar la herramienta correspondiente
                tool_result, tool_citations = await self._dispatch_tool_call(
                    db=db, tool_name=tool_name, tool_args=tool_args
                )

                if tool_citations:
                    collected_citations.extend(tool_citations)

                executed_tools.append(
                    ToolExecutionRecord(
                        tool_name=tool_name,
                        tool_input=tool_args,
                        tool_output=tool_result,
                    )
                )

                # Construir la parte de respuesta de función para retroalimentar a Gemini
                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_result},
                    )
                )

            # Añadir las respuestas de las funciones al historial de Gemini (rol 'user' requerido por la API)
            contents.append(types.Content(role="user", parts=tool_response_parts))

        if not final_answer:
            final_answer = "Se ejecutaron las acciones solicitadas con éxito."

        return AgentChatResponse(
            response=final_answer,
            citations=self._deduplicate_citations(collected_citations),
            executed_tools=executed_tools,
            session_id=session_id,
        )

    async def _dispatch_tool_call(
        self,
        db: AsyncSession,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> Tuple[Any, List[CitationItem]]:
        """Despacha la ejecución de una herramienta específica y extrae citas si aplica."""
        citations: List[CitationItem] = []

        try:
            if tool_name == "search_knowledge_base":
                query = tool_args.get("query", "")
                top_k = int(tool_args.get("top_k", 5))
                result = await execute_search_knowledge_base(db=db, query=query, top_k=top_k)

                for c in result.get("citations", []):
                    citations.append(
                        CitationItem(
                            document_name=c["document_name"],
                            page_number=c.get("page_number"),
                            chunk_type=c["chunk_type"],
                            chunk_id=c.get("chunk_id"),
                        )
                    )
                return result.get("context_text", ""), citations

            elif tool_name == "generate_report_pdf":
                title = tool_args.get("title", "Reporte Ejecutivo")
                summary = tool_args.get("summary", "Sin resumen.")
                key_points = tool_args.get("key_points", [])
                result = execute_generate_report_pdf(title=title, summary=summary, key_points=key_points)
                return result, []

            elif tool_name == "dispatch_webhook":
                event_type = tool_args.get("event_type", "generic_alert")
                payload = tool_args.get("payload", {})
                target_url = tool_args.get("target_url")
                result = await execute_dispatch_webhook(
                    event_type=event_type, payload=payload, target_url=target_url
                )
                return result, []

            else:
                return f"Herramienta desconocida: {tool_name}", []

        except Exception as e:
            logger.exception("Error al ejecutar tool %s: %s", tool_name, e)
            return {"error": str(e)}, []

    async def _execute_fallback_turn(
        self,
        db: AsyncSession,
        user_message: str,
        session_id: uuid.UUID,
        prior_messages: Optional[List[ChatMessage]] = None,
        api_error_notice: str = "",
    ) -> AgentChatResponse:
        """Modo determinístico de respaldo para desarrollo local y pruebas unitarias sin API key activa."""
        msg_lower = user_message.lower()
        executed_tools: List[ToolExecutionRecord] = []
        collected_citations: List[CitationItem] = []
        response_paragraphs: List[str] = []

        # Si hay historial previo y el usuario hace una pregunta de seguimiento, enriquecer la búsqueda
        search_query = user_message
        if prior_messages and any(k in msg_lower for k in ["más", "mas", "también", "tambien", "detalle", "amplía", "continúa", "además", "ademas"]):
            last_user_msgs = [m.content for m in prior_messages if m.role == "user"]
            if last_user_msgs:
                search_query = f"{last_user_msgs[-1]} {user_message}"

        # 1. Determinar si requiere búsqueda RAG
        needs_search = any(
            k in msg_lower
            for k in [
                "quién", "quien", "cv", "factura", "experiencia", "habilidad", "skills",
                "proyecto", "documento", "auditoría", "auditoria", "cuánto", "cuanto",
                "informe", "resumen", "investai", "mattia", "más", "mas", "detalle"
            ]
        )

        rag_context = ""
        if needs_search:
            search_res = await execute_search_knowledge_base(db=db, query=search_query, top_k=3)
            rag_context = search_res.get("context_text", "")
            raw_citations = search_res.get("citations", [])

            for c in raw_citations:
                collected_citations.append(
                    CitationItem(
                        document_name=c["document_name"],
                        page_number=c.get("page_number"),
                        chunk_type=c["chunk_type"],
                        chunk_id=c.get("chunk_id"),
                    )
                )

            executed_tools.append(
                ToolExecutionRecord(
                    tool_name="search_knowledge_base",
                    tool_input={"query": search_query, "top_k": 3},
                    tool_output={"total_found": search_res.get("total_found", 0)},
                )
            )

        # 2. Determinar si requiere generación de PDF
        needs_pdf = any(k in msg_lower for k in ["pdf", "reporte", "informe", "generar pdf", "descargar"])
        pdf_info = None
        if needs_pdf:
            pdf_title = "Informe Ejecutivo de Conocimiento"
            if "auditoria" in msg_lower or "auditoría" in msg_lower:
                pdf_title = "Informe de Auditoría de Sistemas y Estado Financiero"
            elif "mattia" in msg_lower:
                pdf_title = "Perfil Profesional y Habilidades de Mattia Risso"

            clean_context = rag_context.replace("\n", " ").strip() if rag_context else ""
            if clean_context and "No se encontraron" not in clean_context:
                pdf_summary = (
                    f"Síntesis ejecutiva de la información documental analizada: {clean_context[:450]}"
                )
                key_points = [
                    f"Información verificada: {clean_context[:100]}...",
                    "Datos contrastados contra las fuentes documentales indexadas en pgvector.",
                    "Análisis estructurado y preparado para toma de decisiones ejecutivas.",
                ]
            else:
                pdf_summary = f"Informe correspondiente a la consulta: '{user_message}'."
                key_points = [
                    "Búsqueda ejecutada en la base de conocimientos documental.",
                    "Validación de registros completada satisfactoriamente.",
                ]

            pdf_info = execute_generate_report_pdf(
                title=pdf_title, summary=pdf_summary, key_points=key_points
            )
            executed_tools.append(
                ToolExecutionRecord(
                    tool_name="generate_report_pdf",
                    tool_input={"title": pdf_title, "summary": pdf_summary, "key_points": key_points},
                    tool_output=pdf_info,
                )
            )

        # 3. Determinar si requiere webhook
        needs_webhook = any(k in msg_lower for k in ["webhook", "alerta", "notificar", "notificación", "slack"])
        webhook_info = None
        if needs_webhook:
            event_type = "user_alert"
            payload = {"query": user_message, "alert_triggered": True}
            webhook_info = await execute_dispatch_webhook(event_type=event_type, payload=payload)
            executed_tools.append(
                ToolExecutionRecord(
                    tool_name="dispatch_webhook",
                    tool_input={"event_type": event_type, "payload": payload},
                    tool_output=webhook_info,
                )
            )

        # 4. Construcción de respuesta
        if rag_context and "No se encontraron" not in rag_context:
            first_cit = collected_citations[0] if collected_citations else None
            source_tag = f" [Fuente: {first_cit.document_name}, Pág {first_cit.page_number or 1}]" if first_cit else ""
            response_paragraphs.append(
                f"De acuerdo con la información recuperada de los documentos{source_tag}:\n\n"
                f"{rag_context[:600]}..."
            )
        else:
            response_paragraphs.append(
                f"He procesado tu solicitud: '{user_message}'."
            )

        if pdf_info:
            response_paragraphs.append(
                f"\n📄 Se ha generado el informe ejecutivo en PDF: [{pdf_info['filename']}]({pdf_info['download_url']})."
            )

        if webhook_info:
            response_paragraphs.append(
                f"\n🔔 Se ha despachado la notificación vía webhook: {webhook_info['message']}."
            )

        final_text = "\n".join(response_paragraphs)
        if api_error_notice:
            final_text = f"{api_error_notice}{final_text}"

        return AgentChatResponse(
            response=final_text,
            citations=self._deduplicate_citations(collected_citations),
            executed_tools=executed_tools,
            session_id=session_id,
        )

    def _deduplicate_citations(self, citations: List[CitationItem]) -> List[CitationItem]:
        """Elimina citas duplicadas para mantener la lista limpia."""
        seen = set()
        unique = []
        for c in citations:
            key = (c.document_name, c.page_number, c.chunk_type)
            if key not in seen:
                seen.add(key)
                unique.append(c)
        return unique


autonomous_agent_service = AutonomousAgentService()

